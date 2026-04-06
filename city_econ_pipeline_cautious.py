import os
import json
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from together import Together
from dotenv import load_dotenv

load_dotenv()

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
# METRIC WRITING GUIDE
# --------------------------------------------------------

METRIC_GUIDE = {
    "101A": {
        "label": "Unemployment Rate",
        "measures": "Percentage of the labor force without work and actively seeking employment.",
        "business_relevance": "A proxy for labor market tightness. Low unemployment = harder to hire, higher wage pressure. High unemployment = easier to staff but weaker consumer base.",
        "tiers": {
            "top":    "Exceptionally tight labor market. Businesses face real hiring competition; workers have leverage. Lead with this tension — availability is a constraint.",
            "above":  "Healthy, low unemployment. Labor market is constructive without being a severe constraint. Note positively but don't linger.",
            "median": "Unremarkable. Do not spend words on this metric.",
            "below":  "Elevated unemployment signals labor market slack. Easier hiring but potentially weakened local consumer demand. Flag as a risk.",
            "bottom": "Severe labor market weakness. High unemployment dominates this city's story — flag the consumer spending risk and probe whether this is structural or cyclical.",
        },
    },
    "102A": {
        "label": "Labor Force Participation",
        "measures": "Share of working-age adults who are employed or actively looking for work.",
        "business_relevance": "High LFP signals a deep labor pool. Low LFP — especially paired with low unemployment — indicates a shrinking or demographically constrained workforce, not just a tight market.",
        "tiers": {
            "top":    "Deep labor pool. Workforce engagement is a genuine strength — mention as a hiring advantage.",
            "above":  "Good participation rate. Workforce availability is a mild positive.",
            "median": "Unremarkable. Do not spend words on this metric.",
            "below":  "Labor pool is shallow. Even if unemployment looks low, the workforce itself may be aging out or withdrawing.",
            "bottom": "Critically low participation. Workforce availability is a significant structural constraint. Flag for any business considering expansion or relocation.",
        },
    },
    "107E": {
        "label": "Total Nonfarm Employment Growth (YoY)",
        "measures": "Year-over-year percentage change in total jobs across all sectors.",
        "business_relevance": "The headline measure of economic momentum. Fast growth = expanding demand, competition for workers. Decline = contraction, weaker demand but more available labor.",
        "tiers": {
            "top":    "Rapid job creation — this is an economically expanding market. Frame as a momentum story. Note that fast growth often precedes tighter labor conditions.",
            "above":  "Above-average job growth signals a healthy expansion. Mention as a positive indicator of economic health.",
            "median": "Steady but unremarkable. Omit or note only briefly.",
            "below":  "Below-average job growth suggests economic deceleration. Flag for decision-makers as a risk signal worth watching.",
            "bottom": "Job losses or near-stagnation. This is a contraction story — lead with this if it's bottom tier; don't soften it.",
        },
    },
    "103B": {
        "label": "Wage Growth (Hourly Earnings YoY)",
        "measures": "Year-over-year change in average hourly wages.",
        "business_relevance": "High wage growth signals worker leverage and rising labor costs for employers. It can also reflect a healthy consumer economy. Low wage growth = flat cost environment but weak spending power and possibly weak worker bargaining.",
        "tiers": {
            "top":    "Wages rising fast — excellent for workers, a real cost pressure for employers. Flag the labor cost implication explicitly.",
            "above":  "Solid wage growth. Positive for consumer spending; mild cost pressure for businesses.",
            "median": "Unremarkable wage trend. Omit or note briefly.",
            "below":  "Sluggish wage growth. Lower cost environment for employers but may signal weak worker bargaining power or softening demand.",
            "bottom": "Stagnant or declining real wages. Either workers have no leverage or the market is softening. Flag as a warning sign for consumer spending.",
        },
    },
    "106D": {
        "label": "Weekly Hours vs Own Trend",
        "measures": "How current weekly hours worked compare to this metro's own historical trend — not a national benchmark.",
        "business_relevance": "A leading indicator. Hours often shift before employment levels do. Above trend = employers squeezing more from current staff (precursor to hiring or burnout). Below trend = employers pulling back before headcount cuts.",
        "tiers": {
            "top":    "Hours running above trend — a leading indicator of continued hiring demand or elevated productivity pressure on existing staff.",
            "above":  "Slightly elevated hours. Subtle positive signal worth a brief mention if it reinforces other labor strength.",
            "median": "Hours near historical norm. Not a meaningful signal. Omit.",
            "below":  "Hours running below trend — early warning sign of softening demand. Mention alongside employment data as a forward-looking risk.",
            "bottom": "Hours sharply below trend. This is an early contraction signal. Use alongside employment or unemployment data as a corroborating warning.",
        },
    },
    "104C": {
        "label": "Cost of Living Composite",
        "measures": "Composite index of overall living costs (housing, goods, services) combined with direction of change and cost volatility.",
        "business_relevance": "High cost of living = harder to attract talent without premium wages; cost disadvantage for in-person services. Low cost of living = talent attraction advantage, lower real-wage floor, higher real consumer purchasing power.",
        "note": "CRITICAL — The percentile score is INVERTED. A HIGH percentile score means MORE AFFORDABLE. 90th percentile = among the cheapest metros in the dataset.",
        "tiers": {
            "top":    "Among the most affordable metros in this dataset. Strong cost advantage — lower real-wage requirements, higher consumer purchasing power, easier talent attraction.",
            "above":  "Below-average cost of living. Mild cost advantage worth mentioning if it reinforces the broader narrative.",
            "median": "Costs near the national median. Not a differentiating factor. Omit.",
            "below":  "Above-average cost of living. Businesses need to offer wage premiums to attract talent. Flag if pairing with elevated wage growth.",
            "bottom": "Among the most expensive metros. High cost of living is a meaningful constraint on talent acquisition and real consumer spending power. Name it.",
        },
    },
    "105C": {
        "label": "Office/Professional Worker Share",
        "measures": "Composite reflecting the share of the workforce in office and professional roles, including year-over-year change.",
        "business_relevance": "High professional workforce share = strong white-collar talent pool, higher office demand, knowledge-economy orientation. Relevant for tech, finance, legal, consulting, and HQ location decisions.",
        "note": "IMPORTANT: The raw value is a composite index (0–5 scale), NOT a percentage of the workforce. Do NOT quote the raw number in your prose — it is meaningless to a reader. Describe this metric using qualitative terms or the percentile rank only (e.g., 'Raleigh ranks in the 96th percentile for professional workforce concentration').",
        "tiers": {
            "top":    "Deep professional talent pool. Make the case for knowledge-economy businesses, HQ locations, or roles requiring specialized skills. Use the percentile rank to quantify, not the raw index value.",
            "above":  "Above-average professional workforce. Mild positive for office-dependent businesses. Use the percentile rank to quantify, not the raw index value.",
            "median": "Average professional workforce composition. Not a differentiating factor for most decisions. Omit.",
            "below":  "Thinner professional talent pool. May face constraints for specialized or senior roles. Use the percentile rank to quantify, not the raw index value.",
            "bottom": "Low professional/office worker concentration. A significant constraint for knowledge-economy businesses. Name it directly using the percentile rank, not the raw index value.",
        },
    },
    "200B": {
        "label": "Building Permits YoY",
        "measures": "Year-over-year change in residential building permits — a leading indicator of housing supply growth.",
        "business_relevance": "Rising permits signal housing supply expanding to meet demand — supports long-term affordability and workforce attraction. Declining permits = supply squeeze building ahead.",
        "tiers": {
            "top":    "Housing supply expanding aggressively. Strong positive for long-term affordability and workforce accommodation. Worth noting as a structural advantage.",
            "above":  "Above-average permit growth. Housing supply keeping pace with demand. Mild positive.",
            "median": "Permit activity near the median. Not a differentiating signal. Omit.",
            "below":  "Below-average permit growth. Housing supply may tighten — worth flagging as a forward-looking affordability risk.",
            "bottom": "Permits declining sharply. Housing supply is contracting — a leading indicator of future affordability stress and workforce attraction difficulty.",
        },
    },
    "204A": {
        "label": "Days on Market",
        "measures": (
            "How long homes sit on the market before going under contract — reported as both a current "
            "level (median days) and a year-over-year percentage change. These two dimensions must be "
            "read together: the LEVEL tells you whether the market is fast or slow right now compared "
            "to other metros; the YoY DIRECTION tells you whether it is getting faster or slower "
            "relative to its own recent history. They can point in different directions simultaneously."
        ),
        "business_relevance": (
            "For corporate location decisions, Days on Market is a proxy for housing accessibility — "
            "how hard will it be for a relocating employee to find and close on a home? A fast-moving "
            "market creates competition for workers who need to move quickly. A slow market gives buyers "
            "more options and negotiating room but may reflect weak underlying economic demand."
        ),
        "note": (
            "CRITICAL — The percentile score is INVERTED. A HIGH percentile score means homes are "
            "sitting LONGER (slower, cooler market relative to peers). A LOW percentile score means "
            "homes are selling very fast (hot market relative to peers). Always read the percentile rank "
            "alongside the YoY direction — a city can rank as 'fast' vs peers while simultaneously "
            "slowing down year-over-year. These are separate facts."
        ),
        "going_up_framework": (
            "DOM INCREASING (positive YoY) — homes are taking MORE DAYS to sell than last year. "
            "The market is SLOWING relative to its own recent pace. This is NOT automatically bad. "
            "Consider which scenario fits:\n"
            "  SCENARIO A — HEALTHY NORMALIZATION: The market was overheated and is coming back to "
            "earth. Buyers gain negotiating room, bidding wars ease, and affordability pressure "
            "moderates. If employment is strong and cost of living is reasonable, this is a positive "
            "development — the city is becoming more accessible without losing economic momentum. "
            "Write it as a stabilizing force, not a warning.\n"
            "  SCENARIO B — DEMAND EROSION: Fewer qualified buyers are in the market due to economic "
            "softness, population stagnation, or rate sensitivity. If employment growth is weak or "
            "declining and permits are also falling, rising DOM signals genuine demand deterioration. "
            "Write it as a risk and connect it to the broader economic picture.\n"
            "  HOW TO CHOOSE: Cross-reference employment growth (107E) and building permits (200B). "
            "Strong jobs + rising permits → Scenario A. Weak jobs + falling permits → Scenario B."
        ),
        "going_down_framework": (
            "DOM DECREASING (negative YoY) — homes are selling in FEWER DAYS than last year. "
            "The market is HEATING UP relative to its own recent pace. Again, context determines meaning:\n"
            "  SCENARIO A — GENUINE DEMAND SURGE: Population and employment growth is driving real "
            "housing demand. Workers are competing for homes. Strong for the local economy, but "
            "relocating employees face a fast-moving market — potential barrier to talent attraction "
            "if workers can't secure housing quickly or affordably.\n"
            "  SCENARIO B — SUPPLY CONTRACTION: Fewer homes are available, so the ones that do list "
            "sell fast — but it's a thin market, not necessarily thriving. Cross-reference with "
            "building permits: if permits are also falling sharply, this is supply-driven scarcity, "
            "not demand-driven strength.\n"
            "  HOW TO CHOOSE: Cross-reference employment growth (107E) and building permits (200B). "
            "Strong jobs + rising permits → Scenario A (healthy demand). "
            "Weak jobs + falling permits → Scenario B (thin supply illusion)."
        ),
        "points_of_interest": [
            "ABSOLUTE LEVEL MATTERS: 30 days is an extremely hot market; 60 days is fast; 90+ days is "
            "moderate; 120+ is a slow buyer's market. Name the absolute level in your analysis.",
            "MAGNITUDE OF CHANGE: A 5% YoY move may be noise. A 20%+ move is a market in transition "
            "— treat it as a meaningful signal and say so.",
            "PERMITS CROSS-CHECK: Rising DOM + rising permits = supply is finally catching up to demand "
            "(positive). Rising DOM + falling permits = demand collapsed without a supply response "
            "(negative). Falling DOM + falling permits = supply squeeze tightening (negative for "
            "affordability). Falling DOM + rising permits = builders are ahead of the market (watch).",
            "COST OF LIVING CROSS-CHECK: If the city scores well on affordability AND DOM is falling "
            "(market heating), the affordability advantage may be time-limited — flag this tension.",
            "DO NOT conflate the two dimensions: a city can have a LOW percentile score (fast relative "
            "to peers) AND a rising YoY (slowing relative to itself). These are compatible facts. "
            "State both clearly rather than picking one to define the narrative.",
        ],
        "tiers": {
            "top":    "Homes are sitting longer than most metros — a relatively slow, buyer-friendly market. Workers relocating have time and options. Whether this reflects healthy balance or weak demand depends on the employment picture — investigate before framing.",
            "above":  "Above-average days on market — moderate buyer advantage relative to peers. Mild positive for relocating workers.",
            "median": "Housing velocity near the national norm. Not a differentiating factor. Omit.",
            "below":  "Homes selling faster than most metros — a competitive market for buyers. Relocating workers face real time pressure and competition. Flag as a practical workforce attraction barrier.",
            "bottom": "Among the fastest-moving markets in the dataset. New hires face serious housing competition. Name it explicitly as a relocation challenge and connect to affordability if relevant.",
        },
    },
}


