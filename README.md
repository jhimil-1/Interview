# AI Voice Interview Agent - FastAPI + HTML/CSS Version

A modern web-based AI interview agent that conducts voice interviews with real-time analysis and comprehensive reporting.

## Features

- 🎯 **Smart Question Generation**: AI generates relevant interview questions based on job descriptions
- 🎤 **Voice Interaction**: 
  - Text-to-Speech (TTS) for question delivery using ElevenLabs
  - Speech-to-Text (STT) for response recording using Deepgram
- 📊 **Real-time Analysis**: Immediate feedback on candidate responses
- 📝 **Comprehensive Reports**: Detailed evaluation with scores and recommendations
- 🌐 **Modern Web Interface**: Clean HTML/CSS/JavaScript frontend
- ⚡ **FastAPI Backend**: High-performance API with automatic documentation

## Technology Stack

### Backend
- **FastAPI**: Modern Python web framework
- **Google Gemini Flash 1.5**: LLM for question generation and analysis
- **ElevenLabs**: Text-to-Speech conversion
- **Deepgram**: Speech-to-Text transcription

### Frontend
- **HTML5**: Semantic markup with Web Audio API support
- **CSS3**: Modern responsive design with animations
- **JavaScript**: Interactive functionality with async/await

## Setup Instructions

### 1. Environment Setup

Make sure you have Python 3.8+ installed, then:

```bash
# Navigate to project directory
cd c:\Users\nhz\Desktop\JD

# Activate virtual environment (if you have one)
# venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Variables

Ensure your `.env` file contains the required API keys:

```env
GEMINI_API_KEY=your_gemini_api_key_here
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
ELEVENLABS_VOICE_ID=your_preferred_voice_id
DEEPGRAM_API_KEY=your_deepgram_api_key_here
```

### 3. Start the Application

You have several options to start the server:

#### Option 1: Using the startup script (Recommended)
```bash
python start_server.py
```

#### Option 2: Direct FastAPI command
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### Option 3: Python directly
```bash
python main.py
```

### 4. Access the Application

Once the server is running:

1. Open your web browser
2. Navigate to: `http://localhost:8000`
3. You should see the AI Voice Interview Agent interface

## How to Use

### 1. Setup Interview
- Enter a detailed job description
- Select the number of questions (3-10)
- Click "Start Interview"

### 2. Conduct Interview
- **Ask Question**: Click to hear the AI-generated question via TTS
- **Record Response**: Click to start/stop recording your voice response
- **Analyze Response**: Get immediate AI feedback on the response
- **Next Question**: Move to the next question

### 3. Generate Report
- Complete all questions or end early
- Click "Generate Report" for comprehensive analysis
- Download the report as JSON

## API Endpoints

The FastAPI backend provides these main endpoints:

- `GET /` - Serve the main HTML interface
- `POST /api/setup-interview` - Initialize interview with job description
- `GET /api/interview-status` - Get current interview progress
- `POST /api/ask-question` - Generate TTS audio for questions
- `POST /api/upload-audio` - Upload audio for STT transcription
- `POST /api/analyze-response` - Analyze candidate responses
- `POST /api/generate-report` - Create comprehensive interview report
- `POST /api/reset-interview` - Reset for new interview

## Browser Requirements

- **Modern browser** with Web Audio API support (Chrome, Firefox, Safari, Edge)
- **Microphone access** for voice recording
- **Audio playback** capability for TTS questions

## Troubleshooting

### Audio Issues
- **Can't hear questions**: Check browser audio settings and volume
- **Recording not working**: Ensure microphone permissions are granted
- **Audio format errors**: Try using Chrome for best compatibility

### API Issues
- **TTS not working**: Verify ElevenLabs API key and credits
- **STT not working**: Check Deepgram API key and internet connection
- **Analysis failing**: Ensure Gemini API key is valid

### Server Issues
- **Port already in use**: Change port in `start_server.py` or kill existing process
- **Static files not found**: Ensure you're running from the project root directory

## Development

### Project Structure
```
JD/
├── main.py                 # FastAPI application
├── start_server.py         # Startup script
├── requirements.txt        # Python dependencies
├── config.py              # Configuration settings
├── .env                   # Environment variables
├── models/                # AI model handlers
│   ├── llm_handler.py     # Gemini LLM integration
│   ├── tts_handler.py     # ElevenLabs TTS
│   └── stt_handler.py     # Deepgram STT
├── utils/                 # Utility modules
│   └── interview_manager.py # Interview logic
└── static/                # Frontend files
    ├── index.html         # Main HTML page
    ├── styles.css         # CSS styling
    ├── script.js          # JavaScript functionality
    └── audio/             # Generated audio files
```

### Adding Features
- Modify `main.py` for new API endpoints
- Update `static/script.js` for frontend functionality
- Edit `static/styles.css` for styling changes

## Migration from Streamlit

This version replaces the original Streamlit interface with:
- ✅ FastAPI backend for better performance and API documentation
- ✅ Modern HTML/CSS/JS frontend for better user experience
- ✅ Proper audio handling with Web Audio API
- ✅ RESTful API design for potential mobile app integration
- ✅ Better separation of concerns between frontend and backend

## Support

For issues or questions:
1. Check the console logs in your browser (F12)
2. Review the server logs in the terminal
3. Verify all API keys are correctly configured
4. Ensure all dependencies are installed correctly
