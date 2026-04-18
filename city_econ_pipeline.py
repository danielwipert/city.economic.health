"""
city_econ_pipeline.py
Generates city economic briefs from calculated_metrics_reconciled.json.

Output format per city:
  - Opening paragraph (2-3 sentences: overall grade + defining economic character)
  - 8 per-metric sections, each with a **Bold Header** and 2-3 sentences of analysis
  - Closing paragraph (2-3 sentences: bottom line for decision-makers)

Saves to city_reports_ft_cautious/{slug}.md, which generate_site.py and
generate_pdf_report.py read to populate the Economic Analysis section.

Usage:
    python city_econ_pipeline.py
    (Run from the final.1/ directory so relative paths resolve correctly)
"""

import os
import json
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from together import Together
from dotenv import load_dotenv

load_dotenv()

import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

# ─── CONFIG ───────────────────────────────────────────────────────────────────

TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
if TOGETHER_API_KEY is None:
    raise RuntimeError(
        "TOGETHER_API_KEY not set.\n"
        "In PowerShell run: $env:TOGETHER_API_KEY = 'your_key_here'"
    )

MODEL_ID   = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
JSON_PATH  = "calculated_metrics_reconciled.json"
OUTPUT_DIR = Path("city_reports_ft_cautious")
MAX_WORKERS = 4

# ─── METRIC ORDER (matches the website scorecard) ─────────────────────────────

METRICS = [
    ("107E", "Labor Demand",       "25%"),
    ("101A", "Unemployment",       "20%"),
    ("103B", "Wage Growth",        "15%"),
    ("104C", "Cost of Living",     "12%"),
    ("102A", "Labor Force Growth", "10%"),
    ("200B", "Building Permits",   "10%"),
    ("204A", "Days on Market",      "5%"),
    ("105C", "Office Economy",      "3%"),
]

PROCESSED_DATA_PATH = "processed_economic_data_v2.json"

# ─── PER-METRIC WRITING NOTES (fed to LLM as interpretive context) ────────────

METRIC_NOTES = {
    "107E": (
        "Labor Demand (25% weight): composite of employment growth YoY + weekly hours deviation "
        "from each city's own 12-month baseline. Higher score = more jobs being added AND hours "
        "running above trend (genuine demand). Low score = payrolls contracting or hours below trend. "
        "The scenario matters: hours above trend during JOB GROWTH = genuine demand. "
        "Hours above trend during JOB LOSSES = survivor squeeze (remaining workers absorbing load of eliminated roles)."
    ),
    "101A": (
        "Unemployment (20% weight): percentage of the labor force unemployed and seeking work. "
        "INVERTED — a HIGH percentile score means LOW unemployment (tight market). "
        "Low unemployment = harder to hire, more wage pressure. "
        "High unemployment = easier to staff but weaker local consumer demand."
    ),
    "103B": (
        "Wage Growth (15% weight): year-over-year change in average hourly earnings. "
        "Higher score = wages rising faster. Strong wage growth = rising labor costs for employers, "
        "good for worker purchasing power. Slow wage growth = flat cost environment but weak bargaining power."
    ),
    "104C": (
        "Cost of Living (12% weight): composite affordability score (0–10 scale, LOWER = MORE AFFORDABLE). "
        "Combines: (1) absolute PSF/earnings ratio, (2) YoY direction — PSF falling vs rising relative to wages, "
        "(3) peer-relative trend. INVERTED — a HIGH percentile score means MORE AFFORDABLE. "
        "When the briefing shows 'PSF $X / earnings $Y/hr', name these actual dollar figures. "
        "If PSF is falling YoY, say so — that is the key driver of high affordability scores. "
        "High score = talent attraction advantage. Low score = expensive, requires wage premiums."
    ),
    "102A": (
        "Labor Force Growth (10% weight): year-over-year change in the civilian labor force count "
        "(employed + actively seeking work). This is NOT a participation rate — do not call it one. "
        "Positive = workforce supply expanding. Negative = shrinking labor pool, structural headwind for hiring."
    ),
    "200B": (
        "Building Permits (10% weight): year-over-year change in residential building permits (3-month smoothed). "
        "Rising = developer confidence, future housing supply expanding, affordability improving. "
        "Falling sharply = supply squeeze building ahead, future affordability and workforce attraction at risk."
    ),
    "204A": (
        "Days on Market (5% weight): how long homes sit before going under contract. "
        "INVERTED — HIGH percentile = homes sitting LONGER (slower, buyer-friendly market). "
        "LOW percentile = homes selling very fast (hot market, tough for relocating workers). "
        "Rising DOM in a strong job market = healthy normalization. "
        "Rising DOM with weak jobs = demand erosion. "
        "Name both the absolute level in days AND the year-over-year direction."
    ),
    "105C": (
        "Office Economy (3% weight): share of jobs in professional/office sectors + growth trend. "
        "High = deep knowledge-economy talent pool, suited for tech/finance/consulting/HQ decisions. "
        "Low = fewer specialized roles, more industrial or logistics-dominant economy. "
        "IMPORTANT: do NOT quote the raw composite index value — use the percentile rank only."
    ),
}

