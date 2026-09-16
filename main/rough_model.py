import pandas as pd
import numpy as np
import statsmodels.api as sm
import csv
from sqlalchemy import create_engine

# ----------------------------
# Setup
# ----------------------------
engine = create_engine(
    "postgresql+psycopg2://postgres:yhopkq12@localhost:5432/cs"
)

MIN_MAPS = 50

cutoff = pd.Timestamp("2024-10-01")
start = cutoff - pd.DateOffset(months=12)

query = f"""
SELECT m.*, pt.team
FROM players_matches m
JOIN player_teams pt
  ON m.players_name = pt.players_name
 AND m.date BETWEEN pt.start_date AND COALESCE(pt.end_date, m.date)
WHERE m.date >= '{start.date()}'
  AND m.date < '{cutoff.date()}';
"""

merged = pd.read_sql(query, engine)
merged["date"] = pd.to_datetime(merged["date"])

# ----------------------------
# Drop duplicates
# ----------------------------
merged = merged.drop_duplicates(subset=["date", "team", "opponent", "map"])

# ----------------------------
# Time weighting
# ----------------------------
months_ago = (cutoff - merged["date"]).dt.days / 30

def get_weight(m):
    if m <= 3:
        return 0.30
    elif m <= 6:
        return 0.30
    elif m <= 9:
        return 0.25
    else:
        return 0.15

merged["time_weight"] = months_ago.apply(get_weight)

# ----------------------------
# Team frequency filter (last 12 months)
# ----------------------------
team_counts = pd.concat([merged["team"], merged["opponent"]]).value_counts()
valid_teams = set(team_counts[team_counts >= MIN_MAPS].index)

merged = merged[
    merged["team"].isin(valid_teams) &
    merged["opponent"].isin(valid_teams)
]

# ----------------------------
# Normalize matchups
# ----------------------------

merged["team_low"] = merged[["team", "opponent"]].min(axis=1)
merged["team_high"] = merged[["team", "opponent"]].max(axis=1)

merged["rounds_low"] = np.where(
    merged["team"] == merged["team_low"],
    merged["rounds_won"],
    merged["rounds_lost"]
)

merged["rounds_high"] = np.where(
    merged["team"] == merged["team_low"],
    merged["rounds_lost"],
    merged["rounds_won"]
)

# ----------------------------
# Aggregate with weights
# ----------------------------
merged["weighted_low"] = merged["rounds_low"] * merged["time_weight"]
merged["weighted_high"] = merged["rounds_high"] * merged["time_weight"]


agg = merged.groupby(["team_low", "team_high"]).agg(
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

with open("teams.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    
    # header
    writer.writerow(["team", "value"])
    
    # rows
    for team, value in team_strengths.items():
        writer.writerow([team, float(value)])  # float() removes np.float64
