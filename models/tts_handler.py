from elevenlabs.client import ElevenLabs
from config import Config
import io
import tempfile
import os

class TTSHandler:
    def __init__(self):
        self.client = ElevenLabs(api_key=Config.ELEVENLABS_API_KEY)
        
    def text_to_speech(self, text):
        """Convert text to speech and return audio data (mp3 bytes)"""
        audio = self.client.text_to_speech.convert(
            text=text,
            voice_id=Config.ELEVENLABS_VOICE_ID,
            model_id="eleven_monolingual_v1",
            output_format="mp3_44100_128"
        )
        # If audio is a generator (stream), join all chunks
        if hasattr(audio, '__iter__') and not isinstance(audio, (bytes, bytearray)):
            audio = b"".join(chunk for chunk in audio if isinstance(chunk, (bytes, bytearray)))
        return audio
    
    def save_audio_file(self, audio_data, filename=None):
        """Save audio data to file and return the file path"""
        if filename is None:
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            filename = temp_file.name
            temp_file.close()
        
        with open(filename, "wb") as f:
            f.write(audio_data)
        
        return filename
    
    def play_audio(self, audio_data):
        """Save audio data to temporary file (playback handled by frontend)"""
        # For web applications, we just save the file and let the frontend handle playback
        return self.save_audio_file(audio_data)