// Global state
let currentStage = 'setup';
let interviewData = {
    questions: [],
    responses: [],
    analyses: [],
    currentQuestion: 0
};

// Audio recording state
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

// DOM elements
const setupStage = document.getElementById('setup-stage');
const interviewStage = document.getElementById('interview-stage');
const reportStage = document.getElementById('report-stage');
const loadingOverlay = document.getElementById('loading-overlay');
const loadingText = document.getElementById('loading-text');

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    updateQuestionCount();
});

function initializeEventListeners() {
    // Setup stage
    document.getElementById('num-questions').addEventListener('input', updateQuestionCount);
    document.getElementById('start-interview').addEventListener('click', startInterview);
    
    // Interview stage
    document.getElementById('ask-question').addEventListener('click', askQuestion);
    document.getElementById('record-response').addEventListener('click', recordResponse);
    document.getElementById('analyze-response').addEventListener('click', analyzeResponse);
    document.getElementById('next-question').addEventListener('click', nextQuestion);
    document.getElementById('end-interview').addEventListener('click', endInterview);
    
    // Report stage
    document.getElementById('download-report').addEventListener('click', downloadReport);
    document.getElementById('new-interview').addEventListener('click', newInterview);
}

function updateQuestionCount() {
    const slider = document.getElementById('num-questions');
    const countSpan = document.getElementById('question-count');
    countSpan.textContent = slider.value;
}

function showLoading(message = 'Processing...') {
    loadingText.textContent = message;
    loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    loadingOverlay.style.display = 'none';
}

function switchStage(stage) {
    // Hide all stages
    document.querySelectorAll('.stage').forEach(s => s.classList.remove('active'));
    
    // Show target stage
    document.getElementById(`${stage}-stage`).classList.add('active');
    currentStage = stage;
}

async function apiCall(endpoint, method = 'GET', data = null) {
    try {
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            }
        };
        
        if (data) {
            options.body = JSON.stringify(data);
        }
        
        const response = await fetch(`/api/${endpoint}`, options);
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.detail || 'API call failed');
        }
        
        return result;
    } catch (error) {
        console.error('API Error:', error);
        alert(`Error: ${error.message}`);
        throw error;
    }
}

async function startInterview() {
    const jobDescription = document.getElementById('job-description').value.trim();
    const numQuestions = parseInt(document.getElementById('num-questions').value);
    
    if (!jobDescription) {
        alert('Please enter a job description');
        return;
    }
    
    showLoading('Generating interview questions...');
    
    try {
        const result = await apiCall('setup-interview', 'POST', {
            job_description: jobDescription,
            num_questions: numQuestions
        });
        
        interviewData.questions = result.questions;
        interviewData.currentQuestion = 0;
        interviewData.responses = [];
        interviewData.analyses = [];
        
        switchStage('interview');
        updateInterviewUI();
        
    } catch (error) {
        console.error('Failed to start interview:', error);
    } finally {
        hideLoading();
    }
}

function updateInterviewUI() {
    const currentQ = interviewData.currentQuestion;
    const totalQ = interviewData.questions.length;
    
    // Update progress
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const progress = (currentQ / totalQ) * 100;
    
    progressFill.style.width = `${progress}%`;
    progressText.textContent = `Question ${currentQ + 1} of ${totalQ}`;
    
    // Update question display
    if (currentQ < totalQ) {
        const question = interviewData.questions[currentQ];
        document.getElementById('question-title').textContent = `Question ${currentQ + 1}`;
        document.getElementById('current-question').textContent = question.question;
        document.getElementById('question-meta').textContent = 
            `Skill Area: ${question.skill_area} | Difficulty: ${question.difficulty}`;
    }
    
    // Clear previous response
    document.getElementById('response-transcript').value = '';
    document.getElementById('analysis-results').style.display = 'none';
}

