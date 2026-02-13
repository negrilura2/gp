from django.contrib.auth.models import User
from django.conf import settings
from rest_framework import serializers

from .models import VoiceTemplate, VerifyLog, EnrollLog


class UserRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("username", "password")
        extra_kwargs = {
            "password": {"write_only": True, "min_length": 6},
        }

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"],
        )
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "is_staff", "date_joined", "last_login")


class VoiceTemplateSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = VoiceTemplate
        fields = ("id", "user", "username", "template_path", "embedding_count", "created_at", "updated_at")


class EnrollLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(read_only=True)

    class Meta:
        model = EnrollLog
        fields = (
            "id",
            "timestamp",
            "user",
            "username",
            "wav_count",
            "client_ip",
            "success",
            "error_msg",
        )


class VerifyLogSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = VerifyLog
        fields = (
            "id",
            "timestamp",
            "user",
            "user_username",
            "wav_path",
            "predicted_user",
            "score",
            "result",
            "door_state",
            "threshold",
            "client_ip",
            "error_msg",
        )


class ThresholdConfigSerializer(serializers.Serializer):
    threshold = serializers.FloatField(min_value=0.0, max_value=1.0)

    def validate_threshold(self, value):
        if not (0 < value < 1):
            raise serializers.ValidationError("threshold 必须在 0~1 之间")
        return value


def get_effective_threshold():
    return float(getattr(settings, "VOICE_VERIFY_THRESHOLD", 0.70))
