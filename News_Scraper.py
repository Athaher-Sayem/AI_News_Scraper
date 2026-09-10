import requests
from bs4 import BeautifulSoup

url = 'https://www.prothomalo.com/collection/latest'

headers = { 
    'User-Agent' : "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

response = requests.get(url,headers=headers)
print("Status Code:", response.status_code)

soup = BeautifulSoup(response.text , 'html.parser')

titles = soup.select(".title")
print("Total titles found:", len(titles))
for item in titles[:10]:
    print(item.text)


# headings = soup.find_all(['h1', 'h2', 'h3'])
# print("Total headings found:", len(headings))

# for h in headings[:5]:
#     print(h.text.strip())    


titles = soup.select(".tilte-no-link-parent")

print("Total titles found:", len(titles))

for item in titles[:10]:
    print(item.text.strip())