from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from urllib.parse import quote, urlparse


def build_oauth1_header(
    *,
    method: str,
    url: str,
    consumer_key: str,
    consumer_secret: str,
    token: str,
    token_secret: str,
) -> str:
    oauth_params = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": secrets.token_urlsafe(24),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": token,
        "oauth_version": "1.0",
    }
    base_url = _normalized_base_url(url)
    parameter_string = _parameter_string(oauth_params)
    signature_base = "&".join(
        [
            method.upper(),
            _percent_encode(base_url),
            _percent_encode(parameter_string),
        ]
    )
    signing_key = f"{_percent_encode(consumer_secret)}&{_percent_encode(token_secret)}"
    signature = base64.b64encode(
        hmac.new(signing_key.encode(), signature_base.encode(), hashlib.sha1).digest()
    ).decode()
    oauth_params["oauth_signature"] = signature
    header_params = ", ".join(
        f'{_percent_encode(key)}="{_percent_encode(value)}"' for key, value in sorted(oauth_params.items())
    )
    return f"OAuth {header_params}"


def _normalized_base_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower() if parsed.hostname else ""
    port = ""
    if parsed.port and not ((scheme == "http" and parsed.port == 80) or (scheme == "https" and parsed.port == 443)):
        port = f":{parsed.port}"
    return f"{scheme}://{host}{port}{parsed.path or '/'}"


def _parameter_string(params: dict[str, str]) -> str:
    return "&".join(f"{_percent_encode(key)}={_percent_encode(value)}" for key, value in sorted(params.items()))


def _percent_encode(value: str) -> str:
    return quote(str(value), safe="~-._")
