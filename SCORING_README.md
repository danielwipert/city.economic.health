# City Economic Health — Scoring Methodology

## What This System Measures

This system produces an economic health score for each of the top 50 U.S. metropolitan statistical areas (MSAs). The score is designed to answer a specific question: **how healthy is this city's labor market and cost environment for businesses considering locating or expanding there?**

It is not a quality-of-life index, a population growth ranking, or a real estate investment guide. It is a signal of current and near-term economic conditions from the perspective of employers and workers making location decisions.

---

## Core Mechanism: Percentile Ranking

Every metric is scored as a **percentile rank across all 50 metros simultaneously**.

A score of 75 means that metro outperforms 75% of the other 49 cities on that specific metric. A score of 20 means it underperforms 80% of them. The median city scores 50 on any given metric.

This approach has several deliberate advantages over z-scores or absolute thresholds:

- **Interpretability:** A score of 72 is immediately meaningful to a non-technical audience.
- **Outlier resistance:** Extreme values (e.g., San Jose housing costs) don't distort every other city's score — they simply define one end of the distribution.
- **Self-calibrating:** As city conditions change over time, rankings shift naturally. No threshold values ever need manual recalibration except the grade boundaries.
- **Cross-metric comparability:** All 9 metrics live on the same 0-100 scale before weighting, making the weighted average mathematically clean.

---

## The 9 Metrics

### 101A — Unemployment Rate (Weight: 20%)

**What it measures:** The share of the civilian labor force that is unemployed and actively seeking work. Sourced from BLS Local Area Unemployment Statistics (LAUS).

**Direction:** `invert=True` — lower unemployment = higher percentile score.

**Why 20% weight:** Unemployment is the most widely tracked, most politically salient, and most directly actionable labor market signal. A 0.5 percentage point difference in unemployment is statistically and economically significant — it represents tens of thousands of workers in a large metro. It is the single most powerful indicator of labor market health.

**What it does not capture:** Unemployment is a lagging indicator. It peaks after recessions have already begun and falls after recoveries are already underway. It also misses discouraged workers who have left the labor force entirely, which is why 102A (LFP) complements it.

---

### 102A — Labor Force Participation Rate (Weight: 15%)

**What it measures:** The share of the civilian non-institutional population (age 16+) that is either employed or actively looking for work. Sourced from BLS LAUS.

**Direction:** `invert=False` — higher LFP = higher percentile score.

**Why 15% weight:** LFP captures what unemployment misses. A city can have low unemployment simply because discouraged workers stopped looking — LFP exposes this. High LFP means a larger available talent pool and a more engaged workforce. Together, 101A and 102A jointly hold 35% of the total score, reflecting that labor market availability and engagement are the foundation of economic health.

**Structural caveat:** LFP varies by demographic composition. Cities with older populations or higher student populations will have structurally lower LFP independent of economic conditions. The percentile ranking partially mitigates this by comparing cities against each other rather than against a fixed standard.

---

### 103B — Hourly Earnings YoY Growth (Weight: 10%)

**What it measures:** The year-over-year percent change in average hourly earnings for all private-sector employees in the metro. Sourced from BLS State and Metro Area Employment, Hours, and Earnings (SAE).

**Direction:** `invert=False` — stronger wage growth = higher percentile score.

**Why 10% weight:** Rising wages are a demand signal — employers bid up labor prices when they need workers and expect revenue growth. It also directly affects worker purchasing power and quality of life. However, wage growth in isolation can reflect either genuine prosperity or a tight supply-constrained market with few workers, so it is complemented by 101A and 102A.

**What to watch:** A city with strong wage growth but rising unemployment (a rare but possible leading indicator of overheating or layoffs in progress) would show split signals across 101A and 103B — exactly the kind of nuance the multi-metric composite is designed to surface.

---

### 104C — Cost of Living Composite (Weight: 10%)

**What it measures:** A 3-component composite assessing housing cost burden relative to local wages, including the current level, the trend direction, and how that trend compares to other metros.

