"""
dynamo_service.py – DynamoDB interaction logging.

Logs each voice query interaction to the GlobalInteractions table
for analytics and auditing.

Table Schema (per PRD):
  - SessionId (PK): Unique session identifier
  - Timestamp (SK): ISO 8601 timestamp
  - DetectedLanguage: Language code
  - TranscriptNative: User's speech in native language
  - TranscriptEnglishMeta: Translated English query
  - SchemeID: Matched government scheme
  - AudioInputKey: S3 key for user's audio
  - AudioOutputKey: S3 key for response audio
  - ConfidenceScore: Language detection confidence

SECURITY: No PII beyond the speech transcript (which is needed for service).
Audio files are auto-deleted via S3 lifecycle rules.
"""

import os
import logging
from decimal import Decimal
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger("yojanasetu")

# ── Configuration ─────────────────────────────────────────────────
INTERACTIONS_TABLE = os.environ.get("INTERACTIONS_TABLE", "GlobalInteractions")

# Lazy-initialized resource
_dynamodb = None


def _get_table():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb.Table(INTERACTIONS_TABLE)


def log_interaction(
    session_id,
    timestamp,
    detected_language,
    transcript_native,
    transcript_english,
    scheme_id,
    audio_input_key,
    audio_output_key,
    confidence_score,
):
    """
    Log an interaction to the GlobalInteractions DynamoDB table.

    This is a fire-and-forget operation – failures are logged but
    do not interrupt the main response flow.

    Args:
        session_id: Unique session ID (partition key)
        timestamp: ISO 8601 timestamp (sort key)
        detected_language: Language code (e.g., "hi-IN")
        transcript_native: Native language transcript
        transcript_english: English translation of the query
        scheme_id: Matched scheme ID (or None)
        audio_input_key: S3 key for input audio
        audio_output_key: S3 key for output audio
        confidence_score: Language detection confidence (0-1)
    """
    try:
        table = _get_table()

        item = {
            "SessionId": session_id,
            "Timestamp": timestamp,
            "DetectedLanguage": detected_language or "unknown",
            "TranscriptNative": _truncate(transcript_native, 1000),
            "TranscriptEnglishMeta": _truncate(transcript_english, 500),
            "SchemeID": scheme_id or "unmatched",
            "AudioInputKey": audio_input_key or "",
            "AudioOutputKey": audio_output_key or "",
            # DynamoDB doesn't support float – use Decimal
            "ConfidenceScore": Decimal(str(round(confidence_score, 4))),
        }

        table.put_item(Item=item)
        logger.info(f"[{session_id}] Interaction logged to DynamoDB")

    except ClientError as e:
        # Log but don't fail the response – analytics are non-critical
        logger.error(
            f"[{session_id}] DynamoDB log failed: "
            f"{e.response['Error']['Code']}: {e.response['Error']['Message']}"
        )

    except Exception as e:
        logger.error(f"[{session_id}] DynamoDB log error: {str(e)}")


def _truncate(text, max_length):
    """
    Truncate text to max_length to prevent oversized DynamoDB items.
    DynamoDB items have a 400KB limit; we cap individual fields.
    """
    if not isinstance(text, str):
        return ""
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text
