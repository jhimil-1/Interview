from models.llm_handler import LLMHandler
from models.tts_handler import TTSHandler
from models.stt_handler import STTHandler
import asyncio
import time

class InterviewManager:
    def __init__(self):
        self.llm = LLMHandler()
        self.tts = TTSHandler()
        self.stt = STTHandler()
        self.interview_data = {
            "job_description": "",
            "questions": [],
            "responses": [],
            "analyses": []
        }
        
    def setup_interview(self, job_description):
        """Setup interview with job description"""
        self.interview_data["job_description"] = job_description
        questions_data = self.llm.generate_interview_questions(job_description)
        self.interview_data["questions"] = questions_data["questions"]
        return self.interview_data["questions"]
    
    def ask_question(self, question_text):
        """Ask question using TTS"""
        audio_data = self.tts.text_to_speech(question_text)
        self.tts.play_audio(audio_data)
        
    async def get_candidate_response(self, timeout=30):
        """Get candidate's response using STT"""
        await self.stt.start_recording()
        
        # Wait for response or timeout
        start_time = time.time()
        while time.time() - start_time < timeout:
            await asyncio.sleep(0.1)
            
        transcript = self.stt.stop_recording()
        return transcript
    
    def analyze_response(self, question, answer):
        """Analyze candidate's response"""
        analysis = self.llm.analyze_answer(
            question, 
            answer, 
            self.interview_data["job_description"]
        )
        return analysis
    
    def conduct_interview(self):
        """Conduct full interview"""
        for i, question_data in enumerate(self.interview_data["questions"]):
            question_text = question_data["question"]
            
            # Ask question
            self.ask_question(f"Question {i+1}: {question_text}")
            
            # Get response
            response = asyncio.run(self.get_candidate_response())
            self.interview_data["responses"].append({
                "question_id": question_data["id"],
                "response": response
            })
            
            # Analyze response
            analysis = self.analyze_response(question_text, response)
            self.interview_data["analyses"].append(analysis)
            
            # Provide feedback
            feedback_text = f"Thank you for your answer. {analysis['feedback']}"
            self.ask_question(feedback_text)
            
            # Ask follow-up if needed
            if analysis.get("follow_up_question"):
                self.ask_question(analysis["follow_up_question"])
                follow_up_response = asyncio.run(self.get_candidate_response())
                # Store follow-up response
                
    def generate_report(self):
        """Generate final interview report"""
        return self.llm.generate_final_report(self.interview_data)