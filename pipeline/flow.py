import os
import runpy
from pathlib import Path

from pipeline.pipeline import run_pipeline

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_CSV_PATH = BASE_DIR / "data" / "news_data.csv"
UNIQUE_CSV_PATH = BASE_DIR / "data" / "unique_news.csv"
PROCESSED_CSV_PATH = BASE_DIR / "data" / "processed_news.csv"
DEDUP_THRESHOLD = 0.73


def resolve_project_path(path, label="path"):
    """Resolve a user supplied path and require it to stay inside the project."""
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = BASE_DIR / resolved
    resolved = resolved.resolve()
    try:
        resolved.relative_to(BASE_DIR.resolve())
    except ValueError:
        raise ValueError(f"{label} must be inside the project directory") from None
    return resolved


def validate_limit(limit):
    if limit is None:
        return None
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer or None")
    return limit


def validate_paths(
    input_csv=UNIQUE_CSV_PATH,
    output_csv=PROCESSED_CSV_PATH,
    scrape=False,
    deduplicate=False,
):
    """Validate the full flow before any long running work starts."""
    input_path = resolve_project_path(input_csv, "input")
    output_path = resolve_project_path(output_csv, "output")
    if input_path == output_path:
        raise ValueError("input and output CSV paths must be different")
    if output_path == RAW_CSV_PATH:
        raise ValueError("output must not overwrite the raw news CSV")
    if (scrape or deduplicate) and input_path == RAW_CSV_PATH:
        raise ValueError("deduplication output must not overwrite the raw news CSV")
    return input_path, output_path


def collect_news(csv_path=RAW_CSV_PATH):
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    from scraper.scraper import news_collect
    from scraper.configs import (
        DAILY_STAR_CONFIG,
        DHAKA_TRIBUNE_CONFIG,
        BUSINESS_STANDARD_CONFIG,
        DAILY_SUN_CONFIG,
    )
    from sources.Daily_Star import dailystar_base_url, dailystar_categories
    from sources.Dhaka_Tribune import dhakatribune_base_url, dhakatribune_categories
    from sources.The_Business_Standard import (
        theBusinessStandard_base_url,
        theBusinessStandard_categories,
    )
    from sources.Daily_Sun import dailysun_base_url, dailysun_categories

    sources = (
        (dailystar_categories, dailystar_base_url, "Daily Star", DAILY_STAR_CONFIG),
        (dhakatribune_categories, dhakatribune_base_url, "Dhaka Tribune", DHAKA_TRIBUNE_CONFIG),
        (theBusinessStandard_categories, theBusinessStandard_base_url, "The Business Standard", BUSINESS_STANDARD_CONFIG),
        (dailysun_categories, dailysun_base_url, "Daily Sun", DAILY_SUN_CONFIG),
    )
    for categories, base_url, source, config in sources:
        news_collect(categories, base_url, source, config, str(csv_path))


def deduplicate_news(
    output_csv=UNIQUE_CSV_PATH,
    input_csv=RAW_CSV_PATH,
    threshold=DEDUP_THRESHOLD,
):
    input_path = resolve_project_path(input_csv, "input")
    output_path = resolve_project_path(output_csv, "output")
    if input_path == output_path:
        raise ValueError("deduplication input and output must be different")
    if output_path == RAW_CSV_PATH:
        raise ValueError("deduplication output must not overwrite the raw news CSV")

    module = runpy.run_path(str(BASE_DIR / "Sentence-BERT.py"))
    module["deduplicate"](input_path, output_path, threshold=threshold)
    return output_path


def run_flow(
    input_csv=UNIQUE_CSV_PATH,
    output_csv=PROCESSED_CSV_PATH,
    limit=1,
    scrape=False,
    deduplicate=False,
):
    """Scrape, deduplicate, and/or process news as one ordered flow."""
    input_path, output_path = validate_paths(input_csv, output_csv, scrape, deduplicate)
    validate_limit(limit)

    if scrape:
        collect_news()
    if scrape or deduplicate:
        deduplicate_news(input_path)
    return run_pipeline(input_path, output_path, limit=limit)
