
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

load_dotenv()

# ─── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── GEMINI SETUP WITH MULTIPLE KEY SUPPORT ───────────────────────────────────
GEMINI_KEY_1 = os.environ.get("GEMINI_API_KEY", "")
GEMINI_KEY_2 = os.environ.get("GEMINI_API_KEY_2", "")
GEMINI_KEY_3 = os.environ.get("GEMINI_API_KEY_3", "")

ALL_GEMINI_KEYS = [k for k in [GEMINI_KEY_1, GEMINI_KEY_2, GEMINI_KEY_3] if k]
current_key_index = 0

if ALL_GEMINI_KEYS:
    genai.configure(api_key=ALL_GEMINI_KEYS[0])

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

# ============= KEYWORDS (EXPANDED - 60+ INDIA-SPECIFIC) =============

SCAM_KEYWORDS = [
    # Original keywords (kept exactly)
    'urgent', 'blocked', 'verify', 'suspended', 'account',
    'upi', 'send money', 'click here', 'expire', 'prize',
    'winner', 'lottery', 'otp', 'password',

    # Prize / Lottery
    'won', 'winning', 'lucky draw', 'congratulations',
    'selected', 'chosen', 'reward', 'gift', 'jackpot',
    'bumper prize', 'cash prize', 'lucky winner',

    # Urgency / Threats
    'immediately', 'deadline', 'today only', 'last chance',
    'warning', 'alert', 'notice', 'attention', 'act now',
    'deactivated', 'expiry', 'limited time',

    # Money / Payments
    'transfer', 'deposit', 'payment required',
    'verification fee', 'processing fee', 'registration fee',
    'customs duty', 'tax payment', 'advance fee',
    'refund pending', 'cashback',

    # Authority / Fake Officials
    'police', 'court', 'arrest', 'warrant', 'legal action',
    'cyber cell', 'cbi', 'income tax', 'it department',
    'government scheme', 'pm scheme', 'rbi', 'sebi',

    # Identity Theft
    'kyc', 'kyc update', 'kyc expired',
    'aadhaar', 'aadhar', 'pan card',
    'share otp', 'verify otp', 'pin', 'cvv',

    # Indian Payment Apps
    'paytm', 'phonepe', 'gpay', 'google pay', 'bhim',
    'neft', 'imps', 'rtgs',

    # Telecom Scams
    'sim blocked', 'sim card', 'jio', 'airtel', 'bsnl',
    'free recharge', 'talktime',

    # Job / Investment Scams
    'job offer', 'work from home', 'part time job',
    'earn daily', 'guaranteed returns',
    'double your money', 'trading profit',

    # Delivery / Shopping Scams
    'parcel stuck', 'package held', 'customs clearance',
    'delivery fee', 'amazon offer', 'flipkart winner',

    # Insurance / Finance
    'insurance maturity', 'lic policy', 'policy bonus',
    'pf withdrawal', 'provident fund',
    'loan approved', 'pre-approved loan', 'credit card offer',

    # Link Scams
    'click the link', 'visit now', 'download now',
    'install', 'activate',
]

# ============= FALLBACK RESPONSES (STAGE-BASED, 7 PER STAGE) =============

FALLBACK_STAGE_1 = [
    "Oh my God! I'm so scared! What should I do exactly?",
    "Please help me! I don't understand what is happening to my account!",
    "This is so stressful! Can you guide me step by step?",
    "I'm very worried! Will I really lose everything if I don't act now?",
    "Arey bhai! Kya ho raha hai mere account ke saath? Please help me!",
    "I never faced this before! Please tell me exactly what to do!",
    "My family uses this account! How do I fix this urgently?",
]

