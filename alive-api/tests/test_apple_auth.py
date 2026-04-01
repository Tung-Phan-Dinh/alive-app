"""
Test cases for Apple Sign-In implementation.
Run with: pytest tests/test_apple_auth.py -v
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestAppleAuthReqValidation:
    """Test AppleAuthReq Pydantic model validation."""

    def test_empty_email_converts_to_none(self):
        from app.api.routes_auth import AppleAuthReq

        req = AppleAuthReq(
            identity_token="test_token",
            user_email="",  # Empty string
        )
        assert req.user_email is None

    def test_empty_authorization_code_converts_to_none(self):
        from app.api.routes_auth import AppleAuthReq

        req = AppleAuthReq(
            identity_token="test_token",
            authorization_code="",  # Empty string
        )
        assert req.authorization_code is None

    def test_valid_email_preserved(self):
        from app.api.routes_auth import AppleAuthReq

        req = AppleAuthReq(
            identity_token="test_token",
            user_email="test@example.com",
        )
        assert req.user_email == "test@example.com"

    def test_none_email_stays_none(self):
        from app.api.routes_auth import AppleAuthReq

        req = AppleAuthReq(
            identity_token="test_token",
            user_email=None,
        )
        assert req.user_email is None


class TestAppleTokenExchange:
    """Test authorization_code exchange."""

    @pytest.mark.asyncio
    async def test_exchange_success(self):
        from app.core.apple_auth import exchange_authorization_code, AppleTokenResponse

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "id_token": "test_id_token",
            "expires_in": 3600,
        }

        with patch("app.core.apple_auth._generate_apple_client_secret", return_value="mock_secret"):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
                result = await exchange_authorization_code("test_code")

                assert result is not None
                assert result.refresh_token == "test_refresh_token"

    @pytest.mark.asyncio
    async def test_exchange_no_credentials(self):
        from app.core.apple_auth import exchange_authorization_code

        with patch("app.core.apple_auth._generate_apple_client_secret", return_value=None):
            result = await exchange_authorization_code("test_code")
            assert result is None


class TestAppleTokenRevocation:
    """Test token revocation flow."""

    @pytest.mark.asyncio
    async def test_revoke_success(self):
        from app.core.apple_auth import revoke_apple_token

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("app.core.apple_auth._generate_apple_client_secret", return_value="mock_secret"):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
                result = await revoke_apple_token("test_refresh_token")
                assert result is True

    @pytest.mark.asyncio
    async def test_revoke_no_token(self):
        from app.core.apple_auth import revoke_apple_token

        with patch("app.core.apple_auth._generate_apple_client_secret", return_value="mock_secret"):
            # No refresh_token provided - should return True (don't block deletion)
            result = await revoke_apple_token(refresh_token=None)
            assert result is True

    @pytest.mark.asyncio
    async def test_revoke_no_credentials(self):
        from app.core.apple_auth import revoke_apple_token

        with patch("app.core.apple_auth._generate_apple_client_secret", return_value=None):
            # No credentials configured - should return True (don't block deletion)
            result = await revoke_apple_token("test_refresh_token")
            assert result is True


class TestUserModelHasRefreshToken:
    """Test that User model has apple_refresh_token field."""

    def test_user_has_apple_refresh_token_field(self):
        from app.db.models import User

        # Check column exists in model
        assert hasattr(User, 'apple_refresh_token')
