import os
from pathlib import Path
import json
from dotenv import load_dotenv

def setup_supabase():
    """Help set up Supabase connection details"""
    print("\n=== Supabase Setup Guide ===\n")
    
    # Check if .env exists
    env_path = Path('.env')
    if env_path.exists():
        print("Found existing .env file")
        load_dotenv()
        if os.getenv('DATABASE_URL'):
            print("DATABASE_URL is already set")
            return
    
    print("Please follow these steps:")
    print("\n1. Go to https://supabase.com and create a new project")
    print("2. Once created, go to Project Settings -> Database")
    print("3. Find the 'Connection string' section")
    print("4. Copy the 'URI' connection string")
    
    # Get connection details
    connection_string = input("\nPaste your Supabase connection string: ").strip()
    
    # Convert to asyncpg format
    if connection_string.startswith('postgresql://'):
        connection_string = connection_string.replace('postgresql://', 'postgresql+asyncpg://')
    
    # Create .env file
    env_content = f"""# Database Configuration
DATABASE_URL={connection_string}
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800
DB_ECHO=false

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Security
MASTER_ENCRYPTION_KEY=your-32-byte-encryption-key
API_KEY_SALT=your-api-key-salt
ADMIN_API_KEY=your-admin-api-key

# Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60

# Environment
ENVIRONMENT=development
DEBUG=true
"""
    
    # Write to .env file
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("\n.env file created successfully!")
    print("\nNext steps:")
    print("1. Update the security keys in .env:")
    print("   - Generate a secure MASTER_ENCRYPTION_KEY")
    print("   - Generate a secure API_KEY_SALT")
    print("   - Generate a secure ADMIN_API_KEY")
    print("2. Run the database initialization script:")
    print("   python scripts/init_db.py")

if __name__ == "__main__":
    setup_supabase() 