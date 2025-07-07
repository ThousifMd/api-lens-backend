"""
OpenAPI/Swagger Documentation for API Lens
Comprehensive API documentation with examples and schemas
"""

from typing import Dict, Any

# OpenAPI Documentation
api_docs = {
    "openapi": "3.0.2",
    "info": {
        "title": "API Lens - AI Gateway Analytics",
        "version": "2.0.0",
        "description": """
## API Lens - Production-Ready AI Gateway Analytics

API Lens provides comprehensive logging, analytics, and monitoring for AI API calls across multiple vendors.

### Key Features:
- **Multi-vendor support**: OpenAI, Anthropic, Google, Stability AI, Adobe Firefly
- **Real-time analytics**: Track usage, costs, and performance
- **User session tracking**: Monitor user behavior across requests
- **Image generation support**: Full support for DALL-E, Stable Diffusion, and Firefly
- **Location-aware**: Automatic timezone and location detection
- **Schema v2**: Optimized normalized database design

### Authentication
All endpoints require API key authentication via the `X-API-Key` header.

### Rate Limiting
Rate limits are enforced per company based on your subscription tier.
        """,
        "contact": {
            "name": "API Lens Support",
            "email": "support@apilens.com"
        },
        "license": {
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT"
        }
    },
    "servers": [
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        },
        {
            "url": "https://api.apilens.com",
            "description": "Production server"
        }
    ],
    "tags": [
        {
            "name": "Logging",
            "description": "Log AI API requests and responses"
        },
        {
            "name": "Analytics",
            "description": "View usage analytics and statistics"
        },
        {
            "name": "Health",
            "description": "System health and status checks"
        }
    ]
}

