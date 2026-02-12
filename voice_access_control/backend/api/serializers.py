from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth.models import User
from .models import VoiceTemplate, VerifyLog, EnrollLog


class UserRegisterSerializer(serializers.ModelSerializer):
    """用户注册"""
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("用户名已存在")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
        )
        return user


class UserSerializer(serializers.ModelSerializer):
    """用户信息"""
    has_voiceprint = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_staff', 'date_joined', 'has_voiceprint']

    def get_has_voiceprint(self, obj):
        return VoiceTemplate.objects.filter(user=obj).exists()


class VoiceTemplateSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    created_at_display = serializers.SerializerMethodField()
    updated_at_display = serializers.SerializerMethodField()

    class Meta:
        model = VoiceTemplate
        fields = [
            'id', 'username', 'template_path', 'embedding_count',
            'created_at', 'updated_at', 'created_at_display', 'updated_at_display'
        ]

    def get_created_at_display(self, obj):
        return timezone.localtime(obj.created_at).strftime('%Y-%m-%d %H:%M:%S')

    def get_updated_at_display(self, obj):
        return timezone.localtime(obj.updated_at).strftime('%Y-%m-%d %H:%M:%S')


class VerifyLogSerializer(serializers.ModelSerializer):
    request_username = serializers.CharField(source='request_user.username', read_only=True)
    timestamp_display = serializers.SerializerMethodField()
    class Meta:
        model = VerifyLog
        fields = ['id', 'timestamp', 'wav_path', 'predicted_user', 'score',
                  'result', 'threshold', 'client_ip', 'request_username', 'timestamp_display']

    def get_timestamp_display(self, obj):
        return timezone.localtime(obj.timestamp).strftime('%Y-%m-%d %H:%M:%S')


class EnrollLogSerializer(serializers.ModelSerializer):
    timestamp_display = serializers.SerializerMethodField()
    class Meta:
        model = EnrollLog
        fields = ['id', 'timestamp', 'username', 'wav_count', 'client_ip',
                  'success', 'error_msg', 'timestamp_display']

    def get_timestamp_display(self, obj):
        return timezone.localtime(obj.timestamp).strftime('%Y-%m-%d %H:%M:%S')
