"""
handler.py – Main Lambda entrypoint for Yojana-Setu.

Orchestrates the full multilingual voice query pipeline:
  1. Parse & validate multipart audio input
  2. Rate-limit check (IP-based)
  3. Upload audio to S3
  4. Transcribe audio (Amazon Transcribe + IdentifyLanguage)
  5. Translate query to English (Amazon Bedrock)
  6. Retrieve scheme context (Amazon Kendra)
  7. Generate answer in native language (Amazon Bedrock)
  8. Convert answer to speech (Amazon Polly)
  9. Log interaction (DynamoDB)
  10. Return JSON response

SECURITY:
  - All AWS credentials via IAM role (no hardcoded keys)
  - Input validation & sanitization on all user inputs
  - Rate limiting with graceful 429 responses
  - No internal error details exposed to client
  - CORS headers set via API Gateway (SAM template)
"""

import json
import os
import uuid
import logging
import traceback
from datetime import datetime, timezone

# Import service modules
from validators import validate_request, sanitize_string
from rate_limiter import check_rate_limit
from transcribe_service import transcribe_audio
from bedrock_service import translate_to_english, generate_response
from kendra_service import query_kendra
from polly_service import synthesize_speech
from dynamo_service import log_interaction

# ── Configuration from environment variables (SECURITY: no hardcoded values) ──
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Configure structured logging
logger = logging.getLogger("yojanasetu")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))


def lambda_handler(event, context):
    """
    Main Lambda handler for POST /api/process-multilingual-query.

    Expects multipart/form-data with 'audio_blob' field.
    Returns JSON response per API specification.

    OWASP considerations:
      - A1:Injection → Input validation via validators.py
      - A2:Auth → IAM role authentication, no exposed keys
      - A4:Insecure Design → Rate limiting, input size caps
      - A5:Misconfiguration → Environment-based config, least privilege IAM
      - A9:Logging → Structured logging, no PII in logs
    """
    session_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    logger.info(f"[{session_id}] Processing new query request")

    try:
        # ── Step 1: Extract client IP for rate limiting ────────────
        # SECURITY: Use X-Forwarded-For from API Gateway, fallback to source IP
        source_ip = _extract_client_ip(event)

        # ── Step 2: Rate limit check ──────────────────────────────
        rate_limit_result = check_rate_limit(source_ip)
        if not rate_limit_result["allowed"]:
            logger.warning(f"[{session_id}] Rate limited IP: {_mask_ip(source_ip)}")
            return _build_response(429, {
                "status": "error",
                "message": "Too many requests. Please wait and try again.",
            }, headers={
                "Retry-After": str(rate_limit_result.get("retry_after", 60))
            })

        # ── Step 3: Validate & extract audio ──────────────────────
        validation = validate_request(event)
        if not validation["valid"]:
            logger.warning(f"[{session_id}] Validation failed: {validation['error']}")
            return _build_response(400, {
                "status": "error",
                "message": validation["user_message"],
            })

        audio_data = validation["audio_data"]
        content_type = validation.get("content_type", "audio/webm")

        # ── Step 4: Upload audio to S3 ────────────────────────────
        audio_key = f"inputs/{session_id}/{timestamp}.webm"
        logger.info(f"[{session_id}] Uploading audio ({len(audio_data)} bytes)")

        # ── Step 5: Transcribe with language detection ────────────
        transcription = transcribe_audio(audio_data, audio_key, session_id)

        detected_language = transcription["language_code"]
        confidence_score = transcription["confidence"]
        transcript_native = transcription["transcript"]

        logger.info(
            f"[{session_id}] Detected language: {detected_language} "
            f"(confidence: {confidence_score:.2f})"
        )

        # ── Step 6: Translate to English search terms ─────────────
        english_query = translate_to_english(
            transcript_native, detected_language
        )
        logger.info(f"[{session_id}] English query: {sanitize_string(english_query[:100])}")

        # ── Step 7: Query Kendra for scheme context ───────────────
        kendra_results = query_kendra(english_query)
        context_passages = kendra_results.get("passages", [])
        scheme_id = kendra_results.get("scheme_id", None)

        logger.info(
            f"[{session_id}] Retrieved {len(context_passages)} passages"
            f"{f', scheme: {scheme_id}' if scheme_id else ''}"
        )

        # ── Step 8: Generate grounded response in native language ─
        ai_response = generate_response(
            native_transcript=transcript_native,
            english_query=english_query,
            context_passages=context_passages,
            target_language=detected_language,
        )

        # ── Step 9: Convert response to speech ───────────────────
        audio_output = synthesize_speech(
            text=ai_response,
            language_code=detected_language,
            session_id=session_id,
        )
        audio_response_url = audio_output["url"]

        # ── Step 10: Log interaction to DynamoDB ──────────────────
        log_interaction(
            session_id=session_id,
            timestamp=timestamp,
            detected_language=detected_language,
            transcript_native=transcript_native,
            transcript_english=english_query,
            scheme_id=scheme_id,
            audio_input_key=audio_key,
            audio_output_key=audio_output.get("key", ""),
            confidence_score=confidence_score,
        )

        # ── Step 11: Return success response ─────────────────────
        logger.info(f"[{session_id}] Query processed successfully")

        return _build_response(200, {
            "status": "success",
            "detected_language": detected_language,
            "detected_language_confidence": confidence_score,
            "user_intent_translated": sanitize_string(english_query),
            "ai_response_text_native": ai_response,
            "audio_response_url": audio_response_url,
            "relevant_scheme_id": scheme_id,
        })

    except Exception as e:
        # SECURITY: Log full error server-side, return generic message to client
        logger.error(f"[{session_id}] Unhandled error: {str(e)}")
        logger.debug(f"[{session_id}] Traceback: {traceback.format_exc()}")

        return _build_response(500, {
            "status": "error",
            "message": "An error occurred while processing your query. Please try again.",
        })


def _extract_client_ip(event):
    """
    Extract client IP address from API Gateway event.

    SECURITY: Checks X-Forwarded-For header (set by API Gateway),
    uses the leftmost (client) IP. Falls back to requestContext.
    """
    headers = event.get("headers", {}) or {}

    # X-Forwarded-For may contain multiple IPs: "client, proxy1, proxy2"
    xff = headers.get("x-forwarded-for", "")
    if xff:
        # INPUT VALIDATION: Take only the first IP, strip whitespace
        client_ip = xff.split(",")[0].strip()
        # Basic IP format validation
        if client_ip and len(client_ip) <= 45:  # Max IPv6 length
            return client_ip

    # Fallback to requestContext
    request_context = event.get("requestContext", {})
    http_info = request_context.get("http", {})
    return http_info.get("sourceIp", "unknown")


def _mask_ip(ip):
    """
    Mask IP address for logging (SECURITY: minimize PII in logs).
    Example: "192.168.1.100" → "192.168.x.x"
    """
    if not ip or ip == "unknown":
        return "unknown"
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.x.x"
    return "masked"


def _build_response(status_code, body, headers=None):
    """
    Build a standardized API response.

    SECURITY: Sets appropriate headers including:
    - Content-Type (prevent MIME sniffing)
    - Cache-Control (prevent caching of sensitive data)
    - X-Content-Type-Options (prevent MIME sniffing attacks)
    """
    response_headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    }

    if headers:
        response_headers.update(headers)

    return {
        "statusCode": status_code,
        "headers": response_headers,
        "body": json.dumps(body, ensure_ascii=False),
    }
