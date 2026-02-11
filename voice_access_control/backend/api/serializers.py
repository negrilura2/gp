from rest_framework import serializers
from django.contrib.auth.models import User
from .models import VoiceTemplate, VerifyLog

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id','username','email']

class VoiceTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoiceTemplate
        fields = '__all__'

class VerifyLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerifyLog
        fields = '__all__'
