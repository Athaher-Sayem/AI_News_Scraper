import os
import runpy
from pathlib import Path

from pipeline import progress
from pipeline.pipeline import run_pipeline

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_CSV_PATH = BASE_DIR / "data" / "news_data.csv"
UNIQUE_CSV_PATH = BASE_DIR / "data" / "unique_news.csv"
PROCESSED_CSV_PATH = BASE_DIR / "data" / "processed_news.csv"
DEDUP_THRESHOLD = 0.73
SOURCE_NAMES = ("Daily Star", "Dhaka Tribune", "The Business Standard", "Daily Sun")


def resolve_project_path(path, label="path"):
    """Allow only CSV files beneath data/, including resolved symlink targets."""
    if not isinstance(path, (str, Path)) or not str(path).strip():
        raise ValueError(f"{label} must be a CSV path inside data/")
    if any(character in str(path) for character in ("\x00", "\n", "\r")):
        raise ValueError(f"{label} contains invalid path characters")
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = BASE_DIR / resolved
    resolved = resolved.resolve()
    try:
        relative = resolved.relative_to((BASE_DIR / "data").resolve())
    except ValueError:
        raise ValueError(f"{label} must be inside data/") from None
    if resolved.suffix.lower() != ".csv" or resolved.is_dir() or ":" in str(relative):
        raise ValueError(f"{label} must be a CSV file inside data/")
    return resolved


def same_file(first, second):
    first, second = Path(first), Path(second)
    return first.resolve() == second.resolve() or (
        first.exists() and second.exists() and first.samefile(second)
    )


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
    if same_file(input_path, output_path):
        raise ValueError("input and output CSV paths must be different")
    if same_file(output_path, RAW_CSV_PATH):
        raise ValueError("output must not overwrite the raw news CSV")
    if (scrape or deduplicate) and same_file(input_path, RAW_CSV_PATH):
        raise ValueError("deduplication output must not overwrite the raw news CSV")
    return input_path, output_path


def validate_sources(sources):
    """Return the requested publisher names, or None for every source."""
    if sources is None:
        return None
    if isinstance(sources, (str, bytes)) or not isinstance(sources, (list, tuple)):
        raise ValueError("sources must be a list of source names")
    names = list(dict.fromkeys(sources))
    unknown = [name for name in names if name not in SOURCE_NAMES]
    if unknown or not names:
        raise ValueError(
            "sources must be a non-empty subset of: " + ", ".join(SOURCE_NAMES)
        )
    return names


def collect_news(csv_path=RAW_CSV_PATH, sources=None):
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

    selected = validate_sources(sources)
    publishers = (
        (dailystar_categories, dailystar_base_url, "Daily Star", DAILY_STAR_CONFIG),
        (dhakatribune_categories, dhakatribune_base_url, "Dhaka Tribune", DHAKA_TRIBUNE_CONFIG),
        (theBusinessStandard_categories, theBusinessStandard_base_url, "The Business Standard", BUSINESS_STANDARD_CONFIG),
        (dailysun_categories, dailysun_base_url, "Daily Sun", DAILY_SUN_CONFIG),
    )
    for categories, base_url, source, config in publishers:
        if selected is not None and source not in selected:
            continue
        progress.checkpoint()
        progress.log(f"Scraping {source}")
        news_collect(categories, base_url, source, config, str(csv_path))


def deduplicate_news(
    output_csv=UNIQUE_CSV_PATH,
    input_csv=RAW_CSV_PATH,
    threshold=DEDUP_THRESHOLD,
):
    input_path = resolve_project_path(input_csv, "input")
    output_path = resolve_project_path(output_csv, "output")
    if same_file(input_path, output_path):
        raise ValueError("deduplication input and output must be different")
    if same_file(output_path, RAW_CSV_PATH):
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
    sources=None,
):
    """Scrape, deduplicate, and/or process news as one ordered flow."""
    input_path, output_path = validate_paths(input_csv, output_csv, scrape, deduplicate)
    validate_limit(limit)
    validate_sources(sources)

    if scrape:
        with progress.stage("scrape"):
            if sources:
                collect_news(sources=sources)
            else:
                collect_news()
        progress.checkpoint()
    if scrape or deduplicate:
        with progress.stage("deduplicate"):
            deduplicate_news(input_path)
        progress.checkpoint()
    return run_pipeline(input_path, output_path, limit=limit)
