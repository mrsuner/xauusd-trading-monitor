from __future__ import annotations

from public_syncer.security import sign_ingest_request


def test_sign_ingest_request_is_stable() -> None:
    signature = sign_ingest_request(
        secret="secret",
        timestamp="1760000000",
        nonce="nonce-1",
        idempotency_key="event:abc:v1",
        body=b'{"a":1}',
    )

    assert signature == sign_ingest_request(
        secret="secret",
        timestamp="1760000000",
        nonce="nonce-1",
        idempotency_key="event:abc:v1",
        body=b'{"a":1}',
    )
    assert signature != sign_ingest_request(
        secret="secret",
        timestamp="1760000000",
        nonce="nonce-2",
        idempotency_key="event:abc:v1",
        body=b'{"a":1}',
    )
