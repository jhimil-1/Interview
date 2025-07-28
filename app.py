import streamlit as st
import asyncio
from utils.interview_manager import InterviewManager
import json
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="AI Voice Interview Agent",
    page_icon="🎤",
    layout="wide"
)

# Initialize session state
if 'interview_manager' not in st.session_state:
    st.session_state.interview_manager = InterviewManager()
if 'interview_stage' not in st.session_state:
    st.session_state.interview_stage = 'setup'
if 'current_question' not in st.session_state:
    st.session_state.current_question = 0

# App Header
st.title("🎤 AI Voice Interview Agent")
st.markdown("An intelligent interviewer that conducts voice-based interviews and provides real-time analysis")

# Sidebar
with st.sidebar:
    st.header("Interview Controls")
    
    if st.session_state.interview_stage == 'setup':
        st.subheader("Setup Interview")
        job_description = st.text_area(
            "Job Description",
            height=200,
            placeholder="Enter the job description here..."
        )
        
        num_questions = st.slider("Number of Questions", 3, 10, 5)
        
        if st.button("Start Interview", type="primary"):
            if job_description:
                with st.spinner("Generating interview questions..."):
                    questions = st.session_state.interview_manager.setup_interview(job_description)
                    st.session_state.interview_stage = 'interview'
                    st.rerun()
            else:
                st.error("Please enter a job description")
    
    elif st.session_state.interview_stage == 'interview':
        st.subheader("Interview Progress")
        progress = st.session_state.current_question / len(st.session_state.interview_manager.interview_data["questions"])
        st.progress(progress)
        st.write(f"Question {st.session_state.current_question + 1} of {len(st.session_state.interview_manager.interview_data['questions'])}")
        
        if st.button("End Interview", type="secondary"):
            st.session_state.interview_stage = 'report'
            st.rerun()

# Main Content Area
if st.session_state.interview_stage == 'setup':
    # Welcome Screen
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("Welcome to AI Interview Agent")
        st.markdown("""
        ### Features:
        - 🎯 Generates relevant interview questions based on job description
        - 🎤 Voice-based interaction using advanced TTS and STT
        - 📊 Real-time answer analysis and feedback
        - 📝 Comprehensive interview report generation
        - 🤖 Powered by Gemini Flash 1.5, ElevenLabs, and Deepgram
        """)
        
    with col2:
        st.header("How it Works")
        st.markdown("""
        1. **Enter Job Description**: Provide details about the position
        2. **AI Generates Questions**: Relevant questions are created automatically
        3. **Voice Interview**: Candidate answers questions verbally
        4. **Real-time Analysis**: Each answer is analyzed immediately
        5. **Final Report**: Get a comprehensive evaluation report
        """)

elif st.session_state.interview_stage == 'interview':
    # Interview Screen
    questions = st.session_state.interview_manager.interview_data["questions"]
    current_q = st.session_state.current_question
    
    if current_q < len(questions):
        st.header(f"Question {current_q + 1}")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            question_data = questions[current_q]
            st.subheader(question_data["question"])
            st.caption(f"Skill Area: {question_data['skill_area']} | Difficulty: {question_data['difficulty']}")
            
            # Interview controls
            col_a, col_b, col_c = st.columns(3)
            
            with col_a:
                if st.button("🎤 Ask Question", key=f"ask_{current_q}"):
                    st.session_state.interview_manager.ask_question(question_data["question"])
                    
            with col_b:
                if st.button("🎙️ Record Answer", key=f"record_{current_q}"):
                    with st.spinner("Recording... Speak now!"):
                        response = asyncio.run(
                            st.session_state.interview_manager.get_candidate_response()
                        )
                        st.session_state.interview_manager.interview_data["responses"].append({
                            "question_id": question_data["id"],
                            "response": response
                        })
                        st.success("Response recorded!")
                        
            with col_c:
                if st.button("➡️ Next Question", key=f"next_{current_q}"):
                    st.session_state.current_question += 1
                    st.rerun()
                    
        with col2:
            st.subheader("Latest Response")
            if st.session_state.interview_manager.interview_data["responses"]:
                latest_response = st.session_state.interview_manager.interview_data["responses"][-1]
                st.text_area("Transcript", latest_response["response"], height=150)
                
                # Analyze button
                if st.button("🔍 Analyze Response"):
                    with st.spinner("Analyzing..."):
                        analysis = st.session_state.interview_manager.analyze_response(
                            question_data["question"],
                            latest_response["response"]
                        )
                        st.session_state.interview_manager.interview_data["analyses"].append(analysis)
                        
                        # Display analysis
                        st.metric("Overall Score", f"{analysis['overall_score']}/10")
                        st.write("**Feedback:**", analysis['feedback'])
                        
    else:
        st.success("Interview Completed!")
        if st.button("Generate Report", type="primary"):
            st.session_state.interview_stage = 'report'
            st.rerun()

elif st.session_state.interview_stage == 'report':
    # Report Screen
    st.header("Interview Report")
    
    with st.spinner("Generating comprehensive report..."):
        report = st.session_state.interview_manager.generate_report()
    
    # Display report metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Overall Rating", f"{report['overall_rating']}/10")
    with col2:
        st.metric("Technical Skills", f"{report['technical_competency']}/10")
    with col3:
        st.metric("Communication", f"{report['communication_skills']}/10")
    with col4:
        st.metric("Recommendation", report['recommendation'].replace('_', ' ').title())
    
    # Detailed sections
    st.subheader("Summary")
    st.write(report['summary'])
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Strengths")
        for strength in report['strengths']:
            st.write(f"✅ {strength}")
            
    with col2:
        st.subheader("Areas for Improvement")
        for area in report['areas_for_improvement']:
            st.write(f"📈 {area}")
    
    st.subheader("Detailed Feedback")
    st.write(report['detailed_feedback'])
    
    # Question-wise Analysis
    st.subheader("Question-wise Performance")
    
    analyses_df = []
    for i, analysis in enumerate(st.session_state.interview_manager.interview_data["analyses"]):
        analyses_df.append({
            "Question": i + 1,
            "Relevance": analysis['relevance_score'],
            "Clarity": analysis['clarity_score'],
            "Depth": analysis['depth_score'],
            "Overall": analysis['overall_score']
        })
    
    df = pd.DataFrame(analyses_df)
    st.dataframe(df, use_container_width=True)
    
    # Export options
    col1, col2 = st.columns(2)
    
    with col1:
        report_json = json.dumps(report, indent=2)
        st.download_button(
            "📥 Download Report (JSON)",
            report_json,
            f"interview_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "application/json"
        )
        
    with col2:
        if st.button("🔄 New Interview"):
            st.session_state.interview_stage = 'setup'
            st.session_state.current_question = 0
            st.session_state.interview_manager = InterviewManager()
            st.rerun()

# Footer
st.markdown("---")
st.caption("AI Voice Interview Agent - Powered by Gemini Flash 1.5, ElevenLabs TTS, and Deepgram STT")