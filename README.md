# City Economic Health — Scoring & Report System

Ranks the top 50 U.S. metropolitan areas by economic health using live BLS/FRED data. Produces a percentile-based composite score, letter grade, and AI-generated analytical report for each metro. Runs automatically every Monday via GitHub Actions.

---

## Pipeline

```
FRED API ──► pull_economic_data_unified_FIXED.py
                    │
                    ▼
             economic_data_combined.json
                    │
                    ▼
      process_historical_data_v2_FIXED.py
                    │
                    ▼
          processed_economic_data_v2.json
                    │
                    ▼
       calculate_metrics_reconciled_V6.py
                    │
                    ▼
    calculated_metrics_reconciled.json
    Economic_Metrics_All_Metros.xlsx
                    │
                    ▼
       city_econ_pipeline_cautious.py          ← automated weekly
                    │
                    ▼
          city_reports_ft_cautious/
          (one .md report per city)
                    │
                    ▼
       generate_pdf_report.py                  ← local / on-demand
       generate_rankings_pdf.py
       generate_site.py
                    │
                    ▼
          pdf_output/   site/
```

### Step 1 — Data Pull (`pull_economic_data_unified_FIXED.py`)
Fetches 9 data series × 50 metros from the FRED API (~452 calls). Collects 15 observations per series for trend and average calculations. Output: `economic_data_combined.json`.

### Step 2 — Historical Processor (`process_historical_data_v2_FIXED.py`)
Calculates derived fields for each series: 3-month average, 12-month average, YoY change (absolute and percent), 3-month smoothed YoY. Handles annual series detection — if the gap between observations exceeds 300 days, YoY is computed as obs[0] vs obs[1] (true one-year comparison) rather than obs[0] vs obs[12]. The 12-month average is required for the weekly hours trend deviation component inside 107E. Output: `processed_economic_data_v2.json`.

### Step 3 — Scoring Engine (`calculate_metrics_reconciled_V6.py`)
Builds percentile scores for 8 metrics across 50 metros, applies weights, calculates composite grades. Key staleness guards: PSF data older than 9 months is treated as missing for 104C; building permits data older than 6 months (monthly series) or 3 years (annual series) is treated as missing or falls back to annual YoY. Outputs JSON and a formatted Excel workbook (5 sheets).

### Step 4 — LLM Reports (`city_econ_pipeline_cautious.py`)
Generates a two-pass AI report per city using Together AI:
- Pass 1 (Qwen 2.5 72B): evidence-based economic analysis from the metric data
- Pass 2 (Llama 3.1 8B): copy-editing pass for FT-style tone and restraint

Output: one Markdown file per city in `city_reports_ft_cautious/`.

### Step 5 — PDF & Site Generation (local / on-demand)
Three standalone scripts for publishing output:

| Script | Output |
|--------|--------|
| `generate_pdf_report.py` | Full PDF report — `pdf_output/city_economic_report_YYYY-MM-DD.pdf` |
| `generate_rankings_pdf.py` | Single-page landscape rankings — `pdf_output/city_rankings_YYYY-MM-DD.pdf` |
| `generate_site.py` | Full static website — `site/` (index, rankings, methodology, 50 metro pages) |

These are not part of the automated weekly run. Uses Jinja2 for HTML templating and Playwright (headless Chromium) for PDF rendering.

---

## Automation

GitHub Actions runs steps 1–4 every Monday at 9:00 AM UTC (`.github/workflows/economic-data-weekly.yml`). Results are committed back to the repo automatically. Requires two repository secrets: `FRED_API_KEY` and `TOGETHER_API_KEY`.

---

## Local Setup

**Requirements:** Python 3.11+

```bash
pip install requests pandas openpyxl pillow together python-dotenv jinja2 playwright
playwright install chromium
```

Create `.env` in `final.1/`:
```
FRED_API_KEY=your_fred_api_key
TOGETHER_API_KEY=your_together_api_key
```

**Run the full pipeline:**
```bash
python pull_economic_data_unified_FIXED.py
python process_historical_data_v2_FIXED.py
python calculate_metrics_reconciled_V6.py
python city_econ_pipeline_cautious.py   # optional — requires TOGETHER_API_KEY
python generate_pdf_report.py           # optional — generates PDF + site
python generate_rankings_pdf.py         # optional — rankings PDF only
```