# ─── UTILS ────────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    return name.strip("-") or "city"


def tier_label(score: float) -> str:
    if score >= 80: return "top tier"
    if score >= 60: return "above average"
    if score >= 40: return "near median"
    if score >= 20: return "below average"
    return "bottom tier"


def load_metros(path: str) -> pd.DataFrame:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "metros" in data:
        return pd.DataFrame(data["metros"])
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict) and "metros" in entry:
                return pd.DataFrame(entry["metros"])
    raise ValueError("Unable to find 'metros' list in JSON file.")


def load_processed_data(path: str) -> dict:
    """Load processed_economic_data_v2.json and return a dict keyed by metro_name."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        metros = data.get("metros", {})
        if isinstance(metros, dict):
            # Keys are metro_name strings — return as-is
            return metros
        if isinstance(metros, list):
            return {m["metro_name"]: m for m in metros if "metro_name" in m}
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {}


# Loaded once at module level so it's available to build_briefing
_PROCESSED_DATA: dict = {}


# ─── BRIEFING SHEET ───────────────────────────────────────────────────────────

def build_briefing(record: dict, city_name: str) -> str:
    """
    Human-readable data table for the LLM. Labeled rows with raw values
    and percentile tier — no cryptic JSON field names.
    """
    pct   = record.get("percentile_scores", {}) or {}
    raw   = record.get("raw_values", {}) or {}
    grade = record.get("grade", {})
    wp    = round(record.get("weighted_percentile", 50), 1)
    metro = record.get("metro_name", city_name)

    grade_letter = grade.get("letter", "?") if isinstance(grade, dict) else str(grade)
    grade_desc   = grade.get("description", "") if isinstance(grade, dict) else ""

    def fmt_pct(key, decimals=2):
        v = raw.get(key)
        return f"{v:+.{decimals}f}%" if v is not None else "N/A"

    def fmt_val(key, decimals=2, suffix=""):
        v = raw.get(key)
        return f"{v:.{decimals}f}{suffix}" if v is not None else "N/A"

    def row(label, value_str, pct_key):
        sc = pct.get(pct_key, 50)
        return f"  {label:<40} {value_str:<22} {tier_label(sc)} ({round(sc)}th pct)"

    dom_yoy   = raw.get("204A_dom_yoy_pct")
    dom_level = raw.get("204A_dom_level_days")
    dom_str   = (f"{dom_yoy:+.1f}% YoY" if dom_yoy is not None else "N/A")
    if dom_level is not None:
        dom_str += f" ({int(dom_level)} days)"

    # Pull PSF and earnings directly from processed data for accurate CoL description
    metro_proc = _PROCESSED_DATA.get(metro, {})
    proc_data  = metro_proc.get("data", {})
    psf_block  = proc_data.get("price_per_sqft", {})
    earn_block = proc_data.get("hourly_earnings", {})

    psf_val    = psf_block.get("latest_value")
    psf_yoy    = (psf_block.get("yoy_change") or {}).get("pct_change")
    earn_val   = earn_block.get("latest_value")

    if psf_val is not None and earn_val is not None:
        raw_ratio  = psf_val / earn_val
        psf_yoy_s  = f" ({psf_yoy:+.1f}% YoY)" if psf_yoy is not None else ""
        col_str    = f"${psf_val:.0f}/sqft{psf_yoy_s} vs ${earn_val:.2f}/hr → ratio {raw_ratio:.2f}"
    else:
        col_str    = fmt_val("104C_col", suffix=" (composite 0-10)")

    lines = [
        f"METRO: {metro}",
        f"OVERALL GRADE: {grade_letter} — {grade_desc} ({wp}th percentile, ranked out of 50 US metros)",
        "",
        f"  {'METRIC':<40} {'RAW VALUE':<22} PERCENTILE TIER",
        "  " + "-" * 74,
        row("Employment growth YoY",            fmt_pct("107E_employment_growth_yoy"),          "107E"),
        row("Weekly hours vs own trend",         fmt_pct("107E_wh_trend_deviation_pct", 3),      "107E"),
        row("Labor demand composite score",      fmt_val("107E_ldc_composite", suffix=""),       "107E"),
        row("Unemployment rate",                 fmt_val("101A_unemployment", suffix="%"),       "101A"),
        row("Wage growth (hourly earnings YoY)", fmt_pct("103B_earnings_yoy"),                  "103B"),
        row("Cost of living (PSF vs wages)",     col_str,                                        "104C"),
        row("Labor force growth YoY",            fmt_pct("102A_clf_yoy"),                        "102A"),
        row("Building permits YoY",              fmt_pct("200B_permits_yoy"),                    "200B"),
        row("Days on market",                    dom_str,                                        "204A"),
        row("Office/professional worker share",  fmt_val("105C_owr", suffix=" (composite 0-5)"), "105C"),
    ]
    return "\n".join(lines)


# ─── PROMPT ───────────────────────────────────────────────────────────────────

def build_prompt(record: dict, city_name: str) -> str:
    briefing    = build_briefing(record, city_name)
    notes_block = "\n\n".join(
        f"[{code}] {note}" for code, note in METRIC_NOTES.items()
    )

    prompt = f"""\
