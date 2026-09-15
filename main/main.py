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

cutoff = pd.Timestamp("2022-01-01")
end = pd.Timestamp("2026-04-01")

MIN_MAPS = 52


while cutoff <= end:
    start = cutoff - pd.DateOffset(months=12)

    query = f"""
    SELECT *
    FROM players_matches2 m
    WHERE m.date >= '{start.date()}'
    AND m.date < '{cutoff.date()}';
    """

    df_dirty = pd.read_sql(query, engine)
    df_dirty["date"] = pd.to_datetime(df_dirty["date"])

    # ----------------------------
    # Drop duplicates
    # ----------------------------
    merged = df_dirty.copy()
    merged = merged.drop_duplicates(subset=["date", "team", "opponent", "map"])


    def get_weight(m):
        if m <= 3:
            return 0.37
        elif m <= 6:
            return 0.32
        elif m <= 9:
            return 0.21
        else:
            return 0.1

    # ----------------------------
    # Time weighting
    # ----------------------------
    months_ago = (cutoff - merged["date"]).dt.days / 30

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


    # players.py
    
    teams_df = pd.read_csv("teams.csv")
    teams_df["team_wr"] = 1 / (1 + np.exp(-teams_df["value"]))

    team_to_wr = dict(zip(teams_df["team"], teams_df["team_wr"]))

    
    # ----------------------------
    # EXPECTED WR DIFFERENCE
    # ----------------------------
    df = df_dirty.copy()
    df["opp_wr"] = df["opponent"].map(team_to_wr)

    df = df.dropna(subset=["opp_wr"])
    
    # difference in percentage points
    df["wr_diff_pct"] = (df["opp_wr"]) - 0.5

    # ----------------------------
    # ADJUST RATING
    # ----------------------------
    df["rating_adj"] = df["rating"] + 0.02 * df["wr_diff_pct"] * 100
    player_counts = df['players_name'].value_counts()
    valid_players = set(player_counts[player_counts >= MIN_MAPS].index)

    #with open("smth.csv", "w") as f:
    #    f.write(str(valid_players))

    df = df[df["players_name"].isin(valid_players)]


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
    player_avg.to_csv("player_adjusted_ratings.csv", index=False)


    player_avg2 = (
        df.groupby("players_name")
        .agg(avg_rating=("rating", "mean"))
        .reset_index()
    )

    # ----------------------------
    # SAVE TO CSV
    # ----------------------------
    player_avg2 = player_avg2.sort_values(by="avg_rating", ascending=False)
    player_avg2.to_csv("player_adjusted_ratings2.csv", index=False)


    #rankings.py


    players = pd.read_csv("player_adjusted_ratings.csv")


    # ----------------------------
    # GROUP FILTER FUNCTION
    # ----------------------------
    def valid_game(group):
        # must have exactly 5 rows
        if len(group) != 5:
            return False

        return True

    df = df_dirty.copy()

    
    df = (
        df.groupby(["date", "team", "opponent", "map"])
        .filter(valid_game)
    )


    valid_players = set(players["players_name"])

    df = (df.groupby(["date", "team", "opponent", "map"])
            .filter(lambda g: g["players_name"].isin(valid_players).all()))


    #df.to_csv("abc2.csv")


    teams = set(df["team"])



    # total rounds per row
    df["rounds_played"] = df["rounds_won"] + df["rounds_lost"]

    # total rounds per player
    player_rounds = df.groupby("players_name")["rounds_played"].sum()

    player_df = pd.DataFrame({
        "rounds": player_rounds
    }).reset_index()


    # ----------------------------
    # TEAM AVERAGE RATING (ALL TIME)
    # ----------------------------
    df = df.merge(player_df, on="players_name", how="left")
    df = df.merge(players, on="players_name", how="left")




    tmp = df.copy()
    tmp["weighted"] = tmp["avg_rating"] * tmp["rounds_played"]

    match_strength = (
        df.groupby(["date", "team", "opponent", "map"])["avg_rating"]
        .mean()
        .rename("match_rating")
        .reset_index()
    )

    df = df.merge(match_strength, on=["date", "team", "opponent", "map"], how="left")


    team_avg = (
        tmp.groupby("team")
        .agg(
            weighted_sum=("weighted", "sum"),
            total_rounds=("rounds_played", "sum")
        )
    )

    team_avg["team_avg"] = team_avg["weighted_sum"] / (team_avg["total_rounds"])

    team_avg = team_avg["team_avg"].to_dict()


    df["team_avg"] = df["team"].map(team_avg)

    df["rating_diff"] = df["match_rating"] - df["team_avg"]

    df["wr_adjustment"] = (df["rating_diff"] / 0.1) * 5


    match_df = (
        df.groupby(["date", "team", "opponent", "map"])
        .agg(
            rounds_won=("rounds_won", "first"),
            rounds_lost=("rounds_lost", "first"),
            wr_adjustment=("wr_adjustment", "first"),
            team_rating=("team_avg", "first")
        )
        .reset_index()
    )


    match_df["team_low"] = match_df[["team", "opponent"]].min(axis=1)
    match_df["team_high"] = match_df[["team", "opponent"]].max(axis=1)



    match_df = match_df.merge(
        match_df,
        on=["date", "map", "team_low", "team_high"],
        suffixes=("_A", "_B")
    )


    # keep only one pairing (avoid duplicates)
    match_df = match_df[match_df["team_A"] < match_df["team_B"]]

    match_df = match_df.drop(columns=["team_low", "team_high", "opponent_A", "opponent_B", "rounds_lost_A", "rounds_lost_B"])



    match_df["net_adj"] = (
        (match_df["wr_adjustment_A"] - match_df["wr_adjustment_B"]) / 100
    )

    match_df["total_rounds"] = (
        match_df["rounds_won_A"] + match_df["rounds_won_B"]
    )

    match_df["wr_A"] = match_df["rounds_won_A"] / match_df["total_rounds"]

    match_df["wr_A_adj"] = (match_df["wr_A"] + match_df["net_adj"]).clip(0.001, 0.999)

    match_df["rounds_won_A_adj"] = match_df["wr_A_adj"] * match_df["total_rounds"]
    match_df["rounds_won_B_adj"] = match_df["total_rounds"] - match_df["rounds_won_A_adj"]


    merged2 = match_df.copy()
    #merged2 = merged2[(merged2["team_A"] == "OG") | (merged2["team_B"] == "OG")]


    months_ago = (cutoff - match_df["date"]).dt.days / 30

    

    match_df["time_weight"] = months_ago.apply(get_weight)



    match_df["weighted_A"] = match_df["rounds_won_A_adj"] * match_df["time_weight"]
    match_df["weighted_B"] = match_df["rounds_won_B_adj"] * match_df["time_weight"]

    counts = (
            pd.concat([
                match_df["team_A"],
                match_df["team_B"]
            ])
            .value_counts()
            .sort_index()
        )
    
    counts = counts[counts >= MIN_MAPS]

    match_df = match_df[match_df["team_A"].isin(counts.index)]
    match_df = match_df[match_df["team_B"].isin(counts.index)]

    agg = match_df.groupby(["team_A", "team_B"]).agg(
        rounds_A=("weighted_A", "sum"),
        rounds_B=("weighted_B", "sum"),
    ).reset_index()


    buckets = sorted(set(agg["team_A"]) | set(agg["team_B"]))
    bucket_to_idx = {b: i for i, b in enumerate(buckets)}


    # ----------------------------
    # Build design matrix
    # ----------------------------
    X = []
    y = []
    weights = []

    for _, row in agg.iterrows():
        i = bucket_to_idx[row["team_A"]]
        j = bucket_to_idx[row["team_B"]]

        # skip self matches (can happen after merges)
        if i == j:
            continue

        x = np.zeros(len(buckets))
        x[i] = 1
        x[j] = -1

        total = row["rounds_A"] + row["rounds_B"]

        if total == 0:
            continue

        X.append(x)
        y.append(row["rounds_A"] / total)
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

    theta = result.params[1:]  # skip intercept

    filename = cutoff.strftime("%b-%d-%y.csv").lower()

    
    def get_team_rating(team):
        value = match_df.loc[
            match_df["team_A"] == team,
            "team_rating_A"
        ]

        if not value.empty:
            return value.iloc[0]

        value = match_df.loc[
            match_df["team_B"] == team,
            "team_rating_B"
        ]

        match_df.to_csv("abc.csv")


        return value.iloc[0]

    bucket_strengths = dict(
    sorted(
            { bucket: theta[bucket_to_idx[bucket]]
                for bucket in buckets
            }.items(),
            key=lambda x: x[1],
            reverse=True
        )
    )

    
    with open("rankings/" + filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
    
            writer.writerow(["team", "value", "team_rating"])

            for team, value in bucket_strengths.items():
                team_rating = get_team_rating(team)
    
                writer.writerow([team, float(value), team_rating])

    cutoff += pd.DateOffset(days=1)
