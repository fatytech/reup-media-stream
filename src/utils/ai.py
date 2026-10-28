import os
from openai import OpenAI


def translate_desc(msg: str, langcode: str) -> str:
    """Translate msg to langcode, keeping all proper nouns and brand/product names intact."""
    client = OpenAI(
        api_key=os.environ["AI_API_KEY"],
        base_url=os.environ.get("AI_BASE_URL", "https://gpt4.shupremium.com/v1"),
        timeout=60,
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a translator. Translate the user's message to the target language. "
                    "Rules: "
                    "1. Keep all proper nouns, brand names, and product names exactly as-is "
                    "(e.g. 'Flow 2', 'Keychron Q1', 'Nike'). "
                    "2. Output only the translated text, no explanations."
                ),
            },
            {"role": "user", "content": f"Translate to {langcode}:\n{msg}"},
        ],
        temperature=0.3,
    )
    return (resp.choices[0].message.content or "").strip()