async function askQuestion() {
    const currentQ = interviewData.currentQuestion;
    
    if (currentQ >= interviewData.questions.length) {
        alert('No more questions available');
        return;
    }
    
    showLoading('Generating audio...');
    
    try {
        const result = await apiCall(`ask-question?question_id=${currentQ}`, 'POST');
        
        if (result.success && result.audio_url) {
            // Create and play audio element
            const audio = new Audio(result.audio_url);
            
            audio.onloadstart = () => {
                showLoading('Loading audio...');
            };
            
            audio.oncanplay = () => {
                hideLoading();
                console.log('Audio ready to play');
            };
            
            audio.onended = () => {
                console.log('Audio playback finished');
            };
            
            audio.onerror = (e) => {
                console.error('Audio playback error:', e);
                alert('Error playing audio. Please try again.');
                hideLoading();
            };
            
            // Play the audio
            try {
                await audio.play();
                console.log('Playing question audio:', result.question);
            } catch (playError) {
                console.error('Play error:', playError);
                alert('Could not play audio. Please check your browser settings and try again.');
            }
        } else {
            alert('Failed to generate audio for the question.');
        }
        
    } catch (error) {
        console.error('Failed to ask question:', error);
    } finally {
        hideLoading();
    }
}

async function recordResponse() {
    const recordBtn = document.getElementById('record-response');
    
    if (!isRecording) {
        // Start recording
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                } 
            });
            
            audioChunks = [];
            mediaRecorder = new MediaRecorder(stream, {
                mimeType: 'audio/webm;codecs=opus'
            });
            
            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };
            
            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                await uploadAudioForTranscription(audioBlob);
                
                // Stop all tracks to release microphone
                stream.getTracks().forEach(track => track.stop());
            };
            
            mediaRecorder.start();
            isRecording = true;
            
            // Update button appearance
            recordBtn.innerHTML = '<i class="fas fa-stop"></i> Stop Recording';
            recordBtn.classList.remove('btn-success');
            recordBtn.classList.add('btn-danger');
            
            console.log('Recording started...');
            
        } catch (error) {
            console.error('Error accessing microphone:', error);
            alert('Could not access microphone. Please check permissions and try again.');
        }
    } else {
        // Stop recording
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            showLoading('Processing audio...');
            mediaRecorder.stop();
            isRecording = false;
            
            // Reset button appearance
            recordBtn.innerHTML = '<i class="fas fa-microphone"></i> Record Response';
            recordBtn.classList.remove('btn-danger');
            recordBtn.classList.add('btn-success');
        }
    }
}

async function uploadAudioForTranscription(audioBlob) {
    try {
        const formData = new FormData();
        formData.append('audio_file', audioBlob, 'response.webm');
        
        const response = await fetch('/api/upload-audio', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            const transcript = result.transcript;
            document.getElementById('response-transcript').value = transcript;
            
            // Submit response
            await apiCall('submit-response', 'POST', {
                question_id: interviewData.currentQuestion,
                response_text: transcript
            });
            
            interviewData.responses.push({
                question_id: interviewData.currentQuestion,
                response: transcript,
                timestamp: new Date().toISOString()
            });
            
            console.log('Audio transcribed successfully:', transcript);
        } else {
            // Handle transcription failure
            const errorTranscript = result.transcript || '[Transcription failed]';
            document.getElementById('response-transcript').value = errorTranscript;
            
            console.error('Transcription failed:', result.error || 'Unknown error');
            
            // Show error message to user
            alert(`Transcription failed: ${result.error || 'Please check your Deepgram API key and try again.'}`);
            
            // Still allow manual editing of the transcript
            document.getElementById('response-transcript').readOnly = false;
            document.getElementById('response-transcript').placeholder = 'Transcription failed. You can type your response here manually.';
        }
        
    } catch (error) {
        console.error('Failed to upload audio:', error);
        alert('Failed to process audio recording. Please try again.');
    } finally {
        hideLoading();
    }
}

async function analyzeResponse() {
    const currentQ = interviewData.currentQuestion;
    const responseText = document.getElementById('response-transcript').value.trim();
    
    if (!responseText) {
        alert('No response to analyze');
        return;
    }
    
    if (currentQ >= interviewData.questions.length) {
        alert('Invalid question index');
        return;
    }
    
    showLoading('Analyzing response...');
    
    try {
        const question = interviewData.questions[currentQ];
        const result = await apiCall('analyze-response', 'POST', {
            question: question.question,
            response: responseText
        });
        
        if (result.success) {
            const analysis = result.analysis;
            
            // Display analysis results
            document.getElementById('overall-score').textContent = `${analysis.overall_score}/10`;
            document.getElementById('analysis-feedback').textContent = analysis.feedback;
            document.getElementById('analysis-results').style.display = 'block';
            
            interviewData.analyses.push(analysis);
        }
        
    } catch (error) {
        console.error('Failed to analyze response:', error);
    } finally {
        hideLoading();
    }
}

