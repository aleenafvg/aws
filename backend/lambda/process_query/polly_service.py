"""
polly_service.py – Amazon Polly Text-to-Speech integration.

Converts AI-generated text to speech in the detected Indian language.

Features:
  - Language → voice auto-mapping for all 10 supported languages
  - Neural voice preferred, Standard fallback
  - Output stored in S3 with presigned URL for client access
  - MP3 format for broad compatibility on low-end devices

SECURITY: Audio output bucket and URLs configured via environment variables.
"""

import os
import json
import logging
import uuid
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger("yojanasetu")

# ── Configuration ─────────────────────────────────────────────────
AUDIO_OUTPUT_BUCKET = os.environ.get("AUDIO_OUTPUT_BUCKET", "")

# Presigned URL expiration (1 hour – enough time for playback)
PRESIGNED_URL_EXPIRY = 3600

# ── Language → Voice Mapping ──────────────────────────────────────
# Each entry: (Neural voice ID, Standard fallback, Engine preference)
# Polly voice availability varies by language; this maps the best option.
VOICE_MAP = {
    "hi-IN": {
        "neural": "Kajal",       # Hindi Neural voice
        "standard": "Aditi",     # Hindi Standard voice
        "engine": "neural",
    },
    "en-IN": {
        "neural": "Kajal",       # English (Indian) Neural
        "standard": "Aditi",     # English (Indian) Standard
        "engine": "neural",
    },
    "ta-IN": {
        "neural": None,
        "standard": None,
        "engine": "standard",
        "fallback_lang": "en-IN",  # Fallback to English if no Tamil voice
        "fallback_voice": "Kajal",
        "fallback_engine": "neural",
    },
    "te-IN": {
        "neural": None,
        "standard": None,
        "engine": "standard",
        "fallback_lang": "en-IN",
        "fallback_voice": "Kajal",
        "fallback_engine": "neural",
    },
    "mr-IN": {
        "neural": None,
        "standard": None,
        "engine": "standard",
        "fallback_lang": "hi-IN",
        "fallback_voice": "Kajal",
        "fallback_engine": "neural",
    },
    "bn-IN": {
        "neural": None,
        "standard": None,
        "engine": "standard",
        "fallback_lang": "en-IN",
        "fallback_voice": "Kajal",
        "fallback_engine": "neural",
    },
    "gu-IN": {
        "neural": None,
        "standard": None,
        "engine": "standard",
        "fallback_lang": "hi-IN",
        "fallback_voice": "Kajal",
        "fallback_engine": "neural",
    },
    "kn-IN": {
        "neural": None,
        "standard": None,
        "engine": "standard",
        "fallback_lang": "en-IN",
        "fallback_voice": "Kajal",
        "fallback_engine": "neural",
    },
    "ml-IN": {
        "neural": None,
        "standard": None,
        "engine": "standard",
        "fallback_lang": "en-IN",
        "fallback_voice": "Kajal",
        "fallback_engine": "neural",
    },
    "pa-IN": {
        "neural": None,
        "standard": None,
        "engine": "standard",
        "fallback_lang": "hi-IN",
        "fallback_voice": "Kajal",
        "fallback_engine": "neural",
    },
}

# Lazy-initialized clients
_polly_client = None
_s3_client = None


def _get_polly():
    global _polly_client
    if _polly_client is None:
        _polly_client = boto3.client("polly")
    return _polly_client


def _get_s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def synthesize_speech(text, language_code, session_id):
    """
    Convert text to speech using Amazon Polly.

    Attempts Neural engine first, falls back to Standard.
    If no voice is available for the language, uses a fallback language.
    Stores the audio in S3 and returns a presigned URL.

    Args:
        text: Text to synthesize (in the target language)
        language_code: Target language code (e.g., "hi-IN")
        session_id: Session ID for S3 key naming

    Returns:
        dict: {
            "url": str,   # Presigned S3 URL for the audio
            "key": str,   # S3 object key
        }

    Raises:
        RuntimeError: On synthesis failure
    """
    polly = _get_polly()
    s3 = _get_s3()

    voice_config = VOICE_MAP.get(language_code, VOICE_MAP["en-IN"])

    # ── Determine voice and engine ────────────────────────────────
    voice_id, engine, actual_lang = _resolve_voice(voice_config, language_code)

    logger.info(
        f"[{session_id}] Polly synthesis: voice={voice_id}, "
        f"engine={engine}, lang={actual_lang}"
    )

    # ── Synthesize speech ─────────────────────────────────────────
    try:
        response = polly.synthesize_speech(
            Text=text[:3000],  # Polly limit; our responses are <3 sentences anyway
            OutputFormat="mp3",
            VoiceId=voice_id,
            Engine=engine,
            LanguageCode=actual_lang,
        )
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.warning(f"[{session_id}] Polly neural failed ({error_code}), trying standard")

        # ── Fallback: try Standard engine ─────────────────────────
        try:
            fallback_voice = voice_config.get("standard") or voice_config.get("fallback_voice", "Kajal")
            fallback_lang = voice_config.get("fallback_lang", language_code)

            response = polly.synthesize_speech(
                Text=text[:3000],
                OutputFormat="mp3",
                VoiceId=fallback_voice,
                Engine="standard",
                LanguageCode=fallback_lang,
            )
        except ClientError as e2:
            logger.error(f"[{session_id}] Polly fallback also failed: {e2}")
            # Last resort: English neural
            response = polly.synthesize_speech(
                Text=text[:3000],
                OutputFormat="mp3",
                VoiceId="Kajal",
                Engine="neural",
                LanguageCode="en-IN",
            )

    # ── Upload audio to S3 ────────────────────────────────────────
    audio_stream = response["AudioStream"].read()
    output_key = f"outputs/{session_id}/{uuid.uuid4().hex[:8]}.mp3"

    try:
        s3.put_object(
            Bucket=AUDIO_OUTPUT_BUCKET,
            Key=output_key,
            Body=audio_stream,
            ContentType="audio/mpeg",
            ServerSideEncryption="aws:kms",
        )
    except ClientError as e:
        logger.error(f"[{session_id}] S3 output upload failed: {e}")
        raise RuntimeError("Failed to store audio response")

    # ── Generate presigned URL ────────────────────────────────────
    try:
        presigned_url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": AUDIO_OUTPUT_BUCKET,
                "Key": output_key,
            },
            ExpiresIn=PRESIGNED_URL_EXPIRY,
        )
    except ClientError as e:
        logger.error(f"[{session_id}] Presigned URL generation failed: {e}")
        raise RuntimeError("Failed to generate audio URL")

    return {
        "url": presigned_url,
        "key": output_key,
    }


def _resolve_voice(voice_config, language_code):
    """
    Resolve the best voice, engine, and language code for synthesis.

    Priority:
      1. Neural voice in target language
      2. Standard voice in target language
      3. Fallback language voice

    Returns:
        tuple: (voice_id, engine, language_code)
    """
    # Try neural voice
    if voice_config.get("neural"):
        return (voice_config["neural"], "neural", language_code)

    # Try standard voice
    if voice_config.get("standard"):
        return (voice_config["standard"], "standard", language_code)

    # Use fallback
    fallback_voice = voice_config.get("fallback_voice", "Kajal")
    fallback_engine = voice_config.get("fallback_engine", "neural")
    fallback_lang = voice_config.get("fallback_lang", "en-IN")
    return (fallback_voice, fallback_engine, fallback_lang)
