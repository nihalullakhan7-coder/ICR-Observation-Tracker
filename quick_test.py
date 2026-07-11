"""
One-off sanity check: confirms whether GROQ_API_KEY in .env actually
works. Run directly:

    python quick_test.py

Never prints the key itself -- safe to paste output anywhere for help.
"""

from dotenv import load_dotenv
import os

load_dotenv(override=True)

try:
    from groq import Groq
except ImportError:
    print("FAIL: 'groq' not installed. Run: pip install groq")
    raise SystemExit(1)

key = os.environ.get("GROQ_API_KEY", "")
if not key:
    print("FAIL: GROQ_API_KEY is empty or not found in .env")
    raise SystemExit(1)

print(f"Testing key starting with: {key[:10]}...")

try:
    client = Groq(api_key=key)
    response = client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=[{"role": "user", "content": "Say the word PASS and nothing else."}],
    )
    print("SUCCESS -- API responded:", response.choices[0].message.content.strip())
except Exception as e:
    print(f"FAIL: {type(e).__name__}: {e}")