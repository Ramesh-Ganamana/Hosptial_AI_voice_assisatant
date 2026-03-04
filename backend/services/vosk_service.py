import json
import logging
from vosk import Model, KaldiRecognizer
from pathlib import Path

logger = logging.getLogger(__name__)

class VoskService:
    def __init__(self):
        # Path to the Vosk model
        model_path = Path(__file__).parent.parent / "models" / "vosk-model-small-en-in-0.4"
        logger.info(f"Loading Vosk model from {model_path}")
        
        if not model_path.exists():
            raise FileNotFoundError(f"Vosk model not found at {model_path}")
        
        self.model = Model(str(model_path))
        logger.info("Vosk model loaded successfully")
    
    def transcribe_audio(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        """
        Transcribe audio data to text using Vosk
        
        Args:
            audio_data: Raw audio bytes in PCM WAV format
            sample_rate: Sample rate of the audio (default: 16000 Hz)
        
        Returns:
            Transcribed text
        """
        try:
            recognizer = KaldiRecognizer(self.model, sample_rate)
            recognizer.SetWords(True)
            
            # Process audio data
            if recognizer.AcceptWaveform(audio_data):
                result = json.loads(recognizer.Result())
            else:
                result = json.loads(recognizer.FinalResult())
            
            text = result.get('text', '')
            logger.info(f"Transcription result: {text}")
            return text
        
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            raise

# Singleton instance
vosk_service = VoskService()