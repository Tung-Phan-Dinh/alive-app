"""
Apple Sign-In token verification with JWKS caching.
"""
import base64
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional
import httpx
from jose import jwt, jwk, JWTError
from jose.utils import base64url_decode
import json

from app.core.config import settings

logger = logging.getLogger(__name__)


class AppleJWKSCache:
    """In-memory cache for Apple's JWKS keys."""

    def __init__(self):
        self._keys: dict = {}
        self._fetched_at: float = 0
        self._cache_duration: int = settings.APPLE_JWKS_CACHE_HOURS * 3600

    def is_expired(self) -> bool:
        return time.time() - self._fetched_at > self._cache_duration

    async def fetch_keys(self, force: bool = False) -> dict:
        """Fetch JWKS from Apple. Uses cache unless expired or forced."""
        if not force and self._keys and not self.is_expired():
            return self._keys

        async with httpx.AsyncClient() as client:
            response = await client.get(
                settings.APPLE_JWKS_URL,
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()

        # Index keys by kid for fast lookup
        self._keys = {key["kid"]: key for key in data.get("keys", [])}
        self._fetched_at = time.time()
        return self._keys

    async def get_key(self, kid: str) -> Optional[dict]:
        """Get a specific key by kid, refreshing cache if not found."""
        keys = await self.fetch_keys()
        if kid in keys:
            return keys[kid]

        # Key not found - might be rotated, refresh once
        keys = await self.fetch_keys(force=True)
        return keys.get(kid)


# Global cache instance
_jwks_cache = AppleJWKSCache()


class AppleAuthError(Exception):
    """Base exception for Apple auth errors."""
    def __init__(self, code: str, message: str, details: dict = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class AppleTokenClaims:
    """Parsed and verified Apple token claims."""
    def __init__(self, sub: str, email: Optional[str], email_verified: bool):
        self.sub = sub  # Apple user ID (provider_id)
        self.email = email
        self.email_verified = email_verified


def _get_unverified_header(token: str) -> dict:
    """Extract header from JWT without verification."""
    try:
        header_segment = token.split(".")[0]
        header_data = base64url_decode(header_segment.encode("utf-8"))
        return json.loads(header_data.decode("utf-8"))
    except Exception as e:
        raise AppleAuthError(
            code="INVALID_TOKEN",
            message="Malformed token header",
            details={"error": str(e)}
        )


async def verify_apple_token(
    identity_token: str,
    nonce: Optional[str] = None
) -> AppleTokenClaims:
    """
    Verify an Apple identity token and return the claims.

    Args:
        identity_token: The JWT from Apple Sign-In
        nonce: Optional nonce to verify against token's nonce claim

    Returns:
        AppleTokenClaims with sub, email, email_verified

    Raises:
        AppleAuthError: If verification fails
    """
    # Get unverified header to find the key id
    header = _get_unverified_header(identity_token)
    kid = header.get("kid")
    alg = header.get("alg")

    if not kid:
        raise AppleAuthError(
            code="INVALID_TOKEN",
            message="Token missing key id (kid)"
        )

    if alg not in ("RS256", "ES256"):
        raise AppleAuthError(
            code="INVALID_TOKEN",
            message=f"Unsupported algorithm: {alg}"
        )

    # Fetch the matching public key
    apple_key = await _jwks_cache.get_key(kid)
    if not apple_key:
        raise AppleAuthError(
            code="INVALID_TOKEN",
            message="Unable to find matching Apple public key",
            details={"kid": kid}
        )

    # Convert JWK to PEM for python-jose
    try:
        public_key = jwk.construct(apple_key)
    except Exception as e:
        raise AppleAuthError(
            code="SERVER_ERROR",
            message="Failed to construct public key",
            details={"error": str(e)}
        )

    # Verify and decode the token
    try:
        claims = jwt.decode(
            identity_token,
            public_key,
            algorithms=[alg],
            audience=settings.APPLE_CLIENT_ID,
            issuer=settings.APPLE_ISSUER,
            options={
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": True,
            }
        )
    except jwt.ExpiredSignatureError:
        raise AppleAuthError(
            code="INVALID_TOKEN",
            message="Token has expired"
        )
    except jwt.JWTClaimsError as e:
        raise AppleAuthError(
            code="INVALID_TOKEN",
            message=f"Token claims validation failed: {str(e)}"
        )
    except JWTError as e:
        raise AppleAuthError(
            code="INVALID_TOKEN",
            message=f"Token verification failed: {str(e)}"
        )

    # Verify nonce if provided
    if nonce:
        token_nonce = claims.get("nonce")
        if token_nonce != nonce:
            raise AppleAuthError(
                code="INVALID_TOKEN",
                message="Nonce mismatch",
                details={"expected": nonce, "received": token_nonce}
            )

    # Extract required claims
    sub = claims.get("sub")
    if not sub:
        raise AppleAuthError(
            code="INVALID_TOKEN",
            message="Token missing subject (sub) claim"
        )

    return AppleTokenClaims(
        sub=sub,
        email=claims.get("email"),
        email_verified=claims.get("email_verified", False)
    )


def _generate_apple_client_secret() -> Optional[str]:
    """
    Generate a client_secret JWT for Apple API calls.
    Required for token revocation.

    Returns None if credentials are not configured.
    """
    if not all([settings.APPLE_TEAM_ID, settings.APPLE_KEY_ID, settings.APPLE_PRIVATE_KEY]):
        return None

    try:
        # Decode the base64-encoded private key
        private_key_pem = base64.b64decode(settings.APPLE_PRIVATE_KEY).decode("utf-8")
    except Exception:
        # Try using it as-is if not base64 encoded
        private_key_pem = settings.APPLE_PRIVATE_KEY

    now = datetime.now(timezone.utc)
    expiry = now + timedelta(days=180)  # Max 6 months

    headers = {
        "alg": "ES256",
        "kid": settings.APPLE_KEY_ID,
    }

    payload = {
        "iss": settings.APPLE_TEAM_ID,
        "iat": int(now.timestamp()),
        "exp": int(expiry.timestamp()),
        "aud": "https://appleid.apple.com",
        "sub": settings.APPLE_CLIENT_ID,
    }

    try:
        return jwt.encode(payload, private_key_pem, algorithm="ES256", headers=headers)
    except Exception as e:
        logger.error(f"Failed to generate Apple client_secret: {e}")
        return None


async def revoke_apple_token(refresh_token: Optional[str] = None) -> bool:
    """
    Revoke an Apple Sign-In token.

    Apple requires either access_token or refresh_token to revoke.
    If we don't have a stored token, this will log a warning and return False.

    Args:
        refresh_token: The user's Apple refresh_token if stored

    Returns:
        True if revocation succeeded or was skipped (no credentials)
        False if revocation failed
    """
    # Check if we have the required credentials
    client_secret = _generate_apple_client_secret()
    if not client_secret:
        logger.warning(
            "Apple token revocation skipped: APPLE_TEAM_ID, APPLE_KEY_ID, or "
            "APPLE_PRIVATE_KEY not configured. Get these from your Apple Developer account."
        )
        return True  # Don't block deletion

    if not refresh_token:
        logger.warning(
            "Apple token revocation skipped: No refresh_token stored for this user. "
            "Consider storing refresh_token during sign-in for proper revocation."
        )
        return True  # Don't block deletion

    # Attempt revocation
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://appleid.apple.com/auth/revoke",
                data={
                    "client_id": settings.APPLE_CLIENT_ID,
                    "client_secret": client_secret,
                    "token": refresh_token,
                    "token_type_hint": "refresh_token",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )

            if response.status_code == 200:
                logger.info("Apple token revoked successfully")
                return True
            else:
                logger.error(
                    f"Apple token revocation failed: {response.status_code} - {response.text}"
                )
                return False

    except Exception as e:
        logger.error(f"Apple token revocation error: {e}")
        return False
