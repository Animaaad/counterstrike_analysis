import pandas as pd
import re
from sqlalchemy import create_engine




# ---------- main pipeline ----------

# read raw sheet
df = pd.read_csv("players3.csv",
    parse_dates=["date"],
    dayfirst=True
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
    "map"
]].copy()



engine = create_engine(
    "postgresql+psycopg2://postgres:yhopkq12@localhost:5432/cs"
)

with engine.begin() as conn:  # auto-commit

    clean_df.to_sql(
        "players_matches2",
        engine,
        if_exists="append",
        index=False,
    )


print("Clean CSV written")
