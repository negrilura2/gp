
import io
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from api.models import VoiceTemplate, VerifyLog

# Helper to create a dummy WAV file in memory
def create_dummy_wav(duration_sec=1, sample_rate=16000):
    import wave
    import struct
    
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        n_frames = int(duration_sec * sample_rate)
        # Write silence (or simple tone)
        data = struct.pack('<' + ('h' * n_frames), *([0] * n_frames))
        wav_file.writeframes(data)
    
    buffer.seek(0)
    return buffer.read()

class BackendApiTests(TestCase):
    def setUp(self):
        # Create a test user
        self.username = "test_user"
        self.password = "test_pass"
        self.user = User.objects.create_user(username=self.username, password=self.password)
        self.client = Client()
        
        # Get token
        resp = self.client.post("/api/login/", {"username": self.username, "password": self.password})
        self.token = resp.json().get("token")
        self.auth_header = {"HTTP_AUTHORIZATION": f"Token {self.token}"}
        
        # Dummy WAV content
        self.wav_content = create_dummy_wav()

    @patch("api.views.voice.get_service")  # Mock the service getter in views
    def test_enroll_success(self, mock_get_service):
        # Setup mock
        mock_service = MagicMock()
        mock_service.enroll.return_value = {"status": "success", "user_id": self.username, "wav_count": 1}
        mock_get_service.return_value = mock_service
        
        # Prepare file
        wav_file = SimpleUploadedFile("enroll.wav", self.wav_content, content_type="audio/wav")
        
        # Call API
        response = self.client.post(
            "/api/enroll/",
            {"user_id": self.username, "files": [wav_file]},
            **self.auth_header
        )
        
        # Assertions
        self.assertEqual(response.status_code, 200)
        # Note: EnrollView returns "enrolled" instead of "success"
        self.assertEqual(response.json()["status"], "enrolled")
        # Check DB
        self.assertTrue(VoiceTemplate.objects.filter(user=self.user).exists())
        # Check Service called
        mock_service.enroll.assert_called_once()

    @patch("api.views.voice.get_service")
    def test_verify_success(self, mock_get_service):
        # Setup mock for successful verification
        mock_service = MagicMock()
        mock_service.verify.return_value = {
            "status": "success", 
            "score": 0.85, 
            "threshold": 0.75, 
            "result": True, 
            "predicted_user": self.username  # Fix: Service returns 'predicted_user', not 'best_spk'
        }
        mock_get_service.return_value = mock_service
        
        # Ensure user has a template
        # Note: VoiceTemplate does not have 'features_path' field. 
        # Using correct fields based on models.py
        VoiceTemplate.objects.create(
            user=self.user, 
            template_path="dummy/path/templates.npy",
            embedding_count=1
        )
        
        wav_file = SimpleUploadedFile("verify.wav", self.wav_content, content_type="audio/wav")
        
        response = self.client.post(
            "/api/verify/",
            {"file": wav_file, "threshold": 0.75},
            **self.auth_header
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Verify response structure based on voice.py:
        # {
        #     "predicted_user": str(best_spk),
        #     "score": float(best_score),
        #     "result": result,  # "ACCEPT" or "REJECT"
        #     "door_state": door_state,
        #     "user_info": user_info,
        #     "threshold": thr,
        # }
        
        self.assertEqual(data["predicted_user"], self.username)
        self.assertEqual(data["result"], "ACCEPT")
        self.assertEqual(data["door_state"], "OPEN")
        self.assertEqual(data["user_info"]["username"], self.username)
        
        # Check Log
        self.assertTrue(VerifyLog.objects.filter(user=self.user, result="ACCEPT").exists())

    @patch("api.views.voice.get_service")
    def test_verify_failure_low_score(self, mock_get_service):
        # Setup mock for failed verification
        mock_service = MagicMock()
        mock_service.verify.return_value = {
            "status": "success", 
            "score": 0.45, 
            "threshold": 0.75, 
            "result": False, 
            "predicted_user": "unknown" 
        }
        mock_get_service.return_value = mock_service
        
        wav_file = SimpleUploadedFile("verify.wav", self.wav_content, content_type="audio/wav")
        
        response = self.client.post(
            "/api/verify/",
            {"file": wav_file},
            **self.auth_header
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["result"], "REJECT")
        self.assertEqual(data["door_state"], "CLOSED")
        self.assertIsNone(data["user_info"])
        
        # Check Log
        self.assertTrue(VerifyLog.objects.filter(user=self.user, result="REJECT").exists())

    def test_dashboard_access(self):
        # Test protected endpoint
        # Dashboard requires IsAdminUser (is_staff=True), but our test user is just authenticated
        # So 403 Forbidden is actually the CORRECT behavior for a normal user
        response = self.client.get("/api/dashboard/", **self.auth_header)
        self.assertEqual(response.status_code, 403)
        
        # Now upgrade user to staff and try again
        self.user.is_staff = True
        self.user.save()
        response = self.client.get("/api/dashboard/", **self.auth_header)
        self.assertEqual(response.status_code, 200)
        self.assertIn("summary", response.json())
