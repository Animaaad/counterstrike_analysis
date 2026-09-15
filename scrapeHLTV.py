import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import time
import pandas as pd
from sqlalchemy import create_engine
import csv

df = pd.read_csv("player_links.csv")

with open("players.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = uc.Chrome(options=options)
    for link in df["link"]:
        #print(link)

        driver.get(link)

        # wait for Cloudflare to pass
        time.sleep(12)

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        games = soup.find_all("tr", class_=["group-1", "group-2"])

        for stuff in games:
            tds = stuff.find_all("td")

            if len(tds) < 6:
                continue

            date_block = tds[0]
            date_el = date_block.select_one(".time")
            date = date_el.text.strip()

            # --- TEAM 1 ---
            team1_block = tds[1]
            el1 = team1_block.select_one(".gtSmartphone-only a span")
            rounds1_el = team1_block.select_one(".gtSmartphone-only > span")

            if not el1 or not rounds1_el:
                continue

            team1_name = el1.get_text(strip=True)
            team1_rounds = rounds1_el.get_text(strip=True).strip("()")

            # --- TEAM 2 ---
            team2_block = tds[2]
            el2 = team2_block.select_one(".gtSmartphone-only a span")
            rounds2_el = team2_block.select_one(".gtSmartphone-only > span")
            if not el2 or not rounds2_el:
                continue

            team2_name = el2.get_text(strip=True)
            team2_rounds = rounds2_el.get_text(strip=True).strip("()")

            player = link.split("/")[-1].split("?")[0]

            # --- RATING ---
            rating = float(tds[6].text.strip())

            print({
                "team": team1_name,
                "opponent": team2_name,
                "rounds_won": int(team1_rounds),
                "rounds_lost": int(team2_rounds),
                "rating": rating
            })
            

            map = tds[3].text.strip()

            # header
            writer.writerow([player, team1_name, team2_name, team1_rounds,
                            team2_rounds, rating, date, map])
                    
        print(len(games))

#with open("output.html", "w", encoding="utf-8") as f:  
#    f.write(soup.prettify())

driver.quit()
