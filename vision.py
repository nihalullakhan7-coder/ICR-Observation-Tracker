"""
Sends a photographed Observation Record page to Groq (vision-capable Llama
model) and gets back structured data: the handwritten header fields, plus,
per skill code, which levels (B/I/P/E) have an actual handwritten date in
their date box.

Design rule (per product spec): a level is only ever marked if a date is
literally visible in that level's date box. No inferring, no auto-filling
lower levels from a higher one, no guessing on ambiguous handwriting --
those cases should come back as null and get routed to manual review.

Uses Groq because its free tier works without requiring a billing/payment
method on file. Get a free key at: https://console.groq.com/keys
"""

import base64
import io
import json
import os
import re

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

try:
    from groq import Groq
except ImportError as e:
    raise ImportError(
        "The 'groq' package is not installed.\nFix: pip install groq"
    ) from e

try:
    from PIL import Image
except ImportError as e:
    raise ImportError("The 'Pillow' package is not installed. Run: pip install Pillow") from e


MODEL = "qwen/qwen3.6-27b"  # Groq's current vision-capable model (preview)

MAX_DIMENSION = 1568
JPEG_QUALITY = 85


def _prepare_image_b64(image_bytes: bytes) -> str:
    """Resize/re-encode, return base64 string (no data-URL prefix)."""
    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert("RGB")

    width, height = img.size
    longest_edge = max(width, height)
    if longest_edge > MAX_DIMENSION:
        scale = MAX_DIMENSION / longest_edge
        img = img.resize((int(width * scale), int(height * scale)), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


def _build_prompt(skill_codes: list[str]) -> str:
    skill_list = ", ".join(skill_codes)
    return """You are an OCR engine for a preschool "Observation Record" booklet page.

The page has a table with columns: Presentation, Skill, Beginner (B),
Intermediate (I), Proficient (P), Expert (E). Under each level's descriptive
text is a small date box in DD/MM format (printed as "_ _ / _ _" when blank).

Task, for skill rows matching: """ + skill_list + """

1. Read the header fields: Name, Class, Section, Year (may be partially
   filled or blank -- return null for anything not legible or not present).
2. For each skill row, for each level (B, I, P, E), determine whether a
   handwritten date is actually present in that level's date box.
   - If a date is clearly handwritten, return it as a string in DD/MM
     format exactly as written.
   - If the box is blank, or shows only the printed placeholder, return
     null for that level. Do not guess or infer a date that is not
     visually present.
   - If handwriting is present but illegible or ambiguous, return null
     and add the skill_code to "needs_review".
3. Only mark levels with an unambiguous handwritten date.

Respond with ONLY raw JSON (no markdown fences, no prose), in exactly
this shape:
{
  "student": {"name": string|null, "class": string|null, "section": string|null, "year": string|null},
  "skills": [
    {"skill_code": "S1", "levels": {"B": "12/05"|null, "I": null, "P": null, "E": null}}
  ],
  "needs_review": ["S3"]
}"""


def extract_from_image(image_bytes, media_type, skill_codes, api_key=None):
    key = api_key or os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Get a free key at "
            "https://console.groq.com/keys and add it to .env as:\n"
            "  GROQ_API_KEY=your-key-here"
        )

    # Debug lines to inspect the loaded API key details
    print("=" * 50)
    print("Loaded key:", repr(key))
    print("Starts with:", key[:10] if key else "None")
    print("Length:", len(key) if key else 0)
    print("=" * 50)

    client = Groq(api_key=key)
    print("Testing API...")
    print(client.models.list())
    print("API test passed!")

    b64 = _prepare_image_b64(image_bytes)
    prompt = _build_prompt(skill_codes)

    try:
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64}"
                            },
                        },
                    ],
                }
            ],
        )
    except Exception:
        import traceback
        traceback.print_exc()
        raise

    text = response.choices[0].message.content.strip()

    # This model exposes its reasoning in <think>...</think> before the
    # actual answer -- strip that out before parsing.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # Clean up markdown code blocks if the model wrapped the JSON response.
    # Slicing is performed using clean variables to prevent any truncation.
    prefix_json = "```json"
    prefix_fence = "```"
    suffix_fence = "```"

    if text.startswith(prefix_json):
        text = text[len(prefix_json):]
    elif text.startswith(prefix_fence):
        text = text[len(prefix_fence):]
        
    if text.endswith(suffix_fence):
        text = text[:-len(suffix_fence)]
        
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Model response wasn't valid JSON. Raw response:\n{text[:500]}"
        ) from e