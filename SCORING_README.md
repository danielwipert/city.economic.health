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
- **Cross-metric comparability:** All 8 metrics live on the same 0-100 scale before weighting, making the weighted average mathematically clean.

---

## The 8 Metrics

### 101A — Unemployment Rate (Weight: 20%)

**What it measures:** The share of the civilian labor force that is unemployed and actively seeking work. Sourced from BLS Local Area Unemployment Statistics (LAUS).

**Direction:** `invert=True` — lower unemployment = higher percentile score.

**Why 20% weight:** Unemployment is the most widely tracked, most politically salient, and most directly actionable labor market signal. A 0.5 percentage point difference in unemployment is statistically and economically significant — it represents tens of thousands of workers in a large metro. It is the single most powerful indicator of labor market health.

**What it does not capture:** Unemployment is a lagging indicator. It peaks after recessions have already begun and falls after recoveries are already underway. It also misses discouraged workers who have left the labor force entirely, which is why 102A (LFP) complements it.

---

### 102A — Labor Force Participation Rate (Weight: 10%)

**What it measures:** The share of the civilian non-institutional population (age 16+) that is either employed or actively looking for work. Sourced from BLS LAUS.

**Direction:** `invert=False` — higher LFP = higher percentile score.

**Why 10% weight:** LFP captures what unemployment misses — a city can have low unemployment simply because discouraged workers stopped looking. However, LFP is anchored to annual population benchmarks from BLS, meaning the denominator only updates meaningfully once per year. This makes it a slow-moving structural snapshot rather than a dynamic monthly signal. It retains genuine value as a measure of workforce engagement depth, but does not deserve equal footing with monthly dynamic signals. Weight reduced from 15% to reflect this cadence constraint.

**Structural caveat:** LFP varies significantly by demographic composition — cities with older populations (Tampa, Cleveland, Pittsburgh), large student populations (Providence), or significant military presence (Virginia Beach) will have structurally lower LFP independent of economic conditions. The percentile ranking compares cities against each other, which partially mitigates absolute level bias but does not eliminate it.

---

### 103B — Hourly Earnings YoY Growth (Weight: 15%)

**What it measures:** The year-over-year percent change in average hourly earnings for all private-sector employees in the metro. Sourced from BLS State and Metro Area Employment, Hours, and Earnings (SAE).

**Direction:** `invert=False` — stronger wage growth = higher percentile score.

**Why 15% weight:** Rising wages are a real-time demand signal — employers bid up labor prices when they need workers and expect revenue growth. It also directly affects worker purchasing power and quality of life. Weight increased from 10% to 15%: earnings data updates monthly and reflects genuine labor market tightness more dynamically than the annual-anchored LFP rate. The 5% redistributed from 102A reflects the relative timeliness advantage of earnings data.

**What to watch:** A city with strong wage growth but rising unemployment (a rare but possible leading indicator of overheating or layoffs in progress) would show split signals across 101A and 103B — exactly the kind of nuance the multi-metric composite is designed to surface.

---

### 104C — Cost of Living Composite (Weight: 12%)

**What it measures:** A 3-component composite assessing housing cost burden relative to local wages, including the current level, the trend direction, and how that trend compares to other metros.

**Underlying data:** `Price Per Square Foot / Average Hourly Earnings` — a ratio measuring how many hours of local work it takes to buy one square foot of housing. This normalizes housing costs against local wage levels rather than using a national price index.

**Direction:** `invert=True` — lower composite score = more affordable = higher percentile score.

**Why 12% weight:** The cost of living environment is a critical factor in business location decisions — it determines how far wages stretch for workers and directly affects recruitment and retention. Weight increased from 10% to 12% (2% redistributed from 105C) to reflect its importance as a location signal alongside labor metrics.

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

This component answers a different question than c2: not "is affordability improving?" but "is it improving faster or slower than everywhere else?" A city that's worsening when the national trend is also worsening is less alarming than one bucking a broad national improvement.

---

### 105C — Office Worker Ratio Composite (Weight: 3%)

**What it measures:** A 2-component composite assessing the concentration and growth of professional/office-based employment, used as a proxy for knowledge-economy job density.

**Underlying data:** BLS employment in "Information," "Financial Activities," and "Professional and Business Services" sectors as a share of total nonfarm payroll.

**Direction:** `invert=False` — higher score = more office-economy concentration = higher percentile score.

#### Component 1 — YoY Growth (0-3 points)
Percentile-ranks the YoY growth rate in the 3-month smoothed office worker count. Captures whether knowledge-economy jobs are expanding in this market.