You are writing an economic city brief for a senior executive making a business location decision.
The audience is financially literate. Be direct, specific, and anchor every claim in actual numbers.

METRIC INTERPRETATION GUIDE — read this before writing:
{notes_block}

CITY DATA:
{briefing}

─────────────────────────────────────────────
Write the brief in EXACTLY this structure:

[Opening paragraph — 2-3 sentences. State the overall grade and composite score. Name the 1-2 metrics that most define this city's current economic character. Use specific numbers.]

**Labor Demand**
[2-3 sentences. Name the employment growth rate and hours deviation. State what the combination signals — genuine demand expansion, contraction, or survivor squeeze. Be direct.]

**Unemployment**
[2-3 sentences. Name the actual unemployment rate. State whether the market is tight or has slack. Name the practical implication for a business trying to hire here.]

**Wage Growth**
[2-3 sentences. Name the YoY wage growth rate. State whether it is fast, moderate, or stagnant. Name the implication for employer labor costs and worker purchasing power.]

**Cost of Living**
[2-3 sentences. State whether the city is affordable or expensive relative to peers, using the percentile rank as context. Name what this means for talent attraction without wage premiums.]

**Labor Force Growth**
[2-3 sentences. Name the YoY growth rate of the civilian labor force. State whether supply is expanding or contracting. Name the implication for hiring capacity.]

**Building Permits**
[2-3 sentences. Name the YoY change in permits. State whether housing supply is expanding or tightening. Name what this signals for future affordability and workforce accommodation.]

**Days on Market**
[2-3 sentences. Name the current median days on market AND the YoY direction. State what this means for a worker relocating to this city — competitive or accessible?]

**Office Economy**
[2-3 sentences. State how deep the professional talent pool is, using the percentile rank. Name the type of business this city is best and worst suited for.]

[Closing paragraph — 2-3 sentences. Bottom line: what does this city offer a business, and what is the single biggest risk or constraint a decision-maker should factor in?]

─────────────────────────────────────────────
FORMAT RULES — follow exactly:
- Opening and closing are plain paragraphs — no bold label, no section header
- The 8 metric sections use exactly these bold headers on their own line:
  **Labor Demand**, **Unemployment**, **Wage Growth**, **Cost of Living**,
  **Labor Force Growth**, **Building Permits**, **Days on Market**, **Office Economy**
- Each metric section: 2-3 sentences, no more
- Use specific numbers — percentages, days, percentile ranks
- INVERSION reminders: high Cost of Living percentile = MORE affordable; high Days on Market percentile = SLOWER market
- No bullet points inside metric sections
- No preamble like "Here is the brief:" — start directly with the opening paragraph
"""
    return prompt


# ─── LLM CALL ─────────────────────────────────────────────────────────────────

def call_llm(prompt: str) -> str:
    client = Together(api_key=TOGETHER_API_KEY)
    completion = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior economics analyst writing city briefs for corporate location decisions. "
                    "You follow format instructions precisely and never deviate from the specified structure. "
                    "You lead with specific numbers and avoid vague generalities."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=1400,
        temperature=0.25,
        top_p=0.9,
    )
    return completion.choices[0].message.content


# ─── CLEAN OUTPUT ─────────────────────────────────────────────────────────────

def clean_output(text: str) -> str:
    """Strip common LLM preamble and normalize metric header formatting."""
    # Remove preamble lines like "Here is the brief:" or "Sure, here's the analysis:"
    text = re.sub(
        r"^(?:(?:sure,?\s*)?here(?:'s|\s+is)(?:\s+the)?[\w\s]*:)\s*\n*",
        "",
        text.strip(),
        flags=re.IGNORECASE,
    )
    # If LLM put metric header and first sentence on same line ("**Labor Demand** Some text..."),
    # ensure the text starts on its own line beneath the header.
    metric_names = (
        "Labor Demand|Unemployment|Wage Growth|Cost of Living|"
        "Labor Force Growth|Building Permits|Days on Market|Office Economy"
    )
    text = re.sub(
        rf"(\*\*(?:{metric_names})\*\*)[ \t]+",
        r"\1\n",
        text,
    )
    return text.strip()


# ─── PER-CITY PIPELINE ────────────────────────────────────────────────────────

def process_city(city: str, df: pd.DataFrame) -> Path:
    """Run the full pipeline for a single city and write the .md file."""
    df_city = df[df["primary_city"] == city]
    if df_city.empty:
        raise ValueError(f"No data found for '{city}'")

    record = df_city.to_dict(orient="records")[0]
    prompt = build_prompt(record, city)
    raw    = call_llm(prompt)
    output = clean_output(raw)

    grade        = record.get("grade", {})
    grade_letter = grade.get("letter", "?") if isinstance(grade, dict) else str(grade)
    grade_desc   = grade.get("description", "") if isinstance(grade, dict) else ""
    wp           = round(record.get("weighted_percentile", 50), 1)
    metro_name   = record.get("metro_name", city)
    updated      = pd.Timestamp.now().strftime("%B %Y")

    OUTPUT_DIR.mkdir(exist_ok=True)
    filename = OUTPUT_DIR / f"{slugify(city)}.md"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# {metro_name}\n\n")
        f.write(f"**Grade: {grade_letter} ({grade_desc}) | {wp}th percentile | {updated}**\n\n")
        f.write("---\n\n")
        f.write(output)
        f.write("\n")

    return filename


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    global _PROCESSED_DATA

    import argparse
    parser = argparse.ArgumentParser(description="City Economic Brief Pipeline")
    parser.add_argument("--city", nargs="+", metavar="CITY",
                        help="Only process these cities (e.g. --city Austin Dallas)")
    args = parser.parse_args()

    print("=" * 60)
    print("  CITY ECONOMIC BRIEF PIPELINE")
    print("=" * 60)

    print("\n→ Loading metros...")
    df = load_metros(JSON_PATH)
    all_cities = sorted(df["primary_city"].dropna().unique())

    if args.city:
        cities = [c for c in all_cities if c in args.city]
        missing = [c for c in args.city if c not in all_cities]
        if missing:
            print(f"  WARNING: not found in data: {missing}")
        print(f"  Running {len(cities)} city/cities: {cities}")
    else:
        cities = all_cities
        print(f"  {len(cities)} cities found.")

    print("→ Loading processed data for CoL enrichment...")
    _PROCESSED_DATA = load_processed_data(PROCESSED_DATA_PATH)
    print(f"  {len(_PROCESSED_DATA)} metro records loaded.\n")

    OUTPUT_DIR.mkdir(exist_ok=True)

    print(f"→ Generating briefs ({MAX_WORKERS} parallel workers)...\n")

    futures = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for city in cities:
            futures[executor.submit(process_city, city, df)] = city

        for future in as_completed(futures):
            city = futures[future]
            try:
                path = future.result()
                print(f"  [OK]    {city:<30} → {path.name}")
            except Exception as e:
                print(f"  [ERROR] {city:<30} → {e}")

    print(f"\n✓ Done. Reports saved to: {OUTPUT_DIR.resolve()}")
    print("\nNext: run generate_site.py to rebuild the website.")


if __name__ == "__main__":
    main()
