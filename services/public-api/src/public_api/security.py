from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone


def body_sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def sign_ingest_request(*, secret: str, timestamp: str, nonce: str, idempotency_key: str, body: bytes) -> str:
    signing_text = f"{timestamp}\n{nonce}\n{idempotency_key}\n{body_sha256(body)}"
    return hmac.new(secret.encode("utf-8"), signing_text.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_signature(*, secret: str, timestamp: str, nonce: str, idempotency_key: str, body: bytes, signature: str) -> bool:
    expected = sign_ingest_request(
        secret=secret,
        timestamp=timestamp,
        nonce=nonce,
        idempotency_key=idempotency_key,
        body=body,
    )
    return hmac.compare_digest(expected, signature)


def timestamp_age_seconds(timestamp: str) -> float:
    try:
        if timestamp.isdigit():
            dt = datetime.fromtimestamp(int(timestamp), timezone.utc)
        else:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    now = datetime.now(timezone.utc)
    return abs((now - dt.astimezone(timezone.utc)).total_seconds())
