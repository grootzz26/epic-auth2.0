from django.shortcuts import render

# Create your views here.

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .token_client import EpicTokenClient, TokenError
import logging
import requests
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

@require_http_methods(["POST"])
@csrf_exempt
def get_system_token(request):
    """
    View to obtain system-level access token
    """
    breakpoint()
    try:
        client = EpicTokenClient()
        token_data = client.get_client_credentials_token()
        breakpoint()
        # Optionally store the token
        if request.user.is_authenticated:
            client.store_token(request.user.id, token_data)

        return JsonResponse({
            'access_token': token_data['access_token'],
            'expires_in': token_data['expires_in'],
            'scope': token_data['scope']
        })
    except TokenError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error in get_system_token: {str(e)}")
        return JsonResponse(
            {'error': 'An unexpected error occurred'},
            status=500
        )


# Example usage in another service
class EpicService:
    def __init__(self):
        self.token_client = EpicTokenClient()

    def get_token_and_make_request(self):
        try:
            # Get fresh token
            token_data = self.token_client.get_client_credentials_token()

            # Use token to make FHIR request
            headers = {
                'Authorization': f"Bearer {token_data['access_token']}",
                'Accept': 'application/fhir+json'
            }

            response = requests.get(
                f"{settings.EPIC_CONFIG['EPIC_FHIR_URL']}/Patient",
                headers=headers
            )

            return response.json()

        except TokenError as e:
            logger.error(f"Token error: {str(e)}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            raise
