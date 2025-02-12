import requests
import base64
from datetime import datetime, timedelta
from django.conf import settings
import logging
from billing.models import EpicAuthToken

logger = logging.getLogger(__name__)

class TokenError(Exception):
    """Custom exception for token-related errors"""
    pass

class EpicTokenClient:
    def __init__(self):
        self.token_url = settings.EPIC_CONFIG['EPIC_TOKEN_URL']
        self.client_id = settings.EPIC_CONFIG['CLIENT_ID']
        self.client_secret = settings.EPIC_CONFIG['CLIENT_SECRET']

    def get_client_credentials_token(self, scope='patient'):
        """
        Get access token using client credentials flow
        """
        try:
            # Prepare the authorization header
            auth_string = f"{self.client_id}:{self.client_secret}"
            auth_bytes = auth_string.encode('ascii')
            base64_auth = base64.b64encode(auth_bytes).decode('ascii')

            headers = {
                'Authorization': f'Basic {base64_auth}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }

            # Prepare the request body
            data = {
                'grant_type': 'client_credentials',
                'scope': scope
            }

            # Make the token request
            response = requests.post(
                self.token_url,
                headers=headers,
                data=data,
                timeout=10
            )
            breakpoint()

            if response.status_code != 200:
                logger.error(f"Token request failed: {response.text}")
                raise TokenError(f"Failed to obtain token: {response.status_code}")

            token_data = response.json()

            return {
                'access_token': token_data['access_token'],
                'expires_in': token_data['expires_in'],
                'scope': token_data.get('scope', scope),
                'token_type': token_data.get('token_type', 'Bearer')
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during token request: {str(e)}")
            raise TokenError(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error obtaining token: {str(e)}")
            raise TokenError(f"Unexpected error: {str(e)}")

    def store_token(self, user_id, token_data):
        """
        Store the token in the database
        """
        expires_at = datetime.now() + timedelta(seconds=token_data['expires_in'])

        EpicAuthToken.objects.update_or_create(
            user_id=user_id,
            defaults={
                'access_token': token_data['access_token'],
                'expires_at': expires_at,
                'scope': token_data['scope'],
                'token_type': token_data['token_type']
            }
        )


# def get_valid_epic_token(user_id):
#     """
#     Get a valid Epic FHIR access token, refreshing if necessary
#     """
#     try:
#         token = EpicAuthToken.objects.get(user_id=user_id)
#
#         # Check if token is expired or will expire soon (within 5 minutes)
#         if token.expires_at <= datetime.now() + timedelta(minutes=5):
#             return refresh_epic_token(user_id)
#
#         return token.access_token
#
#     except EpicAuthToken.DoesNotExist:
#         logger.error(f"No token found for user {user_id}")
#         raise
#     except Exception as e:
#         logger.error(f"Error getting valid token: {str(e)}")
#         raise
#
# def require_epic_token(view_func):
#     def wrapped(request, *args, **kwargs):
#         try:
#             user_id = request.user.id  # Adjust based on your auth setup
#             token = get_valid_epic_token(user_id)
#             request.epic_token = token
#             return view_func(request, *args, **kwargs)
#         except Exception as e:
#             logger.error(f"Epic token error: {str(e)}")
#             # Redirect to auth or return error based on your needs
#             return HttpResponseRedirect(reverse('epic_auth'))
#     return wrapped