#### Component 2 — Absolute Percentage (0-2 points)
Percentile-ranks the raw share of jobs that are office-based. Captures structural depth of the professional economy independent of recent trends.

**Why 3% weight:** Office worker density is a useful tiebreaker signal — it differentiates knowledge-economy metros from industrial, logistics, and energy-dominated metros. However, it structurally penalizes legitimate economic models (Houston energy, Memphis logistics, Kansas City distribution) that happen to carry fewer office workers, not because of weakness but because of industry composition. Weight reduced from 5% to 3% to keep it as a mild directional signal rather than a meaningful scoring factor. The 2% redistributed to 104C (cost of living).

---

### 107E — Labor Demand Composite (Weight: 25%)

**What it measures:** A 2-component composite combining total nonfarm employment growth (primary signal) with weekly hours deviation from each city's own 12-month baseline (context-adjusted secondary signal). Sourced from BLS SAE (employment) and BLS SAE (weekly hours).

**Direction:** `invert=False` — higher composite = stronger labor demand = higher percentile score.

**Why 25% weight:** This is the single most impactful metric in the system, absorbing the former standalone 107E (employment growth, 15%) and 106D (weekly hours deviation, 10%). The two signals are more valuable combined than separate because the hours signal has opposite economic meaning depending on whether employment is growing or contracting. Combined weight of 25% reflects that labor demand is the central question this scoring system is designed to answer.

#### Component 1 — Employment Growth YoY (70% = 7 pts)

Year-over-year percent change in total nonfarm payroll employment. Scaled linearly:

| Employment YoY | c1 Score |
|----------------|----------|
| -2% or worse | 0.0 |
| 0% (flat) | 3.5 |
| +3% or better | 7.0 |

#### Component 2 — Weekly Hours Deviation, Employment-Conditioned (30% = 3 pts)

How much the recent 3-month average of weekly hours deviates from that metro's own 12-month trailing baseline. The **direction of the signal flips based on whether employment is growing or contracting**, capturing four economically distinct scenarios:

| Scenario | Employment | Hours vs Trend | Interpretation | c2 Treatment |
|---|---|---|---|---|
| STRONG | Growing | Above | Genuine demand confirmation | Rewarded (up to 3 pts) |
| GROWING | Growing | Below | Expansion with hours softening — mild caution | Partial credit |
| SQUEEZE | Contracting | Above | Survivor squeeze — remaining workers overloaded | Penalized (near 0) |
| WEAK | Contracting | Below | Consistent contraction | Neutral (1.5 pts) — c1 captures the decline |

**Why the survivor squeeze matters:** When a company lays off workers, remaining employees often absorb more hours. Under the former standalone 106D metric, this registered as a *positive* signal — hours above trend = good. Kansas City (-0.31% employment, +1.43% hours deviation) scored at the 96th percentile on 106D while actively shedding jobs. The composite correctly penalizes this pattern.

**Why hours below trend during contraction is neutral (not rewarded):** If employment is falling and hours are also falling, that is consistent contraction. It is not a positive signal — c1 already scores the employment decline. No bonus is awarded for hours falling alongside payrolls.

**Hours deviation formulation:** `(3mo_avg - 12mo_avg) / 12mo_avg * 100`. Uses the 12-month trailing average rather than a point-in-time prior-year comparison to prevent false positives from depressed baselines. Scores deviation on a ±1.5% range when employment is growing.

**Why this replaced standalone 106D and 107E:**

The original standalone 106D metric rewarded cities where hours were above trend regardless of employment direction. Analysis of the 50-metro dataset revealed a systematic flaw: cities in active contraction — shedding payrolls while the remaining workforce was being squeezed — scored in the 80th–96th percentile on 106D. Meanwhile, growing cities where workers were shifting to flexible/hybrid arrangements scored near the bottom. The composite resolves this by making the hours signal employment-conditional.

---

### 200B — Building Permits YoY (Weight: 10%)

**What it measures:** The year-over-year percent change in residential building permits, using a 3-month smoothed average to reduce monthly volatility. Sourced from FRED / Census Bureau.

**Direction:** `invert=False` — more permit growth = higher percentile score.

**Why smoothed:** Building permits are volatile month-to-month due to project timing, seasonal factors, and permit-approval batch effects. A 3-month smoothed YoY (comparing the 3-month average ending this month to the 3-month average ending 12 months ago) substantially reduces noise without losing the trend signal.

**What it captures:** Forward-looking construction activity. Rising permits indicate developer confidence in future demand and will eventually translate into housing supply — relevant both as an economic activity indicator and as a leading indicator of future housing availability for workers.

---

