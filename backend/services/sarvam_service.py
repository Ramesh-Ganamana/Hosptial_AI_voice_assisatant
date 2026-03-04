import logging
import os
from dotenv import load_dotenv
from sarvamai import SarvamAI
from sarvamai.core.api_error import ApiError

load_dotenv()
logger = logging.getLogger(__name__)

class SarvamService:
    def __init__(self):
        # Get Sarvam API key from environment
        self.api_key = os.environ.get('SARVAM_API_KEY')
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY not found in environment variables")
        
        # Initialize Sarvam client
        self.client = SarvamAI(api_subscription_key=self.api_key)
        self.model = "saaras:v3"  # Latest model with Indian accent support
        
        logger.info("Sarvam Speech-to-Text service initialized successfully")
    
    def transcribe_audio(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        """
        Transcribe audio data to text using Sarvam API
        
        Args:
            audio_data: Raw audio bytes (WAV format)
            sample_rate: Sample rate of the audio (default: 16000 Hz)
        
        Returns:
            Transcribed text
        """
        try:
            # Create a file-like object from audio bytes
            import io
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "audio.wav"  # Required for Sarvam API
            
            logger.info(f"Transcribing audio: {len(audio_data)} bytes")
            
            # Call Sarvam API for transcription
            response = self.client.speech_to_text.transcribe(
                file=audio_file,
                model=self.model,
                mode="transcribe",  # Standard transcription
                language_code="en-IN"  # Indian English
            )
            
            # Extract transcript from response
            text = response.transcript if hasattr(response, 'transcript') else ""
            
            logger.info(f"Transcription result: {text}")
            return text
        
        except ApiError as e:
            logger.error(f"Sarvam API error: {e.body}")
            
            # Parse and handle specific error codes
            if hasattr(e, 'status_code'):
                if e.status_code == 400:
                    raise Exception("Invalid audio file format or parameters")
                elif e.status_code == 403:
                    raise Exception("Invalid or expired Sarvam API key")
                elif e.status_code == 429:
                    raise Exception("API rate limit exceeded. Please try again later")
                elif e.status_code == 503:
                    raise Exception("Sarvam service temporarily unavailable")
            
            raise Exception(f"Transcription failed: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}", exc_info=True)
            raise

# Singleton instance
sarvam_service = SarvamService()
