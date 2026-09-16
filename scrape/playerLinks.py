import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import time
import csv
import pandas as pd



options = uc.ChromeOptions()
options.add_argument("--start-maximized")

driver = uc.Chrome(options=options)

url = "https://www.hltv.org/stats/players?startDate=2025-01-01&endDate=2026-12-31&rankingFilter=Top50&minMapCount=50"
driver.get(url)

# wait for Cloudflare to pass
time.sleep(20)

html = driver.page_source
soup = BeautifulSoup(html, "html.parser")

base = "https://www.hltv.org/stats/players/matches/"

player_links = []
for p in soup.find_all("td", class_="playerCol"):
    if p.find("a"):
        suffix = p.find("a").get("href").split("players/")[1]
        link1 = base + suffix
        link2 = base + suffix.split("?")[0] + "?offset=100&" + suffix.split("?")[1]
        link3 = base + suffix.split("?")[0] + "?offset=200&" + suffix.split("?")[1]
        link4 = base + suffix.split("?")[0] + "?offset=300&" + suffix.split("?")[1]
        player_links.extend([link1, link2, link3, link4])

# write to CSV
with open("player_links.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    
    # header
    writer.writerow(["link"])
    
    # rows
    for link in player_links:
        writer.writerow([link])