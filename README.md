# API Lens - Globally Distributed AI API Gateway

API Lens is a production-grade API gateway that sits between client applications and AI vendor APIs (OpenAI, Anthropic, Google), providing enterprise-level features at startup costs.

## Features

- Global Performance: <50ms latency worldwide via 300+ edge locations
- Cost Transparency: Real-time cost tracking with ±1% accuracy
- Perfect Isolation: Complete data separation between companies
- BYOK Security: Bring Your Own Key - customers use their own vendor API keys
- Startup Economics: $50-70/month infrastructure vs $1000+ for traditional solutions

## Architecture

- **Cloudflare Workers**: Global proxy servers at 300+ edge locations
- **Python FastAPI**: Backend services and management APIs
- **PostgreSQL**: Main database with schema-based multi-tenancy
- **Redis**: High-performance caching and rate limiting

## Setup Instructions

1. Clone the repository:
```bash
git clone https://github.com/yourusername/api-lens.git
cd api-lens
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in the project root with the following variables:
```env
# Environment
ENVIRONMENT=development
DEBUG=true

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/api_lens

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
MASTER_ENCRYPTION_KEY=your-32-byte-encryption-key-here
ADMIN_API_KEY=your-admin-api-key-here

# Supabase
SUPABASE_SERVICE_KEY=your-supabase-service-key-here

# API Settings
API_PREFIX=/api/v1
RATE_LIMIT_DEFAULT=100
COST_QUOTA_DEFAULT=1000.0
```

5. Initialize the database:
```bash
python scripts/init_db.py
```

6. Run the development server:
```bash
uvicorn app.main:app --reload
```

## Project Structure

```
api-lens/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   └── services/
│       ├── auth.py
│       ├── company.py
│       ├── encryption.py
│       ├── cost.py
│       ├── analytics.py
│       └── cache.py
├── api/
│   ├── admin.py
│   ├── company.py
│   ├── proxy.py
│   └── analytics.py
├── models/
│   ├── company.py
│   ├── api_key.py
│   ├── billing.py
│   └── analytics.py
├── sql/
│   ├── init_schema.sql
│   ├── company_schema.sql
│   ├── indexes.sql
│   └── views.sql
├── tests/
│   ├── test_auth.py
│   ├── test_company.py
│   ├── test_cost.py
│   └── test_integration.py
├── scripts/
│   ├── init_db.py
│   ├── create_company.py
│   └── migrate.py
├── requirements.txt
└── README.md
```

## Development

### Running Tests
```bash
pytest
```

### Code Formatting
```bash
black .
isort .
```

### Type Checking
```bash
mypy .
```

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
