"""
rate_limiter.py – IP-based rate limiting using DynamoDB.

OWASP Best Practice: Rate limit all public endpoints to prevent:
  - Denial of Service (DoS)
  - Brute force attacks
  - Resource exhaustion

Uses a sliding window counter stored in DynamoDB with TTL auto-cleanup.

Configuration (via environment variables):
  - RATE_LIMIT_MAX_REQUESTS: Max requests per window (default: 10)
  - RATE_LIMIT_WINDOW_SECONDS: Window duration in seconds (default: 60)
"""

import os
import time
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger("yojanasetu")

# ── Configuration ─────────────────────────────────────────────────
# SECURITY: Configurable via env vars, sensible defaults
MAX_REQUESTS = int(os.environ.get("RATE_LIMIT_MAX_REQUESTS", "10"))
WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_TABLE = os.environ.get("RATE_LIMIT_TABLE", "YojanaSetuRateLimit")

# Lazy-initialized DynamoDB resource
_dynamodb = None


def _get_table():
    """Get DynamoDB table resource (lazy init for Lambda cold start)."""
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb.Table(RATE_LIMIT_TABLE)


def check_rate_limit(ip_address):
    """
    Check if the given IP address is within rate limits.

    Uses a counter in DynamoDB that tracks requests per IP per window.
    Records auto-expire via DynamoDB TTL (no manual cleanup needed).

    Args:
        ip_address: Client IP address string

    Returns:
        dict: {
            "allowed": bool,
            "remaining": int (requests remaining in window),
            "retry_after": int (seconds to wait, if rate limited),
        }
    """
    if not ip_address or ip_address == "unknown":
        # SECURITY: If we can't identify the IP, allow but log
        logger.warning("Rate limit check with unknown IP – allowing with caution")
        return {"allowed": True, "remaining": MAX_REQUESTS}

    try:
        table = _get_table()
        current_time = int(time.time())
        window_start = current_time - WINDOW_SECONDS
        expires_at = current_time + WINDOW_SECONDS  # TTL for auto-cleanup

        # Atomic increment with conditional check
        response = table.update_item(
            Key={"IpAddress": ip_address},
            UpdateExpression=(
                "SET RequestCount = if_not_exists(RequestCount, :zero) + :one, "
                "WindowStart = if_not_exists(WindowStart, :now), "
                "ExpiresAt = :expires"
            ),
            ExpressionAttributeValues={
                ":zero": 0,
                ":one": 1,
                ":now": current_time,
                ":expires": expires_at,
            },
            ReturnValues="ALL_NEW",
        )

        attrs = response.get("Attributes", {})
        request_count = int(attrs.get("RequestCount", 1))
        window_start_stored = int(attrs.get("WindowStart", current_time))

        # Check if window has expired – reset if so
        if window_start_stored < window_start:
            # Window expired, reset counter
            table.update_item(
                Key={"IpAddress": ip_address},
                UpdateExpression=(
                    "SET RequestCount = :one, "
                    "WindowStart = :now, "
                    "ExpiresAt = :expires"
                ),
                ExpressionAttributeValues={
                    ":one": 1,
                    ":now": current_time,
                    ":expires": expires_at,
                },
            )
            return {"allowed": True, "remaining": MAX_REQUESTS - 1}

        # Check if over limit
        if request_count > MAX_REQUESTS:
            retry_after = WINDOW_SECONDS - (current_time - window_start_stored)
            retry_after = max(retry_after, 1)

            logger.info(
                f"Rate limit exceeded for IP (masked). "
                f"Count: {request_count}/{MAX_REQUESTS}"
            )

            return {
                "allowed": False,
                "remaining": 0,
                "retry_after": retry_after,
            }

        return {
            "allowed": True,
            "remaining": MAX_REQUESTS - request_count,
        }

    except ClientError as e:
        # SECURITY: On DynamoDB error, allow the request but log
        # (fail-open to prevent service disruption, monitor via CloudWatch)
        logger.error(f"Rate limiter DynamoDB error: {e.response['Error']['Code']}")
        return {"allowed": True, "remaining": MAX_REQUESTS}

    except Exception as e:
        logger.error(f"Rate limiter error: {str(e)}")
        return {"allowed": True, "remaining": MAX_REQUESTS}
