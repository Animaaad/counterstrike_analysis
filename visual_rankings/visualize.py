import pandas as pd
import os
from datetime import datetime
import matplotlib.pyplot as plt

folder = "team_rankings"

dfs = []

for file in os.listdir(folder):
    if file.endswith(".csv"):
        # parse date from filename
        date_str = file.replace(".csv", "")
        date = datetime.strptime(date_str, "%b-%d-%y")
        
        df = pd.read_csv(os.path.join(folder, file))
        df["date"] = date
        
        dfs.append(df)

all_rankings = pd.concat(dfs, ignore_index=True)
all_rankings = all_rankings.sort_values("date")

df = all_rankings.sort_values("date")

top10_per_day = (
    df.sort_values(["date", "value"], ascending=[True, False])
    .groupby("date")
    .head(1)
)


pivot = top10_per_day.pivot(index="date", columns="team", values="value")

# sort dates just in case
pivot = pivot.sort_index()

plt.figure()

for team in pivot.columns:
    plt.plot(pivot.index, pivot[team], label=team)

plt.legend()
plt.title("Team Strength Over Time")
plt.xlabel("Date")
plt.ylabel("Ranking")
plt.xticks(rotation=45)

plt.tight_layout()
plt.savefig("results/team_ranking_over_time.png", dpi=300)
plt.show()