"""Diagnostic script to inspect Gemini response structure.

This script makes a test call and prints the complete response structure
without exposing secrets, to understand why content might be None.
"""

import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("ERROR: GEMINI_API_KEY not found")
    sys.exit(1)

print("Creating Gemini client...")
client = OpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

print("Making test request...")
response = client.chat.completions.create(
    model="gemini-3.8-flash",
    messages=[
        {"role": "user", "content": "Say hello"}
    ],
    max_tokens=50
)

print("\n" + "="*60)
print("RESPONSE STRUCTURE ANALYSIS")
print("="*60)

# Response type and attributes
print(f"\nResponse type: {type(response)}")
print(f"Response attributes: {dir(response)}")

# Choices analysis
print(f"\nNumber of choices: {len(response.choices)}")
if response.choices:
    choice = response.choices[0]
    print(f"Choice type: {type(choice)}")
    print(f"Choice attributes: {dir(choice)}")
    
    # Finish reason
    print(f"\nFinish reason: {choice.finish_reason}")
    
    # Message analysis
    message = choice.message
    print(f"\nMessage type: {type(message)}")
    print(f"Message attributes: {dir(message)}")
    print(f"Message.content: {repr(message.content)}")
    print(f"Message.role: {message.role}")
    
    # Check for alternative content fields
    if hasattr(message, 'text'):
        print(f"Message.text: {repr(message.text)}")
    if hasattr(message, 'content_parts'):
        print(f"Message.content_parts: {message.content_parts}")
    if hasattr(message, 'parts'):
        print(f"Message.parts: {message.parts}")
    
    # Tool calls
    print(f"\nMessage.tool_calls: {message.tool_calls}")
    print(f"Message.function_call: {getattr(message, 'function_call', 'N/A')}")

# Usage analysis
print(f"\nUsage type: {type(response.usage)}")
print(f"Usage attributes: {dir(response.usage)}")
print(f"Prompt tokens: {response.usage.prompt_tokens}")
print(f"Completion tokens: {response.usage.completion_tokens}")
print(f"Total tokens: {response.usage.total_tokens}")

# Additional response fields
print(f"\nResponse ID: {response.id}")
print(f"Response model: {response.model}")
print(f"Response created: {response.created}")

# Check for alternative response formats
if hasattr(response, 'content'):
    print(f"Response.content: {response.content}")

print("\n" + "="*60)
print("If content is None, this indicates a response structure issue.")
print("="*60)
