import json

from .llm import generate_text


def generate_article(title, content, facts):

    facts_text = json.dumps(
        facts,
        ensure_ascii=False,
        indent=2
    )

    prompt = f"""
You are a professional newspaper editor.

Create a completely new news article using
the provided facts and source material.

IMPORTANT RULES:

1. Keep the main context unchanged.
2. Preserve all important facts.
3. Do not invent information.
4. Do not change names.
5. Do not change dates.
6. Do not change locations.
7. Do not change numbers.
8. Do not create fake quotes.
9. Do not add personal opinions.
10. Do not copy sentences directly.
11. Use professional newspaper language.
12. Write naturally.
13. Create a new headline.
14. The generated article must remain faithful
    to the original news.

Return ONLY this format:

HEADLINE:
<new headline>

ARTICLE:
<new article>

ORIGINAL TITLE:
{title}

ORIGINAL CONTENT:
{content}

EXTRACTED FACTS:
{facts_text}
"""

    response = generate_text(prompt)

    return response.strip()