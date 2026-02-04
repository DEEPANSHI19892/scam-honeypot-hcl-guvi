from fastapi import FastAPI, HTTPException, Header, Request
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
    
    # Quick keyword check first
    scam_keywords = ['urgent', 'blocked', 'verify', 'suspended', 'account', 
                     'upi', 'send money', 'click here', 'expire', 'prize', 
                     'winner', 'lottery', 'otp', 'password']
    
    text_lower = message_text.lower()
    keyword_count = sum(1 for keyword in scam_keywords if keyword in text_lower)
    
    # If 2+ keywords, likely scam
    if keyword_count >= 2:
        return True
    
    # Otherwise use AI (but with timeout protection)
    try:
        prompt = f"""Is this a scam message? Reply only "SCAM" or "SAFE".

Message: "{message_text}"

Answer:"""
        
        response = model.generate_content(
            prompt,
            generation_config={'max_output_tokens': 10}
        )
        
        result = response.text.strip().upper()
        return "SCAM" in result
    except Exception as e:
        # If AI fails, use keyword heuristic
        return keyword_count >= 1


def generate_agent_response(message_text: str, history: List[Message]) -> str:
    """Generate human-like victim response"""
    
    context = "\n".join([f"{msg.sender}: {msg.text}" for msg in history[-5:]])
    
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

Your response (only the reply, nothing else):"""
    
    try:
        response = model.generate_content(
            prompt,
            generation_config={'max_output_tokens': 100}
        )
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
    intel["upiIds"] = [u for u in upi_matches if '@' in u and '@gmail' not in u.lower() and '@yahoo' not in u.lower()]
    
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

@app.get("/health")
def health_check():
    """Quick health check - wakes up the service"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.post("/honeypot")
async def honeypot_endpoint(
    request: Request,
    x_api_key: str = Header(None)
):
    """Main honeypot endpoint"""
    
    # Verify API key
    if not x_api_key:
    return {"status": "error", "reply": "API key required in x-api-key header"}
if x_api_key != expected_key:
    return {"status": "error", "reply": "Invalid API key"}

    
  try:
    # Parse request body
    data = await request.json()
    
    # Extract fields with defaults
    session_id = data.get('sessionId', 'unknown')
    message_data = data.get('message', {})
    message_text = message_data.get('text', '')
    message_sender = message_data.get('sender', 'scammer')
    
    # Handle timestamp as int or string
    message_timestamp = message_data.get('timestamp', datetime.utcnow().isoformat() + "Z")
    if isinstance(message_timestamp, int):
        # Convert Unix timestamp (milliseconds) to ISO string
        message_timestamp = datetime.fromtimestamp(message_timestamp / 1000).isoformat() + "Z"
    elif not isinstance(message_timestamp, str):
        message_timestamp = datetime.utcnow().isoformat() + "Z"
    
    history_data = data.get('conversationHistory', [])
    
    # Convert to Message objects
    message = Message(
        sender=message_sender,
        text=message_text,
        timestamp=message_timestamp
    )
    
    history = []
    for h in history_data:
        if isinstance(h, dict):
            h_timestamp = h.get('timestamp', datetime.utcnow().isoformat() + "Z")
            # Handle timestamp as int or string
            if isinstance(h_timestamp, int):
                h_timestamp = datetime.fromtimestamp(h_timestamp / 1000).isoformat() + "Z"
            elif not isinstance(h_timestamp, str):
                h_timestamp = datetime.utcnow().isoformat() + "Z"
            
            history.append(Message(
                sender=h.get('sender', 'unknown'),
                text=h.get('text', ''),
                timestamp=h_timestamp
            ))

except Exception as e:
    return {"status": "error", "reply": f"Invalid request format: {str(e)}"}
    
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
            return {"status": "success", "reply": "Thank you for your message."}
    
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
    
    return {"status": "success", "reply": agent_reply}

@app.get("/session/{session_id}")
def get_session(session_id: str, x_api_key: str = Header(None)):
    """Debug endpoint to view session"""
    expected_key = os.environ.get("API_SECRET_KEY")
    if x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id]

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)