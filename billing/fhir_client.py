import requests
from datetime import datetime
from django.core.cache import cache
from django.conf import settings
import logging
from .models import EpicAuthToken

logger = logging.getLogger(__name__)


class FHIRResourceError(Exception):
    """Custom exception for FHIR resource errors"""
    pass


class PatientResource:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.base_url = settings.EPIC_CONFIG['EPIC_FHIR_URL']
        self._access_token = None

    @property
    def access_token(self):
        """Get valid access token for the user"""
        if not self._access_token:
            # token = EpicAuthToken.objects.filter(user_id=self.user_id).first()
            token = EpicAuthToken.objects.last()
            if not token:
                raise FHIRResourceError("No valid access token found")
            self._access_token = token.access_token
        return self._access_token

    def _make_request(self, endpoint, params=None):
        """Make authenticated request to FHI
        breakpoint()R endpoint"""
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/fhir+json',
            'Epic-Client-ID': '978b0df0-9a02-4910-be60-06d597397677'
            # 'Accept': 'application/json',
        }
        print(headers, params, endpoint)

        try:
            response = requests.get(
                f"{self.base_url}/{endpoint}",
                headers=headers,
                params=params,
                timeout=10
            )
            if response.status_code == 401:
                # Token might be expired, clear cached token
                self._access_token = None
                raise FHIRResourceError("Authentication failed")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"FHIR request failed: {str(e)}")
            raise FHIRResourceError(f"Failed to fetch FHIR resource: {str(e)}")

    def get_patient(self, patient_id=None):
        """
        Fetch patient resource. If patient_id is not provided,
        uses the patient context from the OAuth flow
        """
        if not patient_id:
            patient_id = cache.get(f'epic_patient_{self.user_id}')
            if not patient_id:
                raise FHIRResourceError("No patient ID found in context")
        try:
            data = self._make_request(f'Patient/{patient_id}')
            return self._parse_patient_resource(data)
        except Exception as e:
            logger.error(f"Error fetching patient {patient_id}: {str(e)}")
            raise FHIRResourceError(f"Failed to fetch patient data: {str(e)}")

    def search_patients(self, params):
        """
        Search for patients using various parameters
        params can include: family, given, birthdate, gender, etc.
        """
        try:
            data = self._make_request('Patient', params=params)
            return [self._parse_patient_resource(entry['resource'])
                    for entry in data.get('entry', [])]
        except Exception as e:
            logger.error(f"Error searching patients: {str(e)}")
            raise FHIRResourceError(f"Failed to search patients: {str(e)}")

    def _parse_patient_resource(self, data):
        """Parse FHIR Patient resource into a more usable format"""
        try:
            # Get name components
            name = data.get('name', [{}])[0]
            given_names = name.get('given', [])
            family_name = name.get('family', '')

            # Get contact information
            telecom = data.get('telecom', [])
            email = next((t['value'] for t in telecom if t['system'] == 'email'), None)
            phone = next((t['value'] for t in telecom if t['system'] == 'phone'), None)

            # Get addresses
            addresses = data.get('address', [])
            primary_address = addresses[0] if addresses else {}

            # Parse extensions for additional data
            extensions = {ext.get('url'): ext.get('valueString')
                          for ext in data.get('extension', [])}

            return {
                'id': data.get('id'),
                'active': data.get('active', True),
                'first_name': given_names[0] if given_names else '',
                'middle_name': given_names[1] if len(given_names) > 1 else '',
                'last_name': family_name,
                'gender': data.get('gender'),
                'birth_date': data.get('birthDate'),
                'deceased': data.get('deceasedBoolean', False),
                'email': email,
                'phone': phone,
                'address': {
                    'line': primary_address.get('line', []),
                    'city': primary_address.get('city'),
                    'state': primary_address.get('state'),
                    'postal_code': primary_address.get('postalCode'),
                    'country': primary_address.get('country'),
                },
                'marital_status': data.get('maritalStatus', {}).get('text'),
                'language': next((
                    comm['language']['text']
                    for comm in data.get('communication', [])
                    if comm.get('preferred', False)
                ), None),
                'extensions': extensions,
                'raw_resource': data  # Include raw resource for complete access
            }
        except Exception as e:
            logger.error(f"Error parsing patient resource: {str(e)}")
            raise FHIRResourceError(f"Failed to parse patient data: {str(e)}")

    def get_coverage(self, patient_id=None):
        """
        Fetch patient resource. If patient_id is not provided,
        uses the patient context from the OAuth flow
        """
        if not patient_id:
            patient_id = cache.get(f'epic_patient_{self.user_id}')
            if not patient_id:
                raise FHIRResourceError("No patient ID found in context")
        try:
            data = self._make_request(f'Coverage?patient={patient_id}')
            return data
        except Exception as e:
            logger.error(f"Error fetching patient {patient_id}: {str(e)}")
            raise FHIRResourceError(f"Failed to fetch patient data: {str(e)}")

    def get_medication(self, patient_id=None):
        if not patient_id:
            patient_id = cache.get(f'epic_patient_{self.user_id}')
            if not patient_id:
                raise FHIRResourceError("No patient ID found in context")
        try:
            params = {
                'patient': patient_id
            }
            data = self._make_request(f'MedicationRequest', params=params)
            return data
        except Exception as e:
            logger.error(f"Error fetching patient {patient_id}: {str(e)}")
            raise FHIRResourceError(f"Failed to fetch patient data: {str(e)}")