# Schema definitions
schemas = {
    "OptimizedLogEntry": {
        "type": "object",
        "required": [
            "requestId", "companyId", "timestamp", "method", "endpoint",
            "vendor", "model", "inputTokens", "outputTokens", "totalLatency",
            "vendorLatency", "statusCode", "success", "cost"
        ],
        "properties": {
            "requestId": {
                "type": "string",
                "description": "Unique identifier for the request",
                "example": "req_123e4567-e89b-12d3-a456-426614174000"
            },
            "companyId": {
                "type": "string",
                "format": "uuid",
                "description": "UUID of the company making the request",
                "example": "123e4567-e89b-12d3-a456-426614174000"
            },
            "timestamp": {
                "type": "integer",
                "format": "int64",
                "description": "Unix timestamp in milliseconds",
                "example": 1704067200000
            },
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                "description": "HTTP method used",
                "example": "POST"
            },
            "endpoint": {
                "type": "string",
                "description": "API endpoint path",
                "example": "/v1/chat/completions"
            },
            "url": {
                "type": "string",
                "format": "uri",
                "description": "Full URL of the API request",
                "example": "https://api.openai.com/v1/chat/completions"
            },
            "vendor": {
                "type": "string",
                "description": "AI vendor name",
                "example": "openai"
            },
            "model": {
                "type": "string",
                "description": "Model identifier",
                "example": "gpt-4-turbo"
            },
            "userId": {
                "type": "string",
                "description": "User identifier for session tracking",
                "example": "user_123"
            },
            "userAgent": {
                "type": "string",
                "description": "User agent string",
                "example": "Mozilla/5.0..."
            },
            "country": {
                "type": "string",
                "description": "ISO country code",
                "example": "US"
            },
            "region": {
                "type": "string",
                "description": "Region/state name",
                "example": "California"
            },
            "ipAddress": {
                "type": "string",
                "format": "ipv4",
                "description": "Client IP address",
                "example": "192.168.1.1"
            },
            "inputTokens": {
                "type": "integer",
                "description": "Number of input tokens",
                "example": 150
            },
            "outputTokens": {
                "type": "integer",
                "description": "Number of output tokens",
                "example": 500
            },
            "totalLatency": {
                "type": "integer",
                "description": "Total request latency in milliseconds",
                "example": 2500
            },
            "vendorLatency": {
                "type": "integer",
                "description": "Vendor API latency in milliseconds",
                "example": 2000
            },
            "statusCode": {
                "type": "integer",
                "description": "HTTP status code",
                "example": 200
            },
            "success": {
                "type": "boolean",
                "description": "Whether the request was successful",
                "example": True
            },
            "errorMessage": {
                "type": "string",
                "description": "Error message if request failed",
                "example": "Rate limit exceeded"
            },
            "errorCode": {
                "type": "string",
                "description": "Error code if request failed",
                "example": "rate_limit_exceeded"
            },
            "cost": {
                "type": "number",
                "format": "float",
                "description": "Total cost in USD",
                "example": 0.0035
            },
            # Image generation fields
            "imageCount": {
                "type": "integer",
                "minimum": 0,
                "maximum": 10,
                "description": "Number of images generated",
                "example": 2
            },
            "imageUrls": {
                "type": "array",
                "items": {"type": "string", "format": "uri"},
                "description": "URLs of generated images",
                "example": ["https://example.com/image1.png", "https://example.com/image2.png"]
            },
            "imageDimensions": {
                "type": "string",
                "pattern": "^\\d+x\\d+$",
                "description": "Image dimensions in WIDTHxHEIGHT format",
                "example": "1024x1024"
            },
            "imageQuality": {
                "type": "string",
                "description": "Image quality setting",
                "example": "hd"
            },
            "imageStyle": {
                "type": "string",
                "description": "Image style setting",
                "example": "natural"
            },
            "prompt": {
                "type": "string",
                "maxLength": 2000,
                "description": "Image generation prompt",
                "example": "A beautiful sunset over mountains"
            },
            "negativePrompt": {
                "type": "string",
                "maxLength": 1000,
                "description": "Negative prompt for image generation",
                "example": "blur, low quality"
            },
            "seed": {
                "type": "integer",
                "minimum": 0,
                "maximum": 4294967295,
                "description": "Random seed for reproducible generation",
                "example": 12345
            },
            "generationSteps": {
                "type": "integer",
                "minimum": 1,
                "maximum": 150,
                "description": "Number of generation steps",
                "example": 50
            },
            "guidanceScale": {
                "type": "number",
                "format": "float",
                "minimum": 1.0,
                "maximum": 20.0,
                "description": "Guidance scale for generation",
                "example": 7.5
            }
        }
    },
    "LogResponse": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "Response status",
                "example": "success"
            },
            "message": {
                "type": "string",
                "description": "Response message",
                "example": "Optimized log entry processed with real location and pricing data"
            },
            "location": {
                "type": "string",
                "description": "Detected location",
                "example": "San Francisco, California, US"
            },
            "timezone": {
                "type": "string",
                "description": "Detected timezone",
                "example": "America/Los_Angeles"
            },
            "cost": {
                "type": "object",
                "properties": {
                    "input_cost": {"type": "number", "example": 0.001},
                    "output_cost": {"type": "number", "example": 0.002},
                    "total_cost": {"type": "number", "example": 0.003},
                    "source": {"type": "string", "example": "vendor_pricing"}
                }
            },
            "api_key_id": {
                "type": "string",
                "format": "uuid",
                "description": "API key ID used",
                "example": "123e4567-e89b-12d3-a456-426614174000"
            },
            "model_id": {
                "type": "string",
                "format": "uuid",
                "description": "Model ID in database",
                "example": "123e4567-e89b-12d3-a456-426614174000"
            },
            "user_session_id": {
                "type": "string",
                "format": "uuid",
                "description": "User session ID if user was provided",
                "example": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
    },
    "StatsResponse": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "object",
                "properties": {
                    "total_requests": {"type": "integer", "example": 1000},
                    "unique_companies": {"type": "integer", "example": 10},
                    "unique_models": {"type": "integer", "example": 15},
                    "total_cost": {"type": "number", "example": 125.50},
                    "avg_latency": {"type": "number", "example": 2500},
                    "total_image_requests": {"type": "integer", "example": 100},
                    "total_images_generated": {"type": "integer", "example": 250},
                    "image_vendors": {"type": "integer", "example": 3},
                    "image_models": {"type": "integer", "example": 5}
                }
            },
            "breakdown": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "company_name": {"type": "string", "example": "TechCorp Inc"},
                        "vendor": {"type": "string", "example": "openai"},
                        "model": {"type": "string", "example": "gpt-4-turbo"},
                        "request_count": {"type": "integer", "example": 150},
                        "total_cost": {"type": "number", "example": 25.50},
                        "avg_cost": {"type": "number", "example": 0.17},
                        "total_input_tokens": {"type": "integer", "example": 15000},
                        "total_output_tokens": {"type": "integer", "example": 50000},
                        "avg_latency": {"type": "number", "example": 2500},
                        "image_requests": {"type": "integer", "example": 10},
                        "total_images_generated": {"type": "integer", "example": 25},
                        "avg_images_per_request": {"type": "number", "example": 2.5},
                        "most_common_dimensions": {"type": "string", "example": "1024x1024"}
                    }
                }
            },
            "schema_info": {
                "type": "object",
                "properties": {
                    "optimized": {"type": "boolean", "example": True},
                    "normalization": {"type": "string", "example": "Schema v2 (3NF)"},
                    "tables": {"type": "integer", "example": 8},
                    "foreign_keys": {"type": "boolean", "example": True}
                }
            }
        }
    },
    "HealthResponse": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["healthy", "degraded", "error"],
                "example": "healthy"
            },
            "schema": {
                "type": "string",
                "example": "v2"
            },
            "tables": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "example": "healthy"},
                        "record_count": {"type": "integer", "example": 1000},
                        "error": {"type": "string"}
                    }
                }
            },
            "normalization": {
                "type": "string",
                "example": "Third Normal Form (3NF)"
            },
            "timestamp": {
                "type": "string",
                "format": "date-time",
                "example": "2024-01-01T12:00:00Z"
            }
        }
    },
    "ErrorResponse": {
        "type": "object",
        "properties": {
            "detail": {
                "type": "string",
                "description": "Error message",
                "example": "Invalid API key"
            }
        }
    }
}

