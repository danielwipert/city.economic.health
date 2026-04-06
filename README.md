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
Fetches 11 data series x 50 metros from the FRED API (~552 calls). Collects 15 monthly observations per series for trend and average calculations. Output: `economic_data_combined.json`.

### Step 2 — Historical Processor (`process_historical_data_v2_FIXED.py`)
Calculates derived fields for each series: 3-month average, 12-month average, YoY change (absolute and percent), 3-month smoothed YoY. The 12-month average is required for the weekly hours trend deviation component inside 107E. Output: `processed_economic_data_v2.json`.

### Step 3 — Scoring Engine (`calculate_metrics_reconciled_V6.py`)
Builds percentile scores for 8 metrics across 50 metros, applies weights, calculates composite grades. Includes composite scoring logic for COL (3-component), OWR (2-component), Days on Market (2-component), and the Labor Demand Composite (employment + hours, 2-component). Outputs JSON and a formatted Excel workbook (5 sheets).

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

8 metrics, percentile-ranked across 50 metros, weighted composite score. See `SCORING_README.md` for full methodology including composite metric details, grade calibration, and design rationale.

**Weight split: 85% employment-side / 15% housing-side**

| Code | Metric | Weight |
|------|--------|--------|
| 107E | Labor Demand Composite (employment growth + hours deviation) | 25% |
| 101A | Unemployment Rate | 20% |
| 103B | Hourly Earnings YoY | 15% |
| 104C | Cost of Living Composite (3-component) | 12% |
| 102A | Labor Force Participation Rate | 10% |
| 200B | Building Permits YoY | 10% |
| 204A | Days on Market Composite (2-component) | 5% |
| 105C | Office Worker Ratio Composite (2-component) | 3% |

**Key design note on 107E:** The former standalone 106D (weekly hours deviation) was merged into 107E as a conditioned secondary component. Hours above trend only score positively when employment is also growing — this prevents the "survivor squeeze" pattern (layoffs pushing hours up) from registering as a positive signal.

---

## Current Status

- Full pipeline operational and automated weekly
- 107E Labor Demand Composite replaces former standalone 106D + 107E metrics
- Grade thresholds calibrated to the achievable weighted-average range (~24-79)

---

**Last updated:** April 2026
