import os
from django.test import TestCase
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from .models import VerifyLog, VoiceTemplate


class ApiFlowTests(TestCase):
    def test_enroll_and_verify_flow(self):
        wav_path = os.path.join(settings.PROJECT_ROOT, "data", "raw", "user01", "001.wav")
        with open(wav_path, "rb") as f:
            wav_bytes = f.read()
        upload = SimpleUploadedFile("001.wav", wav_bytes, content_type="audio/wav")

        register_resp = self.client.post("/api/register/", {"username": "api_user", "password": "123456"})
        self.assertEqual(register_resp.status_code, 201)

        login_resp = self.client.post("/api/login/", {"username": "api_user", "password": "123456"})
        self.assertEqual(login_resp.status_code, 200)
        token = login_resp.json().get("token")
        self.assertTrue(token)
        user = User.objects.get(username="api_user")
        user.is_staff = True
        user.save()

        enroll_resp = self.client.post(
            "/api/enroll/",
            {"user_id": "api_user", "files": [upload]},
            HTTP_AUTHORIZATION=f"Token {token}",
        )
        self.assertEqual(enroll_resp.status_code, 200)
        self.assertTrue(VoiceTemplate.objects.filter(user__username="api_user").exists())

        verify_upload = SimpleUploadedFile("001.wav", wav_bytes, content_type="audio/wav")
        verify_resp = self.client.post(
            "/api/verify/",
            {"file": verify_upload, "threshold": "0.7"},
        )
        self.assertEqual(verify_resp.status_code, 200)
        data = verify_resp.json()
        self.assertIn("door_state", data)
        self.assertIn(data["door_state"], ["OPEN", "CLOSED"])
        self.assertTrue(VerifyLog.objects.filter(door_state__in=["OPEN", "CLOSED"]).exists())

        stats_resp = self.client.get("/api/stats/", HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(stats_resp.status_code, 200)
        stats_data = stats_resp.json()
        self.assertIn("daily", stats_data)
        self.assertIn("result_distribution", stats_data)
        self.assertIn("users", stats_data)

        dash_resp = self.client.get("/api/dashboard/", HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(dash_resp.status_code, 200)
        dash_data = dash_resp.json()
        self.assertIn("summary", dash_data)
        self.assertIn("data_assets", dash_data)
        self.assertIn("trend", dash_data)
        self.assertIn("model", dash_data)
