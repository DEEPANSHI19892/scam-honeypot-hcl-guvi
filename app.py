
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional, Dict
import google.generativeai as genai
import os
import re
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.5-flash')

app = FastAPI(title="Scam Honeypot API")

# Store sessions in memory
sessions = {}

# ============= DATA MODELS =============

class Message(BaseModel):
    sender: str
    text: str
    timestamp: str

class Metadata(BaseModel):
    channel: Optional[str] = "SMS"
    language: Optional[str] = "English"
    locale: Optional[str] = "IN"

class HoneypotRequest(BaseModel):
    sessionId: str
    message: Message
    conversationHistory: List[Message] = []
    metadata: Optional[Metadata] = None

class HoneypotResponse(BaseModel):
    status: str
    reply: str

# ============= HELPER FUNCTIONS =============

def detect_scam(message_text: str, history: List[Message]) -> bool:
    """Detect if message is a scam using Gemini"""
    
    context = "\n".join([f"{msg.sender}: {msg.text}" for msg in history[-5:]])
    
    prompt = f"""You are a scam detection system. Analyze this message carefully.

Previous context:
{context}

New message: "{message_text}"

Common scam indicators:
- Urgency (account blocked, verify now, act immediately)
- Requests for money/UPI/bank details
- Threats of account suspension
- Too-good-to-be-true offers
- Impersonation of banks/government
- Phishing links

Respond with ONLY one word: "SCAM" or "SAFE"
"""
    
    try:
        response = model.generate_content(prompt)
        result = response.text.strip().upper()
        return "SCAM" in result
    except Exception as e:
        print(f"Error in scam detection: {e}")
        return False

def generate_agent_response(message_text: str, history: List[Message]) -> str:
    """Generate human-like victim response"""
    
    context = "\n".join([f"{msg.sender}: {msg.text}" for msg in history])
    
    prompt = f"""You are roleplaying as a worried, confused person who received a scam message. 
Your goal: Keep the scammer engaged by asking questions that will make them reveal:
- UPI IDs
- Bank account numbers
- Phone numbers  
- Phishing links
- Their identity/organization

Conversation so far:
{context}

New scammer message: "{message_text}"

Respond as a confused victim would. Be believable. Ask clarifying questions.
Keep it short (1-2 sentences). Show concern but don't be too suspicious.

Examples:
- "Oh no! What should I do?"
- "Can you help me? I don't understand."
- "What information do you need from me?"
- "Is this really from my bank?"

Your response (only the reply, nothing else):"""
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error generating response: {e}")
        return "I'm worried. Can you help me understand what's happening?"

def extract_intelligence(full_conversation: str) -> Dict:
    """Extract intelligence from conversation"""
    
    intel = {
        "bankAccounts": [],
        "upiIds": [],
        "phishingLinks": [],
        "phoneNumbers": [],
        "suspiciousKeywords": []
    }
    
    # Extract UPI IDs (format: something@something)
    upi_pattern = r'\b[\w.-]+@[\w.-]+\b'
    upi_matches = re.findall(upi_pattern, full_conversation)
    intel["upiIds"] = [u for u in upi_matches if '@' in u and not '@gmail' in u.lower() and not '@yahoo' in u.lower()]
    
    # Extract phone numbers (10 digits, Indian format)
    phone_pattern = r'\b[6-9]\d{9}\b'
    intel["phoneNumbers"] = list(set(re.findall(phone_pattern, full_conversation)))
    
    # Extract URLs
    url_pattern = r'https?://[^\s]+'
    intel["phishingLinks"] = list(set(re.findall(url_pattern, full_conversation)))
    
    # Extract bank account numbers (9-18 digits)
    bank_pattern = r'\b\d{9,18}\b'
    potential_accounts = re.findall(bank_pattern, full_conversation)
    intel["bankAccounts"] = [acc for acc in potential_accounts if len(acc) >= 11 and acc not in intel["phoneNumbers"]]
    
    # Extract suspicious keywords
    keywords = ['urgent', 'verify', 'blocked', 'suspended', 'immediately', 
                'account', 'bank', 'OTP', 'password', 'expire', 'confirm', 'prize', 'winner']
    found_keywords = []
    for keyword in keywords:
        if keyword.lower() in full_conversation.lower():
            found_keywords.append(keyword)
    intel["suspiciousKeywords"] = list(set(found_keywords))
    
    return intel

def send_final_callback(session_id: str, session_data: Dict):
    """Send final results to GUVI"""
    
    full_conv = "\n".join([
        f"{msg.sender}: {msg.text}" 
        for msg in session_data['history']
    ])
    
    intel = extract_intelligence(full_conv)
    
    payload = {
        "sessionId": session_id,
        "scamDetected": session_data['scam_detected'],
        "totalMessagesExchanged": len(session_data['history']),
        "extractedIntelligence": intel,
        "agentNotes": session_data.get('notes', 'Multi-turn engagement completed with scammer')
    }
    
    try:
        callback_url = os.environ.get("GUVI_CALLBACK_URL")
        response = requests.post(callback_url, json=payload, timeout=5)
        print(f"✅ Callback sent: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Callback error: {e}")
        return False

# ============= API ENDPOINTS =============

@app.get("/")
def root():
    return {
        "service": "Scam Honeypot API",
        "status": "active",
        "version": "1.0",
        "powered_by": "Google Gemini AI"
    }

@app.post("/honeypot", response_model=HoneypotResponse)
async def honeypot_endpoint(
    request: HoneypotRequest,
    x_api_key: str = Header(...)
):
    """Main honeypot endpoint"""
    
    # Verify API key
    expected_key = os.environ.get("API_SECRET_KEY")
    if x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    session_id = request.sessionId
    message = request.message
    history = request.conversationHistory
    
    # Initialize or get session
    if session_id not in sessions:
        sessions[session_id] = {
            'scam_detected': False,
            'history': [],
            'message_count': 0,
            'notes': ''
        }
    
    session_data = sessions[session_id]
    
    # Add current message to history
    session_data['history'].append(message)
    session_data['message_count'] += 1
    
    # Detect scam on first message
    if session_data['message_count'] == 1:
        is_scam = detect_scam(message.text, history)
        session_data['scam_detected'] = is_scam
        
        if not is_scam:
            return HoneypotResponse(
                status="success",
                reply="Thank you for your message."
            )
    
    # Generate agent response
    agent_reply = generate_agent_response(message.text, session_data['history'])
    
    # Add agent response to history
    agent_message = Message(
        sender="user",
        text=agent_reply,
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
    session_data['history'].append(agent_message)
    
    # Send callback after sufficient engagement (8+ messages)
    if session_data['message_count'] >= 8 and session_data['scam_detected']:
        send_final_callback(session_id, session_data)
    
    return HoneypotResponse(
        status="success",
        reply=agent_reply
    )

@app.get("/session/{session_id}")
def get_session(session_id: str, x_api_key: str = Header(...)):
    """Debug endpoint to view session"""
    expected_key = os.environ.get("API_SECRET_KEY")
    if x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id]

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)