# Path definitions
paths = {
    "/proxy/logs/optimized": {
        "post": {
            "tags": ["Logging"],
            "summary": "Log an optimized AI API request",
            "description": """
Log a completed AI API request with comprehensive metadata including:
- Request/response details
- Token usage and costs
- Performance metrics
- Location information
- Image generation parameters (if applicable)
- User session tracking

The endpoint automatically:
- Validates all input data
- Calculates accurate costs based on vendor pricing
- Detects client location and timezone
- Creates/updates user sessions
- Handles image generation metadata
            """,
            "operationId": "receive_optimized_log_entry",
            "security": [{"ApiKeyAuth": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/OptimizedLogEntry"},
                        "examples": {
                            "text_generation": {
                                "summary": "Text generation request",
                                "value": {
                                    "requestId": "req_123",
                                    "companyId": "123e4567-e89b-12d3-a456-426614174000",
                                    "timestamp": 1704067200000,
                                    "method": "POST",
                                    "endpoint": "/v1/chat/completions",
                                    "vendor": "openai",
                                    "model": "gpt-4-turbo",
                                    "userId": "user_123",
                                    "inputTokens": 150,
                                    "outputTokens": 500,
                                    "totalLatency": 2500,
                                    "vendorLatency": 2000,
                                    "statusCode": 200,
                                    "success": True,
                                    "cost": 0.0035
                                }
                            },
                            "image_generation": {
                                "summary": "Image generation request",
                                "value": {
                                    "requestId": "req_456",
                                    "companyId": "123e4567-e89b-12d3-a456-426614174000",
                                    "timestamp": 1704067200000,
                                    "method": "POST",
                                    "endpoint": "/v1/images/generations",
                                    "vendor": "openai",
                                    "model": "dall-e-3",
                                    "userId": "user_123",
                                    "inputTokens": 0,
                                    "outputTokens": 0,
                                    "totalLatency": 5000,
                                    "vendorLatency": 4500,
                                    "statusCode": 200,
                                    "success": True,
                                    "cost": 0.04,
                                    "imageCount": 2,
                                    "imageUrls": ["https://example.com/img1.png", "https://example.com/img2.png"],
                                    "imageDimensions": "1024x1024",
                                    "imageQuality": "hd",
                                    "prompt": "A beautiful sunset"
                                }
                            }
                        }
                    }
                }
            },
            "responses": {
                "200": {
                    "description": "Log entry processed successfully",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/LogResponse"}
                        }
                    }
                },
                "401": {
                    "description": "Invalid API key",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                        }
                    }
                },
                "422": {
                    "description": "Validation error",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                        }
                    }
                },
                "500": {
                    "description": "Internal server error",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                        }
                    }
                }
            }
        }
    },
    "/proxy/stats/optimized": {
        "get": {
            "tags": ["Analytics"],
            "summary": "Get optimized usage statistics",
            "description": """
Retrieve comprehensive usage statistics including:
- Total requests, costs, and performance metrics
- Breakdown by company, vendor, and model
- Image generation statistics
- Schema information

Statistics are calculated in real-time from the optimized Schema v2 database.
            """,
            "operationId": "get_optimized_stats",
            "security": [{"ApiKeyAuth": []}],
            "responses": {
                "200": {
                    "description": "Statistics retrieved successfully",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/StatsResponse"}
                        }
                    }
                },
                "401": {
                    "description": "Invalid API key",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                        }
                    }
                },
                "500": {
                    "description": "Internal server error",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                        }
                    }
                }
            }
        }
    },
    "/proxy/health/optimized": {
        "get": {
            "tags": ["Health"],
            "summary": "Check system health",
            "description": """
Perform a comprehensive health check including:
- Database connectivity
- Table status and record counts
- Schema version information

This endpoint can be used for monitoring and alerting.
            """,
            "operationId": "optimized_health_check",
            "responses": {
                "200": {
                    "description": "Health check completed",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/HealthResponse"}
                        }
                    }
                }
            }
        }
    }
}

# Security schemes
security_schemes = {
    "ApiKeyAuth": {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "API key for authentication. Contact support to obtain a key."
    }
}

def get_openapi_schema() -> Dict[str, Any]:
    """
    Get the complete OpenAPI schema
    
    Returns:
        Complete OpenAPI specification
    """
    return {
        **api_docs,
        "paths": paths,
        "components": {
            "schemas": schemas,
            "securitySchemes": security_schemes
        }
    }

def get_custom_openapi_schema(app) -> Dict[str, Any]:
    """
    Get custom OpenAPI schema with FastAPI app routes
    
    Args:
        app: FastAPI application instance
        
    Returns:
        Merged OpenAPI specification
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi_schema()
    app.openapi_schema = openapi_schema
    return app.openapi_schema