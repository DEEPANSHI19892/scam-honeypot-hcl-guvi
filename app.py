from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel
from typing import List, Optional, Dict
import google.generativeai as genai
import os
import re
import random
import requests
import logging
from dotenv import load_dotenv
from datetime import datetime
import time

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── GEMINI SETUP ───
GEMINI_KEY_1 = os.environ.get("GEMINI_API_KEY", "")
GEMINI_KEY_2 = os.environ.get("GEMINI_API_KEY_2", "")
GEMINI_KEY_3 = os.environ.get("GEMINI_API_KEY_3", "")

ALL_GEMINI_KEYS = [k for k in [GEMINI_KEY_1, GEMINI_KEY_2, GEMINI_KEY_3] if k]
current_key_index = 0

if ALL_GEMINI_KEYS:
    genai.configure(api_key=ALL_GEMINI_KEYS[0])

model = genai.GenerativeModel('gemini-2.5-flash')

app = FastAPI(title="Scam Honeypot API")

sessions = {}
conversation_start_times = {}  # NEW: Track duration

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

# ============= KEYWORDS (YOUR LIST - KEPT EXACTLY) =============

SCAM_KEYWORDS = [
    'urgent', 'blocked', 'verify', 'suspended', 'account',
    'upi', 'send money', 'click here', 'expire', 'prize',
    'winner', 'lottery', 'otp', 'password',
    'won', 'winning', 'lucky draw', 'congratulations',
    'selected', 'chosen', 'reward', 'gift', 'jackpot',
    'bumper prize', 'cash prize', 'lucky winner',
    'immediately', 'deadline', 'today only', 'last chance',
    'warning', 'alert', 'notice', 'attention', 'act now',
    'deactivated', 'expiry', 'limited time',
    'transfer', 'deposit', 'payment required',
    'verification fee', 'processing fee', 'registration fee',
    'customs duty', 'tax payment', 'advance fee',
    'refund pending', 'cashback',
    'police', 'court', 'arrest', 'warrant', 'legal action',
    'cyber cell', 'cbi', 'income tax', 'it department',
    'government scheme', 'pm scheme', 'rbi', 'sebi',
    'kyc', 'kyc update', 'kyc expired',
    'aadhaar', 'aadhar', 'pan card',
    'share otp', 'verify otp', 'pin', 'cvv',
    'paytm', 'phonepe', 'gpay', 'google pay', 'bhim',
    'neft', 'imps', 'rtgs',
    'sim blocked', 'sim card', 'jio', 'airtel', 'bsnl',
    'free recharge', 'talktime',
    'job offer', 'work from home', 'part time job',
    'earn daily', 'guaranteed returns',
    'double your money', 'trading profit',
    'parcel stuck', 'package held', 'customs clearance',
    'delivery fee', 'amazon offer', 'flipkart winner',
    'insurance maturity', 'lic policy', 'policy bonus',
    'pf withdrawal', 'provident fund',
    'loan approved', 'pre-approved loan', 'credit card offer',
    'click the link', 'visit now', 'download now',
    'install', 'activate',
]

# ============= IMPROVED FALLBACK WITH QUESTIONS =============

FALLBACK_STAGE_1 = [
    "Oh my God! I'm so scared! Who are you? Can you give me your phone number?",
    "Please help me! Which department are you from? What's your employee ID?",
    "This is so stressful! Can I call you back? What's your number?",
    "I'm very worried! Who is this? What company? Give me your contact details!",
    "Arey bhai! What's happening? Who are you? What's your phone number?",
    "I never faced this! Are you from bank? What's your official number?",
    "My family account! How to fix? Who to contact? What's your number?",
]

FALLBACK_STAGE_2 = [
    "You seem knowledgeable! Which account to use? What's your UPI ID?",
    "I trust you! What's exact process? Your supervisor's phone?",
    "Give me your direct number so I can call. What is it?",
    "You're helping me! What's your company website? Your phone?",
    "I want to do correctly. Your exact payment details? UPI? Account?",
    "How much exactly to send? What's your UPI ID? PhonePe or GPay?",
    "Safest way to pay? Your exact UPI ID or phone number?",
]

FALLBACK_STAGE_3 = [
    "Ready to send now! What's your EXACT UPI ID? Tell me!",
    "Opening banking app. Your UPI ID? Should I use this number?",
    "Which account for transfer? Give exact details!",
    "Money ready! What's your UPI ID? Sending immediately!",
    "PhonePe or GPay? What's your UPI ID? Confirm phone?",
    "Doing immediately! Exact UPI ID and phone? Let me confirm!",
    "Give exact UPI and I send in 2 minutes! What is it?",
]