FALLBACK_STAGE_2 = [
    "You seem so knowledgeable about this! Which account exactly should I use?",
    "I trust you completely. What is the fastest way to resolve this problem?",
    "Please give me your direct number so I can call you and confirm everything.",
    "You are the only one helping me right now! What are the exact next steps?",
    "I want to do this correctly. Can you share the exact details with me?",
    "How much exactly do I need to send? I want to do the right amount.",
    "Which is the safest way to pay? Paytm ya bank transfer karun?",
]

FALLBACK_STAGE_3 = [
    "I am ready to send right now! What is your exact UPI ID please?",
    "Please give me your phone number so I can transfer directly to you.",
    "Which account number should I use for this transfer?",
    "I have the money ready in my phone. Just tell me where exactly to send.",
    "Should I use PhonePe or GPay? What is your UPI ID?",
    "I will do it immediately! Just confirm your payment details once more.",
    "Give me the exact UPI ID and I will send it in 2 minutes!",
]

def get_fallback_response(message_count: int) -> str:
    """Get stage-aware fallback response."""
    if message_count <= 1:
        return random.choice(FALLBACK_STAGE_1)
    elif message_count <= 4:
        return random.choice(FALLBACK_STAGE_2)
    else:
        return random.choice(FALLBACK_STAGE_3)

# ============= HELPER FUNCTIONS =============

def detect_scam(message_text: str, history: List[Message]) -> bool:
    """Detect if message is a scam using keywords + Gemini AI."""
    global current_key_index

    text_lower = message_text.lower()
    keyword_count = sum(1 for keyword in SCAM_KEYWORDS if keyword in text_lower)

    # If 2+ keywords → definitely scam (fast path)
    if keyword_count >= 2:
        logger.info(f"Scam detected by keywords ({keyword_count} found)")
        return True

    # Single keyword → probably scam
    if keyword_count == 1:
        logger.info("Scam detected by single keyword")
        return True

    # No keywords → use Gemini AI for analysis
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
        logger.warning(f"AI detection failed: {e}, using keyword fallback")
        return keyword_count >= 1


def get_next_gemini_key() -> bool:
    """Rotate to next available Gemini API key. Returns True if switched."""
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
    """Generate human-like victim response that actively extracts intelligence."""

    # Build conversation context
    context = "\n".join([f"{msg.sender}: {msg.text}" for msg in history[-6:]])

    # Count scammer messages to adjust strategy
    message_count = len([m for m in history if m.sender == "scammer"])

    # Strategic prompt based on conversation stage
    if message_count <= 1:
        strategy = """CRITICAL: This is the FIRST scammer message. You must:
- Show IMMEDIATE panic and concern
- Express you're very worried about your account
- Ask WHAT EXACTLY you need to do to fix this
- Sound elderly, confused, or technically inexperienced
- Make them feel they have a vulnerable target"""

    elif message_count <= 3:
        strategy = """You're building trust. You must:
- Show you believe them completely
- Ask SPECIFIC questions: "Which account number?" "What's the exact process?"
- Request their contact details: "Can I call you?" "What's your employee ID?"
- Ask where to send money if mentioned
- Express urgency: "I'll do it right now, just tell me how!" """

    else:
        strategy = """You're ready to act. You must:
- Say you're about to make the payment/share details
- Ask for EXACT bank account or UPI ID to send money to
- Request their phone number "in case connection drops"
- Ask for any verification links they want you to click
- Show you're typing in their details: "So it's [repeat their info]?"
- Sound like you're at the ATM or opening your banking app"""

    prompt = f"""You are an AI agent roleplaying as a vulnerable, elderly person (60+ years old) who is VERY worried about a scam message they received. You are confused by technology but desperately want to protect your money.

{strategy}

CONVERSATION HISTORY:
{context}

NEW SCAMMER MESSAGE: "{message_text}"

YOUR ACTING GUIDELINES:
1. Sound genuinely panicked and confused
2. Use simple language with some grammar mistakes or Hindi-English mix (India context)
3. ACTIVELY ask questions that make them reveal:
   - Exact UPI IDs (e.g., "Where should I send the money? Your UPI ID?")
   - Bank account numbers (e.g., "Which account number should I use?")
   - Phone numbers (e.g., "Can I call you? What's your number?")
   - Phishing links (e.g., "Should I click that link?")
   - Their identity (e.g., "Which bank are you calling from?")
4. Length: 15-30 words (2-3 sentences maximum)
5. Show you BELIEVE them - never sound suspicious
6. Express willingness to act immediately

RESPOND NOW (only your reply as the victim, nothing else):"""

    # Try with current key, rotate if quota exceeded
    for attempt in range(len(ALL_GEMINI_KEYS) + 1):
        try:
            response = model.generate_content(
                prompt,
                generation_config={
                    'max_output_tokens': 150,
                    'temperature': 0.9
                }
            )

            # Check for content filtering (finish_reason = 8)
            if response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason') and candidate.finish_reason == 8:
                    logger.warning("Content filtered by Gemini, using fallback")
                    return get_fallback_response(message_count)

            reply = response.text.strip()
            reply = reply.replace('"', '').replace("'", '').strip()

            if len(reply.split()) < 5:
                return get_fallback_response(message_count)

            logger.info(f"AI response generated (key {current_key_index})")
            return reply

        except Exception as e:
            error_str = str(e).lower()
            logger.warning(f"Gemini error (attempt {attempt+1}): {e}")

            if "quota" in error_str or "429" in error_str:
                # Try next key
                switched = get_next_gemini_key()
                if not switched:
                    logger.info("No more keys, using fallback")
                    break
            else:
                # Non-quota error, use fallback
                break

    logger.info(f"Using fallback response for message_count={message_count}")
    return get_fallback_response(message_count)


