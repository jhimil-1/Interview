import google.generativeai as genai
from config import Config
import json
import logging
import re

class LLMHandler:
    def __init__(self):
        genai.configure(api_key=Config.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(Config.GEMINI_MODEL)
        
    def _extract_text(self, response):
        # Safely extract the text from Gemini response
        try:
            return response.candidates[0].content.parts[0].text
        except Exception as e:
            logging.error(f"Failed to extract text from Gemini response: {e}\nRaw response: {response}")
            return ""

    def _strip_markdown_codeblock(self, text):
        # Remove triple backtick code block and optional 'json' label
        pattern = r"^```(?:json)?\s*([\s\S]*?)\s*```$"
        match = re.match(pattern, text.strip(), re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return text.strip()

    def generate_interview_questions(self, job_description, num_questions=5):
        """Generate interview questions based on job description"""
        prompt = f"""
        You are an expert interviewer. Based on the following job description, generate {num_questions} 
        relevant theoretical interview questions that will help assess the candidate's suitability for the role.
        Ensure the questions evaluate conceptual understanding, problem-solving approach,
        and domain knowledge—not coding or writing-based responses, as the AI agent will judge the candidate's verbal answers.

        Job Description:
        {job_description}
        
        Return the questions in JSON format:
        {{
            "questions": [
                {{"id": 1, "question": "...", "skill_area": "...", "difficulty": "easy/medium/hard"}},
                ...
            ]
        }}
        """
        
        response = self.model.generate_content(prompt)
        text = self._extract_text(response)
        text = self._strip_markdown_codeblock(text)
        try:
            return json.loads(text)
        except Exception as e:
            logging.error(f"JSON decode error: {e}\nRaw output: {text}")
            raise ValueError(f"Failed to parse Gemini output as JSON. Raw output: {text}")
    
    def analyze_answer(self, question, answer, job_description):
        """Analyze candidate's answer"""
        prompt = f"""
        As an expert interviewer, analyze the following answer provided by a candidate.
        
        Job Description: {job_description}
        Question: {question}
        Candidate's Answer: {answer}
        
        Provide a detailed analysis in JSON format:
        {{
            "relevance_score": 0-10,
            "clarity_score": 0-10,
            "depth_score": 0-10,
            "overall_score": 0-10,
            "strengths": ["..."],
            "weaknesses": ["..."],
            "feedback": "...",
            "follow_up_question": "..."
        }}
        """
        
        response = self.model.generate_content(prompt)
        text = self._extract_text(response)
        text = self._strip_markdown_codeblock(text)
        try:
            return json.loads(text)
        except Exception as e:
            logging.error(f"JSON decode error: {e}\nRaw output: {text}")
            raise ValueError(f"Failed to parse Gemini output as JSON. Raw output: {text}")
    
    def generate_final_report(self, interview_data):
        """Generate comprehensive interview report"""
        prompt = f"""
        Based on the interview data below, generate a comprehensive evaluation report and recommendations for the candidate.
        
        Interview Data:
        {json.dumps(interview_data, indent=2)}
        
        Provide a detailed report in JSON format:
        {{
            "overall_rating": 0-10,
            "recommendation": "strong_yes/yes/maybe/no",
            "summary": "...",
            "strengths": ["..."],
            "areas_for_improvement": ["..."],
            "technical_competency": 0-10,
            "communication_skills": 0-10,
            "cultural_fit": 0-10,
            "detailed_feedback": "..."
        }}
        """
        
        response = self.model.generate_content(prompt)
        text = self._extract_text(response)
        text = self._strip_markdown_codeblock(text)
        try:
            return json.loads(text)
        except Exception as e:
            logging.error(f"JSON decode error: {e}\nRaw output: {text}")
            raise ValueError(f"Failed to parse Gemini output as JSON. Raw output: {text}")