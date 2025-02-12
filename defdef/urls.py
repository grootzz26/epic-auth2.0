from django.urls import path
from . import views

urlpatterns = [
    path('token/', views.get_system_token, name='get-system-token'),
]