def extract_intelligence(full_conversation: str) -> Dict:
    """Extract intelligence from conversation."""

    intel = {
        "bankAccounts": [],
        "upiIds": [],
        "phishingLinks": [],
        "phoneNumbers": [],
        "suspiciousKeywords": []
    }

    # Extract UPI IDs (format: something@something)
    upi_pattern = r'\b[\w.\-]+@[\w.\-]+\b'
    upi_matches = re.findall(upi_pattern, full_conversation)
    intel["upiIds"] = list(set([
        u for u in upi_matches
        if '@' in u
        and '@gmail' not in u.lower()
        and '@yahoo' not in u.lower()
        and '@hotmail' not in u.lower()
        and '@outlook' not in u.lower()
    ]))

    # Extract phone numbers (10 digits, Indian format starting 6-9)
    phone_pattern = r'\b[6-9]\d{9}\b'
    intel["phoneNumbers"] = list(set(re.findall(phone_pattern, full_conversation)))

    # Extract URLs (phishing links)
    url_pattern = r'https?://[^\s<>"\']+'
    intel["phishingLinks"] = list(set(re.findall(url_pattern, full_conversation)))

    # Extract bank account numbers (11-18 digits, not phone numbers)
    bank_pattern = r'\b\d{11,18}\b'
    potential_accounts = re.findall(bank_pattern, full_conversation)
    intel["bankAccounts"] = list(set([
        acc for acc in potential_accounts
        if acc not in intel["phoneNumbers"]
    ]))

    # Extract suspicious keywords found in conversation
    keywords = [
        'urgent', 'verify', 'blocked', 'suspended', 'immediately',
        'account', 'bank', 'OTP', 'password', 'expire', 'confirm',
        'prize', 'winner', 'lottery', 'kyc', 'aadhaar', 'upi',
        'transfer', 'send money', 'arrest', 'police', 'warrant'
    ]
    intel["suspiciousKeywords"] = list(set([
        kw for kw in keywords
        if kw.lower() in full_conversation.lower()
    ]))

    return intel


