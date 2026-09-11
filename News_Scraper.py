import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


url = 'https://www.thedailystar.net/'

# headers = { 
#     'User-Agent' : "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
# }

# response = requests.get(url,headers=headers)
# print("Status Code:", response.status_code)

# soup = BeautifulSoup(response.text , 'html.parser')

# titles = soup.select(".title")
# print("Total titles found:", len(titles))
# for item in titles[:10]:
#     print(item.text)


# headings = soup.find_all(['h1', 'h2', 'h3'])
# print("Total headings found:", len(headings))

# for h in headings[:5]:
#     print(h.text.strip())    


# titles = soup.select(".tilte-no-link-parent")

# print("Total titles found:", len(titles))

# for item in titles[:10]:
#     print(item.text.strip())


# with sync_playwright() as p:
#     browser = p.chromium.launch(headless=True)
#     page = browser.new_page()

#     # page.goto(url,wait_until='networkidle')
#     page.goto(url, wait_until="domcontentloaded", timeout=60000)
#     page.wait_for_selector(".tilte-no-link-parent", timeout=15000)
#     html=page.content()
#     browser.close()

# soup = BeautifulSoup(html, "html.parser")
# titles = soup.select(".tilte-no-link-parent")

# print("Total titles found:", len(titles))

# for item in titles[:10]:
#     print("-", item.text.strip())


# url_category=[
# "culture",
# 'sports',
# 'lifestyle',
# 'opinion',
# 'business',

# ]


# url = f"https://www.thedailystar.net/{url_category}"
# base_url = "https://www.thedailystar.net"

# idx=0

# for category in url_category:

#     url = f"https://www.thedailystar.net/{url_category[idx]}"
   

#     with sync_playwright() as p:
#         browser = p.chromium.launch(headless=True)
#         page = browser.new_page()

#         page.goto(url, wait_until="domcontentloaded", timeout=60000)
#         page.wait_for_selector("main, #main-content, .pane-content", timeout=15000)

#         html = page.content()
#         browser.close()

#     soup = BeautifulSoup(html, "html.parser")
#     articles = soup.select("h5.card-title a, h3.title a")

#     main_area = soup.find("main") or soup.find("div" , {'id':'main-cotent'}) or soup
#     articles = main_area.select("""
#         h1 a, 
#         h2 a, 
#         h3 a, 
#         h4 a, 
#         h5 a,
#         .title a,
#         .card-title a
#     """)

#     count=1
#     seen_links = set()

#     print(f"This is form this type of {url_category[idx]}category")
#     idx+=1
    
#     for a in articles:
#         if a.find_parent(class_='header-news-card'):
#             continue

#         title = a.get_text(strip=True)
#         href = a.get("href", "")

#         if not href or href.startswith("#") or href.startswith("javascript:"):
#             continue

#         full_url = base_url + href if href.startswith("/") else href

#         if title and full_url not in seen_links:
#             seen_links.add(full_url)
#             print(f"{count}. {title}")
#             # print(f"   {full_url}\n")
#             count += 1

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

categories = [
    "culture",
    "sports",
    "lifestyle",
    "opinion",
    "business",
]

base_url = "https://www.thedailystar.net"

# ব্রাউজার লুপের বাইরে একবারই শুরু হবে
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    for category in categories:
        target_url = f"{base_url}/{category}"
        print(f"\n==============================")
        print(f" Category: {category.upper()}")
        print(f"==============================")

        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector("main, #main-content, .pane-content", timeout=15000)
            html = page.content()
        except Exception as e:
            print(f"Error loading {category}: {e}")
            continue

        soup = BeautifulSoup(html, "html.parser")
        main_area = soup.find("main") or soup.find("div", {"id": "main-content"}) or soup

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

            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue

            full_url = base_url + href if href.startswith("/") else href

            if title and len(title) > 10 and full_url not in seen_links:
                seen_links.add(full_url)
                print(f"{count}. {title}")
                print(f"   {full_url}\n")
                count += 1

    browser.close()