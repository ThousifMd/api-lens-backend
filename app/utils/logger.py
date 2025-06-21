import logging
import sys
from typing import Optional
from datetime import datetime
import os

def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """Setup application logging with console and optional file output"""
    
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    return root_logger

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given name"""
    return logging.getLogger(name)

# Initialize default logging
if not logging.getLogger().handlers:
    setup_logging()

# Legacy API logger class for backward compatibility
class APILoggerREST:
    """Legacy API logger - kept for backward compatibility"""
    
    def __init__(self, api_url=None):
        self.logger = get_logger(self.__class__.__name__)
        if api_url:
            self.logger.info(f"API Logger initialized with URL: {api_url}")
        else:
            self.logger.warning("API Logger initialized without database URL")
    
    def log(self, user_api_key, vendor, model, request_payload, response_payload, 
            start_time=None, log_type=None, client_time=None, cost=None, 
            call_id=None, feature_name=None):
        """Log API request/response - simplified version"""
        try:
            import time
            import uuid
            
            # Generate call_id if not provided
            if call_id is None:
                call_id = str(uuid.uuid4())
            
            # Calculate latency
            latency_ms = None
            if start_time:
                latency_ms = (time.time() - start_time) * 1000
            
            # Extract token information
            tokens_info = ""
            if response_payload and isinstance(response_payload, dict):
                usage = response_payload.get('usage', {})
                if usage:
                    tokens_info = f"tokens: {usage.get('prompt_tokens', 0)}/{usage.get('completion_tokens', 0)}"
            
            # Log the API call
            log_message = (
                f"API Call [{log_type}] | "
                f"ID: {call_id} | "
                f"Vendor: {vendor} | "
                f"Model: {model} | "
                f"Latency: {latency_ms:.2f}ms | "
                f"{tokens_info}"
            )
            
            if cost:
                log_message += f" | Cost: ${cost:.6f}"
            
            self.logger.info(log_message)
            
        except Exception as e:
            self.logger.error(f"Error in API logging: {e}")
            raise 