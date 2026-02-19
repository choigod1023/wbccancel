import requests
from bs4 import BeautifulSoup
import json
import html

URL = "https://tradead.tixplus.jp/wbc2026"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.9",
}

r = requests.get(URL, headers=headers, timeout=15)
r.raise_for_status()

soup = BeautifulSoup(r.text, "html.parser")

app_div = soup.find("div", id="app")
data_page_raw = app_div["data-page"]          # HTML 엔티티 포함 문자열
data_page_json = html.unescape(data_page_raw) # &quot; -> "
data = json.loads(data_page_json)

print(data.keys())
print(data["props"].keys())

concerts = data["props"]["concerts"]
print(len(concerts))
print(concerts[0].keys())
print(concerts[0])