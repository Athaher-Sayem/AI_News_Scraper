import csv
import os
from datetime import datetime
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from .database import get_existing_urls, save_news


# ============================================================
# TEXT CLEANING
# ============================================================
def clean_text(text):

    if not text:
        return ""

    return " ".join(text.split()).strip()


# ============================================================
# GET TEXT
# ============================================================
def get_text(soup, selectors):

    for selector in selectors:

        element = soup.select_one(selector)

        if element:

            text = clean_text(
                element.get_text(
                    " ",
                    strip=True
                )
            )

            if text:
                return text

    return ""


# ============================================================
# GET ATTRIBUTE
# ============================================================
def get_attribute(soup, selectors, attribute):

    for selector in selectors:

        element = soup.select_one(selector)

        if element:

            value = element.get(
                attribute,
                ""
            )

            if value:
                return value.strip()

    return ""


# ============================================================
# GET ARTICLE CONTENT
# ============================================================
def get_content(soup, selectors):

    content_area = None

    for selector in selectors:

        content_area = soup.select_one(
            selector
        )

        if content_area:
            break

    if not content_area:
        return ""

    # Cleaning must not remove author/date/image elements from the original
    # document before the metadata selectors inspect them.
    content_area = BeautifulSoup(str(content_area), "html.parser")

    # --------------------------------------------------------
    # REMOVE UNWANTED ELEMENTS
    # --------------------------------------------------------
    for tag in content_area.select(
        """
        script,
        style,
        nav,
        header,
        footer,
        aside,
        iframe,
        form,
        .ads,
        .advertisement,
        .related-news,
        .social-share
        """
    ):

        tag.decompose()

    # --------------------------------------------------------
    # EXTRACT PARAGRAPHS
    # --------------------------------------------------------
    paragraphs = []

    for p in content_area.find_all("p"):

        text = clean_text(
            p.get_text(
                " ",
                strip=True
            )
        )

        if len(text) < 20:
            continue

        if text not in paragraphs:

            paragraphs.append(
                text
            )

    return "\n\n".join(
        paragraphs
    )


# ============================================================
# LANGUAGE DETECTION
# ============================================================
def detect_language(text):

    bangla = 0
    english = 0

    for char in text:

        if "\u0980" <= char <= "\u09ff":

            bangla += 1

        elif char.isalpha():

            english += 1

    if bangla > english:

        return "Bangla"

    return "English"


