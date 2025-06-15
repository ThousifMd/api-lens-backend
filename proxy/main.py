import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional
import os
from dotenv import load_dotenv
import uuid
import hashlib
import time
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="LLM Proxy API")

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Request logging model
class RequestLog(Base):
    __tablename__ = "request_logs"

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, nullable=False)
    vendor = Column(String, nullable=False)
    model = Column(String, nullable=False)
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    cost = Column(Float)
    latency = Column(Float)
    status_code = Column(Integer)
    request_id = Column(String, nullable=False)
    prompt_hash = Column(String, nullable=False)

# Create tables
Base.metadata.create_all(bind=engine)

# Request model
class ProxyRequest(BaseModel):
    vendor: str
    model: str
    prompt: str
    extra_params: Optional[Dict] = None

# Vendor-specific API clients
from .clients.openai_client import OpenAIClient
from .clients.anthropic_client import AnthropicClient
from .clients.gemini_client import GeminiClient

# Initialize clients
clients = {
    "openai": OpenAIClient(),
    "anthropic": AnthropicClient(),
    "gemini": GeminiClient()
}

@app.post("/proxy")
async def proxy_request(request: ProxyRequest):
    start_time = time.time()
    request_id = str(uuid.uuid4())
    prompt_hash = hashlib.sha256(request.prompt.encode()).hexdigest()

    try:
        # Get the appropriate client
        client = clients.get(request.vendor.lower())
        if not client:
            raise HTTPException(status_code=400, detail=f"Unsupported vendor: {request.vendor}")

        # Generate response
        response = await client.generate(
            model=request.model,
            prompt=request.prompt,
            extra_params=request.extra_params
        )

        # Calculate latency
        latency = time.time() - start_time

        # Log the request
        with SessionLocal() as db:
            log_entry = RequestLog(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                vendor=request.vendor,
                model=request.model,
                prompt_tokens=response.get("prompt_tokens", 0),
                completion_tokens=response.get("completion_tokens", 0),
                cost=response.get("cost", 0.0),
                latency=latency,
                status_code=200,
                request_id=request_id,
                prompt_hash=prompt_hash
            )
            db.add(log_entry)
            db.commit()

        logger.info(f"Request ID: {request_id}, Vendor: {request.vendor}, Model: {request.model}, Latency: {latency:.3f}s")

        return {
            "request_id": request_id,
            "response": response,
            "latency": latency
        }

    except Exception as e:
        # Log error
        with SessionLocal() as db:
            log_entry = RequestLog(
                id=str(uuid.uuid4()),
                timestamp=datetime.utcnow(),
                vendor=request.vendor,
                model=request.model,
                prompt_tokens=0,
                completion_tokens=0,
                cost=0.0,
                latency=time.time() - start_time,
                status_code=500,
                request_id=request_id,
                prompt_hash=prompt_hash
            )
            db.add(log_entry)
            db.commit()

        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
