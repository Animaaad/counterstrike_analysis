import pandas as pd
from sqlalchemy import create_engine
import numpy as np
import math

engine = create_engine(
    "postgresql+psycopg2://postgres:yhopkq12@localhost:5432/cs"
)

cutoff = pd.Timestamp("2026-03-01").date()

cutoff2 = pd.Timestamp("2022-01-01").date()

query = f"""
SELECT *
FROM players_matches2
WHERE date < '{cutoff}' AND date > '{cutoff2}'
"""

query2 = f"""
SELECT *
FROM betting_odds
WHERE date < '{cutoff}' AND date > '{cutoff2}'
"""

df_dirty = pd.read_sql(query, engine)
df_dirty["date"] = pd.to_datetime(df_dirty["date"])

odds = pd.read_sql(query2, engine)
odds["date"] = pd.to_datetime(odds["date"])

def valid_game(group):
    # must have exactly 5 rows
    if len(group) != 5:
        return False

    return True

df = (
    df_dirty.groupby(["date", "team", "opponent", "map"])
      .filter(valid_game)
)

match_df = (
    df.groupby(["date", "map", "team", "opponent"])
    .agg(
        players=("players_name", lambda x: set(x))
    )
    .reset_index()
)

def get_players_for_date(date):
    fname = "ratings_" + date.strftime("%b-%d-%y").lower()
    path = f"players/{fname}.csv"
    
    r = pd.read_csv(path)
    return r

def get_ranking_for_date(date):
    team_to_wr = {}

    fname = date.strftime("%b-%d-%y").lower()
    path = f"rankings/{fname}.csv"
    
    r = pd.read_csv(path)
    for _, row in r.iterrows():
        
        team_to_wr[row["team"]] = row["value"]
    
    return team_to_wr


match_df["team_low"] = match_df[["team", "opponent"]].min(axis=1)
match_df["team_high"] = match_df[["team", "opponent"]].max(axis=1)

match_df = match_df.merge(
    match_df,
    on=["date", "map", "team_low", "team_high"],
    suffixes=("_A", "_B")
)

match_df.to_csv("smth.csv")

match_df = match_df[match_df["team_A"] < match_df["team_B"]]

def elo_to_prob(diff, scale=3.5):
    return 1 / (1 + np.exp(-np.log(10) * diff / scale))

players = [] 

p_round_list = []
valid_rows = []

def get_winrate(round_wr, bo):
    table = [
        (50,   50, 50, 50),
        (50.5, 51, 51, 52),
        (51,   53, 54, 56),
        (51.5, 55, 58, 59),
        (52,   57, 60, 63),
        (52.5, 59, 63, 66),
        (53,   61, 66, 69),
        (53.5, 63, 69, 72),
        (54,   65, 72, 76),
        (54.5, 67, 75, 79),
        (55,   69, 77, 82),
        (55.5, 71, 80, 84),
        (56,   72, 81, 86),
        (57,   75, 85, 90),
        (58,   78, 87, 92),
        (59,   81, 90, 95),
        (60,   83, 92, 96),
        (61,   85, 94, 97),
    ]

    col = bo

    # clamp
    if round_wr <= table[0][0]:
        return table[0][col]
    if round_wr >= table[-1][0]:
        return table[-1][col]

    # interpolate
    for i in range(len(table) - 1):
        x1, *vals1 = table[i]
        x2, *vals2 = table[i + 1]

        if x1 <= round_wr <= x2:
            y1 = vals1[col - 1]
            y2 = vals2[col - 1]

            t = (round_wr - x1) / (x2 - x1)
            return y1 + t * (y2 - y1)

match_first = (
    match_df
    .sort_values("date")  # optional but safe
    .groupby(["date", "team_A", "team_B"], as_index=False)
    .first()
)

odds["team_low"] = odds[["team1", "team2"]].min(axis=1)
odds["team_high"] = odds[["team1", "team2"]].max(axis=1)

odds = odds.merge(
    odds,
    on=["date", "team_low", "team_high"],
    suffixes=("_A", "_B")
)

odds.rename(columns={"team_low": "team_A", "team_high": "team_B"}, inplace=True)

odds = odds[odds["team_A"] < odds["team_B"]]

odds = odds.merge(
    match_first,
    on=["date", "team_A", "team_B"],
    how="left"
)



player_groups = df.groupby("players_name")

which = ["A", "B"]

def safe_add(a, b):
    return (0 if math.isnan(a) else a) + (0 if math.isnan(b) else b)

