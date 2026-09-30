from requests.exceptions import RequestException

from ai.fact_extractor import extract_facts
from ai.article_generator import generate_article
from ai.fact_verifier import verify_article


def process_news(title, content):
    """Process the manual demo input, preserving its public result contract."""
    stage = "fact_extraction"
    try:
        facts = extract_facts(title, content)
        if not isinstance(facts, dict) or not facts or "error" in facts:
            return {"status": "failed", "stage": stage, "error": facts}

        stage = "article_generation"
        article = generate_article(title, content, facts)
        if not isinstance(article, str) or not article.strip():
            return {"status": "failed", "stage": stage, "error": "No generated article"}

        stage = "article_verification"
        verification = verify_article(content, facts, article)
        approved = isinstance(verification, dict) and verification.get("approved") is True
        return {
            "status": "approved" if approved else "needs_review",
            "original_title": title,
            "original_content": content,
            "facts": facts,
            "generated_article": article,
            "verification": verification,
        }
    except RequestException as error:
        return {"status": "failed", "stage": stage, "error": str(error)}
