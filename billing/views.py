# utils.py
import requests
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from urllib.parse import unquote
import urllib.parse
from urllib.parse import urlencode
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect
from django.http import JsonResponse
import requests
import secrets
from urllib.parse import urlencode
import base64
import secrets
from urllib.parse import urlencode, unquote
from django.shortcuts import redirect
from django.http import HttpResponseBadRequest
from django.conf import settings
import logging
from django.core.cache import cache
from datetime import datetime, timedelta
from .utils import generate_code_challenge
from django.http import HttpResponseBadRequest, HttpResponseServerError
from django.core.cache import cache
from .models import EpicAuthToken
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import ListCreateAPIView

logger = logging.getLogger(__name__)

EPIC_CONFIG = {
    'CLIENT_ID': 'your-client-id',
    'CLIENT_SECRET': 'your-client-secret',
    'REDIRECT_URI': 'https://your-domain.com/callback/',
    'EPIC_AUTH_URL': 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize',
    'EPIC_TOKEN_URL': 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token',
    'EPIC_FHIR_URL': 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4',
    'ADDITIONAL_SCOPES': '',  # Additional scopes if needed
    'PKCE_ENABLED': True,  # Enable PKCE for added security
    'TOKEN_CACHE_TIMEOUT': 3600,  # 1 hour
    'STATE_TIMEOUT': 600,  # 10 minutes
}

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .fhir_client import PatientResource, FHIRResourceError

def make_request(url, method, body=None, params=None, headers=None):
    if method.lower() == "get":
        resp = requests.get(url, params=params, headers=headers)
    else:
        resp = requests.post(url, params=params, data=body, headers=headers)
    return resp

@require_http_methods(["GET"])
def get_patient_data(request, pk=None):
    """View to fetch patient data"""
    try:
        patient_resource = PatientResource()
        if not pk:
            pk = cache.get("patient_id")
        patient_data = patient_resource.get_patient(pk)
        return JsonResponse(patient_data)
    except FHIRResourceError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error fetching patient data: {str(e)}")
        return JsonResponse(
            {'error': 'An unexpected error occurred'},
            status=500
        )

class EpicAuthError(Exception):
    pass


def generate_state_token():
    """Generate a secure state token with timestamp"""
    return f"{secrets.token_urlsafe(32)}-{int(datetime.now().timestamp())}"


def validate_state_token(state_token):
    """Validate the state token and ensure it hasn't expired"""
    try:
        token, timestamp = state_token.rsplit('-', 1)
        creation_time = datetime.fromtimestamp(int(timestamp))
        if datetime.now() - creation_time > timedelta(minutes=10):
            return False
        return True
    except (ValueError, TypeError):
        return False


def start_auth(request):
    """
    Initiate the Epic FHIR OAuth2.0 authorization flow
    """
    try:
        # Generate and store state parameter with timestamp
        state = generate_state_token()

        # Store state in both session and cache with expiration
        request.session['oauth_state'] = state
        cache.set(f'oauth_state_{state}', request.user.id, timeout=600)  # 10 minutes

        # Configuration validation
        if not all([
            settings.EPIC_CONFIG.get('CLIENT_ID'),
            settings.EPIC_CONFIG.get('REDIRECT_URI'),
            settings.EPIC_CONFIG.get('EPIC_AUTH_URL'),
            settings.EPIC_CONFIG.get('EPIC_FHIR_URL')
        ]):
            raise EpicAuthError("Missing required Epic FHIR configuration")

        # Build authorization parameters
        auth_params = {
            'response_type': 'code',
            'client_id': settings.EPIC_CONFIG['CLIENT_ID'],
            'redirect_uri': settings.EPIC_CONFIG['REDIRECT_URI'],
            'state': state,
            'scope': ('launch/patient '
                      'patient/Patient.read '
                      'patient/Coverage.read '
                      'patient/MedicationRequest.read '  # This matches your Epic app configuration
                      'patient/MedicationRequest.search '  # Add this based on your app scopes
                      'patient/DiagnosticReport.read '
                      'patient/Observation.read'),
            # 'scope': 'launch/patient patient/Patient.read patient/Coverage.read patient/MedicationRequest.read patient/DiagnosticReport.read patient/Observation.read',  # Customize scopes as needed
            # 'scope': 'launch/patient patient/*.read',  # Customize scopes as needed
            # 'scope': 'patient/MedicationRequest.read',  # Customize scopes as needed
            # 'scope': 'coverage/*.read',  # Customize scopes as needed
            # 'scope': 'patient',  # Customize scopes as needed
            'aud': settings.EPIC_CONFIG['EPIC_FHIR_URL']
        }

        # Optional parameters based on configuration
        if settings.EPIC_CONFIG.get('ADDITIONAL_SCOPES'):
            auth_params['scope'] += ' ' + settings.EPIC_CONFIG['ADDITIONAL_SCOPES']

        if settings.EPIC_CONFIG.get('PKCE_ENABLED', False):
            code_verifier = secrets.token_urlsafe(32)
            request.session['code_verifier'] = code_verifier
            code_challenge = generate_code_challenge(code_verifier)
            auth_params.update({
                'code_challenge': code_challenge,
                'code_challenge_method': 'S256'
            })

        # Build and sanitize the authorization URL
        auth_url = unquote(f"{settings.EPIC_CONFIG['EPIC_AUTH_URL']}?{urlencode(auth_params)}")
        # Log the initiation of auth flow (excluding sensitive data)
        print(
            "Starting Epic FHIR authorization flow",
            {
                'user_id': request.user.id,
                'redirect_uri': settings.EPIC_CONFIG['REDIRECT_URI'],
                'scopes': auth_params['scope']
            }
        )

        return redirect(auth_url)

    except EpicAuthError as e:
        logger.error(f"Epic auth configuration error: {str(e)}")
        return HttpResponseBadRequest("Epic FHIR configuration error")
    except Exception as e:
        logger.error(f"Unexpected error in Epic auth flow: {str(e)}")
        return HttpResponseBadRequest("An unexpected error occurred")

