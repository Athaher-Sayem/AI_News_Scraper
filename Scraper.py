import csv
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def news_collect(
    categories, base_url, site_name="News Site", csv_filename="news_data.csv"
):
    base_url = base_url.rstrip("/")


    with open(csv_filename, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        
        if file.tell() == 0:
            writer.writerow(["Source", "Category", "Title", "URL"])

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            print(f"\n###################################")
            print(f" Scraping from: {site_name}")
            print(f"###################################")

            for category in categories:
                clean_category = category.strip("/")
                target_url = f"{base_url}/{clean_category}"

                print(f"\n==============================")
                print(f" Category: {clean_category.upper()}")
                print(f"==============================")

                try:
                    page.goto(
                        target_url, wait_until="domcontentloaded", timeout=60000
                    )
                    page.wait_for_selector(
                        "main, #main-content, .pane-content, body",
                        timeout=15000,
                    )
                    html = page.content()
                except Exception as e:
                    print(f"Error loading {clean_category}: {e}")
                    continue

                soup = BeautifulSoup(html, "html.parser")
                main_area = (
                    soup.find("main")
                    or soup.find("div", {"id": "main-content"})
                    or soup
                )

                articles = main_area.select("""
                    h1 a, 
                    h2 a, 
                    h3 a, 
                    h4 a, 
                    h5 a,
                    .title a,
                    .card-title a
                """)

                count = 1
                seen_links = set()

                for a in articles:
                    if a.find_parent(class_="header-news-card"):
                        continue

                    title = a.get_text(strip=True)
                    href = a.get("href", "")

                    if (
                        not href
                        or href.startswith("#")
                        or href.startswith("javascript:")
                    ):
                        continue

                    full_url = (
                        base_url + href if href.startswith("/") else href
                    )

                    if title and len(title) > 10 and full_url not in seen_links:
                        seen_links.add(full_url)

                        
                        print(f"{count}. {title}")
                        print(f"   {full_url}\n")

                        writer.writerow(
                            [site_name, clean_category, title, full_url]
                        )
                        count += 1

            browser.close()