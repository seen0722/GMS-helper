"""
Encryption utilities for sensitive data storage.
Uses Fernet symmetric encryption with a SECRET_KEY from environment.
"""
import os
from cryptography.fernet import Fernet
import base64
import hashlib


def _get_cipher():
    """Get Fernet cipher from SECRET_KEY environment variable."""
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        # Fallback for development only
        print("WARNING: SECRET_KEY not set, using default dev key.")
        secret_key = "dev-secret-key-do-not-use-in-prod"
    
    # Derive a valid Fernet key from the secret
    key = base64.urlsafe_b64encode(hashlib.sha256(secret_key.encode()).digest())
    return Fernet(key)


def encrypt(value: str) -> str:
    """Encrypt a string value."""
    if not value:
        return ""
    
    cipher = _get_cipher()
    encrypted_bytes = cipher.encrypt(value.encode())
    return encrypted_bytes.decode()


def decrypt(encrypted: str) -> str:
    """Decrypt an encrypted string value."""
    if not encrypted:
        return ""
    
    cipher = _get_cipher()
    decrypted_bytes = cipher.decrypt(encrypted.encode())
    return decrypted_bytes.decode()
