import hashlib
import base64

def generate_code_challenge(code_verifier):
    """Generate a PKCE code challenge from the code verifier"""
    sha256_hash = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(sha256_hash).decode('utf-8').rstrip('=')
