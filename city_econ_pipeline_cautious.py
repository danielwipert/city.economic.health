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
    raise RuntimeError(
        "TOGETHER_API_KEY not set. In PowerShell run:\n"
        "$env:TOGETHER_API_KEY = 'your_together_api_key_here'"
    )

# Analysis model (econ reasoning) — Llama 3.3 70B serverless
ANALYSIS_MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct-Turbo"

# Polish model (prose tightening) — Llama 3 8B serverless
STYLE_MODEL_ID = "meta-llama/Meta-Llama-3-8B-Instruct-Lite"

# Input JSON
JSON_PATH = "calculated_metrics_reconciled.json"

# City identifier inside metros[]
PRIMARY_CITY_COLUMN = "primary_city"
FALLBACK_CITY_COLUMN = "msa"

# Output directory
OUTPUT_DIR = Path("city_reports_ft_cautious")

# Parallelism
MAX_WORKERS = 4


# --------------------------------------------------------
# UTILS
# --------------------------------------------------------

def slugify(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    return name.strip("-") or "city"


def tier_label(score: float) -> str:
    """Convert a 0-100 percentile score to a plain-English tier label."""
    if score >= 80: return "top tier"
    if score >= 60: return "above average"
    if score >= 40: return "near median"
    if score >= 20: return "below average"
    return "bottom tier"


# --------------------------------------------------------
# DATA LOADING
# --------------------------------------------------------

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


# --------------------------------------------------------
# PROMPT BUILDERS
# --------------------------------------------------------

def build_briefing_sheet(record: dict, city_name: str) -> str:
    """
    Build a clean, labeled briefing sheet from the scored metro record.
    This replaces the raw JSON dump — gives the model structured,
    human-readable context instead of cryptic field names.
    """
    pct = record.get("percentile_scores", {}) or {}
    raw = record.get("raw_values", {}) or {}
    grade = record.get("grade", {})
    wp   = round(record.get("weighted_percentile", 50), 1)
    metro_name = record.get("metro_name", city_name)

    grade_letter = grade.get("letter", "?") if isinstance(grade, dict) else str(grade)
    grade_desc   = grade.get("description", "") if isinstance(grade, dict) else ""

    def level(raw_val, decimals=2, suffix="%"):
        """Format a level value (no + sign)."""
        v = raw.get(raw_val)
        if v is None: return "N/A"
        return f"{v:.{decimals}f}{suffix}"

    def change(raw_val, decimals=2, suffix="% YoY"):
        """Format a change value (show + sign)."""
        v = raw.get(raw_val)
        if v is None: return "N/A"
        return f"{v:+.{decimals}f}{suffix}"

    def row(label, raw_str, pct_key):
        """One briefing row — percentile scores are already direction-corrected."""
        sc = pct.get(pct_key, 50)
        return f"  {label:<35} {raw_str:<20} {tier_label(sc)} ({round(sc)}th pct)"

    dom_yoy   = raw.get("204A_dom_yoy_pct")
    dom_level = raw.get("204A_dom_level_days")
    dom_str   = f"{dom_yoy:+.1f}% YoY" if dom_yoy is not None else "N/A"
    if dom_level is not None:
        dom_str += f" ({int(dom_level)} days)"

    lines = [
        f"METRO: {metro_name}",
        f"OVERALL GRADE: {grade_letter} — {grade_desc} ({wp}th percentile out of 50 US metros)",
        "",
        "LABOR MARKET",
        row("Unemployment rate",           level("101A_unemployment"),          "101A"),
        row("Labor force participation",   level("102A_lfp"),                   "102A"),
        row("Nonfarm employment growth",   change("107E_employment_growth_yoy"),"107E"),
        row("Wage growth (hourly)",        change("103B_earnings_yoy"),         "103B"),
        row("Weekly hours vs own trend",   change("106D_wh_trend_deviation_pct", suffix="% vs trend"), "106D"),
        "",
        "COSTS & WORKFORCE PROFILE",
        row("Cost of living composite",    level("104C_col", suffix=""),        "104C"),
        row("Office/professional share",   level("105C_owr", suffix=" (composite 0-5)"), "105C"),
        "",
        "HOUSING SUPPLY",
        row("Building permits YoY",        change("200B_permits_yoy", suffix="%"), "200B"),
        row("Days on market",              dom_str,                             "204A"),
    ]
    return "\n".join(lines)


def build_analysis_prompt(record: dict, city_name: str) -> str:
    """
    Build the Qwen prompt. Passes a structured briefing sheet — not raw JSON —
    and gives explicit structural instructions to produce a business brief,
    not a metric enumeration.
    """
    briefing = build_briefing_sheet(record, city_name)

    prompt = f"""You are writing an economic city brief for a senior executive making a business location decision.

{briefing}

Write a 3-paragraph analytical brief. Your job is to synthesize and interpret — not to list metrics.

PARAGRAPH 1 — The dominant story. Lead with the overall grade and what it reflects. What 2-3 metrics combine to define this city's economic character right now? Weave them into a coherent narrative about what kind of market this is.

PARAGRAPH 2 — Nuance and tension. Where do the metrics tell conflicting stories? Is there a leading indicator worth watching — something that suggests conditions may be shifting? Highlight anything top-tier or bottom-tier that deserves specific attention from a decision-maker.

PARAGRAPH 3 — Bottom line. Two sentences maximum. What does this city offer a business, and what is the primary risk or caveat? Be direct and opinionated.

Rules:
- DO NOT enumerate metrics one by one — synthesize across them
- Only highlight metrics that are notably strong or weak (top/bottom tier) — do not narrate average ones
- Anchor the narrative in specific numbers (e.g., "3.0% unemployment", "payrolls up 2.4%") — not just tier labels
- Use the cost of living percentile carefully: a high percentile score means MORE AFFORDABLE (invert=True)
- Avoid hollow filler phrases: "mixed picture", "various indicators", "a range of outcomes", "it is worth noting"
- No bullet points or headers — flowing paragraphs only
- Target 200-250 words
"""
    return prompt


def build_polish_prompt(raw_text: str, city_name: str) -> str:
    """
    Build the Llama polish prompt. Gives the model a concrete, specific task:
    enforce the opening-line rule, tighten prose, cut repetition.
    The model is NOT asked to restructure — just to sharpen.
    """
    prompt = f"""Edit the following economic brief about {city_name} for a senior business audience.

Your specific tasks:
1. The FIRST sentence must name the grade and state the single most important takeaway about this city — make it a headline, not a throat-clear.
2. Cut any sentence that repeats a point already made.
3. Replace vague hedges ("somewhat", "relatively", "may suggest", "appears to") with direct statements where the data clearly supports it.
4. If a sentence contains only a metric and its tier label with no insight, remove or merge it.
5. Keep all numbers and specific facts exactly as written.
6. Output must be exactly 3 paragraphs, no headers, no bullets.
7. Target 200-230 words — tighten, do not expand.

Brief to edit:
{raw_text}"""
    return prompt


# --------------------------------------------------------
# MODEL CALLS
# --------------------------------------------------------

def call_qwen_analysis(prompt: str) -> str:
    client = Together(api_key=TOGETHER_API_KEY)

    completion = client.chat.completions.create(
        model=ANALYSIS_MODEL_ID,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior economics analyst writing city briefs for "
                    "corporate location decisions. You synthesize data into clear, "
                    "direct narratives. You lead with what matters most, identify "
                    "tensions in the data, and close with a crisp bottom line. "
                    "You never list metrics in sequence — you build a story."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=1000,
        temperature=0.3,
        top_p=0.9,
    )

    return completion.choices[0].message.content


def call_llama_polish(prompt: str) -> str:
    client = Together(api_key=TOGETHER_API_KEY)

    completion = client.chat.completions.create(
        model=STYLE_MODEL_ID,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior editor at a business intelligence firm. "
                    "You make economic briefs tighter, more direct, and more useful "
                    "for executives. You follow editing instructions precisely. "
                    "You never add new facts."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=800,
        temperature=0.15,
        top_p=0.9,
    )

    return completion.choices[0].message.content


# --------------------------------------------------------
# PER-CITY PIPELINE
# --------------------------------------------------------

def process_city(city: str, df: pd.DataFrame, city_col: str) -> Path:
    """
    Full pipeline for a single city:
      - extract scored record
      - build structured briefing sheet
      - Qwen: synthesize into analytical narrative
      - Llama: sharpen and enforce structure
      - write clean markdown file
    """
    df_city = df[df[city_col] == city]
    record  = df_city.to_dict(orient="records")[0]

    analysis_prompt  = build_analysis_prompt(record, city)
    raw_analysis     = call_qwen_analysis(analysis_prompt)

    polish_prompt    = build_polish_prompt(raw_analysis, city)
    polished_brief   = call_llama_polish(polish_prompt)

    # Strip common LLM preamble artifacts (e.g. "Here is the edited brief:")
    polished_brief = re.sub(r"^(?:here is(?: the)? [\w\s]+:)\s*\n*", "", polished_brief.strip(), flags=re.IGNORECASE)

    # Build header metadata
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
        f.write(polished_brief.strip())
        f.write("\n")

    return filename


# --------------------------------------------------------
# MAIN
# --------------------------------------------------------

def main():
    print("Loading metros from JSON...")
    df_metros = load_metros(JSON_PATH)

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

    print("\nDone. Reports in:", OUTPUT_DIR.resolve())


if __name__ == "__main__":
    main()