def _tier_key(score: float) -> str:
    if score >= 80: return "top"
    if score >= 60: return "above"
    if score >= 40: return "median"
    if score >= 20: return "below"
    return "bottom"


def _detect_tensions(pct: dict, raw: dict) -> list:
    """Flag interesting metric conflicts worth exploring in the narrative."""
    tensions = []

    unemp_score   = pct.get("101A", 50)
    lfp_score     = pct.get("102A", 50)
    emp_score     = pct.get("107E", 50)
    wage_score    = pct.get("103B", 50)
    col_score     = pct.get("104C", 50)
    hours_score   = pct.get("106D", 50)
    permits_score = pct.get("200B", 50)
    dom_score     = pct.get("204A", 50)

    # Tight unemployment + shrinking labor force = pool is narrowing, not just occupied
    if unemp_score >= 70 and lfp_score <= 35:
        tensions.append(
            "Low unemployment paired with weak labor force participation — the tight headline "
            "rate may mask a shrinking workforce, not just low layoffs. The available pool is genuinely shallow."
        )

    # Job growth + below-trend hours = adding headcount but keeping workloads lean (cautious expansion)
    if emp_score >= 70 and hours_score <= 35:
        tensions.append(
            "Strong job growth alongside below-trend hours — employers are adding workers but "
            "keeping individual workloads lean. May signal caution about the durability of this expansion."
        )

    # Employers pulling back hours before cutting jobs (early contraction warning)
    if emp_score <= 30 and hours_score >= 70:
        tensions.append(
            "Weak employment growth but above-trend hours — employers may be extracting more from "
            "existing staff before eventually cutting headcount. Watch for a coming employment downturn."
        )

    # High wages + expensive CoL = nominal gains, muted real gains
    if wage_score >= 70 and col_score <= 35:
        tensions.append(
            "Strong wage growth paired with high cost of living — workers are gaining in nominal "
            "terms but real purchasing power gains may be limited. The income advantage is partly illusory."
        )

    # Affordable city + hot housing market = affordability edge may be eroding
    if col_score >= 70 and dom_score <= 35:
        tensions.append(
            "Affordable cost of living but a fast-moving housing market — the affordability "
            "advantage may be eroding as demand outpaces housing supply."
        )

    # Strong job growth + collapsing permits = housing supply squeeze building
    if emp_score >= 70 and permits_score <= 35:
        tensions.append(
            "Strong employment growth with sharply declining building permits — a housing supply "
            "squeeze is likely building. Affordability and workforce attraction could deteriorate."
        )

    # High wages + weak employment = wage growth driven by mix shift or desperation, not broad strength
    if wage_score >= 70 and emp_score <= 30:
        tensions.append(
            "Wage growth is strong even as total employment stagnates or declines — wages may "
            "be rising due to mix shift toward higher-paying survivors, not broad labor market health."
        )

    return tensions


