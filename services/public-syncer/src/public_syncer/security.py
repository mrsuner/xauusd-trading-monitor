from __future__ import annotations

import hashlib
import hmac


def body_sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def sign_ingest_request(*, secret: str, timestamp: str, nonce: str, idempotency_key: str, body: bytes) -> str:
    signing_text = f"{timestamp}\n{nonce}\n{idempotency_key}\n{body_sha256(body)}"
    return hmac.new(secret.encode("utf-8"), signing_text.encode("utf-8"), hashlib.sha256).hexdigest()