Free FRED API key: https://fred.stlouisfed.org/docs/api/api_key.html

---

## Output Files

| File / Directory | Description |
|------------------|-------------|
| `economic_data_combined.json` | Raw pull output — 15 observations per series per metro |
| `processed_economic_data_v2.json` | Processed data with averages, YoY changes, trend fields |
| `calculated_metrics_reconciled.json` | Final scores, grades, and raw values for all 50 metros |
| `Economic_Metrics_All_Metros.xlsx` | Excel workbook — Summary, Metric Scores, Raw Values, By Rank, Top vs Bottom |
| `city_reports_ft_cautious/*.md` | AI-generated FT-style economic report per city |
| `pdf_output/*.pdf` | PDF reports (full report + standalone rankings) |
| `site/` | Static website — index, rankings, methodology, 50 metro pages |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Data source | FRED API (Federal Reserve Economic Data) |
| Data processing | Python — pandas, requests |
| Scoring engine | Python — custom percentile ranking |
| Excel output | openpyxl |
| LLM inference | Together AI (Qwen 2.5 72B + Llama 3.1 8B) |
| PDF generation | Jinja2 + Playwright (headless Chromium) |
| Static site | Jinja2 HTML templates |
| Automation | GitHub Actions |

---

## Scoring Overview

8 metrics, percentile-ranked across 50 metros, weighted composite score. **Weight split: 85% employment-side / 15% housing-side.**

| Code | Metric | Weight | Direction |
|------|--------|--------|-----------|
| 107E | Labor Demand Composite (employment growth + hours deviation) | 25% | higher = better |
| 101A | Unemployment Rate Composite (level + YoY direction) | 20% | higher = better |
| 103B | Hourly Earnings YoY (3-month avg) | 15% | higher = better |
| 104C | Cost of Living Composite (3-component) | 12% | lower = better |
| 102A | Civilian Labor Force YoY % change | 10% | higher = better |
| 200B | Building Permits YoY (3-month avg) | 10% | higher = better |
| 204A | Days on Market Composite (2-component) | 5% | higher = better |
| 105C | Office Worker Ratio Composite (2-component) | 3% | higher = better |

---

## Metric Design Notes

### 101A — Unemployment Rate Composite
Two-component composite scored 0–10 (higher = better), then percentile-ranked.
- **c1 (75%):** Absolute level anchored at 2% (full score) → 8% (zero). Scores the current unemployment rate on a fixed scale regardless of where other metros sit.
- **c2 (25%):** YoY point-to-point change in pp. Improvement rewarded, deterioration penalized. ±1.0pp range.

Uses point-to-point YoY (not 3-month avg) — BLS LAUS has a structural publication gap at index 12 for ~46/50 metros each run. A 13-month fallback handles the rare permanently-missing month.

### 102A — Civilian Labor Force YoY
YoY % change in the raw FRED LAUS civilian labor force count. Replaced the former LFP rate calculation (labor force ÷ civilian population) which had two compounding issues: the population denominator was stale Census data (some metros grew 20%+ since the last update) and BLS LAUS geographic codes don't perfectly align with ACS CBSA definitions. YoY growth eliminates the denominator entirely — the series compares to itself 12 months prior.

### 103B — Hourly Earnings YoY
Uses 3-month average YoY rather than point-to-point. Earnings data has no missing-value gaps across the 50-metro dataset, so the 3-month average is always available. Smooths single-month noise (year-end bonus mix, seasonal staffing) that causes >1pp swings in ~40% of metros.

### 104C — Cost of Living Composite
Three-component composite scored 0–10 (lower = better penalty), then inverted for percentile ranking.
- **c1 (50%):** PSF ÷ hourly earnings ratio, min-max normalized across all metros with valid data.
- **c2 (30%):** YoY % change in the ratio. ≤−5% (improving) → 0pts penalty; ≥+5% (worsening) → 3pts.
- **c3 (20%):** Deviation from median YoY across all metros. ±10pp range.