def get_fallback_response(message_count: int) -> str:
    if message_count <= 1:
        return random.choice(FALLBACK_STAGE_1)
    elif message_count <= 4:
        return random.choice(FALLBACK_STAGE_2)
    else:
        return random.choice(FALLBACK_STAGE_3)

# ============= HELPER FUNCTIONS (YOUR CODE + IMPROVEMENTS) =============

def detect_scam(message_text: str, history: List[Message]) -> bool:
    global current_key_index

    text_lower = message_text.lower()
    keyword_count = sum(1 for keyword in SCAM_KEYWORDS if keyword in text_lower)

    if keyword_count >= 2:
        logger.info(f"Scam detected by keywords ({keyword_count} found)")
        return True

    if keyword_count == 1:
        logger.info("Scam detected by single keyword")
        return True

    try:
        prompt = f"""Is this a scam message? Reply only "SCAM" or "SAFE".

Message: "{message_text}"

Answer:"""

        response = model.generate_content(
            prompt,
            generation_config={'max_output_tokens': 10}
        )
        result = response.text.strip().upper()
        is_scam = "SCAM" in result
        logger.info(f"AI scam detection: {'SCAM' if is_scam else 'SAFE'}")
        return is_scam

    except Exception as e:
        logger.warning(f"AI detection failed: {e}")
        return keyword_count >= 1


def get_next_gemini_key() -> bool:
    global current_key_index, model

    if len(ALL_GEMINI_KEYS) <= 1:
        return False

    next_index = (current_key_index + 1) % len(ALL_GEMINI_KEYS)
    if next_index == current_key_index:
        return False

    current_key_index = next_index
    genai.configure(api_key=ALL_GEMINI_KEYS[current_key_index])
    model = genai.GenerativeModel('gemini-2.5-flash')
    logger.info(f"Switched to Gemini key index {current_key_index}")
    return True


def generate_agent_response(message_text: str, history: List[Message]) -> str:
    context = "\n".join([f"{msg.sender}: {msg.text}" for msg in history[-6:]])
    message_count = len([m for m in history if m.sender == "scammer"])

    # IMPROVED: More aggressive questioning
    if message_count <= 1:
        strategy = """CRITICAL: First message! You MUST:
- Show IMMEDIATE panic
- Ask WHO they are: "Who are you? What's your name?"
- Ask for PHONE: "What's your phone number?" or "Employee ID?"
- Sound elderly, confused
- ALWAYS END WITH A QUESTION for their contact"""

    elif message_count <= 3:
        strategy = """Building trust! You MUST:
- Show you believe completely
- Ask MULTIPLE questions:
  * "Which account number?"
  * "What's your exact UPI ID?"
  * "Can I call you? Phone?"
  * "Company website?"
  * "Supervisor's phone?"
- Express urgency: "I'll do it now, just tell me!"
- ALWAYS END asking for payment details"""

    else:
        strategy = """Ready to act! You MUST:
- Say you're making payment RIGHT NOW
- Ask for EXACT details:
  * "What's your EXACT UPI ID? Spell it!"
  * "Should I send to this number: [repeat]?"
  * "Your phone in case connection drops?"
  * "Account number - all digits?"
- Sound like at ATM or opening app
- "Typing it now, what's UPI again?"
- ALWAYS END with DIRECT QUESTION"""

    prompt = f"""You are elderly person (60+) VERY worried about scam. Confused by tech but want to protect money.

{strategy}

CONVERSATION:
{context}

NEW MESSAGE: "{message_text}"

GUIDELINES:
1. Sound panicked, confused
2. Simple language, grammar mistakes, Hindi-English mix
3. CRITICALLY: ALWAYS ASK QUESTIONS - NEVER just statements!
   - Ask for: phone, UPI, account, employee ID, verification
   - Use: "What's your number?" "Tell me UPI?" "Can I call?"
4. Length: 20-35 words (2-3 sentences, ONE QUESTION)
5. BELIEVE them - never suspicious
6. Express willing to act but need details first

CRITICAL: MUST contain question mark (?) asking specific info!

RESPOND (only your reply):"""

    for attempt in range(len(ALL_GEMINI_KEYS) + 1):
        try:
            response = model.generate_content(
                prompt,
                generation_config={'max_output_tokens': 150, 'temperature': 0.9}
            )

            if response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason') and candidate.finish_reason == 8:
                    logger.warning("Content filtered, using fallback")
                    return get_fallback_response(message_count)

            reply = response.text.strip().replace('"', '').replace("'", '').strip()

            # Ensure has question
            if '?' not in reply:
                if message_count <= 1:
                    reply += " What's your phone number?"
                elif message_count <= 3:
                    reply += " What's your exact UPI ID?"
                else:
                    reply += " Tell me UPI ID again?"

            if len(reply.split()) < 5:
                return get_fallback_response(message_count)

            logger.info(f"AI response generated (key {current_key_index})")
            return reply

        except Exception as e:
            error_str = str(e).lower()
            logger.warning(f"Gemini error (attempt {attempt+1}): {e}")

            if "quota" in error_str or "429" in error_str:
                switched = get_next_gemini_key()
                if not switched:
                    break
            else:
                break

    logger.info(f"Using fallback for message_count={message_count}")
    return get_fallback_response(message_count)