**Underlying data:** `Price Per Square Foot / Average Hourly Earnings` — a ratio measuring how many hours of local work it takes to buy one square foot of housing. This normalizes housing costs against local wage levels rather than using a national price index.

**Direction:** `invert=True` — lower composite score = more affordable = higher percentile score.

#### Component 1 — Absolute Affordability (0-5 points, 50% of composite)

Normalizes each metro's PSF/earnings ratio across the full 50-city range using min-max scaling:

```
c1 = (city_ratio - min_ratio) / (max_ratio - min_ratio) * 5.0
```

The absolute level anchors 50% of the composite score. This prevents expensive cities with improving trends from outscoring genuinely affordable cities. Without this anchor, a housing price correction in an expensive market (e.g., Austin post-2022) could generate enough trend credit to outscore a Midwest city that has always been cheap.

#### Component 2 — Direction of Change (0-3 points, 30% of composite)

Uses the YoY percent change in the PSF/earnings ratio, scored on a **graduated linear scale**:

| YoY Change | c2 Score | Interpretation |
|------------|----------|----------------|
| -5% or better | 0.0 | Strongly improving affordability |
| 0% (flat) | 1.5 | Neutral |
| +5% or worse | 3.0 | Strongly worsening affordability |

Values between -5% and +5% are interpolated linearly.

The graduated scale replaced a previous binary design (any positive = 4.0 max penalty, any negative = 0.0). The binary version gave the same maximum penalty to a city whose ratio rose 0.01% as to one that rose 15%, which incorrectly hammered affordable Midwest cities with tiny upticks.

#### Component 3 — Peer-Relative Trend (0-2 points, 20% of composite)

Compares each city's YoY affordability change to the **national median** across all 50 metros:

```
deviation = city_yoy_pct - median_yoy_pct
```

Scored on a ±10% deviation range:

| Deviation from Median | c3 Score |
|----------------------|----------|
| -10% or better (improving much faster than peers) | 0.0 |
| 0% (in line with peers) | 1.0 |
| +10% or worse (worsening much faster than peers) | 2.0 |

This component answers a different question than c2: not "is affordability improving?" but "is it improving faster or slower than everywhere else?" A city that's worsening when the national trend is also worsening is less alarming than one bucking a broad national improvement. It replaced a previous "volatility" proxy that was calculated as `(|PSF_YoY%| + |earnings_YoY%|) / 2` — which was not volatility at all, but the average magnitude of price movement, effectively double-counting the direction component.

---

### 105C — Office Worker Ratio Composite (Weight: 5%)

**What it measures:** A 2-component composite assessing the concentration and growth of professional/office-based employment, used as a proxy for knowledge-economy job density.

**Underlying data:** BLS employment in "Information," "Financial Activities," and "Professional and Business Services" sectors as a share of total nonfarm payroll.

**Direction:** `invert=False` — higher score = more office-economy concentration = higher percentile score.

#### Component 1 — YoY Growth (0-3 points)
Percentile-ranks the YoY growth rate in the 3-month smoothed office worker count. Captures whether knowledge-economy jobs are expanding in this market.

#### Component 2 — Absolute Percentage (0-2 points)
Percentile-ranks the raw share of jobs that are office-based. Captures structural depth of the professional economy independent of recent trends.

**Why 5% weight:** Office worker density is a valuable structural signal for business location decisions but has lower direct economic-health predictive power than unemployment or wage growth. It is intentionally modest in weight.

---

### 106D — Weekly Hours Trend Deviation (Weight: 10%)

**What it measures:** How much the recent 3-month average of weekly hours worked deviates from that metro's own 12-month trailing baseline:

```
deviation = (3mo_avg - 12mo_avg) / 12mo_avg * 100
```

A positive value means workers are currently putting in more hours than their own recent average — a leading demand signal. A negative value means hours are trending below their own baseline.

**Direction:** `invert=False` — positive deviation (above trend) = higher percentile score.

**Why this formulation instead of raw hours level:**

Raw weekly hours are heavily confounded by industry composition. Mining and logging workers average ~45.7 hours/week; Information sector workers average ~37.7 hours/week — an 8.0 hour / 21% structural difference that has nothing to do with economic health. A metro with a large oil and gas sector will always score higher on raw hours than a tech hub, regardless of actual labor market conditions.

