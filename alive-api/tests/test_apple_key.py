#!/usr/bin/env python3
"""
Test script to verify Apple private key parsing and JWT generation.
Run from the alive-api directory with: python test_apple_key.py
"""
import sys
sys.path.insert(0, '.')

from app.core.config import settings
from app.core.apple_auth import _normalize_pem_key, _generate_apple_client_secret

def test_apple_config():
    print("=== Apple Configuration ===")
    print(f"APPLE_CLIENT_ID: {settings.APPLE_CLIENT_ID or '(not set)'}")
    print(f"APPLE_TEAM_ID: {settings.APPLE_TEAM_ID or '(not set)'}")
    print(f"APPLE_KEY_ID: {settings.APPLE_KEY_ID or '(not set)'}")
    print(f"APPLE_PRIVATE_KEY set: {bool(settings.APPLE_PRIVATE_KEY)}")
    if settings.APPLE_PRIVATE_KEY:
        print(f"APPLE_PRIVATE_KEY length: {len(settings.APPLE_PRIVATE_KEY)}")
        print(f"APPLE_PRIVATE_KEY starts with: {settings.APPLE_PRIVATE_KEY[:30]}...")
    print()

def test_key_normalization():
    print("=== Testing Key Normalization ===")
    if not settings.APPLE_PRIVATE_KEY:
        print("ERROR: APPLE_PRIVATE_KEY not set in .env")
        return False

    pem = _normalize_pem_key(settings.APPLE_PRIVATE_KEY)
    if pem:
        print("SUCCESS: Key normalized to PEM format")
        print(f"PEM starts with: {pem[:40]}...")
        print(f"PEM ends with: ...{pem[-40:]}")
        return True
    else:
        print("ERROR: Failed to normalize key to PEM format")
        return False

def test_client_secret_generation():
    print("\n=== Testing Client Secret Generation ===")

    if not all([settings.APPLE_TEAM_ID, settings.APPLE_KEY_ID, settings.APPLE_PRIVATE_KEY]):
        print("ERROR: Missing required settings (APPLE_TEAM_ID, APPLE_KEY_ID, or APPLE_PRIVATE_KEY)")
        return False

    secret = _generate_apple_client_secret()
    if secret:
        print("SUCCESS: Generated Apple client_secret JWT")
        print(f"JWT length: {len(secret)}")
        print(f"JWT starts with: {secret[:50]}...")
        return True
    else:
        print("ERROR: Failed to generate client_secret")
        return False

if __name__ == "__main__":
    print("Testing Apple Sign-In configuration...\n")

    test_apple_config()

    key_ok = test_key_normalization()
    if key_ok:
        test_client_secret_generation()

    print("\n=== Done ===")
