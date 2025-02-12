# from django.middleware import MiddlewareMixin
from django.utils.deprecation import MiddlewareMixin
from .views import validate_state_token


class EpicAuthMiddleware(MiddlewareMixin):
    """Middleware to handle Epic FHIR authentication state"""

    def process_request(self, request):
        # Clean up expired state tokens
        if 'oauth_state' in request.session:
            state = request.session['oauth_state']
            if not validate_state_token(state):
                del request.session['oauth_state']