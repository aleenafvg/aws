# Yojana-Setu – AI for Bharat 🇮🇳

> Voice-first, zero-typing AI assistant for rural Indian citizens to access government scheme information in any Indian language.

![License](https://img.shields.io/badge/license-MIT-blue)
![Platform](https://img.shields.io/badge/platform-AWS-orange)
![Languages](https://img.shields.io/badge/languages-10%20Indian%20languages-green)

---

## 🎯 What is Yojana-Setu?

Yojana-Setu is a **voice-first AI bridge** between government welfare schemes and rural citizens. It removes literacy and language barriers — users simply **speak their question** in any of 10 Indian languages and receive a spoken answer.

**No typing. No language selection. Just speak.**

## 🗣️ Supported Languages

Hindi · Tamil · Telugu · Marathi · Bengali · Gujarati · Kannada · Malayalam · Punjabi · English

## 🏗️ Architecture

```
User Voice → MediaRecorder → API Gateway → Lambda →
  ├── Amazon Transcribe (STT + Language Detection)
  ├── Amazon Bedrock (Query Translation)
  ├── Amazon Kendra (RAG Retrieval)
  ├── Amazon Bedrock (Grounded Response)
  └── Amazon Polly (TTS) → Audio Response → User
```

## 📁 Project Structure

```
├── frontend/                    # React + Vite + Tailwind PWA
│   ├── src/
│   │   ├── components/
│   │   │   ├── SplashScreen.jsx    # "1598" typewriter intro
│   │   │   ├── MainScreen.jsx      # Voice-first main interface
│   │   │   ├── MicButton.jsx       # Animated recording button
│   │   │   ├── ResponseCard.jsx    # Native language response
│   │   │   └── ErrorDisplay.jsx    # Graceful error handling
│   │   ├── hooks/
│   │   │   ├── useVoiceRecorder.js # MediaRecorder + VAD
│   │   │   └── useApi.js           # API client (no client-side keys)
│   │   └── utils/
│   │       └── audioUtils.js       # Format detection utilities
│   └── ...
├── backend/
│   ├── template.yaml              # AWS SAM infrastructure
│   └── lambda/process_query/
│       ├── handler.py              # Pipeline orchestrator
│       ├── validators.py           # Input validation (OWASP)
│       ├── rate_limiter.py         # DynamoDB rate limiter
│       ├── transcribe_service.py   # Amazon Transcribe
│       ├── bedrock_service.py      # Claude 3.5 Sonnet
│       ├── kendra_service.py       # RAG retrieval
│       ├── polly_service.py        # Text-to-Speech
│       └── dynamo_service.py       # Interaction logging
└── README.md
```

## 🚀 Quick Start

### Frontend (Development)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### Backend (Deploy to AWS)

```bash
cd backend
sam build
sam deploy --guided
```

Then set `VITE_API_URL` in the frontend to the API Gateway endpoint URL.

## 🔒 Security

| Measure | Implementation |
|---------|----------------|
| Rate Limiting | IP-based via DynamoDB (10 req/min default, 429 responses) |
| Input Validation | Schema-based: size, type, field whitelisting |
| API Key Handling | Environment variables only, zero client-side secrets |
| Encryption | S3 SSE-KMS, DynamoDB encryption at rest |
| Auto-Delete | S3 lifecycle rules (24h audio retention) |
| IAM | Least-privilege per-service policies |
| Headers | HSTS, X-Content-Type-Options, X-Frame-Options |

## 📊 API

**POST** `/api/process-multilingual-query`

**Input:** `multipart/form-data` with `audio_blob`

**Response:**
```json
{
  "status": "success",
  "detected_language": "ta-IN",
  "detected_language_confidence": 0.98,
  "user_intent_translated": "How to apply for crop loan?",
  "ai_response_text_native": "...",
  "audio_response_url": "https://s3...",
  "relevant_scheme_id": "KCC-Scheme-2024"
}
```

## 📋 Prerequisites

- Node.js 18+
- AWS CLI configured
- AWS SAM CLI
- AWS services enabled: Transcribe, Bedrock (Claude 3.5 Sonnet), Kendra, Polly

---

*Built with ❤️ for Bharat*