def get_adjustment(date, team):
    start = date - pd.DateOffset(months=12)

    team_rating = {"A": 0, "B": 0}
    avg_rating = {"A": 0, "B": 0}
    players = get_players_for_date(date)

    for letter in which:

        match_df2 = match_df[(match_df["team_" + letter] == team)]

        match_df3 = match_df2[(match_df2["date"] >= start) & (match_df2["date"] < date)].copy()
        
        rating_map = dict(zip(players["players_name"], players["avg_rating"]))
        match_df3["team_" + letter + "_rating"] = match_df3["players_" + letter].apply(
            lambda players: sum(rating_map[p] for p in players if p in rating_map) / len(players)
        )
        team_rating[letter] = safe_add(team_rating[letter], match_df3["team_" + letter + "_rating"].mean()) 

        match_df3 = match_df2[match_df2["date"] == date].copy()
        match_df3["team_" + letter + "_rating"] = match_df3["players_" + letter].apply(
            lambda players: sum(rating_map[p] for p in players if p in rating_map) / len(players)
        )
        avg_rating[letter] = safe_add(match_df3["team_" + letter + "_rating"].mean(), avg_rating[letter])

    t_r = [v for v in team_rating.values() if v != 0]
    a_r = [v for v in avg_rating.values() if v != 0]
    if (len(t_r) == 0 or len(a_r) == 0): return float("nan")
    tr = sum(t_r) / len(t_r)
    ar = sum(a_r) / len(a_r)
    rating_diff = ar - tr
    wr_adjustment = (rating_diff / 2)
    return wr_adjustment

money = 1000
n = 0
s = 0
nob = 0

def write(t1, t2, p1_book, p1_model, bet, f):
            f.write("bet " + str(bet) + " on " + t1 + " vs " + t2 + " @ " + str(p1_book)
                        + " date: " + str(date) + " with p1: " + str(p1_model) +
                          " " + str(money) + "\n")

def change_and_log(bet, score1, score2, f, t1, t2, p1_book, p1_model):
    money -= bet
    if (score1 > score2):
        money += bet / p1_book
        f.write("won ")
    write(t1, t2, p1_book, p1_model, bet, f)
    n += 1


with open("bets.csv", "w", newline="", encoding="utf-8") as f: 
    for i, row in odds.iterrows():
        date = row["date"]

        t1 = row["team_A"]
        t2 = row["team_B"]

        if (t1 == "Cloud9"):
            a = 0
        wr_adj_A = get_adjustment(date, t1)
        wr_adj_B = get_adjustment(date, t2)
        adj = wr_adj_A - wr_adj_B

        ranking = get_ranking_for_date(date)
        
        if t1 not in ranking or t2 not in ranking or pd.isna(adj):
            f.write("skip" + " " + t1 + " " + t2 + " " + str(date) + "\n")
            s+=1
            continue

        diff = ranking[t1] - ranking[t2]
        p = elo_to_prob(diff) + adj
        p = p * 100

        score1 = int(row["score1_A"])
        score2 = int(row["score2_A"])

        bo_number = max(score1, score2)
        
        if (p >= 50):
            p1_model = get_winrate(p, bo_number) / 100
            p2_model = 1 - p1_model
        else:
            p2_model = get_winrate(100 - p, bo_number) / 100
            p1_model = 1 - p2_model

        p1_book = 1 / row["odds1_A"]
        p2_book = 1 / row["odds2_A"]

        if (p1_model > p1_book + 0.05):
            if (p1_book < 0.5):
                change_and_log(35, score1, score2, f, t1, t2, p1_book, p1_model)
            if (p1_book > 0.5):
                change_and_log(65, score1, score2, f, t1, t2, p1_book, p1_model)
        elif (p1_model > p1_book + 0.01):
            if (p1_book < 0.5):
                change_and_log(5, score1, score2, f, t1, t2, p1_book, p1_model)
            if (p1_book > 0.5):
                change_and_log(20, score1, score2, f, t1, t2, p1_book, p1_model)
        elif (p2_model > p2_book + 0.05):
            if (p2_book < 0.5):
                change_and_log(35, score2, score1, f, t2, t1, p2_book, p2_model)
            if (p2_book > 0.5):
                change_and_log(65, score2, score1, f, t2, t1, p2_book, p2_model)
        elif (p2_model > p2_book + 0.01):
            if (p2_book < 0.5):
                change_and_log(5, score2, score1, f, t2, t1, p2_book, p2_model)
            if (p2_book > 0.5):
                change_and_log(20, score2, score1, f, t2, t1, p2_book, p2_model)
        else: 
            f.write("NO bet on " + t2 + " vs " + t1 + " @ " + str(p2_book) + 
                               " " + str(date) + str(money) + "\n")
            nob+=1
            
print(str(money) + " skip: " +  str(s) + " bets: " + str(n) + " " + "no bets: " + str(nob))

