# CS2 Match Prediction & Betting Analysis

## Overview

This project explores how well can professional Counter-Strike 2 matches be predicted using round win rates of teams and player ratings, available at hltv.org. It includes a full data pipeline from web scraping to modeling and evaluation.

The goal is not only to build predictive models, but also to understand their limitations in a real-world setting (e.g., betting markets).

---

## Data

* Sources: 1) HLTV players' matches, which were scraped, obtaining for each map their rating, rounds won, rounds lost, map name, and date
           2) Historical odds were copied from [https://www.oddsportal.com]
* Storage: PostgreSQL database, copies in .csv files


## Methodology

### 1. Basic Team Strength Model

* Built a basic team ranking based on round win rates
* Used a binomial logistic regression (GLM) on round outcomes to estimate relative team strengths
* Produced daily basic rankings for teams
* These are only used to assess players' strenths

---

### 2. Player-Based Adjustments

* Computed players' expected ratings, adjusting them based on the opponents' strength from the previous step
* The adjustment is that for each extra 1% of round winrate the opponent has, the player gets +0.02 expected rating for that game.
* This adjustment is justified by the observation that teams which have average rating 0.02 higher typically have 1% higher round winrate, 0.04 higher - 2%, etc.

---

### 3. Proper Team Strength Model

* Built a team ranking based on round winrates as well as player changes in teams (e.g. a team gets a significant upgrade, then the opponents get more expected rounds due to the fact that the team got better)
* Used a binomial logistic regression (GLM) on round outcomes to estimate relative team strengths

---

### 4. Betting Simulation

* The conversion from expected round winrate to actual game winrate is done via a table, which is based on expected round winrate to expected map winrate conversion
* The conversion was approximated by a binomial model with a few adjustments 
* Simulated betting using historical odds by comparing model predictions against bookmaker probabilities, and betting on games where the margin was significant (at least 5%)

---

## Results

* The model was **not profitable** in betting simulations, due to the fact that the weaker teams got, in my opinion, overrated by this model.
* However, it produced somewhat reasonable team ranking

---

## Output

* Team strength rankings (daily)
* Player strength ratings (daily)
* Player-adjusted team ratings
* Round-to-map conversion curves

---

## Project Structure

```
project/
├── scraping.py
├── preprocessing.py
│── modeling.py
├── evaluation.py
├── 
├── README.md
```

---

## Data Availability

* Due to size constraints, the full dataset is not included in this repository.
* Full dataset: [https://drive.google.com/drive/folders/10XyqMZCY--7qR8vQx7iOTn6uwxNxqMXs?usp=drive_link]

---



## Technologies Used

* Python (pandas, numpy, sklearn, statsmodels)
* PostgreSQL
* Web scraping (requests, BeautifulSoup, Selenium)

---

## Future Improvements

---

## Summary

This project demonstrates:

* End-to-end data pipeline design
* Feature engineering on real-world noisy data
* Probabilistic modeling and evaluation
* Critical analysis of model performance

While profitability was not achieved, the project provides a strong foundation in applied data analysis and modeling.

---
