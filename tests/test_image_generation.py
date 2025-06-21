import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_image_generation():
    base_url = "http://localhost:8001/proxy"
    
    # Test cases for image generation
    test_cases = [
        {
            "prompt": "A magical forest scene in Studio Ghibli style, with soft lighting, whimsical creatures, and a sense of wonder. The scene should have the distinctive hand-drawn quality and warm color palette of Hayao Miyazaki's work.",
            "model": "dall-e-3",
            "parameters": {
                "size": "1024x1024",
                "quality": "standard",
                "style": "vivid"
            }
        },
        {
            "prompt": "A cozy Japanese countryside house in Studio Ghibli style, surrounded by cherry blossoms and a small garden. The scene should capture the peaceful, nostalgic atmosphere typical of Ghibli films.",
            "model": "dall-e-3",
            "parameters": {
                "size": "1792x1024",
                "quality": "standard",
                "style": "vivid"
            }
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest case {i}:")
        print(f"Prompt: {test_case['prompt']}")
        
        try:
            response = requests.post(
                f"{base_url}/openai/generate-image",
                json=test_case,
                headers={"Content-Type": "application/json"}
            )
            
            result = {
                "test_case": i,
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else response.text
            }
            
            print(f"Status Code: {result['status_code']}")
            if response.status_code == 200:
                print("Generated Image URLs:")
                for image_data in result['response']['data']:
                    print(f"URL: {image_data['url']}")
                    print(f"Revised Prompt: {image_data['revised_prompt']}")
            else:
                print("Error:", result['response'])
            
            results.append(result)
            
        except Exception as e:
            print(f"Error in test case {i}: {str(e)}")
            results.append({
                "test_case": i,
                "error": str(e)
            })
    
    # Save results to a file
    with open('image_generation_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\nTest results have been saved to image_generation_results.json")

if __name__ == "__main__":
    print("Starting Image Generation Tests...")
    test_image_generation()
    print("\nAll tests completed!") 