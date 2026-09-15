import pandas as pd
import numpy as np
from sqlalchemy import create_engine

# ----------------------------
# SETTINGS
# ----------------------------
cutoff = pd.Timestamp("2023-01-01")
end = pd.Timestamp("2026-04-01")

engine = create_engine(
        "postgresql+psycopg2://postgres:yhopkq12@localhost:5432/cs"
    )

MIN_MAPS = 50



def get_rankings_for_date(date):
    fname = date.strftime("%b-%d-%y").lower()
    path = f"rankings/{fname}.csv"
    
    r = pd.read_csv(path)
    return r

while cutoff <= end:

    start = cutoff - pd.DateOffset(months=9)

    # ----------------------------
    # LOAD TEAM LOG PROBS
    # ----------------------------
    teams_df = get_rankings_for_date(cutoff)

    # convert log-odds → probability
    teams_df["team_wr"] = 1 / (1 + np.exp(-teams_df["value"]))

    team_to_wr = dict(zip(teams_df["team"], teams_df["team_wr"]))

    # ----------------------------
    # LOAD PLAYER MATCH DATA
    # ----------------------------
    

    query = f"""
    SELECT *
    FROM players_matches2
    WHERE date >= '{start.date()}'
    AND date < '{cutoff.date()}'
    """

    df = pd.read_sql(query, engine)
    df["date"] = pd.to_datetime(df["date"])

    df = df.drop_duplicates()
    # ----------------------------
    # MAP TEAM STRENGTH
    # ----------------------------
    df["opp_wr"] = df["opponent"].map(team_to_wr)

    # drop rows where missing
    df = df.dropna(subset=["opp_wr"])



    # ----------------------------
    # EXPECTED WR DIFFERENCE
    # ----------------------------
    # difference in percentage points
    df["wr_diff_pct"] = (df["opp_wr"]) - 0.5

    # ----------------------------
    # ADJUST RATING
    # ----------------------------


    df["rating_adj"] = df["rating"] + 0.02 * df["wr_diff_pct"] * 100
    player_counts = df['players_name'].value_counts()
    valid_players = set(player_counts[player_counts >= MIN_MAPS].index)

    df = df[df["players_name"].isin(valid_players)]

    filename = cutoff.strftime("%b-%d-%y.csv").lower()

    # ----------------------------
    # AGGREGATE PER PLAYER
    # ----------------------------
    player_avg = (
        df.groupby("players_name")
        .agg(avg_rating=("rating_adj", "mean"))
        .reset_index()
    )

    # ----------------------------
    # SAVE TO CSV
    # ----------------------------
    player_avg = player_avg.sort_values(by="avg_rating", ascending=False)
    player_avg.to_csv("players/ratings_" + filename, index=False)

    cutoff += pd.DateOffset(days=1)


