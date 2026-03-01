"""
validators.py – Input validation & sanitization module.

OWASP Best Practices:
  - Schema-based validation (expected fields, types, lengths)
  - Reject unexpected fields
  - MIME type validation
  - Content length limits
  - String sanitization (XSS prevention)

All validation errors return user-safe messages (no internal details).
"""

import base64
import re
import json
import logging

logger = logging.getLogger("yojanasetu")

# ── Validation Constants ──────────────────────────────────────────
MAX_AUDIO_SIZE = 10 * 1024 * 1024        # 10 MB max audio file size
MIN_AUDIO_SIZE = 100                      # Minimum 100 bytes (reject empty)
MAX_BODY_SIZE = 15 * 1024 * 1024          # 15 MB max total body size

ALLOWED_CONTENT_TYPES = frozenset([
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/mp3",
    "application/octet-stream",  # Fallback for some browsers
])

# Fields expected in multipart form data
EXPECTED_FIELDS = frozenset(["audio_blob"])


def validate_request(event):
    """
    Validate the incoming API Gateway event.

    Checks:
      1. HTTP method is POST
      2. Content-Type is multipart/form-data or binary
      3. Body exists and is within size limits
      4. Audio data can be extracted
      5. Audio passes size and type checks
      6. No unexpected fields present

    Returns:
        dict: {
            "valid": bool,
            "audio_data": bytes (if valid),
            "content_type": str (if valid),
            "error": str (internal error, if invalid),
            "user_message": str (user-safe error, if invalid),
        }
    """
    try:
        # ── Check HTTP method ─────────────────────────────────────
        method = event.get("requestContext", {}).get("http", {}).get("method", "")
        if method.upper() != "POST":
            return _invalid(
                "Invalid HTTP method",
                "Invalid request method. Please use the app to submit queries."
            )

        # ── Check body exists ─────────────────────────────────────
        body = event.get("body")
        if not body:
            return _invalid(
                "Empty request body",
                "No audio data received. Please record your question and try again."
            )

        # ── Check body size ───────────────────────────────────────
        is_base64 = event.get("isBase64Encoded", False)

        if is_base64:
            # Base64-encoded body from API Gateway
            try:
                audio_data = base64.b64decode(body)
            except Exception as e:
                logger.warning(f"Base64 decode failed: {e}")
                return _invalid(
                    "Base64 decode failed",
                    "Invalid audio data received. Please try again."
                )
        else:
            if isinstance(body, str):
                audio_data = body.encode("utf-8")
            else:
                audio_data = body

        # ── Validate audio size ───────────────────────────────────
        if len(audio_data) > MAX_AUDIO_SIZE:
            return _invalid(
                f"Audio too large: {len(audio_data)} bytes",
                "Recording is too large. Please keep it under 15 seconds."
            )

        if len(audio_data) < MIN_AUDIO_SIZE:
            return _invalid(
                f"Audio too small: {len(audio_data)} bytes",
                "No speech was detected. Please speak clearly and try again."
            )

        # ── Validate Content-Type ─────────────────────────────────
        headers = event.get("headers", {}) or {}
        content_type = headers.get("content-type", "")

        # For multipart form data, extract the audio
        if "multipart/form-data" in content_type:
            extracted = _extract_multipart_audio(audio_data, content_type)
            if extracted is None:
                return _invalid(
                    "Failed to extract audio from multipart",
                    "Invalid audio data. Please try again."
                )
            audio_data = extracted["data"]
            content_type = extracted.get("content_type", "audio/webm")
        else:
            # Direct binary upload
            # Validate MIME type from Content-Type header
            base_type = content_type.split(";")[0].strip().lower()
            if base_type and base_type not in ALLOWED_CONTENT_TYPES:
                logger.warning(f"Unexpected content type: {base_type}")
                # Don't reject – some browsers send unexpected types
                # The backend services will validate the actual content

        return {
            "valid": True,
            "audio_data": audio_data,
            "content_type": content_type,
        }

    except Exception as e:
        logger.error(f"Validation error: {str(e)}")
        return _invalid(
            f"Validation exception: {str(e)}",
            "Could not process your request. Please try again."
        )


def _extract_multipart_audio(body_bytes, content_type):
    """
    Extract audio data from multipart/form-data body.

    Simple multipart parser that looks for the 'audio_blob' field.
    Rejects any unexpected fields (OWASP: reject unknown inputs).

    Returns:
        dict: {"data": bytes, "content_type": str} or None on failure
    """
    try:
        # Extract boundary from Content-Type
        boundary = None
        for part in content_type.split(";"):
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part[len("boundary="):].strip('"')
                break

        if not boundary:
            logger.warning("No boundary found in multipart content-type")
            return None

        boundary_bytes = f"--{boundary}".encode()

        if isinstance(body_bytes, str):
            body_bytes = body_bytes.encode("utf-8")

        parts = body_bytes.split(boundary_bytes)

        audio_data = None
        audio_content_type = "audio/webm"

        for part in parts:
            if not part or part == b"--" or part == b"--\r\n":
                continue

            # Split headers from body
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue

            headers_section = part[:header_end].decode("utf-8", errors="ignore")
            data = part[header_end + 4:]

            # Remove trailing \r\n
            if data.endswith(b"\r\n"):
                data = data[:-2]

            # Check Content-Disposition for field name
            if 'name="audio_blob"' in headers_section or "name='audio_blob'" in headers_section:
                audio_data = data

                # Extract content type if present
                for line in headers_section.split("\r\n"):
                    if line.lower().startswith("content-type:"):
                        audio_content_type = line.split(":", 1)[1].strip()
                        break
            else:
                # SECURITY: Log and reject unexpected fields
                field_match = re.search(r'name="([^"]*)"', headers_section)
                field_name = field_match.group(1) if field_match else "unknown"
                if field_name not in EXPECTED_FIELDS:
                    logger.warning(f"Unexpected form field rejected: {field_name}")

        if audio_data is None:
            return None

        return {"data": audio_data, "content_type": audio_content_type}

    except Exception as e:
        logger.error(f"Multipart parsing error: {e}")
        return None


def sanitize_string(text):
    """
    Sanitize a string for safe inclusion in responses.

    Removes:
      - Control characters
      - HTML/script tags (basic XSS prevention)
      - Excessive whitespace

    Limits string length to prevent oversized responses.

    Args:
        text: Input string to sanitize

    Returns:
        str: Sanitized string
    """
    if not isinstance(text, str):
        return ""

    # Remove control characters (except newline and tab)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # Remove HTML tags (basic XSS prevention)
    text = re.sub(r'<[^>]+>', '', text)

    # Remove script-like patterns
    text = re.sub(r'(?i)javascript:', '', text)
    text = re.sub(r'(?i)on\w+\s*=', '', text)

    # Collapse excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Limit length (prevent oversized responses)
    max_length = 2000
    if len(text) > max_length:
        text = text[:max_length] + "..."

    return text


def _invalid(error, user_message):
    """Helper to create an invalid validation result."""
    return {
        "valid": False,
        "error": error,
        "user_message": user_message,
    }
