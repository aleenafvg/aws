"""
transcribe_service.py – Amazon Transcribe integration.

Handles:
  1. Audio upload to S3
  2. Transcription job with automatic language identification
  3. Polling for completion with retry logic
  4. Result extraction (transcript + language + confidence)

Supported languages (per PRD):
  hi-IN, ta-IN, te-IN, mr-IN, bn-IN, gu-IN, kn-IN, ml-IN, pa-IN, en-IN
"""

import os
import time
import json
import logging
import uuid
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger("yojanasetu")

# ── Configuration ─────────────────────────────────────────────────
AUDIO_INPUT_BUCKET = os.environ.get("AUDIO_INPUT_BUCKET", "")

# Supported languages for automatic identification
SUPPORTED_LANGUAGES = [
    "hi-IN", "ta-IN", "te-IN", "mr-IN", "bn-IN",
    "gu-IN", "kn-IN", "ml-IN", "pa-IN", "en-IN",
]

# Retry configuration
MAX_POLL_ATTEMPTS = 60       # Maximum polling attempts
POLL_INTERVAL_SECONDS = 2    # Seconds between polls

# Clients (lazy init)
_s3_client = None
_transcribe_client = None


def _get_s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def _get_transcribe():
    global _transcribe_client
    if _transcribe_client is None:
        _transcribe_client = boto3.client("transcribe")
    return _transcribe_client


def transcribe_audio(audio_data, audio_key, session_id):
    """
    Transcribe audio using Amazon Transcribe with automatic language detection.

    Steps:
      1. Upload audio bytes to S3
      2. Start Transcribe job with IdentifyLanguage=True
      3. Poll until completion
      4. Parse and return results

    Args:
        audio_data: Raw audio bytes
        audio_key: S3 key for storing the audio
        session_id: Session ID for job naming

    Returns:
        dict: {
            "transcript": str,
            "language_code": str,  (e.g., "hi-IN")
            "confidence": float,   (0.0 to 1.0)
        }

    Raises:
        RuntimeError: On transcription failure after retries
    """
    s3 = _get_s3()
    transcribe = _get_transcribe()

    # ── Step 1: Upload audio to S3 ────────────────────────────────
    try:
        s3.put_object(
            Bucket=AUDIO_INPUT_BUCKET,
            Key=audio_key,
            Body=audio_data,
            ContentType="audio/webm",
            # SECURITY: Server-side encryption
            ServerSideEncryption="aws:kms",
        )
        logger.info(f"[{session_id}] Audio uploaded to S3: {audio_key}")
    except ClientError as e:
        logger.error(f"[{session_id}] S3 upload failed: {e}")
        raise RuntimeError("Failed to upload audio for processing")

    # ── Step 2: Start Transcribe job ──────────────────────────────
    job_name = f"yojanasetu-{session_id}-{uuid.uuid4().hex[:8]}"
    media_uri = f"s3://{AUDIO_INPUT_BUCKET}/{audio_key}"

    try:
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={"MediaFileUri": media_uri},
            # Automatic language identification (no manual selection)
            IdentifyLanguage=True,
            LanguageOptions=SUPPORTED_LANGUAGES,
            MediaFormat="webm",
            Settings={
                "ShowSpeakerLabels": False,
                "ChannelIdentification": False,
            },
        )
        logger.info(f"[{session_id}] Transcription job started: {job_name}")
    except ClientError as e:
        logger.error(f"[{session_id}] Transcribe start failed: {e}")
        raise RuntimeError("Failed to start speech transcription")

    # ── Step 3: Poll for completion with retry ────────────────────
    for attempt in range(MAX_POLL_ATTEMPTS):
        time.sleep(POLL_INTERVAL_SECONDS)

        try:
            response = transcribe.get_transcription_job(
                TranscriptionJobName=job_name
            )
            status = response["TranscriptionJob"]["TranscriptionJobStatus"]

            if status == "COMPLETED":
                logger.info(f"[{session_id}] Transcription completed (attempt {attempt + 1})")
                return _parse_transcription_result(response, session_id)

            elif status == "FAILED":
                reason = response["TranscriptionJob"].get("FailureReason", "Unknown")
                logger.error(f"[{session_id}] Transcription failed: {reason}")
                raise RuntimeError(f"Transcription failed: {reason}")

            # IN_PROGRESS – continue polling
            logger.debug(f"[{session_id}] Transcription in progress (attempt {attempt + 1})")

        except ClientError as e:
            logger.warning(f"[{session_id}] Poll error (attempt {attempt + 1}): {e}")
            if attempt >= MAX_POLL_ATTEMPTS - 1:
                raise RuntimeError("Transcription polling failed after max retries")
            # Retry with backoff
            time.sleep(min(attempt * 2, 10))

    raise RuntimeError("Transcription timed out")


def _parse_transcription_result(response, session_id):
    """
    Parse Amazon Transcribe job result.

    Extracts transcript text, detected language code, and confidence score.

    Returns:
        dict: {"transcript": str, "language_code": str, "confidence": float}
    """
    job = response["TranscriptionJob"]

    # Extract detected language
    language_code = job.get("LanguageCode", "en-IN")
    confidence = 0.0

    # Get language identification results for confidence score
    language_codes = job.get("LanguageCodes", [])
    if language_codes:
        # Find the detected language's confidence
        for lang in language_codes:
            if lang.get("LanguageCode") == language_code:
                confidence = lang.get("Score", 0.0)
                break
        # If not found, use the highest confidence
        if confidence == 0.0:
            top = max(language_codes, key=lambda x: x.get("Score", 0))
            language_code = top.get("LanguageCode", language_code)
            confidence = top.get("Score", 0.0)

    # Fetch transcript from S3 (Transcribe stores results as JSON in S3)
    transcript_uri = job.get("Transcript", {}).get("TranscriptFileUri", "")
    transcript_text = ""

    if transcript_uri:
        try:
            # Download transcript JSON from the URI
            import urllib.request
            with urllib.request.urlopen(transcript_uri) as resp:
                transcript_json = json.loads(resp.read().decode("utf-8"))
                results = transcript_json.get("results", {})
                transcripts = results.get("transcripts", [])
                if transcripts:
                    transcript_text = transcripts[0].get("transcript", "")
        except Exception as e:
            logger.error(f"[{session_id}] Failed to fetch transcript: {e}")

    if not transcript_text:
        logger.warning(f"[{session_id}] Empty transcript returned")
        raise RuntimeError("No speech could be recognized. Please try again.")

    return {
        "transcript": transcript_text,
        "language_code": language_code,
        "confidence": round(confidence, 2),
    }
