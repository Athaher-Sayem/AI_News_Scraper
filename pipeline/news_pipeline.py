from ai.fact_extractor import extract_facts
from ai.article_generator import generate_article
from ai.fact_verifier import verify_article


def process_news(title, content):

    print("\n==============================")
    print("STARTING NEWS PIPELINE")
    print("==============================")

    print("\n[1] Extracting facts...")

    facts = extract_facts(
        title,
        content
    )

    if "error" in facts:

        return {
            "status": "failed",
            "stage": "fact_extraction",
            "error": facts
        }

    print("[OK] Facts extracted")


    print("\n[2] Generating article...")

    article = generate_article(
        title,
        content,
        facts
    )

    print("[OK] Article generated")


    print("\n[3] Verifying article...")

    verification = verify_article(
        content,
        facts,
        article
    )

    print("[OK] Verification complete")


    if verification.get("approved"):

        status = "approved"

    else:

        status = "needs_review"


    return {
        "status": status,
        "original_title": title,
        "original_content": content,
        "facts": facts,
        "generated_article": article,
        "verification": verification
    }