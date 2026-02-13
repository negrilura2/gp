import os
import json


def main():
    output_path = os.path.join(os.path.dirname(__file__), "api_verify_output.json")
    result = {}
    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
        import django
        django.setup()

        from django.test import Client
        from django.contrib.auth.models import User
        from rest_framework.authtoken.models import Token
        from django.conf import settings
        from django.core.files.uploadedfile import SimpleUploadedFile
        from api.models import VerifyLog, EnrollLog, VoiceTemplate

        c = Client()
        user, _ = User.objects.get_or_create(username="api_user")
        user.set_password("123456")
        user.is_staff = True
        user.save()
        token, _ = Token.objects.get_or_create(user=user)

        wav_path = os.path.join(settings.PROJECT_ROOT, "data", "raw", "user01", "001.wav")
        if not os.path.exists(wav_path):
            raise FileNotFoundError(wav_path)
        with open(wav_path, "rb") as f:
            wav_bytes = f.read()

        upload = SimpleUploadedFile("001.wav", wav_bytes, content_type="audio/wav")
        enroll_resp = c.post(
            "/api/enroll/",
            {"user_id": "api_user", "files": [upload]},
            HTTP_AUTHORIZATION="Token " + token.key,
        )

        verify_upload = SimpleUploadedFile("001.wav", wav_bytes, content_type="audio/wav")
        verify_resp = c.post(
            "/api/verify/",
            {"file": verify_upload, "threshold": "0.7"},
        )

        stats_resp = c.get(
            "/api/stats/",
            HTTP_AUTHORIZATION="Token " + token.key,
        )
        dash_resp = c.get(
            "/api/dashboard/",
            HTTP_AUTHORIZATION="Token " + token.key,
        )

        latest_verify = VerifyLog.objects.order_by("-id").first()
        latest_enroll = EnrollLog.objects.order_by("-id").first()
        latest_template = VoiceTemplate.objects.filter(user=user).first()

        result = {
            "enroll": {"status": enroll_resp.status_code, "body": enroll_resp.content.decode("utf-8")},
            "verify": {"status": verify_resp.status_code, "body": verify_resp.content.decode("utf-8")},
            "stats": {"status": stats_resp.status_code, "body": stats_resp.content.decode("utf-8")},
            "dashboard": {"status": dash_resp.status_code, "body": dash_resp.content.decode("utf-8")},
            "latest_verify_log": {
                "id": latest_verify.id if latest_verify else None,
                "predicted_user": latest_verify.predicted_user if latest_verify else None,
                "result": latest_verify.result if latest_verify else None,
                "door_state": latest_verify.door_state if latest_verify else None,
                "score": latest_verify.score if latest_verify else None,
            },
            "latest_enroll_log": {
                "id": latest_enroll.id if latest_enroll else None,
                "username": latest_enroll.username if latest_enroll else None,
                "wav_count": latest_enroll.wav_count if latest_enroll else None,
                "success": latest_enroll.success if latest_enroll else None,
            },
            "latest_voice_template": {
                "id": latest_template.id if latest_template else None,
                "template_path": latest_template.template_path if latest_template else None,
                "embedding_count": latest_template.embedding_count if latest_template else None,
            },
            "db": {
                "engine": settings.DATABASES["default"]["ENGINE"],
                "name": str(settings.DATABASES["default"]["NAME"]),
            },
            "error": None,
        }
    except Exception as e:
        result = {"error": repr(e)}

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
