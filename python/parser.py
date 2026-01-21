import pandas as pd
import re
from sqlalchemy import create_engine


# ---------- helpers ----------

def parse_team_rounds(s):
    """
    Parses 'Vitality (13)' → ('Vitality', 13)
    """
    match = re.match(r"(.+?)\s*\((\d+)\)", s)
    if not match:
        raise ValueError(f"Invalid team format: {s}")
    return match.group(1).strip(), int(match.group(2))


def parse_date(d):
    """
    Parses DD/MM/YY → YYYY-MM-DD
    """
    return pd.to_datetime(d, dayfirst=True).date()


# ---------- main pipeline ----------

# read raw sheet
df = pd.read_csv("everyone.csv")

# parse date
df["date"] = df["Date"].apply(parse_date)

# parse team + rounds won
df[["team", "rounds_won"]] = df["Player team"].apply(
    lambda x: pd.Series(parse_team_rounds(x))
)

# parse opponent + rounds lost
df[["opponent", "rounds_lost"]] = df["Opponent"].apply(
    lambda x: pd.Series(parse_team_rounds(x))
)

# keep only columns needed for SQL
clean_df = df[[
    "players_name",
    "date",
    "team",
    "opponent",
    "rounds_won",
    "rounds_lost",
    "rating",
    "Map"
]].copy()

# rename columns to match SQL
clean_df.rename(columns={
    "Map": "map",
}, inplace=True)

# optional: sanity checks
assert clean_df["rounds_won"].min() >= 0
assert clean_df["rounds_lost"].min() >= 0

# export for PostgreSQL COPY
clean_df.to_csv(
    "everyone.csv",
    index=False
)

print("Clean CSV written")


engine = create_engine(
    "postgresql+psycopg2://postgres:yhopkq12@localhost:5432/cs"
)

with engine.begin() as conn:  # auto-commit


    clean_df.to_sql(
        "players_matches",
        engine,
        if_exists="append",
        index=False,
        method="multi"   # faster inserts
    )

print("Clean CSV written")


