import csv
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def clean_text(text):

    if not text:
        return ""

    return " ".join(
        text.split()
    ).strip()


def get_text(
    soup,
    selectors,
):

    for selector in selectors:

        element = soup.select_one(
            selector
        )

        if element:

            text = clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if text:
                return text

    return ""


def get_attribute(
    soup,
    selectors,
    attribute,
):

    for selector in selectors:

        element = soup.select_one(
            selector
        )

        if element:

            value = element.get(
                attribute,
                "",
            )

            if value:
                return value.strip()

    return ""


def get_content(
    soup,
    selectors,
):

    content_area = None

    for selector in selectors:

        content_area = soup.select_one(
            selector
        )

        if content_area:
            break

    if not content_area:
        return ""

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

    paragraphs = []

    for p in content_area.find_all("p"):

        text = clean_text(
            p.get_text(
                " ",
                strip=True,
            )
        )

        if len(text) < 20:
            continue

        if text not in paragraphs:
            paragraphs.append(text)

    return "\n\n".join(
        paragraphs
    )


def detect_language(text):

    bangla = 0
    english = 0

    for char in text:

        if "\u0980" <= char <= "\u09FF":
            bangla += 1

        elif char.isalpha():
            english += 1

    if bangla > english:
        return "Bangla"

    return "English"


def scrape_article(
    page,
    article_url,
    config,
):

    try:

        page.goto(
            article_url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        page.wait_for_timeout(1000)

        soup = BeautifulSoup(
            page.content(),
            "html.parser",
        )

        title = get_text(
            soup,
            config["title"],
        )

        content = get_content(
            soup,
            config["content"],
        )

        author = get_text(
            soup,
            config["author"],
        )

        published_date = get_text(
            soup,
            config["published_date"],
        )

        image_url = get_attribute(
            soup,
            config["image"],
            "src",
        )

        # Try OpenGraph image
        if not image_url:

            image_url = get_attribute(
                soup,
                [
                    "meta[property='og:image']"
                ],
                "content",
            )

        language = detect_language(
            title + " " + content
        )

        scraped_date = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
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


def news_collect(
    categories,
    base_url,
    site_name,
    config,
    csv_filename="news_data.csv",
):

    base_url = base_url.rstrip("/")

    existing_titles = set()

    # ========================================================
    # READ EXISTING CSV
    # ========================================================

    try:

        with open(
            csv_filename,
            "r",
            newline="",
            encoding="utf-8",
        ) as file:

            reader = csv.DictReader(
                file
            )

            for row in reader:

                title = row.get(
                    "Title",
                    "",
                ).strip()

                if title:
                    existing_titles.add(
                        title
                    )

        print(
            f"Existing titles: "
            f"{len(existing_titles)}"
        )

    except FileNotFoundError:

        print(
            "CSV does not exist. "
            "Creating new CSV."
        )

    total_found = 0
    total_new = 0

    # ========================================================
    # OPEN CSV
    # ========================================================

    with open(
        csv_filename,
        "a",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.writer(file)

        if file.tell() == 0:

            writer.writerow(
                [
                    "Source",
                    "Category",
                    "Title",
                    "URL",
                    "Content",
                    "Author",
                    "Published_Date",
                    "Image_URL",
                    "Language",
                    "Scraped_Date",
                ]
            )

        # ====================================================
        # PLAYWRIGHT
        # ====================================================

        with sync_playwright() as p:

            browser = p.chromium.launch(
                headless=True
            )

            category_page = (
                browser.new_page()
            )

            article_page = (
                browser.new_page()
            )

            print(
                "\n###################################"
            )

            print(
                f" Scraping: {site_name}"
            )

            print(
                "###################################"
            )

            # =================================================
            # CATEGORY LOOP
            # =================================================

            for category in categories:

                category = category.strip(
                    "/"
                )

                target_url = (
                    f"{base_url}/"
                    f"{category}"
                )

                print(
                    f"\nCategory: "
                    f"{category}"
                )

                try:

                    category_page.goto(
                        target_url,
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )

                    category_page.wait_for_selector(
                        "main, "
                        "#main-content, "
                        "body",
                        timeout=15000,
                    )

                except Exception as e:

                    print(
                        f"Category error: {e}"
                    )

                    continue

                soup = BeautifulSoup(
                    category_page.content(),
                    "html.parser",
                )

                main_area = (
                    soup.find("main")
                    or soup.find(
                        "div",
                        id="main-content",
                    )
                    or soup
                )

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

                seen_links = set()

                category_found = 0
                category_new = 0

                # =================================================
                # ARTICLE LINKS
                # =================================================

                for a in articles:

                    if a.find_parent(
                        class_="header-news-card"
                    ):
                        continue

                    category_title = clean_text(
                        a.get_text(
                            " ",
                            strip=True,
                        )
                    )

                    href = a.get(
                        "href",
                        "",
                    )

                    if (
                        not href
                        or href.startswith("#")
                        or href.startswith(
                            "javascript:"
                        )
                    ):
                        continue

                    article_url = urljoin(
                        base_url,
                        href,
                    )

                    if article_url in seen_links:
                        continue

                    if len(category_title) <= 10:
                        continue

                    seen_links.add(
                        article_url
                    )

                    category_found += 1
                    total_found += 1

                    # =================================================
                    # DUPLICATE TITLE
                    # =================================================

                    if category_title in existing_titles:

                        print(
                            f"SKIPPED: "
                            f"{category_title}"
                        )

                        continue

                    # =================================================
                    # SCRAPE ARTICLE
                    # =================================================

                    print(
                        f"\n{category_new + 1}. "
                        f"NEW: {category_title}"
                    )

                    print(
                        f"URL: {article_url}"
                    )

                    data = scrape_article(
                        article_page,
                        article_url,
                        config,
                    )

                    if not data:

                        continue

                    # Use category title if
                    # article page title fails
                    if not data["Title"]:

                        data["Title"] = (
                            category_title
                        )

                    # =================================================
                    # SAVE
                    # =================================================

                    writer.writerow(
                        [
                            site_name,
                            category,
                            data["Title"],
                            article_url,
                            data["Content"],
                            data["Author"],
                            data["Published_Date"],
                            data["Image_URL"],
                            data["Language"],
                            data["Scraped_Date"],
                        ]
                    )

                    file.flush()

                    existing_titles.add(
                        category_title
                    )

                    existing_titles.add(
                        data["Title"]
                    )

                    category_new += 1
                    total_new += 1

                    print(
                        f"Content: "
                        f"{len(data['Content'])} "
                        f"characters"
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

                print(
                    f"\n{category}: "
                    f"{category_found} found, "
                    f"{category_new} new"
                )

            browser.close()

    print(
        "\n=================================="
    )

    print(
        f"{site_name}"
    )

    print(
        f"Total found: {total_found}"
    )

    print(
        f"Total new: {total_new}"
    )

    print(
        "=================================="
    )

    return total_new