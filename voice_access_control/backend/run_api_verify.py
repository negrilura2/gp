import os
import json


def build_case(resp):
    if resp is None:
        return None
    return {
        "status": resp.status_code,
        "body": resp.content.decode("utf-8"),
    }


def find_impostor_wav(raw_root, reference_path):
    ref_abs = os.path.abspath(reference_path)
    for root, _, files in os.walk(raw_root):
        for name in files:
            if not name.lower().endswith(".wav"):
                continue
            full = os.path.abspath(os.path.join(root, name))
            if full != ref_abs:
                return full
    return None


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

        user01_raw_dir = os.path.join(settings.PROJECT_ROOT, "data", "raw", "user01")
        if not os.path.isdir(user01_raw_dir):
            raise FileNotFoundError(user01_raw_dir)

        raw_candidates = [
            os.path.join(user01_raw_dir, f)
            for f in os.listdir(user01_raw_dir)
            if f.lower().endswith(".wav")
        ]
        if not raw_candidates:
            raise FileNotFoundError(f"no wav files in {user01_raw_dir}")
        raw_candidates.sort()
        raw_main = raw_candidates[-1]

        processed_dir = os.path.join(settings.PROJECT_ROOT, "data", "processed", "user01")
        processed_main = os.path.join(processed_dir, os.path.basename(raw_main))

        with open(raw_main, "rb") as f:
            raw_bytes = f.read()

        enroll_upload = SimpleUploadedFile(os.path.basename(raw_main), raw_bytes, content_type="audio/wav")
        enroll_resp = c.post(
            "/api/enroll/",
            {"user_id": "api_user", "files": [enroll_upload]},
            HTTP_AUTHORIZATION="Token " + token.key,
        )

        default_thr = getattr(settings, "VOICE_VERIFY_THRESHOLD", 0.7)
        thr_str = str(default_thr)

        verify_same_resp = c.post(
            "/api/verify/",
            {"file": SimpleUploadedFile(os.path.basename(raw_main), raw_bytes, content_type="audio/wav"), "threshold": thr_str},
        )

        verify_processed_resp = None
        if os.path.exists(processed_main):
            with open(processed_main, "rb") as f:
                processed_bytes = f.read()
            verify_processed_resp = c.post(
                "/api/verify/",
                {
                    "file": SimpleUploadedFile(
                        os.path.basename(processed_main), processed_bytes, content_type="audio/wav"
                    ),
                    "threshold": thr_str,
                },
            )

        impostor_path = find_impostor_wav(
            os.path.join(settings.PROJECT_ROOT, "data", "raw"),
            raw_main,
        )
        verify_impostor_resp = None
        if impostor_path and os.path.exists(impostor_path):
            with open(impostor_path, "rb") as f:
                imp_bytes = f.read()
            verify_impostor_resp = c.post(
                "/api/verify/",
                {"file": SimpleUploadedFile(os.path.basename(impostor_path), imp_bytes, content_type="audio/wav"), "threshold": thr_str},
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
            "enroll": build_case(enroll_resp),
            "verify_same_raw": build_case(verify_same_resp),
            "verify_processed": build_case(verify_processed_resp)
            if verify_processed_resp is not None
            else {"skipped": True, "reason": "no processed wav found"},
            "verify_impostor": build_case(verify_impostor_resp)
            if verify_impostor_resp is not None
            else {"skipped": True, "reason": "no impostor wav found"},
            "stats": build_case(stats_resp),
            "dashboard": build_case(dash_resp),
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
