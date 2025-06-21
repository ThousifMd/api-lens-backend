import requests
import json
from datetime import datetime
import pytz
import time
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def get_db_session():
    """Create a database session"""
    db_url = os.getenv("POSTGRES_DB_URL")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    return Session()

def verify_log_metrics(session, call_id, vendor):
    """Verify that the log entry has the expected metrics"""
    query = text("""
        SELECT * FROM api_logs 
        WHERE call_id = :call_id 
        AND vendor = :vendor 
        ORDER BY timestamp DESC 
        LIMIT 2
    """)
    result = session.execute(query, {"call_id": call_id, "vendor": vendor})
    logs = result.fetchall()
    
    if len(logs) != 2:
        print(f"❌ {vendor.upper()} - Expected 2 logs (request and response), got {len(logs)}")
        return False
    
    request_log, response_log = logs
    
    # Verify request log
    if request_log.log_type != 'request':
        print(f"❌ {vendor.upper()} - First log should be request type")
        return False
    
    # Verify response log
    if response_log.log_type != 'response':
        print(f"❌ {vendor.upper()} - Second log should be response type")
        return False
    
    # Verify metrics based on vendor
    if vendor == 'openai':
        if not response_log.prompt_tokens or not response_log.completion_tokens:
            print(f"❌ {vendor.upper()} - Missing token counts")
            return False
        if not response_log.cost:
            print(f"❌ {vendor.upper()} - Missing cost")
            return False
    elif vendor in ['claude', 'gemini']:
        if not response_log.latency:
            print(f"❌ {vendor.upper()} - Missing latency")
            return False
    
    print(f"✅ {vendor.upper()} - All metrics verified")
    return True

def test_proxy_chat():
    base_url = "http://localhost:8001/proxy"
    
    # New test cases for each model
    test_cases = {
        "openai": [
            {"model": "gpt-4", "messages": [{"role": "user", "content": "Who wrote the play Hamlet?"}]},
            {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Summarize the theory of relativity in one sentence."}]},
            {"model": "gpt-4", "messages": [{"role": "user", "content": "List three uses of artificial intelligence in healthcare."}]},
            {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Translate 'Good morning' to French."}]},
            {"model": "gpt-4", "messages": [{"role": "user", "content": "What is the boiling point of water in Celsius?"}]},
            {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Name a famous painting by Leonardo da Vinci."}]}
        ],
        "claude": [
            {"model": "claude-3-opus-20240229", "messages": [{"role": "user", "content": "Who wrote the play Hamlet?"}]},
            {"model": "claude-3-sonnet-20240229", "messages": [{"role": "user", "content": "Summarize the theory of relativity in one sentence."}]},
            {"model": "claude-3-opus-20240229", "messages": [{"role": "user", "content": "List three uses of artificial intelligence in healthcare."}]},
            {"model": "claude-3-sonnet-20240229", "messages": [{"role": "user", "content": "Translate 'Good morning' to French."}]},
            {"model": "claude-3-opus-20240229", "messages": [{"role": "user", "content": "What is the boiling point of water in Celsius?"}]},
            {"model": "claude-3-sonnet-20240229", "messages": [{"role": "user", "content": "Name a famous painting by Leonardo da Vinci."}]}
        ],
        "gemini": [
            {"model": "gemini-1.5-pro", "messages": [{"role": "user", "content": "Who wrote the play Hamlet?"}]},
            {"model": "gemini-1.0-pro", "messages": [{"role": "user", "content": "Summarize the theory of relativity in one sentence."}]},
            {"model": "gemini-1.5-pro", "messages": [{"role": "user", "content": "List three uses of artificial intelligence in healthcare."}]},
            {"model": "gemini-1.0-pro", "messages": [{"role": "user", "content": "Translate 'Good morning' to French."}]},
            {"model": "gemini-1.5-pro", "messages": [{"role": "user", "content": "What is the boiling point of water in Celsius?"}]},
            {"model": "gemini-1.0-pro", "messages": [{"role": "user", "content": "Name a famous painting by Leonardo da Vinci."}]}
        ]
    }

    results = {}

    for model, cases in test_cases.items():
        print(f"\nTesting {model.upper()} model...")
        results[model] = []
        
        for i, test_case in enumerate(cases, 1):
            print(f"\nTest case {i} for {model}:")
            print(f"Prompt: {test_case['messages'][0]['content']}")
            
            try:
                start_time = time.time()
                response = requests.post(
                    f"{base_url}/{model}/chat",
                    json=test_case,
                    headers={"Content-Type": "application/json"}
                )
                end_time = time.time()
                
                result = {
                    "test_case": i,
                    "status_code": response.status_code,
                    "response_time": end_time - start_time,
                    "response": response.json() if response.status_code == 200 else response.text
                }
                
                print(f"Status Code: {result['status_code']}")
                print(f"Response Time: {result['response_time']:.2f} seconds")
                if response.status_code == 200:
                    print("Response:", json.dumps(result['response'], indent=2))
                else:
                    print("Error:", result['response'])
                
                results[model].append(result)
                
            except Exception as e:
                print(f"Error in test case {i}: {str(e)}")
                results[model].append({
                    "test_case": i,
                    "error": str(e)
                })
            
            # Add a small delay between requests
            time.sleep(2)

    # Save results to a file
    with open('test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\nTest results have been saved to test_results.json")

def verify_database_logs():
    """Verify that the logs were properly stored in the database"""
    # TODO: Add database verification logic
    pass

if __name__ == "__main__":
    print("Starting LLM Proxy Tests...")
    test_proxy_chat()
    print("\nAll tests completed!")
    
    # TODO: Add database verification
    # verify_database_logs() 