import requests
import sys
import json
import io
from datetime import datetime
from pathlib import Path

class HospitalAITester:
    def __init__(self, base_url="https://smart-doctor-chat.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.session_id = f"test_session_{int(datetime.now().timestamp())}"
        self.tests_run = 0
        self.tests_passed = 0

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}: PASSED")
        else:
            print(f"❌ {name}: FAILED - {details}")
        if details and success:
            print(f"   → {details}")
        return success

    def test_api_root(self):
        """Test root API endpoint"""
        try:
            response = requests.get(f"{self.api_url}/", timeout=10)
            success = response.status_code == 200 and "Hospital AI Assistant API" in response.text
            details = f"Status: {response.status_code}, Response: {response.json()}"
            return self.log_test("API Root Endpoint", success, details)
        except Exception as e:
            return self.log_test("API Root Endpoint", False, str(e))

    def test_doctors_endpoint(self):
        """Test doctors list endpoint"""
        try:
            response = requests.get(f"{self.api_url}/doctors", timeout=10)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                doctors = data.get('doctors', [])
                success = len(doctors) > 0 and 'name' in doctors[0]
                details = f"Found {len(doctors)} doctors"
            else:
                details = f"Status: {response.status_code}"
                
            return self.log_test("Doctors Endpoint", success, details)
        except Exception as e:
            return self.log_test("Doctors Endpoint", False, str(e))

    def test_process_audio_no_file(self):
        """Test process-audio endpoint without file (should fail gracefully)"""
        try:
            response = requests.post(f"{self.api_url}/process-audio", timeout=15)
            # Should fail but gracefully - we expect 422 for missing file
            success = response.status_code in [422, 400]
            details = f"Status: {response.status_code} (expected 422/400 for missing file)"
            return self.log_test("Process Audio (No File)", success, details)
        except Exception as e:
            return self.log_test("Process Audio (No File)", False, str(e))

    def test_process_audio_empty_file(self):
        """Test process-audio endpoint with empty file"""
        try:
            # Create minimal WAV file (44 byte header only - no audio data)
            wav_header = self.create_minimal_wav()
            
            files = {'audio': ('test.wav', io.BytesIO(wav_header), 'audio/wav')}
            data = {'session_id': self.session_id}
            
            response = requests.post(
                f"{self.api_url}/process-audio",
                files=files,
                data=data,
                timeout=20
            )
            
            # Should handle empty audio gracefully 
            success = response.status_code == 200
            if success:
                result = response.json()
                success = 'response' in result
                details = f"Response: {result.get('response', '')[:100]}..."
            else:
                details = f"Status: {response.status_code}, Response: {response.text[:200]}"
                
            return self.log_test("Process Audio (Empty File)", success, details)
        except Exception as e:
            return self.log_test("Process Audio (Empty File)", False, str(e))

    def test_book_appointment(self):
        """Test appointment booking endpoint"""
        try:
            appointment_data = {
                "patient_name": "Test Patient",
                "doctor_id": "doc001",
                "doctor_name": "Dr. Rajesh Kumar",
                "date": "2024-12-20",
                "time": "10:00 AM"
            }
            
            response = requests.post(
                f"{self.api_url}/book-appointment",
                json=appointment_data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            success = response.status_code == 200
            if success:
                result = response.json()
                success = result.get('success', False) and 'appointment' in result
                details = f"Appointment ID: {result.get('appointment', {}).get('id', 'N/A')}"
            else:
                details = f"Status: {response.status_code}, Response: {response.text[:200]}"
                
            return self.log_test("Book Appointment", success, details)
        except Exception as e:
            return self.log_test("Book Appointment", False, str(e))

    def test_status_endpoints(self):
        """Test status check endpoints"""
        try:
            # Test POST status
            status_data = {"client_name": "test_client"}
            response = requests.post(
                f"{self.api_url}/status",
                json=status_data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            post_success = response.status_code == 200
            if not post_success:
                return self.log_test("Status Endpoints", False, f"POST failed: {response.status_code}")
            
            # Test GET status
            response = requests.get(f"{self.api_url}/status", timeout=10)
            get_success = response.status_code == 200
            
            if get_success:
                data = response.json()
                success = isinstance(data, list)
                details = f"Status checks count: {len(data) if success else 'Error'}"
            else:
                success = False
                details = f"GET failed: {response.status_code}"
                
            return self.log_test("Status Endpoints", success, details)
        except Exception as e:
            return self.log_test("Status Endpoints", False, str(e))

    def create_minimal_wav(self):
        """Create a minimal WAV file header"""
        # 44-byte WAV header for empty file
        return bytes([
            # RIFF header
            0x52, 0x49, 0x46, 0x46,  # "RIFF"
            0x24, 0x00, 0x00, 0x00,  # File size - 8
            0x57, 0x41, 0x56, 0x45,  # "WAVE"
            # fmt chunk
            0x66, 0x6D, 0x74, 0x20,  # "fmt "
            0x10, 0x00, 0x00, 0x00,  # Chunk size (16)
            0x01, 0x00,              # Audio format (PCM)
            0x01, 0x00,              # Channels (1)
            0x00, 0x3E, 0x00, 0x00,  # Sample rate (16000)
            0x00, 0x7C, 0x00, 0x00,  # Byte rate
            0x02, 0x00,              # Block align
            0x10, 0x00,              # Bits per sample (16)
            # data chunk
            0x64, 0x61, 0x74, 0x61,  # "data"
            0x00, 0x00, 0x00, 0x00,  # Data size (0 - no audio data)
        ])

    def run_all_tests(self):
        """Run all backend tests"""
        print("🔍 Starting Hospital AI Assistant Backend Tests...")
        print(f"📍 Testing API at: {self.api_url}")
        print("=" * 60)
        
        # Test basic connectivity
        self.test_api_root()
        
        # Test doctors service
        self.test_doctors_endpoint()
        
        # Test audio processing
        self.test_process_audio_no_file()
        self.test_process_audio_empty_file()
        
        # Test appointments
        self.test_book_appointment()
        
        # Test status endpoints
        self.test_status_endpoints()
        
        print("=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All backend tests passed!")
            return True
        else:
            print("⚠️  Some backend tests failed. Check the logs above.")
            return False

def main():
    tester = HospitalAITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())