import pandas as pd
from sqlalchemy import create_engine, text

# ---------- 1. Connect to PostgreSQL ----------
engine = create_engine(
    "postgresql+psycopg2://postgres:yhopkq12@localhost:5432/cs"
)

players_name = "karrigan"

# ---------- 2. Query relevant data ----------
query = text("""
    SELECT rounds_won, rounds_lost, rating
    FROM players_matches
    WHERE players_name = :players_name
""")

df = pd.read_sql(query, engine, params={"players_name": players_name})

if df.empty:
    print(f"No data found for player {players_name}")
else:
    # ---------- 3. Calculate weighted average rating ----------
    df["total_rounds"] = df["rounds_won"] + df["rounds_lost"]
    df["weighted_rating"] = df["rating"] * df["total_rounds"]

    weighted_avg = df["weighted_rating"].sum() / df["total_rounds"].sum()

    print(f"Weighted average rating for {players_name}: {weighted_avg:.3f}")