function nextQuestion() {
    interviewData.currentQuestion++;
    
    if (interviewData.currentQuestion >= interviewData.questions.length) {
        // Interview completed
        document.getElementById('question-title').textContent = 'Interview Completed!';
        document.getElementById('current-question').textContent = 'All questions have been answered.';
        document.getElementById('question-meta').textContent = '';
        
        // Show generate report button
        const questionCard = document.querySelector('.question-card');
        questionCard.innerHTML += `
            <button id="generate-report-btn" class="btn btn-primary" onclick="generateReport()">
                <i class="fas fa-file-alt"></i> Generate Report
            </button>
        `;
    } else {
        updateInterviewUI();
    }
}

function endInterview() {
    if (confirm('Are you sure you want to end the interview?')) {
        generateReport();
    }
}

async function generateReport() {
    showLoading('Generating comprehensive report...');
    
    try {
        const result = await apiCall('generate-report', 'POST');
        
        if (result.success) {
            const report = result.report;
            
            // Update report UI
            document.getElementById('overall-rating').textContent = `${report.overall_rating}/10`;
            document.getElementById('technical-skills').textContent = `${report.technical_competency}/10`;
            document.getElementById('communication-skills').textContent = `${report.communication_skills}/10`;
            document.getElementById('recommendation').textContent = report.recommendation.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
            
            document.getElementById('report-summary').textContent = report.summary;
            document.getElementById('detailed-feedback').textContent = report.detailed_feedback;
            
            // Populate strengths
            const strengthsList = document.getElementById('strengths-list');
            strengthsList.innerHTML = '';
            report.strengths.forEach(strength => {
                const li = document.createElement('li');
                li.textContent = strength;
                strengthsList.appendChild(li);
            });
            
            // Populate improvements
            const improvementsList = document.getElementById('improvements-list');
            improvementsList.innerHTML = '';
            report.areas_for_improvement.forEach(area => {
                const li = document.createElement('li');
                li.textContent = area;
                improvementsList.appendChild(li);
            });
            
            // Create performance table
            createPerformanceTable();
            
            switchStage('report');
        }
        
    } catch (error) {
        console.error('Failed to generate report:', error);
    } finally {
        hideLoading();
    }
}

function createPerformanceTable() {
    const tableContainer = document.getElementById('performance-table');
    
    if (interviewData.analyses.length === 0) {
        tableContainer.innerHTML = '<p>No analysis data available.</p>';
        return;
    }
    
    let tableHTML = `
        <table class="performance-table">
            <thead>
                <tr>
                    <th>Question</th>
                    <th>Relevance</th>
                    <th>Clarity</th>
                    <th>Depth</th>
                    <th>Overall</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    interviewData.analyses.forEach((analysis, index) => {
        tableHTML += `
            <tr>
                <td>${index + 1}</td>
                <td>${analysis.relevance_score || '-'}</td>
                <td>${analysis.clarity_score || '-'}</td>
                <td>${analysis.depth_score || '-'}</td>
                <td>${analysis.overall_score}</td>
            </tr>
        `;
    });
    
    tableHTML += `
            </tbody>
        </table>
    `;
    
    tableContainer.innerHTML = tableHTML;
}

async function downloadReport() {
    try {
        const result = await apiCall('generate-report', 'POST');
        
        if (result.success) {
            const report = result.report;
            const reportJson = JSON.stringify(report, null, 2);
            const blob = new Blob([reportJson], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            
            const a = document.createElement('a');
            a.href = url;
            a.download = `interview_report_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }
        
    } catch (error) {
        console.error('Failed to download report:', error);
    }
}

async function newInterview() {
    if (confirm('Are you sure you want to start a new interview? This will reset all current data.')) {
        showLoading('Resetting interview...');
        
        try {
            await apiCall('reset-interview', 'POST');
            
            // Reset local state
            interviewData = {
                questions: [],
                responses: [],
                analyses: [],
                currentQuestion: 0
            };
            
            // Clear form
            document.getElementById('job-description').value = '';
            document.getElementById('num-questions').value = 5;
            updateQuestionCount();
            
            switchStage('setup');
            
        } catch (error) {
            console.error('Failed to reset interview:', error);
        } finally {
            hideLoading();
        }
    }
}