def get_access_token():
    token_url = settings.EPIC_FHIR["TOKEN_URL"]
    client_id = settings.EPIC_FHIR["CLIENT_ID"]
    client_secret = settings.EPIC_FHIR["CLIENT_SECRET"]

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }

    response = requests.post(token_url, data=payload)
    response.raise_for_status()
    return response.json()["access_token"]


def get_account(account_id):
    base_url = settings.EPIC_FHIR["BASE_URL"]
    url = f"{base_url}/Account/{account_id}"

    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/fhir+json",
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def account_detail(request, account_id):
    try:
        account_data = get_account(account_id)
        return JsonResponse(account_data, safe=False)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def callback(request):
    pass

# Step 1: Initiate the authorization request
def initiate_auth(request):
    # client_id = settings.EPIC_FHIR["CLIENT_ID"]  # Replace with your client_id
    client_id = "978b0df0-9a02-4910-be60-06d597397677"
    redirect_uri = "https://f25a-202-83-25-55.ngrok-free.app/callback/"  # Redirect URI
    # scope = "launch openid patient/*.read"  # Scopes required for your app
    scope = "patient.read"
    # scope = "patient.read"
    state = "4567"  # Optional, a unique identifier for the session
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
    }
    # authorization_url = (
    #     f"https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize?"
    #     f"response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&state={state}"
    # )
    authorization_url = f"https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize?{urlencode(params)}"
    return redirect(unquote(authorization_url))


# Step 2: Handle the redirect and extract authorization_code
@csrf_exempt
def auth_callback(request):
    code = request.GET.get("code")  # Extract the authorization_code
    state = request.GET.get("state")  # Ensure state matches if used

    if code:
        # Return the code or use it directly to get an access token
        return JsonResponse({"authorization_code": code})
    else:
        return JsonResponse({"error": "No authorization code provided"}, status=400)


def get_start_auth(request):
    # """Start the OAuth flow by redirecting to Epic's authorization endpoint"""
    # # Generate and store state parameter to prevent CSRF
    #
    # # Build authorization URL
    # auth_params = {
    #     'response_type': 'code',
    #     'client_id': settings.EPIC_FHIR['CLIENT_ID'],
    #     'redirect_uri': settings.EPIC_FHIR['REDIRECT_URI'],
    #     'state': 1234,
    #     'scope': 'patient.read'  # Add more scopes as needed
    # }
    #
    # auth_url = f"{settings.EPIC_FHIR['EPIC_AUTH_URL']}?{urllib.parse.urlencode(auth_params)}"
    # breakpoint()
    # return HttpResponse(f'''
    #     <h1>Epic FHIR Authorization</h1>
    #     <p>Click below to start the authorization process:</p>
    #     <a href="{auth_url}">Start Authorization</a>
    # ''')
    state = secrets.token_urlsafe(16)
    request.session['oauth_state'] = state
    client_id = "978b0df0-9a02-4910-be60-06d597397677"
    redirect_uri = "https://f25a-202-83-25-55.ngrok-free.app/callback/"

    auth_params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'state': state,
        'scope': 'launch/patient patient/*.read',
        'aud': EPIC_CONFIG['EPIC_FHIR_URL']
    }

    auth_url = unquote(f"{EPIC_CONFIG['EPIC_AUTH_URL']}?{urlencode(auth_params)}")
    return redirect(auth_url)


