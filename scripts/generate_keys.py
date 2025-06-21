import secrets
import base64
import os
from pathlib import Path
from dotenv import load_dotenv

def generate_secure_key(length: int = 32) -> str:
    """Generate a secure random key"""
    return base64.b64encode(secrets.token_bytes(length)).decode('utf-8')

def update_env_keys():
    """Update security keys in .env file"""
    env_path = Path('.env')
    if not env_path.exists():
        print("Error: .env file not found. Please run setup_supabase.py first.")
        return
    
    # Load existing .env content
    load_dotenv()
    with open(env_path) as f:
        env_content = f.read()
    
    # Generate new keys
    master_key = generate_secure_key(32)
    api_salt = generate_secure_key(16)
    admin_key = generate_secure_key(32)
    
    # Update keys in content
    env_content = env_content.replace('your-32-byte-encryption-key', master_key)
    env_content = env_content.replace('your-api-key-salt', api_salt)
    env_content = env_content.replace('your-admin-api-key', admin_key)
    
    # Write updated content
    with open(env_path, 'w') as f:
        f.write(env_content)
    
    print("\nSecurity keys updated successfully!")
    print("\nGenerated keys:")
    print(f"MASTER_ENCRYPTION_KEY: {master_key}")
    print(f"API_KEY_SALT: {api_salt}")
    print(f"ADMIN_API_KEY: {admin_key}")
    print("\nThese keys have been saved to your .env file")

if __name__ == "__main__":
    update_env_keys() 