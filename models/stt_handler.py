import asyncio
import websockets
import json
import base64
from config import Config
import pyaudio
import threading
import queue
import requests
import os
import wave
import tempfile
import subprocess
import shutil
import time
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class STTHandler:
    def __init__(self):
        self.api_key = Config.DEEPGRAM_API_KEY
        self.websocket = None
        self.audio_queue = queue.Queue()
        self.is_recording = False
        self.transcript = ""
        self.enable_accent_detection = getattr(Config, 'ENABLE_ACCENT_DETECTION', False)  # Default to False
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((
            websockets.exceptions.ConnectionClosedError,
            ConnectionError,
            asyncio.TimeoutError,
            Exception
        )),
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying connection (attempt {retry_state.attempt_number}): {str(retry_state.outcome.exception())}"
        )
    )
    async def connect_deepgram(self, language="en", model="nova-2"):
        """Connect to Deepgram WebSocket with optimized parameters and retry logic"""
        if not self.api_key:
            raise ValueError("Deepgram API key is not configured")
            
        # Base parameters
        params = {
            'encoding': 'linear16',
            'sample_rate': '16000',
            'channels': '1',
            'language': language,
            'model': model,
            'punctuate': 'true',
            'smart_format': 'true',
            'filler_words': 'false',
            'profanity_filter': 'true',
            'redact': 'false',
            'alternatives': '1',
            'numerals': 'true',
            'diarize': 'false',
            'endpointing': '200',
            'utterance_end_ms': '1000'
        }
        
        # Only enable advanced features if accent detection is on
        if self.enable_accent_detection:
            params.update({
                'tier': 'enhanced',
                'keywords': 'interview,resume,experience,education,skills',
                'keywords_threshold': '0.5'
            })
        
        # Build query string
        query_string = '&'.join(f"{k}={v}" for k, v in params.items())
        
        # Create headers
        headers = [
            ('Authorization', f'Token {self.api_key}'),
            ('User-Agent', 'JD-Interview-App/1.0')
        ]
        
        try:
            # Connect with proper headers and parameters
            self.websocket = await asyncio.wait_for(
                websockets.connect(
                    f'wss://api.deepgram.com/v1/listen?{query_string}',
                    additional_headers=headers,
                    ping_interval=30,
                    ping_timeout=30,
                    close_timeout=10,
                    max_size=None  # Remove message size limit
                ),
                timeout=10.0  # 10 seconds connection timeout
            )
            logger.info("Successfully connected to Deepgram API")
            return self.websocket
            
        except asyncio.TimeoutError:
            logger.error("Connection to Deepgram API timed out")
            raise ConnectionError("Connection to Deepgram API timed out")
            
        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 503:
                logger.error("Deepgram API is currently unavailable (503). Please try again later.")
                raise ConnectionError("Deepgram API is currently unavailable. Please try again later.")
            elif e.status_code == 429:
                logger.error("Rate limit exceeded. Please reduce request frequency or upgrade your plan.")
                raise ConnectionError("Rate limit exceeded. Please try again later.")
            else:
                logger.error(f"Deepgram API error {e.status_code}: {e.headers}")
                raise
                
        except Exception as e:
            if 'quota' in str(e).lower():
                logger.error("API quota exceeded. Please check your Deepgram account or disable accent detection.")
                raise Exception("API quota exceeded. Please check your Deepgram account or disable accent detection.")
            logger.error(f"Unexpected error connecting to Deepgram: {str(e)}")
            raise
        
    async def send_audio(self):
        """Send audio data to Deepgram with error handling"""
        consecutive_errors = 0
        max_consecutive_errors = 3
        
        while self.is_recording:
            try:
                if not self.audio_queue.empty():
                    audio_data = self.audio_queue.get()
                    if self.websocket and not self.websocket.closed:
                        await self.websocket.send(audio_data)
                        consecutive_errors = 0  # Reset on successful send
                    else:
                        logger.warning("WebSocket connection is closed. Attempting to reconnect...")
                        await self.connect_deepgram()
                        
                await asyncio.sleep(0.01)
                
            except (websockets.exceptions.ConnectionClosed, ConnectionError) as e:
                consecutive_errors += 1
                logger.warning(f"Connection error (attempt {consecutive_errors}/{max_consecutive_errors}): {str(e)}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Max connection retries reached. Stopping audio send.")
                    self.is_recording = False
                    break
                    
                # Exponential backoff before retry
                await asyncio.sleep(min(2 ** consecutive_errors, 10))  # Cap at 10 seconds
                
                try:
                    await self.connect_deepgram()
                except Exception as reconnect_error:
                    logger.error(f"Failed to reconnect: {str(reconnect_error)}")
                    self.is_recording = False
                    break
                    
            except Exception as e:
                logger.error(f"Error in send_audio: {str(e)}")
                self.is_recording = False
                break
            
    async def receive_transcript(self):
        """Receive transcription from Deepgram with error handling"""
        while self.is_recording:
            try:
                if not self.websocket or self.websocket.closed:
                    logger.warning("WebSocket not connected. Attempting to reconnect...")
                    await self.connect_deepgram()
                    continue
                    
                message = await asyncio.wait_for(self.websocket.recv(), timeout=30.0)
                data = json.loads(message)
                
                # Handle different response types
                if 'error' in data:
                    logger.error(f"Deepgram API error: {data['error']}")
                    continue
                    
                if 'channel' in data and 'alternatives' in data['channel'] and data['channel']['alternatives']:
                    transcript = data['channel']['alternatives'][0].get('transcript', '').strip()
                    if transcript:
                        self.transcript += transcript + " "
                        logger.debug(f"Received transcript: {transcript}")
                        
            except asyncio.TimeoutError:
                logger.warning("No message received from Deepgram for 30 seconds")
                # Send a ping to check connection
                try:
                    if self.websocket and not self.websocket.closed:
                        await self.websocket.ping()
                except Exception as e:
                    logger.error(f"Ping failed: {str(e)}")
                    self.is_recording = False
                    break
                    
            except (websockets.exceptions.ConnectionClosed, ConnectionError) as e:
                logger.error(f"Connection closed while receiving: {str(e)}")
                try:
                    await self.connect_deepgram()
                except Exception as reconnect_error:
                    logger.error(f"Failed to reconnect: {str(reconnect_error)}")
                    self.is_recording = False
                    break
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Deepgram response: {str(e)}")
                
            except Exception as e:
                logger.error(f"Error in receive_transcript: {str(e)}")
                self.is_recording = False
                break
                    
    def record_audio(self):
        """Record audio from microphone"""
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=Config.SAMPLE_RATE,
            input=True,
            frames_per_buffer=Config.CHUNK_SIZE
        )
        
        while self.is_recording:
            data = stream.read(Config.CHUNK_SIZE)
            self.audio_queue.put(data)
            
        stream.stop_stream()
        stream.close()
        p.terminate()
        
    async def start_recording(self, language="en", model="nova-2"):
        """Start recording and transcription with optimized settings"""
        if not self.api_key:
            raise ValueError("Deepgram API key is not configured")
            
        self.is_recording = True
        self.transcript = ""
        
        try:
            # Only perform accent detection if enabled
            if self.enable_accent_detection and language == "en":
                # Create a temporary file for accent detection
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
                    temp_path = temp_audio.name
                    
                try:
                    # Save a small sample for accent detection
                    self.save_audio_sample(temp_path, duration=5)
                    
                    # Detect accent and get optimized model
                    detected_lang, accent_type = self.detect_accent_and_language(temp_path)
                    if detected_lang and detected_lang != language:
                        language = detected_lang
                        print(f"Detected language: {language}, accent: {accent_type}")
                        
                    # Select model based on accent
                    if accent_type in ["indian", "south_african"]:
                        model = "nova-2-general"
                    elif accent_type in ["british", "australian"]:
                        model = "nova-2-english"
                        
                finally:
                    # Clean up temp file
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            
            # Connect with optimized parameters
            await self.connect_deepgram(language=language, model=model)
            
            # Start recording thread
            record_thread = threading.Thread(target=self.record_audio)
            record_thread.daemon = True
            record_thread.start()
            
            # Start async tasks
            await asyncio.gather(
                self.send_audio(),
                self.receive_transcript()
            )
            
        except Exception as e:
            self.is_recording = False
            if 'quota' in str(e).lower():
                raise Exception("API quota exceeded. Please check your Deepgram account or disable accent detection in .env")
            raise
        
    def stop_recording(self):
        """Stop recording"""
        self.is_recording = False
        if self.websocket:
            asyncio.create_task(self.websocket.close())
        return self.transcript
    
    def detect_accent_and_language(self, audio_file_path):
        """Detect potential accent/language characteristics for better model selection"""
        try:
            # Quick transcription with multiple language models to detect accent
            test_params = {
                "model": "nova-3",
                "language": "en",
                "smart_format": "false",
                "punctuate": "false",
                "confidence": "true",
                "alternatives": "1"
            }
            
            # Test with a small sample (first 10 seconds) for accent detection
            temp_sample = self.create_audio_sample(audio_file_path, duration=10)
            if not temp_sample:
                return "en", "general"  # Default fallback
            
            headers = {
                "Authorization": f"Token {self.api_key}",
                "Content-Type": "audio/wav"
            }
            
            with open(temp_sample, "rb") as audio_file:
                audio_data = audio_file.read()
            
            response = requests.post(
                "https://api.deepgram.com/v1/listen",
                headers=headers,
                params=test_params,
                data=audio_data,
                timeout=30
            )
            
            # Clean up sample file
            if os.path.exists(temp_sample):
                os.remove(temp_sample)
            
            if response.status_code == 200:
                result = response.json()
                if "results" in result and "channels" in result["results"]:
                    channels = result["results"]["channels"]
                    if channels and "alternatives" in channels[0] and channels[0]["alternatives"]:
                        transcript = channels[0]["alternatives"][0].get("transcript", "")
                        confidence = channels[0]["alternatives"][0].get("confidence", 0.0)
                        
                        # Analyze transcript for accent indicators
                        accent_type = self.analyze_accent_patterns(transcript)
                        
                        print(f"Accent detection - Transcript: '{transcript[:50]}...', Confidence: {confidence:.3f}, Detected accent: {accent_type}")
                        
                        return "en", accent_type
            
            return "en", "general"
            
        except Exception as e:
            print(f"Accent detection error: {e}")
            return "en", "general"
    
    def analyze_accent_patterns(self, transcript):
        """Analyze transcript patterns to identify potential accent characteristics"""
        if not transcript:
            return "general"
        
        transcript_lower = transcript.lower()
        
        # Pattern indicators for different accent types
        patterns = {
            "indian": ["actually", "basically", "definitely", "obviously", "totally", "really", "very much", "good", "nice", "excellent"],
            "british": ["quite", "rather", "brilliant", "lovely", "proper", "indeed", "certainly", "absolutely", "whilst", "amongst"],
            "australian": ["mate", "fair dinkum", "no worries", "good on you", "she'll be right", "reckon", "heaps", "bloody"],
            "american": ["awesome", "cool", "dude", "totally", "like", "you know", "whatever", "basically", "literally"],
            "canadian": ["eh", "about", "house", "out", "sorry", "aboot", "hoose", "oot"],
            "south_african": ["ja", "now now", "just now", "shame", "lekker", "boet", "howzit"]
        }
        
        accent_scores = {}
        for accent, keywords in patterns.items():
            score = sum(1 for keyword in keywords if keyword in transcript_lower)
            if score > 0:
                accent_scores[accent] = score
        
        if accent_scores:
            detected_accent = max(accent_scores, key=accent_scores.get)
            print(f"Accent pattern analysis: {accent_scores}, detected: {detected_accent}")
            return detected_accent
        
        return "general"
    
    def create_audio_sample(self, audio_file_path, duration=10):
        """Create a short audio sample for accent detection"""
        try:
            temp_dir = tempfile.mkdtemp()
            sample_file = os.path.join(temp_dir, "accent_sample.wav")
            
            # Use ffmpeg to extract first 10 seconds
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-i", audio_file_path,
                "-t", str(duration),  # Duration in seconds
                "-ar", "16000",
                "-ac", "1",
                "-c:a", "pcm_s16le",
                "-f", "wav",
                sample_file
            ]
            
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and os.path.exists(sample_file):
                return sample_file
            
        except Exception as e:
            print(f"Sample creation error: {e}")
        
        return None
    
    def preprocess_audio(self, audio_file_path, accent_type="general"):
        """Preprocess audio for better accent and noise handling with adaptive filtering"""
        try:
            print(f"Preprocessing audio for better accent and noise handling: {audio_file_path} (accent: {accent_type})")
            
            # First, validate the input file is already in proper format
            is_valid, validation_error = self.validate_audio_file(audio_file_path)
            if not is_valid:
                print(f"Input audio validation failed: {validation_error}")
                return audio_file_path, f"Input validation failed: {validation_error}"
            
            # Check if file is already in good format - if so, skip preprocessing
            try:
                with wave.open(audio_file_path, 'rb') as wav_file:
                    sample_rate = wav_file.getframerate()
                    channels = wav_file.getnchannels()
                    sample_width = wav_file.getsampwidth()
                    
                    # If already in ideal format (16kHz, mono, 16-bit), skip preprocessing
                    if sample_rate == 16000 and channels == 1 and sample_width == 2:
                        print(f"Audio already in optimal format, skipping preprocessing")
                        return audio_file_path, None
            except Exception as wav_check:
                print(f"WAV format check failed: {wav_check}, proceeding with preprocessing")
            
            # Create temporary file for processed audio
            temp_dir = tempfile.mkdtemp()
            processed_file = os.path.join(temp_dir, "processed_audio.wav")
            
            # Minimal processing to ensure compatibility without corruption
            # Skip complex filters that might cause issues
            ffmpeg_cmd = [
                "ffmpeg", "-y",  # Overwrite output file
                "-i", audio_file_path,  # Input file
                "-ar", "16000",  # Sample rate 16kHz
                "-ac", "1",      # Mono channel
                "-c:a", "pcm_s16le",  # PCM 16-bit little-endian
                "-f", "wav",     # WAV format
                "-avoid_negative_ts", "make_zero",  # Fix timestamp issues
                processed_file
            ]
            
            print(f"Converting to standard format: 16kHz, mono, PCM 16-bit")
            
            # Check if ffmpeg is available
            try:
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=60)
                if result.returncode == 0 and os.path.exists(processed_file):
                    # Verify the processed file is valid
                    file_size = os.path.getsize(processed_file)
                    if file_size > 1024:  # At least 1KB
                        # Additional validation: check if file is valid WAV
                        try:
                            with wave.open(processed_file, 'rb') as test_wav:
                                frames = test_wav.getnframes()
                                if frames > 0:
                                    print(f"Audio preprocessing successful: {processed_file} ({file_size} bytes)")
                                    return processed_file, None
                                else:
                                    print(f"Processed audio has no frames, using original")
                                    return audio_file_path, "Processed audio invalid, using original"
                        except Exception as wav_test:
                            print(f"Processed audio validation failed: {wav_test}, using original")
                            return audio_file_path, "Processed audio validation failed, using original"
                    else:
                        print(f"Processed file too small: {file_size} bytes")
                        return audio_file_path, "Processed file too small, using original"
                else:
                    print(f"FFmpeg failed: {result.stderr}")
                    return audio_file_path, f"FFmpeg processing failed: {result.stderr[:100]}"
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                print(f"FFmpeg not available or timeout: {e}")
                # Fall back to original file
                return audio_file_path, "FFmpeg not available, using original file"
                
        except Exception as e:
            print(f"Audio preprocessing error: {e}")
            return audio_file_path, f"Preprocessing error: {str(e)}"
    
    def validate_processed_audio(self, audio_file_path):
        """Validate that processed audio file is valid and not corrupted"""
        try:
            # Check if file exists and has reasonable size
            if not os.path.exists(audio_file_path):
                return False
            
            file_size = os.path.getsize(audio_file_path)
            if file_size < 1024:  # Less than 1KB is likely corrupted
                return False
            
            # Try to read the file header to check if it's valid WAV
            with open(audio_file_path, 'rb') as f:
                header = f.read(12)
                if len(header) < 12:
                    return False
                
                # Check for valid WAV header (RIFF...WAVE)
                if header[:4] == b'RIFF' and header[8:12] == b'WAVE':
                    return True
                
                # If not WAV, check if it's at least a valid audio file by trying to process a small sample
                try:
                    test_cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", audio_file_path]
                    result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0 and result.stdout.strip():
                        duration = float(result.stdout.strip())
                        return duration > 0  # Valid if has positive duration
                except:
                    pass
            
            return False
            
        except Exception as e:
            print(f"Audio validation error: {e}")
            return False
    
    def simple_preprocess_audio(self, audio_file_path):
        """Simple audio preprocessing fallback when advanced processing fails"""
        try:
            temp_dir = tempfile.mkdtemp()
            processed_file = os.path.join(temp_dir, "simple_processed.wav")
            
            # Basic processing - just convert to standard format
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-i", audio_file_path,
                "-ar", "16000",
                "-ac", "1",
                "-c:a", "pcm_s16le",
                "-f", "wav",
                processed_file
            ]
            
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0 and os.path.exists(processed_file):
                print(f"Simple audio preprocessing successful: {processed_file}")
                return processed_file, "Used simple preprocessing"
            else:
                return audio_file_path, "Simple preprocessing failed, using original"
                
        except Exception as e:
            print(f"Simple preprocessing error: {e}")
            return audio_file_path, "Simple preprocessing failed"
    
    def validate_audio_file(self, audio_file_path):
        """Validate audio file without complex preprocessing (Python 3.13 compatible)"""
        try:
            print(f"Validating audio file: {audio_file_path}")
            
            # Check file exists and has content
            if not os.path.exists(audio_file_path):
                return False, "Audio file not found"
            
            file_size = os.path.getsize(audio_file_path)
            if file_size < 1024:  # Less than 1KB
                return False, "Audio file too small - likely corrupted"
            elif file_size > 50 * 1024 * 1024:  # More than 50MB
                return False, "Audio file too large - please use smaller files"
            
            print(f"Audio file size: {file_size} bytes")
            
            # Check file extension
            file_extension = os.path.splitext(audio_file_path)[1].lower()
            supported_formats = ['.wav', '.mp3', '.webm', '.m4a', '.ogg', '.flac']
            
            if file_extension not in supported_formats:
                return False, f"Unsupported audio format: {file_extension}"
            
            # For WAV files, do basic header validation
            if file_extension == '.wav':
                try:
                    with wave.open(audio_file_path, 'rb') as wav_file:
                        frames = wav_file.getnframes()
                        sample_rate = wav_file.getframerate()
                        duration = frames / sample_rate if sample_rate > 0 else 0
                        
                        print(f"WAV file - Duration: {duration:.2f}s, Sample rate: {sample_rate}Hz")
                        
                        if duration < 0.5:
                            return False, "Audio too short for transcription (< 0.5s)"
                        elif duration > 300:
                            return False, "Audio too long - please use clips under 5 minutes"
                        
                except Exception as wav_error:
                    print(f"WAV validation warning: {wav_error}")
                    # Continue anyway - might still work with Deepgram
            
            print("Audio file validation passed")
            return True, None
            
        except Exception as e:
            print(f"Audio validation error: {e}")
            return False, f"Audio validation failed: {str(e)}"
    
    def validate_transcript(self, transcript, confidence=None):
        """Validate transcript quality and detect potential hallucinations"""
        if not transcript or not transcript.strip():
            return False, "Empty transcript"
        
        # Check for common hallucination patterns
        hallucination_patterns = [
            "thank you for watching",
            "subscribe to my channel",
            "like and subscribe",
            "please subscribe",
            "music playing",
            "background music",
            "applause",
            "laughter",
            "silence",
            "[music]",
            "[applause]",
            "[laughter]"
        ]
        
        transcript_lower = transcript.lower()
        for pattern in hallucination_patterns:
            if pattern in transcript_lower:
                return False, f"Detected potential hallucination: '{pattern}'"
        
        # Check transcript length vs expected speech
        words = transcript.split()
        if len(words) < 2:
            return False, "Transcript too short - likely noise"
        
        # Check for repetitive patterns (common in hallucinations)
        if len(set(words)) < len(words) * 0.3:  # Less than 30% unique words
            return False, "Transcript appears repetitive - possible hallucination"
        
        # Check confidence if available
        if confidence is not None and confidence < 0.5:
            return False, f"Low confidence score: {confidence}"
        
        return True, "Transcript appears valid"
    
    def transcribe_audio_file(self, audio_file_path):
        """Transcribe audio file using Deepgram REST API with enhanced error handling"""
        preprocessed_file = None
        try:
            # Check if API key is valid
            if not self.api_key or len(self.api_key) < 30:
                return "Invalid Deepgram API key. Please get a valid key from https://console.deepgram.com/"
            
            # Check if file exists
            if not os.path.exists(audio_file_path):
                return f"Audio file not found: {audio_file_path}"
            
            # Validate audio file
            is_valid, error = self.validate_audio_file(audio_file_path)
            if not is_valid:
                return f"Audio validation failed: {error}"
            
            # Detect accent for adaptive processing
            detected_language, detected_accent = self.detect_accent_and_language(audio_file_path)
            print(f"Detected language: {detected_language}, accent: {detected_accent}")
            
            # Try preprocessing, but use original file if it fails or causes issues
            try:
                file_to_transcribe, preprocessing_warning = self.preprocess_audio(audio_file_path, detected_accent)
                if preprocessing_warning:
                    print(f"Preprocessing warning: {preprocessing_warning}")
                    # If preprocessing failed, use original file
                    if "failed" in preprocessing_warning.lower() or "error" in preprocessing_warning.lower():
                        print("Using original file due to preprocessing failure")
                        file_to_transcribe = audio_file_path
            except Exception as e:
                print(f"Audio preprocessing failed: {e}")
                print("Falling back to original audio file")
                file_to_transcribe = audio_file_path
            
            print(f"Transcribing file: {file_to_transcribe}")
            
            # Deepgram REST API endpoint
            url = "https://api.deepgram.com/v1/listen"
            
            # Determine content type based on file extension
            file_extension = os.path.splitext(audio_file_path)[1].lower()
            content_type_map = {
                '.wav': 'audio/wav',
                '.mp3': 'audio/mpeg',
                '.webm': 'audio/webm',
                '.m4a': 'audio/mp4',
                '.ogg': 'audio/ogg',
                '.flac': 'audio/flac'
            }
            content_type = content_type_map.get(file_extension, 'audio/wav')
            
            # Headers for authentication
            headers = {
                "Authorization": f"Token {self.api_key}",
                "Content-Type": content_type
            }
            
            # Clean parameters for Nova-3 model (no deprecated parameters)
            params = {
                "model": "nova-3",
                "language": detected_language,
                "smart_format": "true",
                "punctuate": "true",
                "confidence": "true",
                "alternatives": "3",
                "filler_words": "true",
                "numerals": "true",
                "interim_results": "false",
                "encoding": "linear16",
                "sample_rate": "16000",
                "channels": "1"
            }
            
            # Add accent-specific endpointing (only non-deprecated parameter)
            if detected_accent == "indian":
                params["endpointing"] = "400"
                params["tier"] = "enhanced"
            elif detected_accent == "british":
                params["endpointing"] = "250"
            elif detected_accent == "australian":
                params["endpointing"] = "350"
            elif detected_accent == "south_african":
                params["endpointing"] = "450"
            else:
                params["endpointing"] = "300"
            
            print(f"Using clean API parameters: {list(params.keys())}")
            
            # Read audio file
            with open(file_to_transcribe, "rb") as audio_file:
                audio_data = audio_file.read()
            
            print(f"Audio file size: {len(audio_data)} bytes")
            
            # Make request to Deepgram API with retry logic
            print("Making request to Deepgram API...")
            max_retries = 5
            retry_delay = 2  # seconds
            response = None
            
            for attempt in range(max_retries):
                try:
                    print(f"Attempt {attempt + 1}/{max_retries}...")
                    response = requests.post(
                        url,
                        headers=headers,
                        params=params,
                        data=audio_data,
                        timeout=90
                    )
                    
                    # If successful, break the loop
                    if response.status_code == 200:
                        print("Request successful!")
                        break
                        
                    # For retryable errors (503, 429, 502, 504), wait and try again
                    if response.status_code in [503, 429, 502, 504]:
                        if attempt < max_retries - 1:
                            error_msg = "Unknown error"
                            try:
                                error_data = response.json()
                                error_msg = error_data.get('err_msg', 'Unknown error')
                            except:
                                error_msg = response.text[:100] if response.text else "No error message"
                            
                            print(f"Attempt {attempt + 1} failed with status {response.status_code}: {error_msg}")
                            print(f"Retrying in {retry_delay} seconds...")
                            import time
                            time.sleep(retry_delay)
                            retry_delay = min(retry_delay * 2, 30)  # Exponential backoff, max 30s
                        else:
                            print(f"All {max_retries} attempts failed with retryable errors")
                    else:
                        # Non-retryable error, break immediately
                        print(f"Non-retryable error {response.status_code}, stopping retries")
                        break
                        
                except requests.exceptions.Timeout:
                    if attempt < max_retries - 1:
                        print(f"Request timeout on attempt {attempt + 1}, retrying in {retry_delay} seconds...")
                        import time
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 30)
                    else:
                        return "Request timeout after multiple attempts. Audio processing took too long - try a shorter audio clip."
                except requests.exceptions.ConnectionError:
                    if attempt < max_retries - 1:
                        print(f"Connection error on attempt {attempt + 1}, retrying in {retry_delay} seconds...")
                        import time
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 30)
                    else:
                        return "Network connection error after multiple attempts. Please check your internet connection."
                except requests.exceptions.RequestException as e:
                    print(f"Request error on attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 30)
                    else:
                        return f"Network error during transcription after multiple attempts: {str(e)}"
            
            # Check if we have a response
            if response is None:
                return "Failed to get response from Deepgram API after multiple attempts"
            
            print(f"Deepgram API response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"Deepgram API response structure: {list(result.keys())}")
                
                # Extract transcript from Nova-3 response
                if "results" in result and "channels" in result["results"]:
                    channels = result["results"]["channels"]
                    if channels and "alternatives" in channels[0]:
                        alternatives = channels[0]["alternatives"]
                        
                        # Enhanced multi-alternative processing for better accent handling
                        if alternatives and len(alternatives) > 0:
                            print(f"Processing {len(alternatives)} alternatives for best accuracy")
                            
                            best_transcript = None
                            best_confidence = 0.0
                            best_alt = None
                            
                            # Evaluate all alternatives to find the best one
                            for i, alt in enumerate(alternatives):
                                if "transcript" in alt and alt["transcript"].strip():
                                    transcript = alt["transcript"]
                                    confidence = alt.get("confidence", 0.0)
                                    
                                    print(f"Alternative {i+1}: '{transcript[:30]}...' (confidence: {confidence:.3f})")
                                    
                                    # Validate transcript quality
                                    is_valid, validation_msg = self.validate_transcript(transcript, confidence)
                                    
                                    # Score alternatives based on confidence and validation
                                    score = confidence
                                    if is_valid:
                                        score += 0.2  # Bonus for passing validation
                                    
                                    # Prefer longer transcripts (more content)
                                    word_count = len(transcript.split())
                                    if word_count > 3:
                                        score += 0.1
                                    
                                    # Prefer transcripts with interview-related keywords
                                    interview_keywords = ['experience', 'skills', 'position', 'job', 'work', 'company', 'role', 'responsibility', 'qualification', 'background', 'education', 'training', 'project', 'team', 'leadership', 'management', 'communication', 'problem', 'solution', 'achievement', 'challenge', 'goal', 'strength', 'weakness', 'motivation', 'career', 'development']
                                    keyword_matches = sum(1 for keyword in interview_keywords if keyword.lower() in transcript.lower())
                                    if keyword_matches > 0:
                                        score += min(keyword_matches * 0.05, 0.2)  # Up to 0.2 bonus
                                    
                                    print(f"Alternative {i+1} score: {score:.3f}")
                                    
                                    if score > best_confidence:
                                        best_confidence = score
                                        best_transcript = transcript
                                        best_alt = alt
                            
                            if best_transcript:
                                actual_confidence = best_alt.get("confidence", 0.0)
                                print(f"Selected best transcript: '{best_transcript[:50]}...' (confidence: {actual_confidence:.3f}, score: {best_confidence:.3f})")
                                
                                # Final validation of selected transcript
                                is_valid, validation_msg = self.validate_transcript(best_transcript, actual_confidence)
                                
                                if is_valid:
                                    print(f"Valid transcript selected: {best_transcript[:100]}...")
                                    return best_transcript.strip()
                                else:
                                    print(f"Best transcript validation failed: {validation_msg}")
                                    # Return with warning if confidence is reasonable
                                    if actual_confidence > 0.2:
                                        return f"[Warning: {validation_msg}] {best_transcript.strip()}"
                                    else:
                                        return f"Low quality transcription detected: {validation_msg}"
                            else:
                                return "No valid speech detected in any alternative"
                        else:
                            return "No alternatives found in API response"
                
                    return "No transcript found in Deepgram response"
            else:
                error_text = response.text
                print(f"Deepgram API error: {response.status_code} - {error_text}")
                
                # Provide more specific error messages
                if response.status_code == 401:
                    return "Authentication failed. Please check your Deepgram API key at https://console.deepgram.com/"
                elif response.status_code == 400:
                    return f"Bad request to Deepgram API. Audio format issue. Error: {error_text[:200]}"
                elif response.status_code == 402:
                    return "Insufficient credits in Deepgram account. Please add credits."
                elif response.status_code == 429:
                    return "Rate limit exceeded. Please wait and try again."
                else:
                    return f"Deepgram API error {response.status_code}: {error_text[:200]}"
                
        except requests.exceptions.Timeout:
            print("Request timeout")
            return "Request timeout. Audio processing took too long - try a shorter audio clip."
        except requests.exceptions.ConnectionError:
            print("Connection error")
            return "Network connection error. Please check your internet connection."
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return f"Network error during transcription: {str(e)}"
        except FileNotFoundError:
            print(f"Audio file not found: {audio_file_path}")
            return "Audio file not found"
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return "Invalid response from Deepgram API"
        except Exception as e:
            print(f"Unexpected error during transcription: {e}")
            return f"Transcription error: {str(e)}"
        finally:
            # Clean up temporary preprocessed file if it was created
            if file_to_transcribe != audio_file_path and os.path.exists(file_to_transcribe):
                try:
                    temp_dir = os.path.dirname(file_to_transcribe)
                    shutil.rmtree(temp_dir)
                    print(f"Cleaned up temporary file: {file_to_transcribe}")
                except Exception as cleanup_error:
                    print(f"Warning: Could not clean up temporary file: {cleanup_error}")
   