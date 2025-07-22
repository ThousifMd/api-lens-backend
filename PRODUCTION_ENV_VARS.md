# Production Environment Variables Guide

## Required Environment Variables for Production

When deploying to production (Railway, Render, etc.), you need to set these environment variables:

### 🔴 CRITICAL (Must Set)
```bash
# Database
DATABASE_URL=postgresql+asyncpg://[your-supabase-url]
SUPABASE_POSTGRES_URL=postgresql://[your-supabase-url]

# Security
ADMIN_API_KEY=[generate-new-secure-key]
MASTER_ENCRYPTION_KEY=[your-current-key]
API_KEY_SALT=[your-current-salt]
SECRET_KEY=[generate-new-32-char-key]

# AI Vendor Keys
OPENAI_API_KEY=sk-proj-[your-key]
ANTHROPIC_API_KEY=sk-ant-[your-key]
GEMINI_API_KEY=[your-key]
```

### 🟡 IMPORTANT (Should Set)
```bash
# Application
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# CORS (Update with your domains)
CORS_ORIGINS=["https://your-frontend.com","https://your-workers.dev"]
```

### 🟢 OPTIONAL (Can Use Defaults)
```bash
# Performance
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
WORKERS=4

# Features
RATE_LIMIT_ENABLED=true
METRICS_ENABLED=true
```

## Security Notes

⚠️ **NEVER commit .env file to git**
⚠️ **Generate new ADMIN_API_KEY for production**
⚠️ **Generate new SECRET_KEY for production**

## Generate Secure Keys

```bash
# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate ADMIN_API_KEY
python -c "import secrets; print(f'admin_{secrets.token_urlsafe(32)}')"

# Generate MASTER_ENCRYPTION_KEY (if needed)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Deployment Examples

### Railway
```bash
railway variables set DATABASE_URL="your-url"
railway variables set ADMIN_API_KEY="your-key"
# ... set all variables
railway up
```

### Render
Set in Dashboard > Environment > Environment Variables

### Heroku
```bash
heroku config:set DATABASE_URL="your-url"
heroku config:set ADMIN_API_KEY="your-key"
# ... set all variables
```

## Checklist Before Deploy

- [ ] Generate new SECRET_KEY
- [ ] Generate new ADMIN_API_KEY  
- [ ] Set ENVIRONMENT=production
- [ ] Set DEBUG=false
- [ ] Update CORS_ORIGINS with production domains
- [ ] Remove REDIS_URL (not used)
- [ ] Test database connection
- [ ] Verify all AI keys work