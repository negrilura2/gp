from django.db import models
from django.contrib.auth.models import User

class VoiceTemplate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    template_path = models.CharField(max_length=512)  # 存储在 data/voiceprints/....
    created_at = models.DateTimeField(auto_now_add=True)

class VerifyLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    wav_path = models.CharField(max_length=512, null=True, blank=True)
    predicted_user = models.CharField(max_length=128)
    score = models.FloatField()
    result = models.CharField(max_length=16)  # ACCEPT/REJECT
