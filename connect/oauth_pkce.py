#!/usr/bin/env python3
"""
connect/oauth_pkce.py — OAuth 2.1 PKCE helper for Connect (Phase 3C).

Pattern source (reimplemented fresh, no code copied): modelcontextprotocol
authorization spec (OAuth 2.1 + PKCE mandatory for public clients) and
RFC 7636. Pure functions over stdlib crypto — no tokens are stored here,
no network calls are made here. Connect composes these; the human runs the
browser leg of the flow (HERMES never impersonates a user agent).

S256 only. RFC 7636 §4.2 allows a 'plain' method; it exists for clients
that cannot hash, which is not us — offering it would only be a downgrade
path, so it has no code path here (same philosophy as the Chinese-API
exclusion: absent, not disabled).

CLI:
    python3 connect/oauth_pkce.py new
    python3 connect/oauth_pkce.py challenge <verifier>
"""
import base64
import hashlib
import json
import secrets
import sys
from urllib.parse import urlencode

VERIFIER_BYTES = 64  # -> 86 urlsafe chars, inside RFC 7636's 43..128 window


def _b64url(data: bytes) -> str:
    """base64url without padding — RFC 7636 appendix A."""
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def new_verifier() -> str:
    return _b64url(secrets.token_bytes(VERIFIER_BYTES))


def challenge_s256(verifier: str) -> str:
    return _b64url(hashlib.sha256(verifier.encode("ascii")).digest())


def new_pair() -> dict:
    verifier = new_verifier()
    return {"code_verifier": verifier,
            "code_challenge": challenge_s256(verifier),
            "code_challenge_method": "S256"}


def authorization_url(auth_endpoint: str, client_id: str, redirect_uri: str,
                      challenge: str, scope: str = "", state: str = None) -> str:
    """The URL the HUMAN opens in their browser. state defaults to a fresh
    random value — callers that pass their own must also verify it on the
    way back (CSRF protection is only as good as the check)."""
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state or _b64url(secrets.token_bytes(16)),
    }
    if scope:
        params["scope"] = scope
    return f"{auth_endpoint}?{urlencode(params)}"


def token_request_body(token_endpoint: str, client_id: str, redirect_uri: str,
                       code: str, verifier: str) -> dict:
    """Payload for the authorization-code exchange. Returned as data for the
    caller to POST (Connect owns transport + TLS policy, not this module)."""
    return {
        "url": token_endpoint,
        "body": {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "code_verifier": verifier,
        },
    }


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "new":
        print(json.dumps(new_pair(), indent=2))
    elif len(sys.argv) >= 3 and sys.argv[1] == "challenge":
        print(json.dumps({"code_challenge": challenge_s256(sys.argv[2]),
                          "code_challenge_method": "S256"}, indent=2))
    else:
        print("usage: oauth_pkce.py new | challenge <verifier>", file=sys.stderr)
        sys.exit(2)
