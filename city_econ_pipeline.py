import os
import json
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from together import Together


# --------------------------------------------------------
# CONFIG
# --------------------------------------------------------

TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
if TOGETHER_API_KEY is None:
    raise RuntimeError("TOGETHER_API_KEY not set. In PowerShell run:\n"
                       "$env:TOGETHER_API_KEY = 'your_together_api_key_here'")

# Analysis model (econ reasoning)
ANALYSIS_MODEL_ID = "Qwen/Qwen3-235B-A22B-Instruct-2507-tput"

# Stylist model (prose polish)
STYLE_MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct-Turbo"

# Input JSON
JSON_PATH = "calculated_metrics_reconciled.json"

# City identifier inside metros[]
PRIMARY_CITY_COLUMN = "primary_city"   # will use if present
FALLBACK_CITY_COLUMN = "msa"           # fallback if primary_city missing

# Output directory
OUTPUT_DIR = Path("city_reports_ft_cautious")

# Parallelism (how many cities at once)
MAX_WORKERS = 4


# --------------------------------------------------------
# UTILS
# --------------------------------------------------------

def slugify(name: str) -> str:
    """Convert a city name into a safe filename."""
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    return name.strip("-") or "city"


# --------------------------------------------------------
# DATA LOADING
# --------------------------------------------------------

def load_metros(path: str) -> pd.DataFrame:
    """
    Load your JSON and extract the metros list into a DataFrame.

    Expected structures:
      - { ..., "metros": [ {...}, {...}, ... ] }
      - or [ { ..., "metros": [ ... ] }, ... ]
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Case 1: top-level dict with 'metros'
    if isinstance(data, dict) and "metros" in data:
        return pd.DataFrame(data["metros"])

    # Case 2: list of dicts, one of which has 'metros'
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict) and "metros" in entry:
                return pd.DataFrame(entry["metros"])

    raise ValueError("Unable to find 'metros' list in JSON file.")


# --------------------------------------------------------
# PROMPT BUILDERS
# --------------------------------------------------------

def build_analysis_prompt(df_city: pd.DataFrame, city_name: str) -> str:
    """
    Build the prompt that the analysis model uses to produce the economic analysis.
    """
    records = df_city.to_dict(orient="records")
    data_json = json.dumps(records, indent=2)

    interpretation_guide = """
METRIC INTERPRETATION RULES — follow these exactly, never contradict them:

1. 101A_unemployment (Unemployment Rate, %):
   - LOWER is better. Below 3.5% = very tight. 3.5–4.5% = healthy. 4.5–6% = slack. Above 6% = weak.
   - 101A_unemp_yoy_pp: NEGATIVE = unemployment FALLING = improving. POSITIVE = rising = worsening.

2. 102A_clf_yoy (Civilian Labor Force YoY % change):
   - Measures how fast the pool of available workers is growing.
   - HIGHER is better. Positive = workforce expanding. Negative = workforce shrinking.
   - Do NOT call this a participation rate — it is not.

3. 103B_earnings_yoy (Average Hourly Earnings YoY %):
   - HIGHER is better. Above 4% = strong wage growth.
   - If above ~3–4% inflation benchmark, workers are gaining real purchasing power.

4. 104C_col (Cost of Living Composite — PSF/earnings ratio):
   - LOWER is better = more affordable relative to earnings.
   - High score = expensive. Low score = affordable.

5. 105C_owr (Office Worker Ratio Composite):
   - HIGHER is better = more white-collar / professional services density.
   - Very low score = city is structurally reliant on logistics, industrial, or service-sector employment.

6. 107E_ldc_composite (Labor Demand Composite):
   - HIGHER is better = stronger overall labor demand signal.

7. 107E_employment_growth_yoy (Nonfarm Payroll YoY %):
   - HIGHER is better. Above 2% = strong. 1–2% = moderate. Below 1% = slow. Negative = contracting.

8. 107E_wh_trend_deviation_pct (Weekly Hours vs 12-Month Baseline, %):
   - POSITIVE = workers logging MORE hours than their recent trend = demand strengthening.
   - NEGATIVE = hours below recent trend = demand softening.

9. 200B_permits_yoy (Residential Building Permits YoY %):
   - Higher = more construction activity = builder confidence.
   - Large positive swing = strong supply response or speculative building.

10. 204A_dom_level_days (Median Days on Market):
    - LOWER is better = homes selling faster = stronger buyer demand.
    - Higher number = homes sitting longer = buyer hesitation or excess supply.

11. 204A_dom_yoy_pct (Median Days on Market YoY % change):
    - NEGATIVE = homes selling FASTER than last year = market tightening.
    - POSITIVE = homes taking LONGER to sell = market cooling/softening.
    - CRITICAL: Rising days on market means the market is SLOWING, not tightening. Never describe rising DOM as "tight inventory."

12. 204A_dom_composite (Days on Market Composite Score):
    - HIGHER is better. Low composite = slow-moving housing market.
"""

    output_format = f"""
OUTPUT FORMAT — follow this structure exactly for {city_name}:

Write one paragraph per section below, each beginning with the bold header shown.
Each paragraph should: state the key value(s), assess whether it is strong/weak/mixed, and explain what it means for this city in 2–4 sentences.
End with a Conclusion paragraph that synthesizes the overall picture.
Use plain numbers when citing data. Do not add asterisks, bullet points, or sub-headers inside paragraphs.

