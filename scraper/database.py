from news.models import News
from pathlib import Path

import pandas as pd

from utils.csv_utils import write_csv_atomic


CSV_FIELDS = ("source", "category", "title", "url", "content", "author",
              "published_date", "image_url", "language", "scraped_date")


def export_missing_news(csv_filename):
    """Recover database rows missing from the CSV without removing old records."""
    path = Path(csv_filename)
    rows = []
    if path.exists() and path.stat().st_size:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        frame.columns = [column.strip().lower() for column in frame.columns]
        if list(frame.columns) != list(CSV_FIELDS):
            raise ValueError("Raw CSV columns do not match the scraper schema")
        rows = frame.to_dict("records")
    existing_urls = {row["url"] for row in rows}
    added = 0
    for row in News.objects.order_by("id").values(*CSV_FIELDS).iterator():
        if row["url"] in existing_urls:
            continue
        row["scraped_date"] = row["scraped_date"].isoformat()
        rows.append(row)
        existing_urls.add(row["url"])
        added += 1
    if added or not path.exists() or not path.stat().st_size:
        write_csv_atomic(pd.DataFrame(rows, columns=CSV_FIELDS), path, encoding="utf-8")
    return added


# ============================================================
# GET ALL EXISTING NEWS URLS
# ============================================================
def get_existing_urls():
    """
    Return all news URLs currently stored in Django database.
    """

    return set(
        News.objects.values_list(
            "url",
            flat=True
        )
    )


# ============================================================
# CHECK IF NEWS EXISTS
# ============================================================
def news_exists(url):
    """
    Check whether a news article exists in Django database.

    This function should be used OUTSIDE the Playwright
    scraping context.
    """

    return News.objects.filter(
        url=url
    ).exists()


# ============================================================
# SAVE NEWS
# ============================================================
def save_news(data):
    """
    Save a new news article to Django database.

    URL is used for duplicate protection.
    """

    news, created = News.objects.get_or_create(
        url=data["URL"],
        defaults={
            "source": data["Source"],
            "category": data["Category"],
            "title": data["Title"],
            "content": data["Content"],
            "author": data["Author"],
            "published_date": data["Published_Date"],
            "image_url": data["Image_URL"],
            "language": data["Language"],
        },
    )

    return news, created
