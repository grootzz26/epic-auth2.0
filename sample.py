import requests
import base64
import time
from datetime import datetime
from typing import Optional, Dict, Any
import json


class EpicFHIRAuth:
    def __init__(self, client_id: str, client_secret: str,
                 base_url: str = "https://fhir.epic.com/interconnect-fhir-oauth/"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip('/')
        self.access_token: Optional[str] = None
        self.token_expiry: float = 0

    def get_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        if not self.access_token or time.time() >= self.token_expiry - 60:  # 60 second buffer
            self._authenticate()
        return self.access_token

    def _authenticate(self) -> None:
        """Authenticate with Epic FHIR and get a new access token."""
        auth_string = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        headers = {
            "Authorization": f"Basic {auth_string}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = {
            "grant_type": "client_credentials",
            "scope": "patient/*.read"
        }
        breakpoint()
        response = requests.post(
            f"{self.base_url}/oauth2/token",
            headers=headers,
            data=data
        )
        breakpoint()

        if response.status_code != 200:
            raise Exception(f"Authentication failed: {response.text}")

        token_data = response.json()
        self.access_token = token_data["access_token"]
        self.token_expiry = time.time() + token_data["expires_in"]


class EpicFHIRClient:
    def __init__(self, auth: EpicFHIRAuth):
        self.auth = auth
        self.api_base = f"{auth.base_url}/api/FHIR/R4"

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with current access token."""
        return {
            "Authorization": f"Bearer {self.auth.get_token()}",
            "Epic-Client-ID": self.auth.client_id,
            "Accept": "application/fhir+json",
            "Content-Type": "application/fhir+json"
        }

    def get_patient(self, patient_id: str) -> Dict[str, Any]:
        """Retrieve a patient by ID."""
        response = requests.get(
            f"{self.api_base}/Patient/{patient_id}",
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()

    def search_patients(self, **search_params) -> Dict[str, Any]:
        """Search for patients using various parameters."""
        response = requests.get(
            f"{self.api_base}/Patient",
            headers=self._get_headers(),
            params=search_params
        )
        response.raise_for_status()
        return response.json()

    def create_patient(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new patient record."""
        response = requests.post(
            f"{self.api_base}/Patient",
            headers=self._get_headers(),
            json=patient_data
        )
        response.raise_for_status()
        return response.json()

    def submit_billing(self, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """Submit billing information."""
        response = requests.post(
            f"{self.api_base}/Account",
            headers=self._get_headers(),
            json=account_data
        )
        response.raise_for_status()
        return response.json()


# Example usage
if __name__ == "__main__":
    # Initialize authentication
    auth = EpicFHIRAuth(
        client_id="c57e8208-edda-4139-9af1-ddb5ee51b0d5",
        client_secret="7w2vYQ1iqJ/9ryA/OFepkaa1BsZicHf5muf2vARtO/mIv4Yshu7uFIfDLxP16V3pJnSIqEUTUy3In+VXJCDPUw=="
    )

    # Create FHIR client
    client = EpicFHIRClient(auth)
    breakpoint()

    try:
        # Example: Search for a patient by MRN
        patients = client.search_patients(identifier="MRN|12345")
        print(json.dumps(patients, indent=2))

        # Example: Create a new patient
        new_patient = {
            "resourceType": "Patient",
            "name": [{
                "use": "official",
                "family": "Smith",
                "given": ["John"]
            }],
            "birthDate": "1970-01-01",
            "gender": "male"
        }

        created_patient = client.create_patient(new_patient)
        print(json.dumps(created_patient, indent=2))

    except Exception as e:
        print(f"Error: {str(e)}")