from __future__ import annotations

from public_api.security import sign_ingest_request, verify_signature


def test_hmac_signature_roundtrip() -> None:
    body = b'{"idempotency_key":"event:1:v1"}'
    signature = sign_ingest_request(
        secret="secret",
        timestamp="1760000000",
        nonce="nonce-1",
        idempotency_key="event:1:v1",
        body=body,
    )

    assert verify_signature(
        secret="secret",
        timestamp="1760000000",
        nonce="nonce-1",
        idempotency_key="event:1:v1",
        body=body,
        signature=signature,
    )
    assert not verify_signature(
        secret="secret",
        timestamp="1760000000",
        nonce="nonce-1",
        idempotency_key="event:2:v1",
        body=body,
        signature=signature,
    )