def extract_intelligence(full_conversation: str) -> Dict:
    intel = {
        "bankAccounts": [],
        "upiIds": [],
        "phishingLinks": [],
        "phoneNumbers": [],
        "emailAddresses": [],
        "suspiciousKeywords": []
    }

    # UPI IDs
    upi_pattern = r'\b[\w.\-]+@[\w.\-]+\b'
    upi_matches = re.findall(upi_pattern, full_conversation)
    intel["upiIds"] = list(set([
        u for u in upi_matches
        if '@' in u and '@gmail' not in u.lower() and '@yahoo' not in u.lower()
    ]))

    # Phone numbers
    phone_pattern = r'\b[6-9]\d{9}\b'
    intel["phoneNumbers"] = list(set(re.findall(phone_pattern, full_conversation)))

    # URLs
    url_pattern = r'https?://[^\s<>"\']+'
    intel["phishingLinks"] = list(set(re.findall(url_pattern, full_conversation)))

    # Bank accounts
    bank_pattern = r'\b\d{11,18}\b'
    potential_accounts = re.findall(bank_pattern, full_conversation)
    intel["bankAccounts"] = list(set([
        acc for acc in potential_accounts if acc not in intel["phoneNumbers"]
    ]))

    # Emails
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, full_conversation)
    intel["emailAddresses"] = list(set([e for e in emails if e not in intel["upiIds"]]))

    # Keywords
    keywords = ['urgent', 'verify', 'blocked', 'otp', 'transfer', 'prize', 'kyc']
    intel["suspiciousKeywords"] = list(set([
        kw for kw in keywords if kw.lower() in full_conversation.lower()
    ]))

    return intel


def send_final_callback(session_id: str, session_data: Dict):
    full_conv = "\n".join([f"{msg.sender}: {msg.text}" for msg in session_data['history']])
    intel = extract_intelligence(full_conv)

    start_time = conversation_start_times.get(session_id, time.time())
    duration = int(time.time() - start_time)

    payload = {
        "sessionId": session_id,
        "scamDetected": session_data['scam_detected'],
        "totalMessagesExchanged": len(session_data['history']),
        "engagementDurationSeconds": duration,
        "extractedIntelligence": intel,
        "agentNotes": f"Scam detected. Engaged for {len(session_data['history'])} messages."
    }

    try:
        callback_url = os.environ.get("GUVI_CALLBACK_URL")
        if not callback_url:
            logger.info("No callback URL, skipping")
            return False

        response = requests.post(callback_url, json=payload, timeout=10)
        logger.info(f"✅ Callback sent: {response.status_code}")
        return response.status_code == 200

    except Exception as e:
        logger.error(f"❌ Callback error: {e}")
        return False

# ============= API ENDPOINTS =============

@app.get("/")
def root():
    return {
        "service": "Scam Honeypot API",
        "status": "active",
        "version": "2.0",
        "powered_by": "Google Gemini AI",
        "gemini_keys_loaded": len(ALL_GEMINI_KEYS),
        "endpoints": {
            "/honeypot": "Original format",
            "/detect": "Evaluation format",
            "/health": "Health check"
        }
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "active_sessions": len(sessions),
        "gemini_keys": len(ALL_GEMINI_KEYS)
    }


