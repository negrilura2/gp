from django.contrib.auth.models import User
from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError
from rest_framework import serializers

from .models import VoiceTemplate, VerifyLog, EnrollLog, UserProfile, AdminAccessLog


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
    has_voiceprint = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "is_active",
            "has_voiceprint",
            "full_name",
            "phone",
            "department",
            "date_joined",
            "last_login",
        )

    def get_has_voiceprint(self, obj):
        return VoiceTemplate.objects.filter(user=obj).exists()

    def _get_profile_value(self, obj, field):
        try:
            profile = getattr(obj, "profile", None)
        except (OperationalError, ProgrammingError):
            return ""
        return getattr(profile, field, "") if profile else ""

    def get_full_name(self, obj):
        return self._get_profile_value(obj, "full_name")

    def get_phone(self, obj):
        return self._get_profile_value(obj, "phone")

    def get_department(self, obj):
        return self._get_profile_value(obj, "department")


class AdminListUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    last_login = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "is_active",
            "full_name",
            "phone",
            "department",
            "date_joined",
            "last_login",
        )

    def _get_profile_value(self, obj, field):
        try:
            profile = getattr(obj, "profile", None)
        except (OperationalError, ProgrammingError):
            return ""
        return getattr(profile, field, "") if profile else ""

    def get_full_name(self, obj):
        return self._get_profile_value(obj, "full_name")

    def get_phone(self, obj):
        return self._get_profile_value(obj, "phone")

    def get_department(self, obj):
        return self._get_profile_value(obj, "department")

    def get_last_login(self, obj):
        return getattr(obj, "last_admin_login", None)


class AdminUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    full_name = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    department = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ("username", "password", "email", "is_active", "full_name", "phone", "department")

    def create(self, validated_data):
        full_name = validated_data.pop("full_name", "")
        phone = validated_data.pop("phone", "")
        department = validated_data.pop("department", "")
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, is_staff=False, **validated_data)
        try:
            UserProfile.objects.create(
                user=user,
                full_name=full_name,
                phone=phone,
                department=department
            )
        except (OperationalError, ProgrammingError):
            pass
        return user


class AdminStaffCreateSerializer(AdminUserCreateSerializer):
    def create(self, validated_data):
        full_name = validated_data.pop("full_name", "")
        phone = validated_data.pop("phone", "")
        department = validated_data.pop("department", "")
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, is_staff=True, **validated_data)
        try:
            UserProfile.objects.create(
                user=user,
                full_name=full_name,
                phone=phone,
                department=department
            )
        except (OperationalError, ProgrammingError):
            pass
        return user


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    department = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ("email", "is_active", "full_name", "phone", "department")

    def update(self, instance, validated_data):
        full_name = validated_data.pop("full_name", None)
        phone = validated_data.pop("phone", None)
        department = validated_data.pop("department", None)
        instance = super().update(instance, validated_data)
        if full_name is not None or phone is not None or department is not None:
            try:
                profile, _ = UserProfile.objects.get_or_create(user=instance)
                if full_name is not None:
                    profile.full_name = full_name
                if phone is not None:
                    profile.phone = phone
                if department is not None:
                    profile.department = department
                profile.save()
            except (OperationalError, ProgrammingError):
                pass
        return instance


class AdminStaffUpdateSerializer(AdminUserUpdateSerializer):
    pass


class AdminPasswordResetSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=6)


class AdminSecretSetSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, min_length=6)
    secret_password = serializers.CharField(write_only=True, min_length=6)


class AdminSecretVerifySerializer(serializers.Serializer):
    secret_password = serializers.CharField(write_only=True, min_length=6)


class AdminAccessLogSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = AdminAccessLog
        fields = ("id", "action", "user", "user_username", "success", "client_ip", "created_at")


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
