import pandas as pd
import numpy as np
import statsmodels.api as sm
from sqlalchemy import create_engine

# ----------------------------
# Setup
# ----------------------------
engine = create_engine(
    "postgresql+psycopg2://postgres:yhopkq12@localhost:5432/cs"
)

cutoff = pd.Timestamp("2024-12-01")
start = cutoff - pd.DateOffset(months=12)

query = f"""
SELECT
    date,
    team,
    opponent,
    rounds_won,
    rounds_lost
FROM players_matches
WHERE date >= '{start.date()}'
  AND date < '{cutoff.date()}'
"""

df = pd.read_sql(query, engine)
df["date"] = pd.to_datetime(df["date"])

# ----------------------------
# Drop duplicates
# ----------------------------
df = df.drop_duplicates(subset=["date", "team", "opponent", "rounds_won", "rounds_lost"])

# ----------------------------
# Time weighting
# ----------------------------
months_ago = (cutoff - df["date"]).dt.days / 30

def get_weight(m):
    if m <= 3:
        return 0.35
    elif m <= 6:
        return 0.30
    elif m <= 9:
        return 0.25
    else:
        return 0.10

df["time_weight"] = months_ago.apply(get_weight)

# ----------------------------
# Team frequency filter (last 12 months)
# ----------------------------
team_counts = pd.concat([df["team"], df["opponent"]]).value_counts()
valid_teams = set(team_counts[team_counts >= 50].index)

df = df[
    df["team"].isin(valid_teams) &
    df["opponent"].isin(valid_teams)
]

# ----------------------------
# Normalize matchups
# ----------------------------

df["team_low"] = df[["team", "opponent"]].min(axis=1)
df["team_high"] = df[["team", "opponent"]].max(axis=1)

df["rounds_low"] = np.where(
    df["team"] == df["team_low"],
    df["rounds_won"],
    df["rounds_lost"]
)

df["rounds_high"] = np.where(
    df["team"] == df["team_low"],
    df["rounds_lost"],
    df["rounds_won"]
)

# ----------------------------
# Aggregate with weights
# ----------------------------
df["weighted_low"] = df["rounds_low"] * df["time_weight"]
df["weighted_high"] = df["rounds_high"] * df["time_weight"]

df.to_csv("test.csv")

agg = df.groupby(["team_low", "team_high"]).agg(
    rounds_low=("weighted_low", "sum"),
    rounds_high=("weighted_high", "sum"),
).reset_index()

# ----------------------------
# Build model
# ----------------------------
teams = sorted(set(agg["team_low"]) | set(agg["team_high"]))
team_to_idx = {t: i for i, t in enumerate(teams)}

X = []
y = []
weights = []

for _, row in agg.iterrows():
    i = team_to_idx[row["team_low"]]
    j = team_to_idx[row["team_high"]]

    x = np.zeros(len(teams))
    x[i] = 1
    x[j] = -1

    total = row["rounds_low"] + row["rounds_high"]

    if total == 0:
        continue

    X.append(x)
    y.append(row["rounds_low"] / total)
    weights.append(total)

X = np.array(X)
y = np.array(y)
weights = np.array(weights)

# ----------------------------
# Fit binomial model
# ----------------------------
X = sm.add_constant(X, has_constant="add")

model = sm.GLM(
    y,
    X,
    family=sm.families.Binomial(),
    var_weights=weights
)

result = model.fit()

theta = result.params[1:]

# ----------------------------
# Final strengths
# ----------------------------
team_strengths = {
    team: theta[team_to_idx[team]]
    for team in teams
}

team_strengths = dict(
    sorted(team_strengths.items(), key=lambda x: x[1], reverse=True)
)

print(team_strengths)