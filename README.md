# Economic City Health Report System

A data-driven analysis platform that ranks the top 50 U.S. metropolitan areas by economic health and generates automated LinkedIn content.

## Overview

This system analyzes 10 economic indicators across 50 major U.S. metros, assigns a letter grade (A-F) to each, and generates professional LinkedIn copy explaining each city's economic performance.

## Pipeline

```
FRED API → Economic Data → Percentile Scoring → Grades → LinkedIn Copy → Automated Posts
```

### Step 1: Pull Economic Data (`pull_economic_data.py`)
- **Source:** Federal Reserve Economic Data (FRED) API
- **Data:** 10 indicators × 50 metros × 15 observations per metric
- **Output:** `raw_economic_data.json`

### Step 2: Process Historical Data (`process_historical_data.py`)
- Calculates 3-month averages
- Computes year-over-year growth rates
- Handles data validation and conversion

### Step 3: Calculate Metrics & Grades (`calculate_metrics_65_35.py`)
- **Scoring:** 100-point percentile-based system
- **Weighting:** 65% Employment / 35% Housing
- **Output:** `calculated_metrics_reconciled.json`

### Step 4: Generate LinkedIn Copy (`generate_city_summaries_pro.py`)
- **LLM:** Hugging Face API (Llama-2 70B)
- **Content:** 3-4 sentence professional analysis per city
- **Output:** `generated_city_copy.json`

## Scoring System

### Employment Metrics (65 points)
- Unemployment Rate (15 pts)
- Labor Force Participation (15 pts)
- Hourly Earnings Growth YoY (10 pts)
- Cost of Living (10 pts)
- Office Worker Ratio (5 pts)
- Weekly Hours Worked (10 pts)

### Housing Metrics (35 points)
- Building Permits Growth YoY (10 pts)
- Home Price Index Growth YoY (10 pts)
- Price Per Sqft Growth YoY (10 pts)
- Median Days on Market (5 pts)

**Grading Scale:**
- A: 75-100 percentile (Excellent)
- B+: 65-74 percentile (Above Average)
- B: 50-64 percentile (Average)
- B-: 40-49 percentile (Below Average)
- C+: 30-39 percentile (Poor)
- C: 20-29 percentile (Very Poor)
- C-: 0-19 percentile (Critical)

## Key Features

✅ **Percentile-Based Scoring** - Intuitive interpretation (75th percentile = better than 75% of metros)  
✅ **Automated Data Pipeline** - Monthly updates via GitHub Actions  
✅ **Smart API Usage** - 552 total API calls for all 10 metrics across 50 metros  
✅ **Professional Copy Generation** - AI-powered LinkedIn content with economic insights  
✅ **Cross-Platform Compatible** - Runs on Windows, Mac, Linux  

## Data Sources

| Data | Source | Frequency |
|------|--------|-----------|
| Employment metrics | FRED API | Monthly |
| Housing metrics | FRED API | Monthly |
| Cost of living | FRED API | Quarterly |

Free API keys: https://fred.stlouisfed.org/docs/api/

## Local Setup

### Prerequisites
- Python 3.8+
- Hugging Face Pro account (for LLM access)

### Quick Start
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env file with API keys
FRED_API_KEY=your_key
HUGGING_FACE_API_KEY=your_key

# 3. Test the setup
python test_pro_account.py

# 4. Generate copy for all 50 cities
python generate_city_summaries_pro.py
```

## Output Format

### JSON Output Example
```json
{
  "rank": 1,
  "city": "New York",
  "grade": "C",
  "percentile": 27.5,
  "generated_copy": "New York ranks 1st out of 50 metros but scores a C grade due to structural employment challenges. While wage growth outpaces most cities (70th percentile), unemployment remains elevated (12th percentile) and labor force participation lags significantly (32nd percentile)..."
}
```

## Content Strategy

**Monthly rotation across 4 weeks:**
- Week 1: Top 10 metros (ranks 1-10)
- Week 2: Mid-major metros (ranks 11-20)
- Week 3: Smaller metros (ranks 21-30)
- Week 4: Monthly analysis & insights

## Technology Stack

- **Data Processing:** Python (pandas, requests)
- **Spreadsheets:** Excel (openpyxl)
- **LLM API:** Hugging Face Hub
- **Automation:** GitHub Actions
- **Data Source:** FRED API

## Current State

✅ Complete 3-script data pipeline with 100% API success rate  
✅ All 10 metrics properly calculated with 65/35 weighting  
✅ JSON data ready for all 50 metros  
⏳ LinkedIn copy generation in progress  
⏳ Automated carousel image generation (planned)  
⏳ AI-powered economic commentary integration (planned)  

## Files

| File | Purpose |
|------|---------|
| `pull_economic_data.py` | Fetch data from FRED API |
| `process_historical_data.py` | Calculate derived metrics |
| `calculate_metrics_65_35.py` | Score and grade metros |
| `generate_city_summaries_pro.py` | Generate LinkedIn copy |
| `calculated_metrics_reconciled.json` | Complete economic data for all 50 metros |

## Next Steps

1. ✅ Test Hugging Face API setup
2. ✅ Generate LinkedIn copy for all 50 cities
3. ⏳ Build carousel image generator (Canva → HTML/CSS → Playwright)
4. ⏳ Schedule automated LinkedIn posts
5. ⏳ Add real-time cost of living calculations

## Project Goals

**Short-term:** Automated monthly LinkedIn content with professional economic analysis  
**Long-term:** Comprehensive economic intelligence platform for metro-level decision making

## Questions or Contributions?

This is an active project. Updates and improvements are ongoing.

---

**Last Updated:** November 2025  
**Status:** Active Development
