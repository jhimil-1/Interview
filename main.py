from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json
import asyncio
import os
from datetime import datetime

from utils.interview_manager import InterviewManager
from models.tts_handler import TTSHandler
from models.stt_handler import STTHandler

app = FastAPI(title="AI Voice Interview Agent", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global instances
interview_manager = InterviewManager()
tts_handler = TTSHandler()
stt_handler = STTHandler()

# Create audio directory if it doesn't exist
audio_dir = "static/audio"
if not os.path.exists(audio_dir):
    os.makedirs(audio_dir)

# Pydantic models
class InterviewSetup(BaseModel):
    job_description: str
    num_questions: int = 5

class QuestionResponse(BaseModel):
    question_id: int
    response_text: str

class AnalysisRequest(BaseModel):
    question: str
    response: str

# Routes
@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main HTML page"""
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="HTML file not found")

@app.post("/api/setup-interview")
async def setup_interview(setup: InterviewSetup):
    """Setup a new interview with job description and generate questions"""
    try:
        global interview_manager
        interview_manager = InterviewManager()
        
        questions = interview_manager.setup_interview(setup.job_description)
        
        return {
            "success": True,
            "questions": questions,
            "total_questions": len(questions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/interview-status")
async def get_interview_status():
    """Get current interview status and progress"""
    try:
        interview_data = interview_manager.interview_data
        return {
            "questions": interview_data.get("questions", []),
            "responses": interview_data.get("responses", []),
            "analyses": interview_data.get("analyses", []),
            "current_question": len(interview_data.get("responses", [])),
            "total_questions": len(interview_data.get("questions", []))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ask-question")
async def ask_question(question_id: int):
    """Generate TTS audio for a question"""
    try:
        questions = interview_manager.interview_data.get("questions", [])
        if question_id >= len(questions):
            raise HTTPException(status_code=404, detail="Question not found")
        
        question = questions[question_id]["question"]
        
        # Generate TTS audio
        audio_data = tts_handler.text_to_speech(question)
        
        # Save audio file
        audio_filename = f"question_{question_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        audio_path = os.path.join(audio_dir, audio_filename)
        
        with open(audio_path, "wb") as f:
            f.write(audio_data)
        
        return {
            "success": True,
            "audio_url": f"/static/audio/{audio_filename}",
            "question": question
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload-audio")
async def upload_audio(audio_file: UploadFile = File(...)):
    """Upload audio file and convert to text using STT"""
    try:
        # Validate file type
        if not audio_file.content_type.startswith('audio/'):
            raise HTTPException(status_code=400, detail="File must be an audio file")
        
        # Read the uploaded content
        content = await audio_file.read()
        
        # Determine original file extension
        original_filename = audio_file.filename or "audio.wav"
        original_ext = os.path.splitext(original_filename)[1].lower()
        
        # Save as temporary file first with original extension
        temp_filename = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}{original_ext}"
        temp_path = os.path.join(audio_dir, temp_filename)
        
        with open(temp_path, "wb") as f:
            f.write(content)
        
        # Convert to proper WAV format using FFmpeg
        audio_filename = f"response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        audio_path = os.path.join(audio_dir, audio_filename)
        
        # Use FFmpeg to ensure proper WAV format (PCM 16-bit, mono, 16kHz)
        import subprocess
        ffmpeg_cmd = [
            "ffmpeg", "-y",  # Overwrite output
            "-i", temp_path,  # Input file
            "-ar", "16000",  # Sample rate 16kHz
            "-ac", "1",      # Mono channel
            "-c:a", "pcm_s16le",  # PCM 16-bit little-endian
            "-f", "wav",     # WAV format
            audio_path
        ]
        
        try:
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and os.path.exists(audio_path):
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                print(f"Audio converted to proper WAV format: {audio_path}")
            else:
                # If FFmpeg fails, try to use the original file
                print(f"FFmpeg conversion failed: {result.stderr}")
                if os.path.exists(temp_path):
                    os.rename(temp_path, audio_path)
                print(f"Using original file format: {audio_path}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"FFmpeg not available: {e}")
            # Use original file if FFmpeg is not available
            if os.path.exists(temp_path):
                os.rename(temp_path, audio_path)
            print(f"Using original file without conversion: {audio_path}")
            
        
        # Use STT handler to transcribe the audio file
        try:
            print(f"Starting transcription for file: {audio_path}")
            transcript = stt_handler.transcribe_audio_file(audio_path)
            print(f"Transcription result: {transcript[:100] if transcript else 'None'}...")
            
            # Check for various error conditions
            error_indicators = [
                "Transcription failed", "Network error", "Authentication failed", 
                "Invalid Deepgram API key", "Audio file not found", "Bad request",
                "Insufficient credits", "Request timeout", "Connection error",
                "No transcript found", "Invalid response"
            ]
            
            is_error = any(indicator in transcript for indicator in error_indicators) if transcript else True
            
            if transcript and not is_error and transcript.strip():
                print(f"Successful transcription: {transcript}")
                return {
                    "success": True,
                    "transcript": transcript,
                    "audio_path": audio_path
                }
            else:
                # If transcription failed, return error but keep the uploaded file
                error_msg = transcript or "Unknown transcription error"
                print(f"Transcription failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "transcript": f"[{error_msg}]",
                    "audio_path": audio_path
                }
        except Exception as transcription_error:
            error_msg = f"STT Exception: {str(transcription_error)}"
            print(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "transcript": "[Transcription system error - please check server logs]",
                "audio_path": audio_path
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/submit-response")
async def submit_response(response: QuestionResponse):
    """Submit a response for a question"""
    try:
        # Add response to interview data
        interview_manager.interview_data["responses"].append({
            "question_id": response.question_id,
            "response": response.response_text,
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "success": True,
            "message": "Response submitted successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze-response")
async def analyze_response(analysis_request: AnalysisRequest):
    """Analyze a candidate's response"""
    try:
        analysis = interview_manager.analyze_response(
            analysis_request.question,
            analysis_request.response
        )
        
        # Store analysis
        interview_manager.interview_data["analyses"].append(analysis)
        
        return {
            "success": True,
            "analysis": analysis
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-report")
async def generate_report():
    """Generate comprehensive interview report"""
    try:
        report = interview_manager.generate_report()
        return {
            "success": True,
            "report": report
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reset-interview")
async def reset_interview():
    """Reset interview to start fresh"""
    try:
        global interview_manager
        interview_manager = InterviewManager()
        return {
            "success": True,
            "message": "Interview reset successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