def build_writing_guide(record: dict, city_name: str) -> str:
    """
    Generate a per-city writing guide that explains each metric in the context
    of this city's actual data. Primes the LLM with interpretive scaffolding
    before it writes a single word of analysis.

    Structure per metric:
      - Label and what it measures
      - Actual value + percentile tier
      - Tier-specific 'what to write' instruction
      - Any important inversion notes

    Closes with a tensions section flagging interesting metric conflicts.
    """
    pct = record.get("percentile_scores", {}) or {}
    raw = record.get("raw_values", {}) or {}

    metric_order = [
        ("101A", "101A_unemployment",           None,  "%"),
        ("107E", "107E_employment_growth_yoy",  "+",   "% YoY"),
        ("102A", "102A_lfp",                    None,  "%"),
        ("103B", "103B_earnings_yoy",           "+",   "% YoY"),
        ("106D", "106D_wh_trend_deviation_pct", "+",   "% vs trend"),
        ("104C", "104C_col",                    None,  ""),
        ("105C", "105C_owr",                    None,  " (composite)"),
        ("200B", "200B_permits_yoy",            "+",   "% YoY"),
        ("204A", None,                          None,  None),  # special handling
    ]

    lines = [
        f"WRITING GUIDE — {city_name.upper()}",
        "=" * 60,
        "Read this before writing. It tells you what each metric means and, given",
        "this city's actual data, what angle to take. Focus your narrative on metrics",
        "in the TOP or BOTTOM tier. Metrics labeled 'median' should be omitted.",
        "",
    ]

    for metric_key, raw_key, sign, suffix in metric_order:
        guide = METRIC_GUIDE.get(metric_key)
        if not guide:
            continue

        score = pct.get(metric_key, 50)
        tk    = _tier_key(score)
        insight = guide["tiers"][tk]

        # Format raw value
        if metric_key == "204A":
            dom_yoy = raw.get("204A_dom_yoy_pct")
            dom_lvl = raw.get("204A_dom_level_days")
            val_str = (
                f"{dom_yoy:+.1f}% YoY ({int(dom_lvl)} days avg)"
                if dom_yoy is not None else "N/A"
            )
        else:
            v = raw.get(raw_key)
            if v is None:
                val_str = "N/A"
            elif sign == "+":
                val_str = f"{v:+.2f}{suffix}"
            else:
                val_str = f"{v:.2f}{suffix}"

        lines.append(f"[{metric_key}] {guide['label']}")
        lines.append(f"  Value: {val_str}  |  Score: {round(score)}th pct ({tier_label(score)})")
        lines.append(f"  Measures: {guide['measures']}")
        if "note" in guide:
            lines.append(f"  NOTE: {guide['note']}")
        lines.append(f"  What to write: {insight}")

        # For Days on Market, inject a rich interpretive framework so the LLM
        # understands both the direction signal and the correct contextual reading
        if metric_key == "204A":
            dom_yoy     = raw.get("204A_dom_yoy_pct")
            dom_lvl     = raw.get("204A_dom_level_days")
            emp_score   = pct.get("107E", 50)
            permits_score = pct.get("200B", 50)
            dom_score_val = pct.get("204A", 50)

            if dom_yoy is not None:
                # Direction statement
                if dom_yoy > 0:
                    direction_line = (
                        f"  YoY DIRECTION: +{dom_yoy:.1f}% → homes are taking MORE DAYS to sell "
                        f"than last year. The market is SLOWING relative to its own recent pace."
                    )
                    framework_text = guide.get("going_up_framework", "")
                else:
                    direction_line = (
                        f"  YoY DIRECTION: {dom_yoy:.1f}% → homes are selling in FEWER DAYS "
                        f"than last year. The market is SPEEDING UP relative to its own recent pace."
                    )
                    framework_text = guide.get("going_down_framework", "")

                # Absolute level characterization
                if dom_lvl is not None:
                    if dom_lvl <= 35:
                        level_char = "extremely fast (very hot market)"
                    elif dom_lvl <= 55:
                        level_char = "fast (competitive market)"
                    elif dom_lvl <= 75:
                        level_char = "moderate (balanced market)"
                    elif dom_lvl <= 100:
                        level_char = "slow (buyer-friendly market)"
                    else:
                        level_char = "very slow (strong buyer's market)"
                    level_line = (
                        f"  ABSOLUTE LEVEL: {int(dom_lvl)} days on market — {level_char}. "
                        f"Rank vs peers: {round(dom_score_val)}th pct ({tier_label(dom_score_val)})."
                    )
                else:
                    level_line = ""

                # Scenario lean based on employment and permits
                if dom_yoy > 0:
                    if emp_score >= 60 and permits_score >= 60:
                        scenario_lean = (
                            "SCENARIO LEAN → HEALTHY NORMALIZATION (Scenario A): "
                            f"Employment growth is above average ({round(emp_score)}th pct) and "
                            f"permits are strong ({round(permits_score)}th pct). "
                            "Frame the slowing market as a stabilizing force, not a warning sign."
                        )
                    elif emp_score < 40 or permits_score < 40:
                        scenario_lean = (
                            "SCENARIO LEAN → DEMAND EROSION (Scenario B): "
                            f"Employment growth is {'weak' if emp_score < 40 else 'average'} "
                            f"({round(emp_score)}th pct) and permits are "
                            f"{'declining' if permits_score < 40 else 'average'} ({round(permits_score)}th pct). "
                            "Rising DOM here looks more like softening demand. Flag as a risk."
                        )
                    else:
                        scenario_lean = (
                            "SCENARIO LEAN → MIXED SIGNALS: Employment and permits give no clear "
                            "verdict. Acknowledge the slowing market and note the ambiguity — "
                            "is this normalization or softening? Let the reader judge."
                        )
                else:
                    if emp_score >= 60 and permits_score >= 40:
                        scenario_lean = (
                            "SCENARIO LEAN → GENUINE DEMAND SURGE (Scenario A): "
                            f"Employment growth is above average ({round(emp_score)}th pct). "
                            "Faster sales reflect real demand. Flag the relocation challenge for workers."
                        )
                    elif permits_score < 35:
                        scenario_lean = (
                            "SCENARIO LEAN → SUPPLY CONTRACTION (Scenario B): "
                            f"Building permits are weak ({round(permits_score)}th pct) while homes "
                            "are selling faster. This may be a thin-supply illusion, not genuine "
                            "demand strength. Be cautious about framing this as a boom."
                        )
                    else:
                        scenario_lean = (
                            "SCENARIO LEAN → MIXED SIGNALS: Faster sales but unclear whether "
                            "demand-driven or supply-driven. Describe the market velocity and "
                            "flag the relocation implication without overinterpreting the cause."
                        )

                lines.append(direction_line)
                if level_line:
                    lines.append(level_line)
                lines.append(f"  {scenario_lean}")
                lines.append("")
                lines.append("  INTERPRETIVE FRAMEWORK:")
                for fw_line in framework_text.split("\n"):
                    lines.append(f"  {fw_line}")
                lines.append("")
                lines.append("  POINTS OF INTEREST — consider these before writing:")
                for poi in guide.get("points_of_interest", []):
                    lines.append(f"    • {poi}")

        lines.append("")

    tensions = _detect_tensions(pct, raw)
    if tensions:
        lines.append("KEY TENSIONS TO EXPLORE IN YOUR NARRATIVE:")
        for t in tensions:
            lines.append(f"  • {t}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


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
    Build the analysis prompt. Leads with a per-city writing guide that defines
    each metric and tells the model what interpretive angle to take given the
    actual data — before any prose is written. Follows with the raw briefing
    sheet and structural writing instructions.
    """
    writing_guide = build_writing_guide(record, city_name)
    briefing      = build_briefing_sheet(record, city_name)

    prompt = f"""You are writing an economic city brief for a senior executive making a business location decision.

{writing_guide}

RAW DATA BRIEFING SHEET:
{briefing}

Now write a 3-paragraph analytical brief. Your job is to synthesize and interpret — not to list metrics.
Use the writing guide above to understand what each metric means and which angles are worth pursuing.

PARAGRAPH 1 — The dominant story. Lead with the overall grade and what it reflects. What 2-3 metrics combine to define this city's economic character right now? Weave them into a coherent narrative about what kind of market this is.

PARAGRAPH 2 — Nuance and tension. Where do the metrics tell conflicting stories? If the writing guide flagged any key tensions, this is where to explore them. Highlight anything top-tier or bottom-tier that deserves specific attention from a decision-maker.

PARAGRAPH 3 — Bottom line. Two sentences maximum. What does this city offer a business, and what is the primary risk or caveat? Be direct and opinionated.

Rules:
- DO NOT enumerate metrics one by one — synthesize across them
- Only highlight metrics that are notably strong or weak (top/bottom tier) — skip median metrics entirely
- Anchor the narrative in specific numbers (e.g., "3.0% unemployment", "payrolls up 2.4%") — not just tier labels
- Inversion reminder: high cost-of-living score = MORE AFFORDABLE; high days-on-market score = SLOWER (cooler) housing market
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

    # Generate PDF report now that all city narratives are fresh
    print("\n" + "=" * 60)
    print("  Generating PDF report...")
    print("=" * 60)
    import generate_pdf_report
    generate_pdf_report.main()


if __name__ == "__main__":
    main()
