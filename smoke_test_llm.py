"""Smoke test for Google Gemini API access through OpenAI-compatible endpoint.

Safe minimal test that:
- Loads .env locally
- Reads GEMINI_API_KEY without exposing it
- Makes one request to gemini-3.8-flash using the model's default temperature
- Reports token usage and errors clearly
- Treats None or empty responses as failures
- Safely handles missing token usage
"""

import os
import sys
from dotenv import load_dotenv

# Load .env file
load_dotenv(override=True)

# Read API key
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("ERROR: GEMINI_API_KEY not found in .env file")
    sys.exit(1)

# Never print the API key, even partially
print("[OK] API key loaded from environment")

try:
    # Import OpenAI client
    try:
        from openai import OpenAI
    except ImportError:
        print("\nERROR: openai package not installed")
        print("Run: pip install openai")
        sys.exit(1)

    print("[OK] OpenAI package imported")

    # Create client configured for Gemini's OpenAI-compatible endpoint
    client = OpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    print("[OK] Gemini client created")

    # Make minimal request
    print("\nMaking test request to gemini-3.8-flash...")
    print("(Using model's default temperature)")

    response = client.chat.completions.create(
        model="gemini-3.8-flash",
        messages=[
            {"role": "user", "content": "Reply with exactly: Hello from DriftShield"}
        ],
        max_tokens=50
    )

    # Validate response structure
    if not response.choices or len(response.choices) == 0:
        print("\n" + "="*60)
        print("ERROR: No response choices returned")
        print("="*60)
        sys.exit(1)

    # Extract response
    message = response.choices[0].message.content
    finish_reason = response.choices[0].finish_reason
    usage = response.usage

    # Treat None or empty content as failure
    if message is None or message == "":
        print("\n" + "="*60)
        print("ERROR: Response content is None or empty")
        print("="*60)
        print(f"Finish reason: {finish_reason}")
        print(f"Content type: {type(message)}")
        print(f"Content repr: {repr(message)}")
        if usage:
            print(f"\nToken usage:")
            print(f"  Prompt tokens:     {usage.prompt_tokens}")
            print(f"  Completion tokens: {usage.completion_tokens}")
            print(f"  Total tokens:      {usage.total_tokens}")
        print("="*60)
        sys.exit(1)

    # Display results
    print("\n" + "="*60)
    print("RESPONSE:")
    print("="*60)
    print(message)
    print("\n" + "="*60)
    print("TOKEN USAGE:")
    print("="*60)
    if usage:
        print(f"  Prompt tokens:     {usage.prompt_tokens}")
        print(f"  Completion tokens: {usage.completion_tokens}")
        print(f"  Total tokens:      {usage.total_tokens}")
    else:
        print("  Token usage unavailable")
    print("="*60)
    print(f"Finish reason: {finish_reason}")
    print("="*60)

    print("\n[SUCCESS] Gemini API access verified")
    print(f"   Model: gemini-3.8-flash")
    print(f"   Temperature: Model default (not specified)")
    sys.exit(0)

except Exception as e:
    error_msg = str(e).lower()
    
    # Remove any potential key exposure from error message
    safe_msg = str(e)
    if api_key and api_key in safe_msg:
        safe_msg = safe_msg.replace(api_key, "[REDACTED]")

    print("\n" + "="*60)
    print("ERROR:")
    print("="*60)

    # Classify errors without exposing secrets
    if "401" in error_msg or "authentication" in error_msg or "invalid api key" in error_msg or "unauthorized" in error_msg:
        print("[FAIL] AUTHENTICATION ERROR")
        print("   The API key may be invalid or expired")
        print("   Check GEMINI_API_KEY in .env file")
    elif "404" in error_msg or ("model" in error_msg and "not found" in error_msg):
        print("[FAIL] MODEL ACCESS ERROR")
        print("   Model 'gemini-3.8-flash' may not be available")
        print("   Check your Google Cloud project permissions")
    elif "429" in error_msg or "quota" in error_msg or "rate limit" in error_msg or "resource exhausted" in error_msg:
        print("[FAIL] QUOTA/RATE LIMIT ERROR")
        print("   API quota exceeded or rate limit hit")
        print("   Check your Google Cloud project billing/limits")
    elif "403" in error_msg or "permission" in error_msg or "forbidden" in error_msg:
        print("[FAIL] PERMISSION ERROR")
        print("   Access denied to the requested resource")
        print("   Check your Google Cloud project permissions")
    elif "connection" in error_msg or "timeout" in error_msg or "network" in error_msg:
        print("[FAIL] NETWORK ERROR")
        print("   Could not connect to Gemini API")
        print("   Check your internet connection")
    else:
        print("[FAIL] UNEXPECTED ERROR")
        # Truncate and sanitize error message
        print(f"   {safe_msg[:200]}")

    print("="*60)
    sys.exit(1)
