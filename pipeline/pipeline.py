import json
from pathlib import Path

import pandas as pd
from requests.exceptions import RequestException

from pipeline import progress
from pipeline.content_checker import check_content
from ai.fact_extractor import extract_facts
from ai.article_generator import generate_article
from ai.fact_verifier import verify_article
from utils.csv_utils import write_csv_atomic


RESULT_COLUMNS = ("status", "reason", "facts", "generated_article", "verification")


def process_row(news):
    # Clear previous results if a processed CSV is used as input.
    news.update(dict.fromkeys(RESULT_COLUMNS, ""))
    progress.step("content_check")
    valid, reason = check_content(news)
    if not valid:
        news.update(status="CONTENT_REJECTED", reason=reason)
        return news

    stage = "FACT_EXTRACTION_FAILED"
    try:
        progress.step("fact_extraction")
        facts = extract_facts(news["title"], news["content"])
        news["facts"] = json.dumps(facts, ensure_ascii=False)
        if not isinstance(facts, dict) or not facts or "error" in facts:
            news.update(status=stage, reason="Could not extract facts")
            return news

        stage = "ARTICLE_GENERATION_FAILED"
        progress.step("article_generation")
        article = generate_article(news["title"], news["content"], facts)
        if not isinstance(article, str) or not article.strip():
            news.update(status=stage, reason="Could not generate article")
            return news
        news["generated_article"] = article.strip()

        stage = "ARTICLE_VERIFICATION_FAILED"
        progress.step("verification")
        verification = verify_article(news["content"], facts, article)
        news["verification"] = json.dumps(verification, ensure_ascii=False)
        if isinstance(verification, dict) and verification.get("approved") is True:
            news["status"] = "APPROVED"
        else:
            reason = "Article failed verification"
            if isinstance(verification, dict):
                reason = verification.get("summary") or reason
            news.update(status="ARTICLE_REJECTED", reason=reason)
    except RequestException as error:
        news.update(status=stage, reason=str(error))

    return news


def run_pipeline(input_csv, output_csv, limit=None):
    """Process every input row, or an explicit positive limit, and save results."""
    input_path = Path(input_csv).resolve()
    output_path = Path(output_csv).resolve()
    if input_path == output_path or (output_path.exists() and input_path.samefile(output_path)):
        raise ValueError("Input and output CSV paths must be different")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
        raise ValueError("limit must be a positive integer or None")

    news_data = pd.read_csv(input_path, keep_default_na=False, dtype=str)
    required = {"title", "content", "url", "source"}
    missing = required.difference(news_data.columns)
    if missing:
        raise ValueError("Missing CSV columns: " + ", ".join(sorted(missing)))

    print("\nMAIN NEWS PROCESSING PIPELINE")
    print("Total unique news:", len(news_data))
    if limit is not None:
        news_data = news_data.head(limit)
    print("Rows selected:", len(news_data))

    columns = list(news_data.columns)
    columns.extend(column for column in RESULT_COLUMNS if column not in columns)
    results = []
    progress.set_total(len(news_data))
    progress.log(f"Processing {len(news_data)} article(s)")
    try:
        for index, news in enumerate(news_data.to_dict("records"), start=1):
            progress.checkpoint()
            progress.row_start(index, len(news_data), news["title"])
            print(f"Processing {index}/{len(news_data)}: {news['title']}")
            result = process_row(news)
            results.append(result)
            progress.row_done(result["status"])
            print("Status:", result["status"])
    except progress.RunCancelled:
        # Keep the rows finished so far, exactly like a smaller --limit run.
        partial = pd.DataFrame(results, columns=columns)
        if results:
            write_csv_atomic(partial, output_path)
        raise progress.RunCancelled(partial) from None

    result_df = pd.DataFrame(results, columns=columns)
    write_csv_atomic(result_df, output_path)
    print("Processed:", len(result_df))
    print("Approved:", int((result_df["status"] == "APPROVED").sum()))
    print("Saved:", output_path)
    return result_df