# ============================================================
# SCRAPE SINGLE ARTICLE
# ============================================================
def scrape_article(
    page,
    article_url,
    config
):

    try:

        response = page.goto(
            article_url,
            wait_until="domcontentloaded",
            timeout=60000,
        )
        if response is not None and response.status >= 400:
            raise ValueError(f"Article returned HTTP {response.status}")

        page.wait_for_timeout(
            1000
        )

        soup = BeautifulSoup(
            page.content(),
            "html.parser"
        )

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------
        title = get_text(
            soup,
            config["title"]
        )

        # ----------------------------------------------------
        # CONTENT
        # ----------------------------------------------------
        content = get_content(
            soup,
            config["content"]
        )
        if not content:
            raise ValueError("Article has no extractable content")

        # ----------------------------------------------------
        # AUTHOR
        # ----------------------------------------------------
        author = get_text(
            soup,
            config["author"]
        )

        # ----------------------------------------------------
        # PUBLISHED DATE
        # ----------------------------------------------------
        published_date = get_attribute(soup, config["published_date"], "datetime") or get_text(
            soup,
            config["published_date"]
        )

        # ----------------------------------------------------
        # IMAGE
        # ----------------------------------------------------
        image_url = get_attribute(
            soup,
            config["image"],
            "src"
        )

        # ----------------------------------------------------
        # OPEN GRAPH IMAGE FALLBACK
        # ----------------------------------------------------
        if not image_url:

            image_url = get_attribute(
                soup,
                [
                    "meta[property='og:image']"
                ],
                "content"
            )

        if image_url:
            image_url = urljoin(article_url, image_url)

        # ----------------------------------------------------
        # LANGUAGE
        # ----------------------------------------------------
        language = detect_language(
            title + " " + content
        )

        # ----------------------------------------------------
        # SCRAPED DATE
        # ----------------------------------------------------
        scraped_date = (
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

        return {

            "Title": title,

            "Content": content,

            "Author": author,

            "Published_Date": published_date,

            "Image_URL": image_url,

            "Language": language,

            "Scraped_Date": scraped_date,
        }

    except Exception as e:

        print(
            f"Article scraping error: {e}"
        )

        return None


# ============================================================
# NEWS COLLECTOR
# ============================================================
def news_collect(
    categories,
    base_url,
    site_name,
    config,
    csv_filename="data/news_data.csv",
):

    # ========================================================
    # CREATE CSV DIRECTORY
    # ========================================================
    csv_directory = os.path.dirname(
        csv_filename
    )

    if csv_directory:

        os.makedirs(
            csv_directory,
            exist_ok=True
        )

    # ========================================================
    # LOAD EXISTING DATABASE URLS
    #
    # IMPORTANT:
    # This happens BEFORE Playwright starts.
    # ========================================================
    print("\n==================================")
    print(
        "Loading existing URLs from Django database..."
    )
    print("==================================")

    existing_urls = get_existing_urls()

    print(
        f"Existing DB URLs: "
        f"{len(existing_urls)}"
    )

    # ========================================================
    # TEMPORARY DATABASE RECORDS
    # ========================================================
    pending_database_records = []

    # ========================================================
    # BASE URL
    # ========================================================
    base_url = base_url.rstrip("/")

    # ========================================================
    # COUNTERS
    # ========================================================
    total_found = 0
    total_new = 0
    total_existing = 0

    # ========================================================
    # OPEN PLAYWRIGHT
    # ========================================================
    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        category_page = browser.new_page()

        article_page = browser.new_page()

        print("\n###################################")
        print(
            f" Scraping: {site_name}"
        )
        print("###################################")

        # ====================================================
        # CATEGORY LOOP
        # ====================================================
        for category in categories:

            category = category.strip(
                "/"
            )

            target_url = (
                f"{base_url}/{category}"
            )

            print(
                f"\nCategory: {category}"
            )

            # ------------------------------------------------
            # OPEN CATEGORY PAGE
            # ------------------------------------------------
            try:

                response = category_page.goto(
                    target_url,
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                if response is not None and response.status >= 400:
                    raise ValueError(f"Category returned HTTP {response.status}")

                category_page.wait_for_selector(
                    "main, #main-content, body",
                    timeout=15000,
                )

            except Exception as e:

                print(
                    f"Category error: {e}"
                )

                continue

            # ------------------------------------------------
            # PARSE CATEGORY PAGE
            # ------------------------------------------------
            soup = BeautifulSoup(
                category_page.content(),
                "html.parser"
            )

            main_area = (
                soup.find("main")
                or soup.find(
                    "div",
                    id="main-content"
                )
                or soup
            )

            # ------------------------------------------------
            # FIND ARTICLE LINKS
            # ------------------------------------------------
            articles = main_area.select(
                """
                h1 a,
                h2 a,
                h3 a,
                h4 a,
                h5 a,
                .title a,
                .card-title a
                """
            )

            # ------------------------------------------------
            # PREVENT DUPLICATE LINKS
            # ------------------------------------------------
            seen_links = set()

            category_found = 0
            category_new = 0
            category_existing = 0

            # =================================================
            # ARTICLE LOOP
            # =================================================
            for a in articles:

                # ------------------------------------------------
                # SKIP HEADER NEWS CARDS
                # ------------------------------------------------
                if a.find_parent(
                    class_="header-news-card"
                ):

                    continue

                # ------------------------------------------------
                # GET CATEGORY TITLE
                # ------------------------------------------------
                category_title = clean_text(
                    a.get_text(
                        " ",
                        strip=True
                    )
                )

                # ------------------------------------------------
                # GET URL
                # ------------------------------------------------
                href = a.get(
                    "href",
                    ""
                )

                if (
                    not href
                    or href.startswith("#")
                    or href.startswith(
                        "javascript:"
                    )
                ):

                    continue

                # ------------------------------------------------
                # MAKE FULL URL
                # ------------------------------------------------
                article_url = urldefrag(urljoin(target_url, href.strip()))[0]
                parsed_url = urlsplit(article_url)
                if parsed_url.scheme not in ("http", "https") or parsed_url.hostname != urlsplit(base_url).hostname:
                    continue

                # ------------------------------------------------
                # SAME PAGE DUPLICATE
                # ------------------------------------------------
                if article_url in seen_links:

                    continue

                # ------------------------------------------------
                # IGNORE SHORT TITLES
                # ------------------------------------------------
                if len(category_title) <= 10:

                    continue

                seen_links.add(
                    article_url
                )

                category_found += 1
                total_found += 1

                # =================================================
                # DATABASE DUPLICATE CHECK
                #
                # IMPORTANT:
                # We are checking a Python SET here.
                # NO Django ORM call happens inside Playwright.
                # =================================================
                if article_url in existing_urls:

                    print(
                        f"DB EXISTS → SKIPPED: "
                        f"{category_title}"
                    )

                    category_existing += 1
                    total_existing += 1

                    continue

                # =================================================
                # NEW ARTICLE
                # =================================================
                print(
                    f"\n{category_new + 1}. NEW: "
                    f"{category_title}"
                )

                print(
                    f"URL: {article_url}"
                )

                # =================================================
                # SCRAPE ARTICLE
                # =================================================
                data = scrape_article(
                    article_page,
                    article_url,
                    config
                )

                if not data:

                    print(
                        "Article scraping failed."
                    )

                    continue

                # =================================================
                # TITLE FALLBACK
                # =================================================
                if not data["Title"]:

                    data["Title"] = (
                        category_title
                    )

                # =================================================
                # ADD DATABASE INFORMATION
                # =================================================
                data["Source"] = (
                    site_name
                )

                data["Category"] = (
                    category
                )

                data["URL"] = (
                    article_url
                )

                # =================================================
                # ADD TO DATABASE QUEUE
                # =================================================
                pending_database_records.append(
                    data
                )

                # =================================================
                # IMPORTANT
                #
                # Add the URL to our in-memory set immediately.
                #
                # This prevents the same URL from being added
                # again if it appears in another category during
                # this same run.
                # =================================================
                existing_urls.add(
                    article_url
                )

                category_new += 1
                total_new += 1

                # =================================================
                # ARTICLE INFORMATION
                # =================================================
                print(
                    f"Content: "
                    f"{len(data['Content'])} characters"
                )

                print(
                    f"Author: "
                    f"{data['Author']}"
                )

                print(
                    f"Date: "
                    f"{data['Published_Date']}"
                )

                print(
                    f"Language: "
                    f"{data['Language']}"
                )

            # =================================================
            # CATEGORY SUMMARY
            # =================================================
            print(
                f"\n{category}: "
                f"{category_found} found, "
                f"{category_new} new, "
                f"{category_existing} existing"
            )

        # ====================================================
        # CLOSE BROWSER
        # ====================================================
        browser.close()

    # ========================================================
    # SAVE TO DJANGO DATABASE
    #
    # IMPORTANT:
    # Playwright is already closed here.
    # Django ORM is now safe.
    # ========================================================
    print("\n==================================")
    print(
        "Saving new articles to Django database..."
    )
    print("==================================")

    database_new = 0
    database_existing = 0
    database_failed = 0

    successfully_saved = []

    for data in pending_database_records:

        try:

            news, created = save_news(
                data
            )

            if created:

                database_new += 1

                successfully_saved.append(
                    data
                )

                print(
                    f"DB SAVED: "
                    f"{data['Title']}"
                )

            else:

                database_existing += 1

                print(
                    f"DB EXISTS: "
                    f"{data['Title']}"
                )

        except Exception as e:

            database_failed += 1

            print(
                f"Database error: {e}"
            )

            print(
                f"FAILED: "
                f"{data['Title']}"
            )

    # ========================================================
    # SAVE ONLY SUCCESSFULLY SAVED ARTICLES TO CSV
    # ========================================================
    print("\n==================================")
    print(
        "Saving successfully stored articles to CSV..."
    )
    print("==================================")

    csv_saved = 0
    csv_failed = 0

    with open(
        csv_filename,
        "a",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(
            file
        )

        for data in successfully_saved:

            try:

                writer.writerow(
                    [
                        data["Source"],
                        data["Category"],
                        data["Title"],
                        data["URL"],
                        data["Content"],
                        data["Author"],
                        data["Published_Date"],
                        data["Image_URL"],
                        data["Language"],
                        data["Scraped_Date"],
                    ]
                )

                file.flush()

                csv_saved += 1

            except Exception as e:

                csv_failed += 1

                print(
                    f"CSV error: {e}"
                )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================
    print("\n==================================")

    print(
        f"Source: {site_name}"
    )

    print(
        f"Total found: {total_found}"
    )

    print(
        f"Already in DB: {total_existing}"
    )

    print(
        f"New articles: {total_new}"
    )

    print(
        f"DB new: {database_new}"
    )

    print(
        f"DB existing: {database_existing}"
    )

    print(
        f"DB failed: {database_failed}"
    )

    print(
        f"CSV saved: {csv_saved}"
    )

    print(
        f"CSV failed: {csv_failed}"
    )

    print("==================================")

    return database_new