**Staleness guard:** if PSF latest date lags earnings latest date by more than 9 months, PSF is treated as missing and the metro receives a neutral 50th percentile score. Prevents stale housing data (e.g., a series discontinued mid-year) from producing misleading affordability trends.

### 105C — Office Worker Ratio Composite
Two-component composite scored 0–5 (higher = better), then percentile-ranked.
- **c1 (60%):** 3-month avg YoY % change in office worker headcount. Growing = better.
- **c2 (40%):** Office workers as a share of **total employment** (not civilian population). Replaced the prior population-denominator approach which used stale Census data and produced systematically low ratios for metros with older/larger non-working populations.

### 107E — Labor Demand Composite
Two-component composite scored 0–10 (higher = better), then percentile-ranked.
- **c1 (70%):** YoY % change in total nonfarm employment.
- **c2 (30%):** Weekly hours deviation from 12-month trend. **Employment-conditioned:** hours above trend only contribute positively when employment is also growing. Prevents the "survivor squeeze" pattern (layoffs pushing remaining workers' hours up) from registering as a positive signal.

Absorbs the former standalone 106D (weekly hours, 10%) and 107E (employment growth, 15%) into a single 25% metric.

### 200B — Building Permits YoY
Uses 3-month avg YoY for monthly series. Four metros have non-standard data:
- **Cleveland:** MSA monthly series (`CLEV439BPPRIV`) discontinued after Dec 2023. Uses Ohio state series (`OHBPPRIVSA`) as proxy.
- **Providence:** Uses Rhode Island state series (`RIBPPRIVSA`) as proxy — MSA-level monthly series unavailable on FRED.
- **Hartford:** Uses Connecticut state series (`CTBPPRIVSA`) as proxy.
- **Fresno:** Uses county annual series (`BPPRIV006019`). Annual YoY computed as current year vs prior year (obs[0] vs obs[1]). No monthly MSA or useful sub-California regional series available on FRED.

Staleness guards: monthly series older than 6 months → neutral. Annual series older than 3 years → neutral.

### 204A — Days on Market Composite
Two-component composite scored 0–10 (higher = better), then percentile-ranked.
- **c1 (60%):** YoY % change in median DoM. Direction interpretation uses a **graduated blend zone** (45–75 days) rather than a hard inflection at 60 days.
  - Below 45 days: loosening (rising DoM) = good — more inventory for incoming workers.
  - Above 75 days: loosening = bad — demand destruction, owners locked in.
  - 45–75 days: linearly blended. At 60 days, each interpretation carries 50% weight.
- **c2 (40%):** Absolute DoM level. Peaks at 4pts for 35–80 days (healthy/accessible). Penalizes extreme tightness (<15 days, accessibility problem) and severe softness (>130 days, distress).

The blend zone eliminates the cliff where a 1-day difference in DoM level caused a multi-point composite swing.

---

## Grade Thresholds

Thresholds are calibrated to the achievable weighted-average range (~24–79) that results from averaging 8 percentile scores across 50 metros. No city can realistically score above ~79 on the weighted average.

| Grade | Threshold | Description |
|-------|-----------|-------------|
| A+ | ≥ 68 | Excellent |
| A | ≥ 63 | Very Good |
| A- | ≥ 59 | Good |
| B+ | ≥ 55 | Above Average |
| B | ≥ 50 | Average |
| B- | ≥ 44 | Below Average |
| C+ | ≥ 38 | Poor |
| C | ≥ 32 | Very Poor |
| C- | ≥ 26 | Critical |
| D | < 26 | Emergency |

---

## Current Status

- Full pipeline operational and automated weekly
- All 8 metrics audited and calibrated (April 2026)
- Key improvements from April 2026 audit:
  - 102A switched from LFP rate to labor force YoY growth (eliminates stale population denominator)
  - 104C added PSF staleness guard (Cleveland, Detroit → neutral when PSF data >9 months old)
  - 105C switched OWR denominator from population to total employment
  - 200B fixed 4 metros with bad/missing series; state proxies for Cleveland/Providence/Hartford
  - 204A replaced hard 60-day regime cliff with 45–75 day blend zone
  - 101A upgraded to 2-component composite (level + YoY direction)
  - 103B switched to 3-month average YoY

---

**Last updated:** April 2026
