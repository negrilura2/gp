from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django import forms

from .models import UserProfile, AdminSecret, AdminAccessLog, VoiceTemplate, VerifyLog, EnrollLog


class UserProfileInline(admin.TabularInline):
    model = UserProfile
    extra = 0


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "user_role", "full_name", "phone", "department", "updated_at")
    search_fields = ("user__username", "full_name", "phone", "department")
    list_filter = ("user__is_staff",)

    def user_role(self, obj):
        return "管理员" if obj.user.is_staff else "普通用户"

    user_role.short_description = "角色"


class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    list_display = UserAdmin.list_display + ("profile_full_name", "profile_phone")

    def profile_full_name(self, obj):
        try:
            profile = getattr(obj, "profile", None)
        except UserProfile.DoesNotExist:
            profile = None
        return getattr(profile, "full_name", "") if profile else ""

    def profile_phone(self, obj):
        try:
            profile = getattr(obj, "profile", None)
        except UserProfile.DoesNotExist:
            profile = None
        return getattr(profile, "phone", "") if profile else ""

    profile_full_name.short_description = "姓名"
    profile_phone.short_description = "联系电话"


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


class AdminSecretForm(forms.ModelForm):
    secret_password = forms.CharField(required=False, widget=forms.PasswordInput)

    class Meta:
        model = AdminSecret
        fields = ("secret_password", "updated_by")


@admin.register(AdminSecret)
class AdminSecretAdmin(admin.ModelAdmin):
    form = AdminSecretForm
    list_display = ("id", "updated_at", "updated_by")
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        if not request.user.is_superuser:
            return False
        if AdminSecret.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        if not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj=obj)

    def save_model(self, request, obj, form, change):
        secret_password = form.cleaned_data.get("secret_password")
        if secret_password:
            obj.password_hash = make_password(secret_password)
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AdminAccessLog)
class AdminAccessLogAdmin(admin.ModelAdmin):
    list_display = ("action", "user", "success", "client_ip", "created_at")
    list_filter = ("action", "success")
    search_fields = ("user__username", "client_ip")


@admin.register(VoiceTemplate)
class VoiceTemplateAdmin(admin.ModelAdmin):
    list_display = ("user", "template_path", "embedding_count", "created_at", "updated_at")
    search_fields = ("user__username",)


@admin.register(VerifyLog)
class VerifyLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "predicted_user", "result", "score", "client_ip")
    list_filter = ("result",)
    search_fields = ("predicted_user", "user__username", "client_ip")


@admin.register(EnrollLog)
class EnrollLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "username", "wav_count", "success", "client_ip")
    list_filter = ("success",)
    search_fields = ("username", "client_ip")
