# AI Agentic Honeypot for Scam Detection & Intelligence Extraction

**India AI Impact Buildathon 2026 - Problem Statement 2**  
**Team: Techz**

---

## Overview

An intelligent honeypot system that actively engages scammers in multi-turn conversations, extracts criminal identifiers (UPI IDs, phone numbers, bank accounts), and provides actionable intelligence to law enforcement. Built to shift fraud prevention from reactive blocking to proactive intelligence gathering.

**Live Deployment**: `https://scam-honeypot-ap8q.onrender.com`

---

## Problem Statement

India faces a cyber fraud crisis:
- **₹10,319+ crores** lost annually to cyber fraud (2023)
- **7.4 lakh complaints** filed nationwide  
- **2,000+ victims daily** - that's one family every 43 seconds

Current fraud prevention systems **block** scammers who simply create new numbers within minutes. This defensive approach collects **zero intelligence** on criminals, enabling them to continue targeting new victims indefinitely.

**Our solution**: Flip from defensive blocking to offensive intelligence gathering.

---

## Solution Approach

Instead of blocking scammers, we **engage** them through an AI-powered honeypot that:

1. **Pretends to be a vulnerable victim** - mimics elderly or technically inexperienced users
2. **Maintains realistic multi-turn conversations** - averages 8-10 message exchanges  
3. **Extracts criminal identifiers** through strategic questioning and natural dialogue
4. **Provides intelligence to law enforcement** via automated callbacks for proactive prevention

**Key Insight**: One blocked scammer = one prevented attack. One engaged scammer = hundreds of prevented attacks through intelligence-driven prosecution.

---

## Tech Stack

- **Backend Framework**: FastAPI (Python 3.11)
- **AI Model**: Google Gemini 2.0 Flash (`gemini-2.0-flash-exp`)
- **Deployment Platform**: Render.com (Cloud)
- **HTTP Client**: httpx (async)
- **ASGI Server**: Uvicorn
- **Key Libraries**: `google-generativeai`, `fastapi`, `uvicorn`, `httpx`, `pydantic`

---

## Setup Instructions

### Prerequisites
- Python 3.11+
- 3 Google Gemini API keys

### Installation

```bash
# Clone repository
git clone https://github.com/yogeshwargopihoneyPot/scam-honeypot
cd scam-honeypot

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your Gemini API keys

# Run locally
uvicorn app:app --reload --port 8000
```

### Environment Variables

Create `.env` file:
```env
GEMINI_API_KEY_1=your_key_here
GEMINI_API_KEY_2=your_key_here
GEMINI_API_KEY_3=your_key_here
CALLBACK_URL=your_callback_url_here
```

⚠️ **Security**: Never commit API keys to version control!

---

## API Endpoints

### `/honeypot` - Original Format

```json
POST /honeypot

Request:
{
  "message": "URGENT! Account blocked...",
  "session_id": "unique-id"
}

Response:
{
  "response": "Oh no! Who are you?",
  "is_scam": true,
  "confidence": 0.95,
  "message_count": 1
}
```

### `/detect` - Evaluation Format

```json
POST /detect

Request:
{
  "sessionId": "uuid",
  "message": {
    "sender": "scammer",
    "text": "URGENT! Account blocked...",
    "timestamp": "2026-02-20T10:00:00Z"
  },
  "conversationHistory": [],
  "metadata": {
    "channel": "SMS",
    "language": "English",
    "locale": "IN"
  }
}
Response:
{
  "status": "success",
  "reply": "Oh no! Who are you? What's your phone number?"
}
```

### `/health` - Health Check

```json
GET /health

Response:
{
  "status": "ok",
  "gemini_keys": 3
}
```
---

## Architecture

### Three-Layer Detection System

**Layer 1: Keyword Detection (70% coverage)**
- 60+ India-specific scam keywords
- Instant detection, zero AI cost
- Patterns: "urgent", "OTP", "verify", "Aadhaar", "blocked"

**Layer 2: AI Analysis (30% coverage)**
- Google Gemini for sophisticated scams
- Context-aware detection
- Confidence scoring

**Layer 3: Fallback System (100% uptime)**
- Stage-aware responses
- Activates on AI quota exhaustion
- Proven zero-downtime operation

### Stage-Based Agentic Persona

**Stage 1 - Panic (Messages 1-3)**
- "Oh no! I'm scared! Who are you? What's your phone number?"
- Displays vulnerability
- Asks identifying questions

**Stage 2 - Trust (Messages 4-7)**
- "You seem knowledgeable. What's your company's website?"
- Builds false confidence
- Probes for details

**Stage 3 - Extraction (Messages 8+)**
- "I'm ready to send. What's your exact UPI ID?"
- Direct questioning
- Confirms payment details

### Multi-Key Rotation

