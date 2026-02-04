
import requests
import json

url = "https://scam-honeypot-ap8q.onrender.com/honeypot"

headers = {
    "x-api-key": "guvi_honeypot_secret_2026",
    "Content-Type": "application/json"
}

# Test 1: Timestamp as int (like GUVI sends)
print("TEST 1: Timestamp as integer")
print("="*60)

data1 = {
    "sessionId": "final-test-001",
    "message": {
        "sender": "scammer",
        "text": "URGENT! Your account blocked. Send ₹500 to verify.",
        "timestamp": 1770187265077  # Integer timestamp
    },
    "conversationHistory": []
}

response = requests.post(url, headers=headers, json=data1)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
print()

# Test 2: Follow-up message
print("TEST 2: Follow-up message")
print("="*60)

data2 = {
    "sessionId": "final-test-001",
    "message": {
        "sender": "scammer",
        "text": "Send to UPI: scammer@paytm. Call 9876543210 now!",
        "timestamp": 1770187275077
    },
    "conversationHistory": [
        {
            "sender": "scammer",
            "text": "URGENT! Your account blocked. Send ₹500 to verify.",
            "timestamp": 1770187265077
        },
        {
            "sender": "user",
            "text": "Oh no! What should I do?",
            "timestamp": 1770187270077
        }
    ]
}

response = requests.post(url, headers=headers, json=data2)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")