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

MAX_DIMENSION = 900  # smaller image = fewer input tokens, to fit Groq's free-tier TPM limit
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

    client = Groq(api_key=key)

    b64 = _prepare_image_b64(image_bytes)
    prompt = _build_prompt(skill_codes)

    # qwen/qwen3.6-27b officially supports reasoning_effort="none" to
    # properly disable its verbose chain-of-thought reasoning at the API
    # level (the in-prompt "/no_think" trick was not reliably honored).
    # reasoning_format="hidden" further ensures only the final answer
    # text is returned, with no <think> content mixed into it.
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        max_tokens=2000,
        reasoning_effort="none",
        reasoning_format="hidden",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                ],
            }
        ],
    )

    text = response.choices[0].message.content.strip()

    # This model exposes its reasoning in <think>...</think> before the
    # actual answer -- strip that out before parsing.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    if text.startswith("```json"):
        text = text[len("```json"):]
    if text.startswith("```"):
        text = text[len("```"):]
    if text.endswith("```"):
        text = text[:-len("```")]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Model response wasn't valid JSON -- try again. "
            f"Raw response start: {text[:200]}"
        ) from e