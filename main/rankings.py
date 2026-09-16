import pandas as pd
import numpy as np
import statsmodels.api as sm
import csv
import config

def process_teams(df, cutoff):
    players = pd.read_csv("player_adjusted_ratings.csv")

    # ----------------------------
    # GROUP FILTER FUNCTION
    # ----------------------------
    def valid_game(group):
        # must have exactly 5 rows
        if len(group) != 5:
            return False

        return True
    
    df = (
        df.groupby(["date", "team", "opponent", "map"])
        .filter(valid_game)
    )

    valid_players = set(players["players_name"])

    df = (df.groupby(["date", "team", "opponent", "map"])
            .filter(lambda g: g["players_name"].isin(valid_players).all()))

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

    months_ago = (cutoff - match_df["date"]).dt.days / 30

    match_df["time_weight"] = months_ago.apply(config.get_weight)

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

    theta = result.params[1:]

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

