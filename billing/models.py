from django.db import models
from django.conf import settings
from datetime import datetime, timedelta

class EpicAuthToken(models.Model):
    """Store Epic FHIR OAuth tokens"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    access_token = models.TextField(null=True, blank=True)
    refresh_token = models.TextField(null=True, blank=True)
    expires_at = models.DateTimeField()
    scope = models.TextField(default='')
    token_type = models.CharField(max_length=50, default='Bearer')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['expires_at']),
        ]

    @property
    def is_expired(self):
        return datetime.now() > self.expires_at

    @property
    def is_refresh_expired(self):
        if not self.refresh_token:
            return True
        refresh_expires_at = self.created_at + timedelta(
            days=settings.EPIC_CONFIG.get('REFRESH_TOKEN_LIFETIME_DAYS', 30)
        )
        return datetime.now() > refresh_expires_at