# NEW: /detect endpoint for evaluation!
@app.post("/detect")
async def detect_endpoint(request: Request):
    """Evaluation-compatible endpoint."""
    
    try:
        data = await request.json()
        
        session_id = data.get("sessionId", "unknown")
        message_obj = data.get("message", {})
        message_text = message_obj.get("text", "")
        
        if session_id not in conversation_start_times:
            conversation_start_times[session_id] = time.time()
        
        if session_id not in sessions:
            sessions[session_id] = {
                'scam_detected': False,
                'history': [],
                'message_count': 0,
                'callback_sent': False
            }
        
        session_data = sessions[session_id]
        
        message = Message(
            sender="scammer",
            text=message_text,
            timestamp=message_obj.get("timestamp", datetime.utcnow().isoformat() + "Z")
        )
        
        session_data['history'].append(message)
        session_data['message_count'] += 1
        msg_count = session_data['message_count']
        
        logger.info(f"Session {session_id[:8]}... | Msg #{msg_count} | {message_text[:50]}...")
        
        if msg_count == 1:
            is_scam = detect_scam(message.text, [])
            session_data['scam_detected'] = is_scam
            logger.info(f"Scam detection: {is_scam}")
            
            if not is_scam:
                return {"status": "success", "reply": "Thank you for your message."}
        
        agent_reply = generate_agent_response(message.text, session_data['history'])
        
        agent_message = Message(
            sender="user",
            text=agent_reply,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )
        session_data['history'].append(agent_message)
        
        if session_data['scam_detected']:
            if msg_count >= 3 and not session_data['callback_sent']:
                send_final_callback(session_id, session_data)
                session_data['callback_sent'] = True
                logger.info("Early callback at 3+ messages")
            elif msg_count >= 10:
                send_final_callback(session_id, session_data)
                logger.info(f"Repeat callback at {msg_count} messages")
        
        return {"status": "success", "reply": agent_reply}
        
    except Exception as e:
        logger.error(f"Error in /detect: {e}")
        return {"status": "error", "reply": "Internal error"}


@app.post("/honeypot")
async def honeypot_endpoint(request: Request, x_api_key: str = Header(None)):
    """Original endpoint - kept for compatibility."""

    expected_key = os.environ.get("API_SECRET_KEY")
    if not x_api_key:
        return {"status": "error", "reply": "API key required"}
    if x_api_key != expected_key:
        return {"status": "error", "reply": "Invalid API key"}

    try:
        data = await request.json()

        session_id = data.get('sessionId', 'unknown')
        message_data = data.get('message', {})
        message_text = message_data.get('text', '')
        message_sender = message_data.get('sender', 'scammer')

        message_timestamp = message_data.get('timestamp', datetime.utcnow().isoformat() + "Z")
        if isinstance(message_timestamp, int):
            message_timestamp = datetime.fromtimestamp(message_timestamp / 1000).isoformat() + "Z"

        message = Message(sender=message_sender, text=message_text, timestamp=message_timestamp)

    except Exception as e:
        logger.error(f"Parse error: {e}")
        return {"status": "error", "reply": f"Invalid format: {str(e)}"}

    if session_id not in conversation_start_times:
        conversation_start_times[session_id] = time.time()

    if session_id not in sessions:
        sessions[session_id] = {
            'scam_detected': False,
            'history': [],
            'message_count': 0,
            'callback_sent': False
        }

    session_data = sessions[session_id]
    session_data['history'].append(message)
    session_data['message_count'] += 1
    msg_count = session_data['message_count']

    logger.info(f"Session {session_id[:8]}... | Msg #{msg_count} | {message_text[:50]}...")

    if msg_count == 1:
        is_scam = detect_scam(message.text, [])
        session_data['scam_detected'] = is_scam
        logger.info(f"Scam detection: {is_scam}")

        if not is_scam:
            return {"status": "success", "reply": "Thank you."}
    agent_reply = generate_agent_response(message.text, session_data['history'])

    agent_message = Message(sender="user", text=agent_reply, timestamp=datetime.utcnow().isoformat() + "Z")
    session_data['history'].append(agent_message)

    if session_data['scam_detected']:
        if msg_count >= 3 and not session_data['callback_sent']:
            send_final_callback(session_id, session_data)
            session_data['callback_sent'] = True
        elif msg_count >= 8 and msg_count % 5 == 0:
            send_final_callback(session_id, session_data)

    return {"status": "success", "reply": agent_reply}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)