def oauth_callback(request):
    """
    Handle the OAuth callback from Epic FHIR
    """
    try:
        # Extract parameters from request
        error = request.GET.get('error')
        if error:
            error_description = request.GET.get('error_description', 'No description provided')
            logger.error(f"Epic OAuth error: {error} - {error_description}")
            return HttpResponseBadRequest(f"Authorization failed: {error}")

        code = request.GET.get('code')
        state = request.GET.get('state')
        if not code or not state:
            logger.error("Missing required parameters in callback")
            return HttpResponseBadRequest("Missing required parameters")

        # Validate state parameter
        stored_state = request.session.get('oauth_state')
        if not stored_state or stored_state != state:
            logger.error("State parameter mismatch")
            return HttpResponseBadRequest("Invalid state parameter")

        # Clean up state from session
        del request.session['oauth_state']

        # Retrieve cached user ID associated with state
        user_id = cache.get(f'oauth_state_{state}')
        # if not user_id:
        #     logger.error("No user ID found for state token")
        #     return HttpResponseBadRequest("Invalid or expired state token")

        # Prepare token exchange request
        token_params = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': settings.EPIC_CONFIG['REDIRECT_URI'],
            'client_id': settings.EPIC_CONFIG['CLIENT_ID'],
        }

        # Add PKCE code verifier if enabled
        if settings.EPIC_CONFIG.get('PKCE_ENABLED', False):
            code_verifier = request.session.get('code_verifier')
            if code_verifier:
                token_params['code_verifier'] = code_verifier
                del request.session['code_verifier']

        # Add client secret if using confidential client
        if settings.EPIC_CONFIG.get('CLIENT_SECRET'):
            token_params['client_secret'] = settings.EPIC_CONFIG['CLIENT_SECRET']

        # Exchange code for tokens
        token_response = requests.post(
            settings.EPIC_CONFIG['EPIC_TOKEN_URL'],
            data=token_params,
            headers={'Accept': 'application/json'}
        )
        if not token_response.ok:
            logger.error(f"Token exchange failed: {token_response.text}")
            return HttpResponseServerError("Failed to exchange code for tokens")

        token_data = token_response.json()
        # Calculate token expiration
        expires_at = datetime.now() + timedelta(seconds=token_data['expires_in'])
        # Store tokens in database
        print( "token response", token_data)
        EpicAuthToken.objects.update_or_create(
            user_id=user_id,
            defaults={
                'access_token': token_data['access_token'],
                'refresh_token': token_data.get('refresh_token'),
                'expires_at': expires_at,
                'scope': token_data.get('scope', ''),
                'token_type': token_data.get('token_type', 'Bearer')
            }
        )

        # Store patient ID if present
        patient_id = token_data.get('patient')
        request.session["patient_id"] = patient_id
        cache.set("patient_id", patient_id, 3600)
        cache.set(patient_id, token_data["access_token"], 3600)
        if patient_id:
            cache.set(f'epic_patient_{user_id}', patient_id,
                     timeout=settings.EPIC_CONFIG.get('TOKEN_CACHE_TIMEOUT', 3600))

        print(
            "Successfully completed Epic FHIR authorization",
            {
                'user_id': user_id,
                'scopes': token_data.get('scope'),
                'expires_in': token_data['expires_in']
            }
        )

        # Redirect to success page or original destination
        success_url = request.session.pop('epic_auth_success_url',
                                        settings.EPIC_CONFIG.get('AUTH_SUCCESS_URL', '/'))
        return HttpResponse("Token generated")

    except Exception as e:
        logger.error(f"Unexpected error in OAuth callback: {str(e)}")
        return HttpResponseServerError("An unexpected error occurred")


class CoverageAPIView(ListCreateAPIView):

    def list(self, request, *args, **kwargs):
        """View to fetch Coverage data"""
        try:
            pk = kwargs.get("pk")
            patient_resource = PatientResource()
            if not pk:
                pk = cache.get("patient_id")
            patient_data = patient_resource.get_coverage(pk)
            return JsonResponse(patient_data)
        except FHIRResourceError as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"Unexpected error fetching patient data: {str(e)}")
            return JsonResponse(
                {'error': 'An unexpected error occurred'},
                status=500
            )


class MedicationAPIView(ListCreateAPIView):

    def list(self, request, *args, **kwargs):
        """View to fetch medication data"""
        try:
            pk = kwargs.get("pk")
            patient_resource = PatientResource()
            if not pk:
                pk = cache.get("patient_id")
            patient_data = patient_resource.get_medication(pk)
            return JsonResponse(patient_data)
        except FHIRResourceError as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"Unexpected error fetching patient data: {str(e)}")
            return JsonResponse(
                {'error': 'An unexpected error occurred'},
                status=500
            )