**Unemployment & Labor Market**
[Cover 101A_unemployment and 101A_unemp_yoy_pp]

**Workforce Supply**
[Cover 102A_clf_yoy]

**Wage Growth**
[Cover 103B_earnings_yoy]

**Labor Demand**
[Cover 107E_ldc_composite, 107E_employment_growth_yoy, and 107E_wh_trend_deviation_pct]

**Cost of Living**
[Cover 104C_col]

**Office Economy**
[Cover 105C_owr]

**Housing — Construction**
[Cover 200B_permits_yoy]

**Housing — Market Velocity**
[Cover 204A_dom_level_days and 204A_dom_yoy_pct — apply rule 11 above strictly]

**Conclusion**
[3–5 sentences synthesizing overall economic health, key strengths, key risks, and near-term outlook]
"""

    prompt = (
        f"Write a structured economic analysis of {city_name} using the dataset and rules below.\n\n"
        f"{interpretation_guide}\n"
        f"{output_format}\n"
        "Dataset (JSON):\n"
        f"{data_json}"
    )
    return prompt


def build_polish_prompt(raw_text: str, city_name: str) -> str:
    """
    Build the prompt that the polish model uses to refine the analysis draft.
    """
    prompt = (
        f"You are a copy editor. Polish the prose in this economic analysis of {city_name}.\n\n"
        "Rules:\n"
        "- Preserve every factual claim, number, and interpretation exactly as written.\n"
        "- Preserve the bold section headers and paragraph structure exactly — do not merge, reorder, or remove sections.\n"
        "- Improve sentence clarity, word choice, and flow within each paragraph only.\n"
        "- Remove redundant phrases and tighten wordy sentences.\n"
        "- Maintain a neutral, analytical tone throughout.\n"
        "- Do NOT introduce new data, change any stated direction (e.g. rising vs falling), or alter the meaning of any sentence.\n\n"
        f"{raw_text}"
    )
    return prompt


# --------------------------------------------------------
# MODEL CALLS
# --------------------------------------------------------

def call_analysis_model(prompt: str) -> str:
    """
    Call the analysis model via Together to produce the economic analysis.
    """
    client = Together(api_key=TOGETHER_API_KEY)

    completion = client.chat.completions.create(
        model=ANALYSIS_MODEL_ID,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior economics columnist at the Financial Times. "
                    "Write clear, neutral, data-driven economic analysis."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=3000,
        temperature=0.3,
        top_p=0.9,
    )

    return completion.choices[0].message.content


def call_polish_model(prompt: str) -> str:
    """
    Call the polish model via Together to refine the analysis draft.
    """
    client = Together(api_key=TOGETHER_API_KEY)

    completion = client.chat.completions.create(
        model=STYLE_MODEL_ID,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a world-class copy editor for the Financial Times. "
                    "You refine wording and structure but do not invent new facts."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=3000,
        temperature=0.2,
        top_p=0.9,
    )

    return completion.choices[0].message.content


# --------------------------------------------------------
# PER-CITY PIPELINE
# --------------------------------------------------------

def process_city(city: str, df: pd.DataFrame, city_col: str) -> Path:
    """
    Full pipeline for a single city:
      - subset data
      - analysis model pass
      - polish model pass
      - write markdown file
    Returns the output file path.
    """
    df_city = df[df[city_col] == city]

    analysis_prompt = build_analysis_prompt(df_city, city)
    raw_analysis = call_analysis_model(analysis_prompt)

    polish_prompt = build_polish_prompt(raw_analysis, city)
    polished_analysis = call_polish_model(polish_prompt)

    OUTPUT_DIR.mkdir(exist_ok=True)
    filename = OUTPUT_DIR / f"{slugify(city)}.md"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# {city} — Economic Overview (FT Style)\n\n")
        f.write("## Polished FT-style column\n\n")
        f.write(polished_analysis.strip())
        f.write("\n\n---\n\n")
        f.write("## Original analysis draft (for reference)\n\n")
        f.write(raw_analysis.strip())
        f.write("\n")

    return filename


# --------------------------------------------------------
# MAIN
# --------------------------------------------------------

def main():
    print("Loading metros from JSON...")
    df_metros = load_metros(JSON_PATH)

    # Decide which column identifies the city
    if PRIMARY_CITY_COLUMN in df_metros.columns:
        city_col = PRIMARY_CITY_COLUMN
    elif FALLBACK_CITY_COLUMN in df_metros.columns:
        city_col = FALLBACK_CITY_COLUMN
    else:
        raise ValueError(
            f"Neither '{PRIMARY_CITY_COLUMN}' nor '{FALLBACK_CITY_COLUMN}' "
            f"found in metro columns: {list(df_metros.columns)}"
        )

    cities = sorted(df_metros[city_col].dropna().unique())
    print(f"Using city column: {city_col}")
    print(f"Found {len(cities)} cities.\n")

    OUTPUT_DIR.mkdir(exist_ok=True)

    # Parallel processing
    futures = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for city in cities:
            futures[executor.submit(process_city, city, df_metros, city_col)] = city

        for future in as_completed(futures):
            city = futures[future]
            try:
                path = future.result()
                print(f"[OK] {city} -> {path}")
            except Exception as e:
                print(f"[ERROR] {city}: {e}")

    print("\nDone. All available city reports generated in:", OUTPUT_DIR.resolve())


if __name__ == "__main__":
    main()