### 204A — Days on Market Composite (Weight: 5%)

**What it measures:** A 2-component composite assessing housing market health for workers, combining a level-dependent trend signal with a level-based context filter.

**Underlying data:** Median days a listing spends on market before going under contract. Sourced from Realtor.com/FRED.

**Direction:** `invert=False` — higher composite score = healthier market = higher percentile score.

#### Component 1 — YoY Trend (0-6 points, 60% of composite)

The direction of the trend signal depends on the current DoM level. A **60-day inflection point** separates two economically distinct regimes:

**When DoM < 60 days (tight/healthy-low market):** rising DoM is good — the market is gaining inventory and accessibility for incoming workers.

| YoY Change | c1 Score | Interpretation |
|------------|----------|----------------|
| -30% or worse | 0.0 | Tightening sharply — harder for workers to find housing |
| 0% (flat) | 3.0 | Neutral |
| +30% or better | 6.0 | Loosening — more inventory, more time to transact |

**When DoM ≥ 60 days (elevated/soft market):** direction inverts — rising DoM is demand destruction, penalized. A market at 60+ days that keeps softening signals that buyers cannot or will not transact at current prices. Existing owners are locked in, labor mobility is impaired.

| YoY Change | c1 Score | Interpretation |
|------------|----------|----------------|
| +30% or worse | 0.0 | Worsening demand destruction |
| 0% (flat) | 3.0 | Neutral |
| -30% or better | 6.0 | Recovering — demand returning, market tightening from soft base |

**Why the inflection:** a market loosening from 25→40 days is gaining healthy inventory. A market softening from 65→80 days means no one is buying — the same direction change has the opposite economic meaning depending on where you start. Rising DoM in an already-soft market also signals labor mobility impairment: homeowners who cannot sell are unable to relocate for better opportunities, reducing workforce flexibility for both workers and employers.

#### Component 2 — Level Context (0-4 points, 40% of composite)

Scores the absolute level of days on market against a "healthy market" anchor using a bell-curve-shaped scale:

| Level | c2 Score | Interpretation |
|-------|----------|----------------|
| 35-80 days | 4.0 | Healthy, accessible range — peaks here |
| Below 15 days | 0.0 | Extreme tightness — workers cannot compete effectively |
| Above 130 days | 0.0 | Demand destruction / market distress |
| Between 15-35 days | Linear 0-4 | Transitioning from tight to healthy |
| Between 80-130 days | Linear 4-0 | Transitioning from healthy to soft |

**Why not just score the level (lower = better):** The original metric scored raw DoM level with `invert=True` (fewer days = better). This systematically rewarded supply-constrained coastal metros while penalizing markets with healthy inventory levels. The composite captures both market health (trend) and context (level).

---

## Composite Score Calculation

```
weighted_percentile = sum(percentile[metric] * weight[metric]) / sum(weights)
```

Since all weights sum to 100, this simplifies to a weighted average of percentile scores.

The resulting `weighted_percentile` represents approximately what percentile the metro occupies on the joint distribution of all 8 metrics, weighted by their economic importance.

---

## Weight Summary

| Code | Metric | Weight | Category |
|------|--------|--------|----------|
| 107E | Labor Demand Composite (employment + hours) | 25% | Employment |
| 101A | Unemployment Rate | 20% | Employment |
| 103B | Hourly Earnings YoY | 15% | Employment |
| 104C | Cost of Living Composite | 12% | Employment |
| 102A | Labor Force Participation Rate | 10% | Employment |
| 200B | Building Permits YoY | 10% | Housing |
| 204A | Days on Market Composite | 5% | Housing |
| 105C | Office Worker Ratio Composite | 3% | Employment |
| | **Total** | **100%** | **85% Employment / 15% Housing** |

---

## Grade Thresholds

Grade thresholds are calibrated to the **actual achievable range** of weighted percentile scores, not the theoretical 0-100 range.

Because the weighted score is an average of 8 individual percentile scores across 50 cities, the distribution compresses. No city can plausibly average 90+ across all 8 metrics simultaneously, and no city averages below 20. The practical range observed is approximately 21-79.

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

**Why composite scoring for COL, OWR, DoM, and LDC?** Simple single-value metrics can miss important nuance. COL measured as a single ratio misses whether affordability is improving or worsening. OWR measured as a snapshot misses whether the professional economy is growing. DoM measured as a level misses whether the market is loosening or tightening. The Labor Demand Composite is the most important example: hours deviation has opposite economic meaning (demand signal vs. survivor squeeze) depending on whether employment is growing or contracting — a single-value metric cannot capture this.

---

**Last updated:** April 2026
