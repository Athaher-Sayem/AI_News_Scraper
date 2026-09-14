from news.models import News


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