- **3 Gemini API keys** with automatic switching
- Detects 429 quota errors
- Seamless failover with retry logic
- **Proven**: 7+ rotations during national testing with 100% uptime

### Intelligence Extraction

Real-time regex patterns for:
- **Phone Numbers**: `+91-XXXXXXXXXX`, various formats
- **UPI IDs**: `xyz@paytm`, `abc@okbank`
- **Bank Accounts**: 12-16 digit sequences
- **URLs**: Phishing link detection
- **Emails**: Standard formats

---

## Key Features

✅ Multi-turn engagement (10+ messages proven)  
✅ Stage-based emotional adaptation  
✅ Multi-key rotation with zero downtime  
✅ Fallback system for 100% uptime  
✅ Real-time intelligence extraction  
✅ Dual-stage law enforcement callbacks  
✅ India-specific keyword patterns  
✅ Production-grade reliability  
✅ Evaluation format compatible  

---

## Scam Detection Strategy

### Keywords Monitored (60+)

**Urgency**: urgent, immediately, now, fast, quickly  
**Financial**: OTP, verify, account, blocked, suspended, KYC, UPI  
**India-specific**: Aadhaar, PAN, verify@paytm, PhonePe, GPay  
**Threats**: blocked, legal action, police, arrest, frozen  
**Rewards**: won, prize, lottery, cashback, congratulations  

### Investigative Questions

**Identity Verification**:
- "Who are you? What's your employee ID?"
- "Can you give me your official phone number?"
- "Which department are you from?"

**Information Elicitation**:
- "What's your exact UPI ID?"
- "Can I have your supervisor's number?"
- "What's your company's official website?"

**Confirmation Seeking**:
- "Let me confirm: your number is +91-XXX, right?"
- "Should I send to this UPI ID: [repeat]?"
- "What's the account number again?"

---

## Limitations & Future Enhancements

### Current Limitations

**Short Conversations**: If scammer disconnects early (<3 messages), minimal intelligence  
**Cautious Scammers**: Some avoid sharing identifiers directly  
**Evolving Patterns**: New tactics may need keyword updates  
**Text-Only**: No voice call integration yet  

### Future Roadmap

**Q2 2026**:
- Voice call integration
- Hindi and regional language support
- Real-time monitoring dashboard

**Q3 2026**:
- WhatsApp/Telegram integration
- ML-based behavior analysis
- Law enforcement portal

**Q4 2026**:
- National deployment via telecom operators
- I4C integration
- Predictive fraud prevention

---

## Deployment

**Production URL**: `https://scam-honeypot-ap8q.onrender.com`

**Platform**: Render.com with automatic GitHub deployments

**Performance**:
- Cold start: 15-30 seconds
- Warm response: 2-5 seconds
- Concurrent: Up to 10 connections

---

## Security & Privacy

**Data Collection**:
- ✅ Only from confirmed scam conversations
- ✅ Scammer-shared identifiers
- ❌ No victim personal information
- ❌ No legitimate conversation data

**Compliance**:
- IT Act 2000 compliant
- HTTPS encrypted transmission
- Minimal data retention
- Environment-based secret management

---

## Code Quality

**Best Practices**:
✅ Type hints throughout  
✅ Comprehensive error handling  
✅ Structured logging  
✅ Environment-based configuration  
✅ No hardcoded credentials  
✅ Async/await for performance  
✅ Clean separation of concerns  

---

## Testing

**Automated**:
- Unit tests for keyword detection, extraction, session management
- Integration tests for conversation flows
- Stress testing: 60+ concurrent requests proven

**Manual**:
- 6 diverse scam types tested
- Edge cases covered
- Multi-language scenarios

---

## Impact & Vision

**Current Achievement**:
- Top 2% of 38,000+ participants nationwide
- Grand Finale at Bharat Mandapam, New Delhi
- Presented to national jury (MongoDB, AICTE, Government)
- 100% success rate during live evaluation

**Vision**:
- **6 months**: Pilot with banks, 10,000 conversations, ₹5-10 crores prevented
- **1 year**: Telecom integration, 100,000/month, ₹50+ crores prevented
- **2-3 years**: National deployment, multi-channel, ₹100+ crores prevented

**Social Impact**:
- Protect thousands of families from financial devastation
- Enable prosecution of repeat offenders
- Shift to proactive intelligence-driven prevention

---

## License

This project is provided for evaluation in the India AI Impact Buildathon 2026.  
All rights reserved by Team Techz.
---

## Contact

**Team**: Techz  
**Event**: India AI Impact Buildathon 2026 - Grand Finale  
**Venue**: Bharat Mandapam, New Delhi  

---

## Acknowledgments

- **HCL GUVI** - Buildathon organization
- **Google Gemini** - AI platform
- **Render.com** - Cloud hosting
- **India AI Summit 2026** - National platform

**"Built for real-world cybercrime intelligence impact."**

*Turning scammers into sources of their own downfall.*