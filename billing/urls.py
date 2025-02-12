from django.urls import path
from .views import *

urlpatterns = [
    # path("", get_start_auth),
    path("", start_auth),
    path("account/<str:account_id>/", account_detail, name="account_detail"),
    # path("callback/", callback),
    path("callback/", oauth_callback, name='epic-oauth-callback'),
    # path("callback/", auth_callback),
    path("initiate/", initiate_auth),
    # path("initiate/", start_auth),
    path('patient/<str:pk>', get_patient_data, name='get-patient-data'),
    path('patient/', get_patient_data, name='get-patient-data'),
    path("coverage/<str:pk>", CoverageAPIView.as_view(), name="coverage"),
    path("medication/<str:pk>", MedicationAPIView.as_view(), name="medication"),
]