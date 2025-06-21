import os
import sys
import asyncio
import json
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai

# Add the parent directory to the Python path (if needed)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# Get API key from environment
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Configure the Gemini client
genai.configure(api_key=api_key)

async def check_available_models():
    """Check which Gemini models are available."""
    print("\nChecking available models...")
    print("-" * 50)
    
    models_to_check = [
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-1.5-pro-vision",
        "gemini-1.0-pro",
        "gemini-1.0-pro-vision",
        "gemini-pro",
        "gemini-pro-vision",
        "gemini-ultra",
        "gemini-ultra-vision"
    ]
    
    available_models = []
    
    for model_name in models_to_check:
        try:
            model = genai.GenerativeModel(model_name)
            response = await model.generate_content_async("Hello")
            if response:
                print(f"✓ {model_name} is available")
                available_models.append(model_name)
        except Exception as e:
            print(f"✗ {model_name} is not available: {str(e)}")
    
    return available_models

async def test_gemini_models():
    """Run test prompts across available Gemini models."""
    available_models = await check_available_models()
    
    if not available_models:
        print("No models are currently available.")
        return
    
    print(f"\nFound {len(available_models)} available models: {', '.join(available_models)}")
    
    test_cases = [
        {
            "name": "Technical explanation",
            "prompt": "Explain quantum computing in simple terms"
        },
        {
            "name": "Creative writing",
            "prompt": "Write a short poem about artificial intelligence"
        },
        {
            "name": "Factual knowledge",
            "prompt": "What are Isaac Asimov's Three Laws of Robotics?"
        }
    ]
    
    results = []
    
    for model_name in available_models:
        print(f"\nTesting {model_name}")
        print("-" * 50)
        
        model = genai.GenerativeModel(model_name)
        
        for test_case in test_cases:
            print(f"\nTesting {model_name} - {test_case['name']}")
            print("-" * 50)
            
            try:
                response = await model.generate_content_async(test_case["prompt"])
                token_count = getattr(response, 'token_count', None)
                cost = calculate_cost(token_count) if token_count else None
                
                result = {
                    "model": model_name,
                    "test_case": test_case["name"],
                    "prompt": test_case["prompt"],
                    "response": response.text,
                    "tokens_used": token_count,
                    "cost": cost,
                    "timestamp": datetime.now().isoformat()
                }
                
                print(f"Response: {response.text[:100]}...")
                if token_count:
                    print(f"Tokens used: {token_count}")
                if cost:
                    print(f"Cost: ${cost:.6f}")
                
                results.append(result)
            except Exception as e:
                print(f"Error testing {model_name} with {test_case['name']}: {str(e)}")
    
    # Save results to file
    output_file = "gemini_test_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nTest results have been saved to {os.path.abspath(output_file)}")

def calculate_cost(token_count: int) -> float:
    """Estimate Gemini API cost based on token usage."""
    input_cost = (token_count * 0.5) * 0.00025 / 1000
    output_cost = (token_count * 0.5) * 0.0005 / 1000
    return input_cost + output_cost

if __name__ == "__main__":
    asyncio.run(test_gemini_models())
