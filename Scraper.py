import csv
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def news_collect(
    categories,
    base_url,
    site_name="News Site",
    csv_filename="news_data.csv",
):
    base_url = base_url.rstrip("/")

    # Store all existing titles from CSV
    existing_titles = set()

    try:
        with open(
            csv_filename,
            mode="r",
            newline="",
            encoding="utf-8",
        ) as file:

            reader = csv.DictReader(file)

            for row in reader:
                title = row.get("Title", "").strip()

                if title:
                    existing_titles.add(title)

        print(f"\nExisting titles in CSV: {len(existing_titles)}")

    except FileNotFoundError:
        print("\nCSV file not found. Creating a new file.")

    # Count only NEW titles
    total_new = 0

    with open(
        csv_filename,
        mode="a",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.writer(file)

        # Create header if CSV is empty
        if file.tell() == 0:
            writer.writerow(
                [
                    "Source",
                    "Category",
                    "Title",
                    "URL",
                ]
            )

        with sync_playwright() as p:

            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            print("\n###################################")
            print(f" Scraping from: {site_name}")
            print("###################################")

            for category in categories:

                clean_category = category.strip("/")
                target_url = f"{base_url}/{clean_category}"

                print("\n==============================")
                print(f" Category: {clean_category.upper()}")
                print("==============================")

                try:
                    page.goto(
                        target_url,
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )

                    page.wait_for_selector(
                        "main, #main-content, .pane-content, body",
                        timeout=15000,
                    )

                    html = page.content()

                except Exception as e:
                    print(
                        f"Error loading {clean_category}: {e}"
                    )
                    continue

                soup = BeautifulSoup(
                    html,
                    "html.parser",
                )

                main_area = (
                    soup.find("main")
                    or soup.find(
                        "div",
                        {"id": "main-content"},
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

                count = 1
                seen_links = set()

                for a in articles:

                    # Skip header news cards
                    if a.find_parent(
                        class_="header-news-card"
                    ):
                        continue

                    title = a.get_text(strip=True)
                    href = a.get("href", "")

                    # Invalid URL
                    if (
                        not href
                        or href.startswith("#")
                        or href.startswith("javascript:")
                    ):
                        continue

                    # Create full URL
                    if href.startswith("/"):
                        full_url = base_url + href
                    else:
                        full_url = href

                    # Skip duplicate links
                    if full_url in seen_links:
                        continue

                    # Skip short titles
                    if not title or len(title) <= 10:
                        continue

                    seen_links.add(full_url)

                    # Check if title already exists in CSV
                    if title in existing_titles:
                        print(
                            f"SKIPPED: {title}"
                        )
                        continue

                    # New article
                    print(
                        f"{count}. NEW: {title}"
                    )

                    print(
                        f"   {full_url}\n"
                    )

                    # Save new article
                    writer.writerow(
                        [
                            site_name,
                            clean_category,
                            title,
                            full_url,
                        ]
                    )

                    # Add title to existing titles
                    # so it cannot be added again
                    existing_titles.add(title)

                    count += 1
                    total_new += 1

            browser.close()

    print("\n-----------------------------------")
    print(
        f"{site_name}: {total_new} NEW titles collected"
    )
    print("-----------------------------------")

    return total_new