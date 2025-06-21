#!/usr/bin/env python3
import secrets
import base64

def generate_master_encryption_key():
    """Generate a secure 32-byte master encryption key"""
    # Generate 32 random bytes
    key_bytes = secrets.token_bytes(32)
    
    # Encode as base64 for easy storage
    key_base64 = base64.b64encode(key_bytes).decode()
    
    # Also provide hex representation
    key_hex = key_bytes.hex()
    
    print("🔐 Generated Master Encryption Key:")
    print(f"Base64 (recommended): {key_base64}")
    print(f"Hex format:           {key_hex}")
    print(f"Length:               {len(key_bytes)} bytes")
    
    return key_base64

if __name__ == "__main__":
    key = generate_master_encryption_key()
    print(f"\n📝 Add this to your .env file:")
    print(f'MASTER_ENCRYPTION_KEY="{key}"')