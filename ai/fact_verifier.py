import json

from .llm import generate_text


def verify_article(
    original_content,
    facts,
    generated_article
):

    facts_text = json.dumps(
        facts,
        ensure_ascii=False,
        indent=2
    )

    prompt = f"""
You are a strict news fact-checking system.

Compare the generated article against the
original source and extracted facts.

Check:

1. Are the names correct?
2. Are the dates correct?
3. Are the locations correct?
4. Are the numbers correct?
5. Are the important facts preserved?
6. Are there invented facts?
7. Are there unsupported claims?
8. Are quotes accurate?
9. Has the main context changed?

Return ONLY valid JSON.

Use this structure:

{{
    "approved": true,
    "score": 0,
    "errors": [],
    "warnings": [],
    "missing_facts": [],
    "invented_facts": [],
    "summary": ""
}}

ORIGINAL CONTENT:

{original_content}

EXTRACTED FACTS:

{facts_text}

GENERATED ARTICLE:

{generated_article}
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
        result = json.loads(response)

    except json.JSONDecodeError:

        return {
            "approved": False,
            "score": 0,
            "errors": [
                "Could not parse verification result"
            ],
            "raw_response": response
        }

    return result