Scoring deviation from each city's own baseline removes this structural bias. It answers: "relative to this city's own normal, is demand for labor currently elevated or depressed?" A 0.5-hour increase above a city's own 12-month average is a statistically meaningful demand signal even though the absolute level means little in cross-city comparison.

**Base effect protection:** Using the 12-month trailing average rather than a point-in-time prior-year comparison prevents false positives from depressed baselines. A city with chronically low hours that ticks up slightly still scores below neutral on this metric — the 12-month average reflects its depressed state, not a pre-depression peak.

**Data dependency:** Requires `12month_average` to be populated in `processed_economic_data_v2.json`, which requires at least 12 monthly observations. New metros or first-run scenarios default to the 50th percentile (neutral).

---

### 107E — Total Nonfarm Employment Growth YoY (Weight: 15%)

**What it measures:** The year-over-year percent change in total nonfarm payroll employment for the metro. Sourced from BLS SAE.

**Direction:** `invert=False` — stronger employment growth = higher percentile score.

**Why 15% weight:** Employment growth is the most direct measure of labor demand. When businesses are expanding headcount, they are expressing confidence in revenue expectations. It captures growth that unemployment and LFP may miss — a market can have stable unemployment while employment is growing rapidly if the labor force is also expanding.

**Why this replaced HPI and PSF as standalone metrics:**

The original scoring included Home Price Index (HPI) YoY and Price Per Square Foot (PSF) YoY as separate housing metrics. This created two problems:

1. **Double-counting:** PSF appears in the COL composite (104C) AND was scored as a standalone metric (202), giving housing price appreciation approximately 20% combined weight with partial cancellation.

2. **Signal contamination:** Rising housing prices can reflect either genuine demand (people moving to a growing city) or supply constraints in a stagnant or contracting market. Milwaukee and Cincinnati showed rising prices despite contracting employment — the price signal was misleading about economic health. Employment growth directly measures actual labor demand without the supply-constraint contamination.

---

### 200B — Building Permits YoY (Weight: 10%)

**What it measures:** The year-over-year percent change in residential building permits, using a 3-month smoothed average to reduce monthly volatility. Sourced from FRED / Census Bureau.

**Direction:** `invert=False` — more permit growth = higher percentile score.

**Why smoothed:** Building permits are volatile month-to-month due to project timing, seasonal factors, and permit-approval batch effects. A 3-month smoothed YoY (comparing the 3-month average ending this month to the 3-month average ending 12 months ago) substantially reduces noise without losing the trend signal.

**What it captures:** Forward-looking construction activity. Rising permits indicate developer confidence in future demand and will eventually translate into housing supply — relevant both as an economic activity indicator and as a leading indicator of future housing availability for workers.

---

### 204A — Days on Market Composite (Weight: 5%)

**What it measures:** A 2-component composite assessing housing market accessibility for incoming workers, combining the trend direction with a level-based context filter.

**Underlying data:** Median days a listing spends on market before going under contract. Sourced from Realtor.com/FRED.

**Direction:** `invert=False` — higher composite score = more accessible/healthy market = higher percentile score.

#### Component 1 — YoY Trend (0-6 points, 60% of composite)

Scores the YoY percent change in median days on market on a linear scale:

| YoY Change | c1 Score | Interpretation |
|------------|----------|----------------|
| -30% or worse | 0.0 | Market tightening sharply — harder for workers to find housing |
| 0% (flat) | 3.0 | Neutral |
| +30% or better | 6.0 | Market loosening significantly — more inventory for incoming workers |

Rising days on market (loosening) is scored as better for incoming workers because more inventory means more options, less competition, and more time to find the right home. Falling days on market (tightening) means workers must compete aggressively for scarce inventory.

#### Component 2 — Level Context (0-4 points, 40% of composite)

Scores the absolute level of days on market against a "healthy market" anchor using a bell-curve-shaped scale:

