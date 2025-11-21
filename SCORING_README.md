# Economic City Health Report: Scoring System Overview

## What This System Does

This system ranks the top 50 U.S. metropolitan areas based on their economic health. It collects real economic data from the Federal Reserve Economic Data (FRED) API, converts that data into scores, and then ranks cities from best to worst. Each city gets a final grade (A, B, C, etc.) that summarizes its overall economic health.

---

## Core Concept: Percentile Scoring

This system uses **percentile-based scoring**, which means scores tell you how a city ranks compared to all others.

**What does a score of 75 mean?** It means that city is better than 75% of the other metros in the analysis.

**How it works:**
1. All 50 metros are ranked from best to worst on each individual metric
2. The best city gets a percentile score of 100 (it's better than 100% of cities)
3. The worst city gets a percentile score of 0 (it's better than 0% of cities)
4. Everyone else gets a score between 0-100 based on their rank

This approach is much simpler to understand than statistical z-scores, and it handles extreme outliers naturally (like expensive cities such as New York).

---

## The 10 Metrics (Weighted System)

The system uses 10 different economic measurements, divided into two categories:

### Employment Metrics (65% of total score)
These represent job quality, worker availability, and income growth:

| Code | Metric | Weight | What It Measures |
|------|--------|--------|------------------|
| 101A | Unemployment Rate | 15 | % of people without jobs (lower is better) |
| 102A | Labor Force Participation | 15 | % of people working or looking for work (higher is better) |
| 103B | Hourly Earnings Growth (Year-over-Year) | 10 | How fast wages are increasing (higher is better) |
| 104C | Cost of Living (3-Component) | 10 | How affordable the city is (explained below) |
| 105C | Office Worker Ratio (2-Component) | 5 | % of jobs that are office-based (higher is better) |
| 106D | Weekly Hours Worked | 10 | Average hours workers work per week (higher is better) |

**Employment Total Weight: 65 points**

### Housing Metrics (35% of total score)
These represent the real estate market and construction activity:

| Code | Metric | Weight | What It Measures |
|------|--------|--------|------------------|
| 200B | Building Permits (3-Month Smoothed) | 10 | Construction growth per capita (higher is better) |
| 201 | Home Price Index Growth (Year-over-Year) | 10 | How fast home values are appreciating (higher is better) |
| 202 | Price Per Square Foot (3-Month Smoothed) | 10 | How home prices per sq ft are growing (higher is better) |
| 204A | Median Days on Market | 5 | How quickly homes sell (lower is better) |

**Housing Total Weight: 35 points**

---

## Special Scoring Rules

Some metrics need special handling because they're more complex:

### Cost of Living (104C): 3-Component Scoring
Instead of a simple metric, this breaks down into three parts:
- **Absolute Affordability (3 points):** Is the city overall affordable right now?
- **Direction of Trend (4 points):** Is affordability improving or getting worse?
- **Volatility/Stability (3 points):** Is the city's affordability predictable and stable?

Total: 10 points. A city can score well if it's expensive but improving and stable (like NYC might).

### Office Worker Ratio (105C): 2-Component Scoring
This breaks down into:
- **Year-over-Year Growth (3 points):** Are office jobs growing?
- **Absolute Percentage (2 points):** What % of all jobs are office-based?

Total: 5 points.

### Building Permits & Price Per Sq Ft: Smoothed Averages
These two metrics use a **3-month rolling average** of year-over-year growth. This smooths out monthly volatility so one bad month doesn't skew the results.

---

## How Scores Are Calculated

Here's the step-by-step process:

### Step 1: Raw Data Collection
- System collects actual economic values from FRED API for each metric
- Example: New York's unemployment rate = 5.2%

### Step 2: Percentile Conversion
- Raw values are ranked across all 50 metros
- Converted to percentile scores (0-100)
- Example: If New York ranks 45th out of 50 on unemployment, that's roughly the 10th percentile = score of 12

### Step 3: Weight Application
- Each percentile score is multiplied by its weight
- Example: Unemployment (weight 15) × score of 12 = 180 points out of a possible 1500

### Step 4: Final Weighted Score
- Sum all weighted scores
- Divide by maximum possible points (1500)
- Multiply by 100 to get a 0-100 scale

**Formula:**
```
Weighted Score = (Sum of all metric scores × their weights) / 1500 × 100
```

---

## Letter Grades

Final scores are converted to letter grades:

| Score Range | Grade | Emoji | Description |
|------------|-------|-------|-------------|
| 85-100 | A | 🎯 | Excellent |
| 75-84 | A- | 🎯 | Excellent |
| 65-74 | B+ | 📈 | Above Average |
| 55-64 | B | ➡️ | Average |
| 45-54 | B- | ⚠️ | Below Average |
| 35-44 | C+ | 📉 | Poor |
| 25-34 | C | 🚫 | Very Poor |
| 0-24 | C- | 🔴 | Extremely Poor |

---

## Quick Example: Chicago

Let's walk through how Chicago gets its score:

**Chicago's Raw Values:**
- Unemployment: 4.6%
- Labor Force Participation: 65.11%
- Hourly Earnings Growth: 5.12%
- Cost of Living: 4.97 (composite)
- Office Worker Ratio: 2.18%
- Weekly Hours: 33.3
- Building Permits: +11.46% (smoothed 3-month)
- Home Price Index: +5.89%
- Price Per Sq Ft: -0.16% (smoothed 3-month)
- Days on Market: 38

**Chicago's Percentile Scores:**
- Unemployment: 32 (better than 32% of metros)
- Labor Force Participation: 60 (better than 60% of metros)
- Hourly Earnings: 66
- Cost of Living: 50
- Office Worker Ratio: 44
- Weekly Hours: 8
- Building Permits: 72
- Home Price Index: 44
- Price Per Sq Ft: 62
- Days on Market: 84

**Weighted Calculation:**
```
Employment (65% of score):
  (32×15 + 60×15 + 66×10 + 50×10 + 44×5 + 8×10) / 1500 × 100

Housing (35% of score):
  (72×10 + 44×10 + 62×10 + 84×5) / 1500 × 100

Final Weighted Score: 50.4 → Grade: B (Average)
```

Chicago is right in the middle because it's strong on employment metrics but weaker on some housing metrics like home price growth.

---

## Understanding Your City's Results

When you look at a city's results, focus on three things:

1. **The Letter Grade:** Quick summary of overall economic health (A = excellent, B = average, C = poor)

2. **Percentile Score:** Tells you exactly how the city ranks (50 = median, 75+ = top tier, <25 = struggling)

3. **Individual Metric Scores:** Shows which areas are strengths and weaknesses
   - Employment metrics (codes 101-106) show job market health
   - Housing metrics (codes 200-204) show real estate market health

---

## Why Percentile Scoring?

We chose percentile scoring over traditional z-score methods because:

- **Easy to understand:** A score of 72 clearly means better than 72% of other cities
- **Handles outliers naturally:** New York's extreme cost of living doesn't unfairly penalize it
- **Fair comparison:** Cities of different sizes are compared on equal footing
- **Business-friendly:** Non-technical audiences immediately understand what the numbers mean

---

## Data Source & Frequency

- **Data Source:** Federal Reserve Economic Data (FRED) API
- **Metrics:** 10 economic indicators collected monthly
- **Update Frequency:** Weekly (every Monday at 9 AM UTC)
- **Coverage:** Top 50 U.S. metropolitan statistical areas
- **Historical Data:** 15 monthly observations per metric used for trends and smoothing

---

## Notes

- All scores are on a **0-100 scale** where higher is better
- **Percentile rankings** show how each metro compares to the other 49
- **Weighted scores** combine all metrics with employment (65%) weighted more heavily than housing (35%)
- The system **ranks all 50 metros simultaneously**, so a city's score can change if other cities' conditions change dramatically
