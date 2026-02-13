from django.contrib import admin
from .models import VoiceTemplate, EnrollLog, VerifyLog

admin.site.register(VoiceTemplate)
admin.site.register(EnrollLog)
admin.site.register(VerifyLog)
