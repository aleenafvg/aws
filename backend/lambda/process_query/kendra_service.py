"""
kendra_service.py – Amazon Kendra integration for RAG retrieval.

Queries the Kendra index with English-optimized search terms to
retrieve relevant government scheme passages.

SECURITY: Kendra Index ID is configured via environment variable.
"""

import os
import json
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger("yojanasetu")

# ── Configuration ─────────────────────────────────────────────────
KENDRA_INDEX_ID = os.environ.get("KENDRA_INDEX_ID", "")

# Maximum number of results to retrieve
MAX_RESULTS = 5

# Lazy-initialized client
_kendra_client = None


def _get_kendra():
    global _kendra_client
    if _kendra_client is None:
        _kendra_client = boto3.client("kendra")
    return _kendra_client


def query_kendra(english_query):
    """
    Query Amazon Kendra for relevant government scheme information.

    Uses the Kendra Retrieve API for semantic retrieval,
    falling back to the Query API if Retrieve is unavailable.

    Args:
        english_query: Optimized English search terms

    Returns:
        dict: {
            "passages": list[str],     # Relevant text passages
            "scheme_id": str or None,  # Best matching scheme identifier
        }
    """
    if not KENDRA_INDEX_ID or KENDRA_INDEX_ID == "PLACEHOLDER_KENDRA_INDEX_ID":
        logger.warning("Kendra index not configured – returning empty results")
        return {
            "passages": [
                "Government scheme information is being set up. "
                "Please try again later or contact your local government office."
            ],
            "scheme_id": None,
        }

    kendra = _get_kendra()

    try:
        # ── Try Retrieve API first (semantic retrieval) ───────────
        return _retrieve_from_kendra(kendra, english_query)

    except ClientError as e:
        error_code = e.response["Error"]["Code"]

        if error_code == "ValidationException":
            # Retrieve API may not be available; fallback to Query API
            logger.info("Kendra Retrieve unavailable, falling back to Query API")
            return _query_from_kendra(kendra, english_query)

        logger.error(f"Kendra error: {error_code}")
        raise RuntimeError("Scheme retrieval service error")

    except Exception as e:
        logger.error(f"Kendra query failed: {str(e)}")
        raise RuntimeError("Scheme retrieval service error")


def _retrieve_from_kendra(kendra, query_text):
    """
    Use Kendra Retrieve API for passage-level retrieval.

    Returns top passages ranked by relevance.
    """
    response = kendra.retrieve(
        IndexId=KENDRA_INDEX_ID,
        QueryText=query_text,
        PageSize=MAX_RESULTS,
    )

    passages = []
    scheme_id = None

    for result in response.get("ResultItems", []):
        content = result.get("Content", "").strip()
        if content:
            passages.append(content)

        # Extract scheme ID from document attributes if available
        doc_attrs = result.get("DocumentAttributes", [])
        for attr in doc_attrs:
            if attr.get("Key") in ("scheme_id", "SchemeID", "_source_uri"):
                if not scheme_id:
                    value = attr.get("Value", {})
                    scheme_id = (
                        value.get("StringValue")
                        or value.get("StringListValue", [None])[0]
                    )

        # Try to extract scheme ID from document title
        if not scheme_id:
            doc_title = result.get("DocumentTitle", "")
            if doc_title:
                scheme_id = _extract_scheme_id(doc_title)

    return {
        "passages": passages,
        "scheme_id": scheme_id,
    }


def _query_from_kendra(kendra, query_text):
    """
    Fallback: Use Kendra Query API (returns answer + document excerpts).
    """
    response = kendra.query(
        IndexId=KENDRA_INDEX_ID,
        QueryText=query_text,
        PageSize=MAX_RESULTS,
    )

    passages = []
    scheme_id = None

    for result in response.get("ResultItems", []):
        result_type = result.get("Type", "")

        if result_type == "ANSWER":
            # Direct answer from Kendra
            answer_text = (
                result.get("AdditionalAttributes", [{}])[0]
                .get("Value", {})
                .get("TextWithHighlightsValue", {})
                .get("Text", "")
            )
            if answer_text:
                passages.insert(0, answer_text)

        elif result_type in ("DOCUMENT", "QUESTION_ANSWER"):
            excerpt = (
                result.get("DocumentExcerpt", {})
                .get("Text", "")
                .strip()
            )
            if excerpt:
                passages.append(excerpt)

        # Extract scheme ID
        doc_title = result.get("DocumentTitle", {}).get("Text", "")
        if doc_title and not scheme_id:
            scheme_id = _extract_scheme_id(doc_title)

    return {
        "passages": passages[:MAX_RESULTS],
        "scheme_id": scheme_id,
    }


def _extract_scheme_id(title):
    """
    Attempt to extract a scheme identifier from a document title.

    Common patterns:
      - "PM-KISAN-2024"
      - "KCC-Scheme-2024"
      - "MGNREGA-Guidelines"
    """
    if not title:
        return None

    # Simple heuristic: use the title itself as scheme ID if it looks like one
    import re
    match = re.search(r'[A-Z]{2,}[-\s][A-Za-z]+-?\d{0,4}', title)
    if match:
        return match.group(0).strip()

    # Fallback: use first 50 chars of title
    clean_title = title.strip()[:50]
    return clean_title if clean_title else None
