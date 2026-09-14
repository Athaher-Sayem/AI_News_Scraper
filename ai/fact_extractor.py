import json

from .llm import generate_text


def extract_facts(title, content):

    prompt = f"""
You are a professional news fact extraction system.

Your job is to extract facts from the original news article.

Do NOT write a new article.

Do NOT add information.

Do NOT guess missing information.

Return ONLY valid JSON.

The JSON must have this structure:

{{
    "title": "",
    "who": [],
    "what": "",
    "when": "",
    "where": "",
    "why": "",
    "important_facts": [],
    "people": [],
    "organizations": [],
    "locations": [],
    "dates": [],
    "numbers": [],
    "quotes": []
}}

ORIGINAL TITLE:
{title}

ORIGINAL CONTENT:
{content}
"""

    response = generate_text(prompt)

    response = response.strip()

    if response.startswith("```json"):
        response = response[7:]

    if response.startswith("```"):
        response = response[3:]

    if response.endswith("```"):
        response = response[:-3]

    response = response.strip()

    try:
        facts = json.loads(response)

    except json.JSONDecodeError:

        return {
            "error": "Could not parse AI response",
            "raw_response": response
        }

    return facts