| Level | c2 Score | Interpretation |
|-------|----------|----------------|
| 35-80 days | 4.0 | Healthy, accessible range — peaks here |
| Below 15 days | 0.0 | Extreme tightness — workers cannot compete effectively |
| Above 130 days | 0.0 | Potential demand destruction / market distress |
| Between 15-35 days | Linear 0-4 | Transitioning from tight to healthy |
| Between 80-130 days | Linear 4-0 | Transitioning from healthy to soft |

This component exists to prevent a single misleading signal from the trend alone. A market loosening from a distressed-soft base (rising from 100 to 120 days) gets trend credit from c1 but is appropriately penalized by a low c2, resulting in a middling composite. A market loosening from a healthy-tight base (rising from 45 to 60 days) gets full credit on both components.

**Why not just score the level (lower = better):** The original metric scored raw DoM level with `invert=True` (fewer days = better). This systematically rewarded supply-constrained coastal metros — San Jose at 23 days scored at the 98th percentile, Charlotte at 69 days scored at the 20th percentile — despite San Jose having contracting employment and Charlotte having some of the strongest payroll growth in the country. The composite captures both accessibility (trend) and context (level).

---

## Composite Score Calculation

```
weighted_percentile = sum(percentile[metric] * weight[metric]) / sum(weights)
```

Since all weights sum to 100, this simplifies to a weighted average of percentile scores.

The resulting `weighted_percentile` represents approximately what percentile the metro occupies on the joint distribution of all 9 metrics, weighted by their economic importance.

---

## Grade Thresholds

Grade thresholds are calibrated to the **actual achievable range** of weighted percentile scores, not the theoretical 0-100 range.

Because the weighted score is an average of 9 individual percentile scores across 50 cities, the distribution compresses. No city can plausibly average 90+ across all 9 metrics simultaneously, and no city averages below 20. The practical range observed is approximately 21-79.

Thresholds are set so the grade distribution is meaningful and discriminating across the full spectrum:

| Threshold | Grade | Description |
|-----------|-------|-------------|
| 68+ | A+ | Excellent |
| 63+ | A | Very Good |
| 59+ | A- | Good |
| 55+ | B+ | Above Average |
| 50+ | B | Average |
| 44+ | B- | Below Average |
| 38+ | C+ | Poor |
| 32+ | C | Very Poor |
| 26+ | C- | Critical |
| Below 26 | D | Emergency |

This produces a natural bell-curve distribution across the 50 metros with meaningful separation at every grade level. Cities in the A range are genuinely performing well across most metrics; D-grade cities have meaningful weakness across the board.

---

## What the Score Is Not

**It is not a quality-of-life index.** Amenities, climate, culture, and livability are not measured.

**It is not a real estate investment signal.** Rising home prices can indicate either strong demand (good) or supply constraints in a weak market (misleading). This is why raw housing price appreciation was removed as a standalone metric.

**It is not a prediction.** The score reflects current and trailing conditions. It is a lagging-to-coincident indicator, not a forecast.

**It is not size-adjusted.** A metro with 500,000 workers and a metro with 5,000,000 workers are compared on rates and percentages, not absolute counts. This is intentional — the question is economic health, not scale.

---

## Design Decisions and Tradeoffs

**Why 85% employment / 15% housing?** Employment metrics directly measure the labor market conditions that drive business location decisions. Housing metrics matter — they affect worker recruitment, retention, and quality of life — but they are secondary signals. The previous 65/35 split gave housing too much influence and allowed supply-constrained markets to score deceptively well on housing price appreciation.

**Why percentile ranking rather than z-scores?** Percentile ranks are bounded 0-100, immune to outliers pulling the scale, and immediately interpretable by business audiences who are not statisticians. Z-scores require knowing what a "good" vs. "bad" z-score is; percentile ranks are self-explanatory.

**Why composite scoring for COL, OWR, and DoM?** Simple single-value metrics can miss important nuance. COL measured as a single ratio misses whether affordability is improving or worsening. OWR measured as a snapshot misses whether the professional economy is growing. DoM measured as a level misses whether the market is loosening or tightening. Composite scoring lets each metric carry multiple economic signals in proportion to their importance.

---

**Last updated:** April 2026
