"""
Image Generation Service
Handles image generation requests across multiple AI providers
"""
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID, uuid4
import json
import logging

from ..database import DatabaseUtils
from ..utils.logger import get_logger
from ..utils.db_errors import handle_database_error
from .pricing_old import PricingService

logger = get_logger(__name__)

class ImageGenerationService:
    """Service for handling image generation across multiple providers"""
    
    # Supported image dimensions by provider
    SUPPORTED_DIMENSIONS = {
        "openai": {
            "dall-e-3": ["1024x1024", "1024x1792", "1792x1024"],
            "dall-e-2": ["256x256", "512x512", "1024x1024"]
        },
        "stability-ai": {
            "stable-diffusion-xl-1024-v1-0": ["1024x1024", "1152x896", "1216x832", "1344x768", "1536x640"],
            "stable-diffusion-v1-6": ["512x512", "768x768", "512x768", "768x512"]
        },
        "adobe": {
            "firefly-v2": ["1024x1024", "1152x896", "896x1152", "1344x768", "768x1344"],
            "firefly-v1": ["1024x1024", "512x512"]
        }
    }
    
    # Quality settings by provider
    QUALITY_SETTINGS = {
        "openai": ["standard", "hd"],
        "stability-ai": ["standard", "high"],
        "adobe": ["standard", "premium"]
    }
    
    # Style settings by provider
    STYLE_SETTINGS = {
        "openai": ["vivid", "natural"],
        "stability-ai": ["photographic", "digital-art", "comic-book", "fantasy-art", "line-art", "analog-film", "neon-punk", "isometric"],
        "adobe": ["photo", "art", "graphic"]
    }
    
    @staticmethod
    async def generate_image(
        vendor: str,
        model: str,
        prompt: str,
        company_id: UUID,
        user_id: UUID,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate images using specified provider and model
        
        Args:
            vendor: AI provider (openai, stability-ai, adobe)
            model: Specific model name
            prompt: Text description for image generation
            company_id: Company UUID
            user_id: User UUID
            **kwargs: Additional parameters (dimensions, quality, style, etc.)
            
        Returns:
            Dictionary with generation results and metadata
        """
        try:
            # Validate input parameters
            validation_result = await ImageGenerationService._validate_generation_request(
                vendor, model, prompt, **kwargs
            )
            
            if not validation_result["valid"]:
                return {
                    "status": "error",
                    "error": validation_result["error"],
                    "vendor": vendor,
                    "model": model
                }
            
            # Get model information
            model_info = await ImageGenerationService._get_model_info(vendor, model)
            if not model_info:
                return {
                    "status": "error",
                    "error": f"Model {vendor}/{model} not found or not active",
                    "vendor": vendor,
                    "model": model
                }
            
            # Extract generation parameters
            image_count = kwargs.get("image_count", 1)
            dimensions = kwargs.get("dimensions", "1024x1024")
            quality = kwargs.get("quality", "standard")
            style = kwargs.get("style")
            negative_prompt = kwargs.get("negative_prompt")
            seed = kwargs.get("seed")
            steps = kwargs.get("steps", 50)
            guidance_scale = kwargs.get("guidance_scale", 7.5)
            
            # Calculate cost before generation
            cost_result = await PricingService.calculate_cost(
                vendor=vendor,
                model=model,
                input_tokens=0,  # Image generation doesn't use input tokens
                output_tokens=0,  # Image generation doesn't use output tokens
                company_id=company_id,
                image_count=image_count
            )
            
            if cost_result.get("total_cost", 0) <= 0:
                logger.warning(f"No cost calculated for {vendor}/{model} image generation")
            
            # Simulate image generation (in real implementation, this would call actual APIs)
            generation_result = await ImageGenerationService._simulate_image_generation(
                vendor, model, prompt, image_count, dimensions, quality, style
            )
            
            if not generation_result["success"]:
                return {
                    "status": "error",
                    "error": generation_result["error"],
                    "vendor": vendor,
                    "model": model
                }
            
            # Log the request to database
            request_log = await ImageGenerationService._log_generation_request(
                vendor=vendor,
                model=model,
                company_id=company_id,
                user_id=user_id,
                prompt=prompt,
                negative_prompt=negative_prompt,
                image_count=image_count,
                dimensions=dimensions,
                quality=quality,
                style=style,
                seed=seed,
                steps=steps,
                guidance_scale=guidance_scale,
                cost=cost_result.get("total_cost", 0),
                image_urls=generation_result["image_urls"]
            )
            
            logger.info(f"Image generation successful: {vendor}/{model}, {image_count} images, ${cost_result.get('total_cost', 0):.4f}")
            
            return {
                "status": "success",
                "vendor": vendor,
                "model": model,
                "prompt": prompt,
                "image_count": image_count,
                "dimensions": dimensions,
                "quality": quality,
                "style": style,
                "images": generation_result["image_urls"],
                "cost": {
                    "total_cost": cost_result.get("total_cost", 0),
                    "per_image_cost": cost_result.get("per_image_price", 0),
                    "currency": "USD"
                },
                "generation_time_ms": generation_result["generation_time_ms"],
                "request_id": request_log["request_id"] if request_log else None,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            error_info = handle_database_error(e)
            logger.error(f"Image generation failed for {vendor}/{model}: {error_info['user_message']}")
            return {
                "status": "error",
                "error": error_info['user_message'],
                "vendor": vendor,
                "model": model
            }
    
    @staticmethod
    async def get_supported_models() -> Dict[str, Any]:
        """Get all supported image generation models with their capabilities"""
        try:
            models_query = """
            SELECT v.name as vendor, vm.name as model, vm.display_name, vm.description,
                   vp.image_cost_per_item as cost_per_image
            FROM vendor_models vm
            JOIN vendors v ON vm.vendor_id = v.id
            LEFT JOIN vendor_pricing vp ON vm.id = vp.model_id AND vp.is_active = true
            WHERE vm.model_type = 'image_generation' AND vm.is_active = true
            ORDER BY v.name, vm.name
            """
            
            models = await DatabaseUtils.execute_query(models_query, [], fetch_all=True)
            
            result = {"providers": {}}
            
            for model in models:
                vendor = model["vendor"]
                if vendor not in result["providers"]:
                    result["providers"][vendor] = {"models": []}
                
                model_info = {
                    "name": model["model"],
                    "display_name": model["display_name"],
                    "description": model["description"],
                    "cost_per_image": float(model["cost_per_image"]) if model["cost_per_image"] else 0.0,
                    "supported_dimensions": ImageGenerationService.SUPPORTED_DIMENSIONS.get(vendor, {}).get(model["model"], ["1024x1024"]),
                    "quality_options": ImageGenerationService.QUALITY_SETTINGS.get(vendor, ["standard"]),
                    "style_options": ImageGenerationService.STYLE_SETTINGS.get(vendor, [])
                }
                
                result["providers"][vendor]["models"].append(model_info)
            
            result["total_models"] = len(models)
            result["total_providers"] = len(result["providers"])
            
            return {
                "status": "success",
                "data": result,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            error_info = handle_database_error(e)
            logger.error(f"Failed to get supported models: {error_info['user_message']}")
            return {
                "status": "error",
                "error": error_info['user_message']
            }
    
    @staticmethod
    async def get_generation_history(
        company_id: UUID,
        user_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get image generation history for a company or user"""
        try:
            where_conditions = ["r.company_id = $1", "r.image_count > 0"]
            params = [company_id]
            
            if user_id:
                where_conditions.append("r.client_user_id = $2")
                params.append(user_id)
                limit_offset_params = ["$3", "$4"]
            else:
                limit_offset_params = ["$2", "$3"]
            
            params.extend([limit, offset])
            
            history_query = f"""
            SELECT r.id, r.request_id, v.name as vendor, vm.name as model,
                   r.prompt, r.image_count, r.image_dimensions, r.image_quality,
                   r.image_style, r.image_urls, r.total_cost, r.timestamp_utc,
                   r.status_code, r.total_latency_ms
            FROM requests r
            JOIN vendor_models vm ON r.model_id = vm.id
            JOIN vendors v ON vm.vendor_id = v.id
            WHERE {' AND '.join(where_conditions)}
            ORDER BY r.timestamp_utc DESC
            LIMIT {limit_offset_params[0]} OFFSET {limit_offset_params[1]}
            """
            
            history = await DatabaseUtils.execute_query(history_query, params, fetch_all=True)
            
            # Get total count
            count_query = f"""
            SELECT COUNT(*) as total
            FROM requests r
            WHERE {' AND '.join(where_conditions[:-1])}
            """
            
            count_params = params[:-2]  # Remove limit and offset
            total_result = await DatabaseUtils.execute_query(count_query, count_params, fetch_all=False)
            total_count = total_result["total"] if total_result else 0
            
            # Format results
            formatted_history = []
            for record in history:
                formatted_history.append({
                    "id": str(record["id"]),
                    "request_id": record["request_id"],
                    "vendor": record["vendor"],
                    "model": record["model"],
                    "prompt": record["prompt"],
                    "image_count": record["image_count"],
                    "dimensions": record["image_dimensions"],
                    "quality": record["image_quality"],
                    "style": record["image_style"],
                    "image_urls": record["image_urls"] or [],
                    "cost": float(record["total_cost"]) if record["total_cost"] else 0.0,
                    "generation_time_ms": record["total_latency_ms"],
                    "status": "success" if record["status_code"] == 200 else "error",
                    "created_at": record["timestamp_utc"].isoformat()
                })
            
            return {
                "status": "success",
                "data": {
                    "history": formatted_history,
                    "pagination": {
                        "total": total_count,
                        "limit": limit,
                        "offset": offset,
                        "has_more": (offset + limit) < total_count
                    }
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            error_info = handle_database_error(e)
            logger.error(f"Failed to get generation history: {error_info['user_message']}")
            return {
                "status": "error",
                "error": error_info['user_message']
            }
    
    # Helper methods
    
    @staticmethod
    async def _validate_generation_request(vendor: str, model: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """Validate image generation request parameters"""
        
        if not prompt or len(prompt.strip()) < 3:
            return {"valid": False, "error": "Prompt must be at least 3 characters long"}
        
        if len(prompt) > 4000:
            return {"valid": False, "error": "Prompt is too long (max 4000 characters)"}
        
        image_count = kwargs.get("image_count", 1)
        if not isinstance(image_count, int) or image_count < 1 or image_count > 10:
            return {"valid": False, "error": "Image count must be between 1 and 10"}
        
        dimensions = kwargs.get("dimensions", "1024x1024")
        if not isinstance(dimensions, str) or not dimensions.count("x") == 1:
            return {"valid": False, "error": "Dimensions must be in format 'WIDTHxHEIGHT'"}
        
        try:
            width, height = map(int, dimensions.split("x"))
            if width < 256 or height < 256 or width > 2048 or height > 2048:
                return {"valid": False, "error": "Dimensions must be between 256x256 and 2048x2048"}
        except ValueError:
            return {"valid": False, "error": "Invalid dimensions format"}
        
        # Validate vendor-specific constraints
        if vendor in ImageGenerationService.SUPPORTED_DIMENSIONS:
            if model in ImageGenerationService.SUPPORTED_DIMENSIONS[vendor]:
                supported = ImageGenerationService.SUPPORTED_DIMENSIONS[vendor][model]
                if dimensions not in supported:
                    return {
                        "valid": False, 
                        "error": f"Dimensions {dimensions} not supported for {vendor}/{model}. Supported: {supported}"
                    }
        
        steps = kwargs.get("steps")
        if steps is not None and (not isinstance(steps, int) or steps < 1 or steps > 150):
            return {"valid": False, "error": "Steps must be between 1 and 150"}
        
        guidance_scale = kwargs.get("guidance_scale")
        if guidance_scale is not None and (not isinstance(guidance_scale, (int, float)) or guidance_scale < 1.0 or guidance_scale > 20.0):
            return {"valid": False, "error": "Guidance scale must be between 1.0 and 20.0"}
        
        return {"valid": True}
    
    @staticmethod
    async def _get_model_info(vendor: str, model: str) -> Optional[Dict[str, Any]]:
        """Get model information from database"""
        try:
            model_query = """
            SELECT vm.id, vm.name, vm.display_name, vm.is_active
            FROM vendor_models vm
            JOIN vendors v ON vm.vendor_id = v.id
            WHERE v.name = $1 AND vm.name = $2 AND vm.is_active = true
            """
            
            result = await DatabaseUtils.execute_query(model_query, [vendor, model], fetch_all=False)
            return result
            
        except Exception as e:
            logger.error(f"Failed to get model info for {vendor}/{model}: {e}")
            return None
    
    @staticmethod
    async def _simulate_image_generation(
        vendor: str, model: str, prompt: str, count: int, 
        dimensions: str, quality: str, style: Optional[str]
    ) -> Dict[str, Any]:
        """
        Simulate image generation (replace with actual API calls in production)
        """
        try:
            # Simulate generation time based on parameters
            base_time = 2000  # 2 seconds base
            time_per_image = 1500  # 1.5 seconds per additional image
            quality_multiplier = 1.5 if quality == "hd" or quality == "high" else 1.0
            
            generation_time = int((base_time + (count - 1) * time_per_image) * quality_multiplier)
            
            # Simulate delay
            await asyncio.sleep(min(generation_time / 1000, 3.0))  # Max 3 second delay for testing
            
            # Generate mock image URLs
            image_urls = []
            for i in range(count):
                # In production, these would be real URLs from the providers
                url = f"https://api-lens-generated.example.com/{vendor}/{model}/{uuid4()}.png"
                image_urls.append(url)
            
            return {
                "success": True,
                "image_urls": image_urls,
                "generation_time_ms": generation_time
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Generation failed: {str(e)}"
            }
    
    @staticmethod
    async def _log_generation_request(
        vendor: str, model: str, company_id: UUID, user_id: UUID,
        prompt: str, negative_prompt: Optional[str], image_count: int,
        dimensions: str, quality: str, style: Optional[str],
        seed: Optional[int], steps: int, guidance_scale: float,
        cost: float, image_urls: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Log image generation request to database"""
        try:
            # Get vendor and model IDs
            vendor_model_query = """
            SELECT v.id as vendor_id, vm.id as model_id
            FROM vendor_models vm
            JOIN vendors v ON vm.vendor_id = v.id
            WHERE v.name = $1 AND vm.name = $2
            """
            
            ids_result = await DatabaseUtils.execute_query(vendor_model_query, [vendor, model], fetch_all=False)
            if not ids_result:
                logger.error(f"Could not find vendor/model IDs for {vendor}/{model}")
                return None
            
            request_id = f"img_{uuid4()}"
            
            log_query = """
            INSERT INTO requests (
                id, request_id, company_id, client_user_id, vendor_id, model_id,
                method, endpoint, prompt, negative_prompt, image_count, image_urls,
                image_dimensions, image_quality, image_style, seed, generation_steps,
                guidance_scale, total_cost, timestamp_utc, status_code, total_latency_ms
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22
            ) RETURNING id, request_id
            """
            
            result = await DatabaseUtils.execute_query(
                log_query,
                [
                    uuid4(), request_id, company_id, user_id,
                    ids_result["vendor_id"], ids_result["model_id"],
                    "POST", f"/v1/{vendor}/images/generations",
                    prompt, negative_prompt, image_count, image_urls,
                    dimensions, quality, style, seed, steps,
                    guidance_scale, cost, datetime.utcnow(), 200, 2500
                ],
                fetch_all=False
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to log generation request: {e}")
            return None