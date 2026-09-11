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



url = "https://www.thedailystar.net/culture"
base_url = "https://www.thedailystar.net"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_selector("h5.card-title, h3.title", timeout=15000)

    html = page.content()
    browser.close()

soup = BeautifulSoup(html, "html.parser")
articles = soup.select("h5.card-title a, h3.title a")

for idx, a in enumerate(articles, start=1):
    print(f"{idx}. {a.get_text(strip=True)}")
    print(f"   {base_url + a.get('href', '')}\n")