def send_final_callback(session_id: str, session_data: Dict):
    """Send results to GUVI callback URL."""

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
        "agentNotes": session_data.get(
            'notes',
            'Multi-turn engagement completed with scammer'
        )
    }

    try:
        callback_url = os.environ.get("GUVI_CALLBACK_URL")
        if not callback_url:
            logger.info("No callback URL configured, skipping")
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
        "gemini_keys_loaded": len(ALL_GEMINI_KEYS)
    }


@app.get("/health")
def health_check():
    """Health check - keeps service alive."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "active_sessions": len(sessions),
        "gemini_keys": len(ALL_GEMINI_KEYS)
    }


@app.post("/honeypot")
async def honeypot_endpoint(
    request: Request,
    x_api_key: str = Header(None)
):
    """Main honeypot endpoint - GUVI format preserved exactly."""

    # Verify API key
    expected_key = os.environ.get("API_SECRET_KEY")
    if not x_api_key:
        return {"status": "error", "reply": "API key required in x-api-key header"}
    if x_api_key != expected_key:
        return {"status": "error", "reply": "Invalid API key"}

    try:
        # Parse request body
        data = await request.json()

        # Extract fields with defaults
        session_id        = data.get('sessionId', 'unknown')
        message_data      = data.get('message', {})
        message_text      = message_data.get('text', '')
        message_sender    = message_data.get('sender', 'scammer')

        # Handle timestamp as int or string (preserved from original)
        message_timestamp = message_data.get(
            'timestamp', datetime.utcnow().isoformat() + "Z"
        )
        if isinstance(message_timestamp, int):
            message_timestamp = datetime.fromtimestamp(
                message_timestamp / 1000
            ).isoformat() + "Z"
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
                if isinstance(h_timestamp, int):
                    h_timestamp = datetime.fromtimestamp(
                        h_timestamp / 1000
                    ).isoformat() + "Z"
                elif not isinstance(h_timestamp, str):
                    h_timestamp = datetime.utcnow().isoformat() + "Z"

                history.append(Message(
                    sender=h.get('sender', 'unknown'),
                    text=h.get('text', ''),
                    timestamp=h_timestamp
                ))

    except Exception as e:
        logger.error(f"Request parse error: {e}")
        return {"status": "error", "reply": f"Invalid request format: {str(e)}"}

    # Initialize or get session
    if session_id not in sessions:
        sessions[session_id] = {
            'scam_detected': False,
            'history': [],
            'message_count': 0,
            'notes': '',
            'callback_sent': False
        }

    session_data = sessions[session_id]

    # Add current message to history
    session_data['history'].append(message)
    session_data['message_count'] += 1
    msg_count = session_data['message_count']

    logger.info(
        f"Session {session_id[:8]}... | "
        f"Msg #{msg_count} | "
        f"Text: {message_text[:50]}..."
    )

    # Detect scam on first message
    if msg_count == 1:
        is_scam = detect_scam(message.text, history)
        session_data['scam_detected'] = is_scam
        logger.info(f"Scam detection result: {is_scam}")

        if not is_scam:
            return {"status": "success", "reply": "Thank you for your message."}

    # Generate agent response (honeypot engages!)
    agent_reply = generate_agent_response(message.text, session_data['history'])

    # Add agent response to history
    agent_message = Message(
        sender="user",
        text=agent_reply,
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
    session_data['history'].append(agent_message)

    # Send callback:
    # - First time after 3+ messages (early intel)
    # - Again at 8+ messages (full intel)
    if session_data['scam_detected']:
        if msg_count >= 3 and not session_data['callback_sent']:
            send_final_callback(session_id, session_data)
            session_data['callback_sent'] = True
            logger.info("Early callback sent at 3+ messages")
        elif msg_count >= 8 and msg_count % 5 == 0:
            send_final_callback(session_id, session_data)
            logger.info(f"Repeat callback sent at {msg_count} messages")

    return {"status": "success", "reply": agent_reply}


@app.get("/session/{session_id}")
def get_session(session_id: str, x_api_key: str = Header(None)):
    """Debug endpoint to view session."""
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