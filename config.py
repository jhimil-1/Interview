from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration class to manage API keys and feature flags"""
    
    # API Keys
    DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')
    ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

    # Model Configuration
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')

    # ElevenLabs Configuration
    ELEVENLABS_VOICE_ID = os.getenv('ELEVENLABS_VOICE_ID', 'pNInz6obpgDQGcFmaJgB')  # Default voice ID

    # Audio Configuration
    SAMPLE_RATE = int(os.getenv('SAMPLE_RATE', '16000'))  # Default 16kHz
    CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '1024'))     # Default chunk size

    # Feature Flags
    ENABLE_ACCENT_DETECTION = os.getenv('ENABLE_ACCENT_DETECTION', 'false').lower() == 'true'

    @classmethod
    def validate_config(cls):
        """Validate that all required API keys are present"""
        required_keys = ['DEEPGRAM_API_KEY', 'ELEVENLABS_API_KEY', 'GOOGLE_API_KEY']
        
        missing_keys = []
        for key in required_keys:
            if not getattr(cls, key):
                missing_keys.append(key)
        
        if missing_keys:
            raise ValueError(f"Missing required API keys: {', '.join(missing_keys)}")

# Validate configuration on import
Config.validate_config()

from config import Config

# Access configuration values
api_key = Config.DEEPGRAM_API_KEY
accent_detection = Config.ENABLE_ACCENT_DETECTION