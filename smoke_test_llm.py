"""Smoke test for OpenAI API access with gpt-6-luna.

Safe minimal test that:
- Loads .env locally
- Reads LLM_API_KEY without exposing it
- Makes one request to gpt-6-luna at temperature 0
- Reports token usage and errors clearly
"""

import os
import sys
from dotenv import load_dotenv

# Load .env file
load_dotenv(override=True)

# Read API key
api_key = os.getenv("LLM_API_KEY")

if not api_key:
    print("ERROR: LLM_API_KEY not found in .env file")
    sys.exit(1)

# Mask key for display (show only first/last 4 chars)
masked_key = f"{api_key[:7]}...{api_key[-4:]}" if len(api_key) > 11 else "***"
print(f"✓ API key loaded: {masked_key}")

try:
    # Import OpenAI client
    try:
        from openai import OpenAI
    except ImportError:
        print("\nERROR: openai package not installed")
        print("Run: pip install openai")
        sys.exit(1)
    
    print("✓ OpenAI package imported")
    
    # Create client
    client = OpenAI(api_key=api_key)
    print("✓ OpenAI client created")
    
    # Make minimal request
    print("\nMaking test request to gpt-6-luna...")
    print("(Note: gpt-6-luna only supports default temperature=1)")
    
    response = client.chat.completions.create(
        model="gpt-6-luna",
        messages=[
            {"role": "user", "content": "Reply with exactly: Hello from DriftShield"}
        ],
        max_completion_tokens=50
    )
    
    # Extract response
    message = response.choices[0].message.content
    usage = response.usage
    
    # Display results
    print("\n" + "="*60)
    print("RESPONSE:")
    print("="*60)
    print(message)
    print("\n" + "="*60)
    print("TOKEN USAGE:")
    print("="*60)
    print(f"  Prompt tokens:     {usage.prompt_tokens}")
    print(f"  Completion tokens: {usage.completion_tokens}")
    print(f"  Total tokens:      {usage.total_tokens}")
    print("="*60)
    
    print("\n✅ SUCCESS: OpenAI API access verified")
    print(f"   Model: gpt-6-luna")
    print(f"   Temperature: 1 (default, only supported value)")
    
except Exception as e:
    error_msg = str(e)
    
    print("\n" + "="*60)
    print("ERROR:")
    print("="*60)
    
    # Parse common errors without exposing key
    if "authentication" in error_msg.lower() or "invalid api key" in error_msg.lower():
        print("❌ AUTHENTICATION ERROR")
        print("   The API key may be invalid or expired")
        print("   Check LLM_API_KEY in .env file")
    elif "model" in error_msg.lower() and "does not exist" in error_msg.lower():
        print("❌ MODEL ACCESS ERROR")
        print("   Model 'gpt-6-luna' may not be available")
        print("   Check your OpenAI account permissions")
    elif "quota" in error_msg.lower() or "rate limit" in error_msg.lower():
        print("❌ QUOTA/RATE LIMIT ERROR")
        print("   API quota exceeded or rate limit hit")
        print("   Check your OpenAI account billing/limits")
    elif "connection" in error_msg.lower() or "timeout" in error_msg.lower():
        print("❌ NETWORK ERROR")
        print("   Could not connect to OpenAI API")
        print("   Check your internet connection")
    else:
        print("❌ UNEXPECTED ERROR")
        print(f"   {error_msg[:200]}")  # Truncate to avoid exposing sensitive data
    
    print("="*60)
    sys.exit(1)
