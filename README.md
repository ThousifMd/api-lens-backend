# LLM Proxy MVP

A FastAPI-based proxy service that routes requests to different LLM providers (OpenAI, Anthropic, and Gemini) with comprehensive logging and monitoring.

## Features

- Unified API endpoint for multiple LLM providers
- Automatic request logging to PostgreSQL
- Token usage and cost tracking
- Request deduplication via prompt hashing
- Vendor-specific parameter handling
- Simple Streamlit chat interface for querying logs

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd llm-proxy-mvp
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Create a `.env` file with the following variables:
```
# API Keys
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/llm_proxy

# Server
HOST=0.0.0.0
PORT=8000
```

4. Set up PostgreSQL database:
```bash
# Create database
createdb llm_proxy

# The tables will be automatically created when you run the application
```

5. Run the FastAPI server:
```bash
cd proxy
uvicorn main:app --reload
```

6. Run the Streamlit chatbot:
```bash
cd chatbot
streamlit run app.py
```

## API Usage

### Proxy Endpoint

```bash
curl -X POST "http://localhost:8000/proxy" \
     -H "Content-Type: application/json" \
     -d '{
           "vendor": "openai",
           "model": "gpt-4",
           "prompt": "Hello, how are you?",
           "extra_params": {
             "temperature": 0.8
           }
         }'
```

## Project Structure

```
llm-proxy-mvp/
├── proxy/
│   ├── main.py
│   └── clients/
│       ├── openai_client.py
│       ├── anthropic_client.py
│       └── gemini_client.py
├── chatbot/
│   └── app.py
├── db/
│   └── models.py
├── utils/
│   └── helpers.py
├── requirements.txt
└── README.md
```

## Development

- The proxy service is built with FastAPI
- Database models use SQLAlchemy
- The chatbot interface uses Streamlit
- All API keys and configuration are managed through environment variables

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License
