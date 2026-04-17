"""
generate_pdf_report.py
Generates a world-class PDF report of U.S. Metro Economic Health scores.
Uses Jinja2 for HTML templating and Playwright (headless Chromium) for PDF rendering.

WeasyPrint requires GTK runtime on Windows which is complex to install.
Playwright uses full Chromium — identical CSS support, better output quality.

Output: pdf_output/city_economic_report_YYYY-MM-DD.pdf
"""

import sys
import json
import re
from pathlib import Path
from datetime import datetime

# Ensure UTF-8 output on Windows (avoids charmap errors with → ✓ — characters)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

# ─── PATHS ────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent
METRICS_FILE = SCRIPT_DIR / 'calculated_metrics_reconciled.json'
REPORTS_DIR  = SCRIPT_DIR / 'city_reports_ft_cautious'
TEMPLATES_DIR = SCRIPT_DIR / 'templates'
OUTPUT_DIR   = SCRIPT_DIR / 'pdf_output'
OUTPUT_DIR.mkdir(exist_ok=True)

# ─── GRADE COLORS ─────────────────────────────────────────────────────────────
GRADE_COLORS = {
    'A+': '#059669', 'A':  '#0D9488', 'A-': '#0284C7',
    'B+': '#2563EB', 'B':  '#4F46E5', 'B-': '#64748B',
    'C+': '#D97706', 'C':  '#EA580C', 'C-': '#DC2626',
    'D':  '#7C3AED',
}

GRADE_DESCRIPTIONS = {
    'A+': 'Excellent', 'A': 'Very Good', 'A-': 'Good',
    'B+': 'Above Average', 'B': 'Average', 'B-': 'Below Average',
    'C+': 'Poor', 'C': 'Very Poor', 'C-': 'Critical', 'D': 'Emergency',
}

# Grade distribution groupings for cover page
GRADE_TIERS = [
    ('A+ / A / A-', ['A+', 'A', 'A-'], '#0284C7'),
    ('B+ / B / B-', ['B+', 'B', 'B-'], '#4F46E5'),
    ('C+ / C / C-', ['C+', 'C', 'C-'], '#EA580C'),
    ('D',           ['D'],             '#7C3AED'),
]

# ─── METRIC CONFIG ─────────────────────────────────────────────────────────────
METRICS = [
    ('107E', 'Labor Demand',     '25%'),
    ('101A', 'Unemployment',     '20%'),
    ('103B', 'Wage Growth',      '15%'),
    ('104C', 'Cost of Living',   '12%'),
    ('102A', 'Labor Force Part.','10%'),
    ('200B', 'Bldg. Permits',    '10%'),
    ('204A', 'Housing Access',   ' 5%'),
    ('105C', 'Office Economy',   ' 3%'),
]

# ─── SCENARIO CONFIG ───────────────────────────────────────────────────────────
SCENARIO_COLORS = {
    'STRONG':  '#059669',
    'GROWING': '#0284C7',
    'SQUEEZE': '#D97706',
    'WEAK':    '#DC2626',
    'N/A':     '#9CA3AF',
}

SCENARIO_DESCS = {
    'STRONG':  'Employment and hours both above trend — genuine demand confirmation.',
    'GROWING': 'Payrolls expanding; hours softening — healthy growth with some moderation.',
    'SQUEEZE': 'Payrolls contracting while hours rise — survivor squeeze signal.',
    'WEAK':    'Both employment and hours declining — broad contraction.',
    'N/A':     'Insufficient data to determine labor market scenario.',
}

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def bar_color(score: float) -> str:
    if score >= 60:
        return '#059669'
    elif score >= 40:
        return '#D97706'
    else:
        return '#EF4444'


def fmt_pct(val, decimals=1, plus=True) -> str:
    if val is None:
        return 'N/A'
    sign = '+' if (plus and val > 0) else ''
    return f'{sign}{val:.{decimals}f}%'


def fmt_val(val, decimals=2) -> str:
    if val is None:
        return 'N/A'
    return f'{val:.{decimals}f}'


def get_scenario(emp_yoy, wh_dev) -> str:
    if emp_yoy is None or wh_dev is None:
        return 'N/A'
    if emp_yoy >= 0 and wh_dev >= 0:
        return 'STRONG'
    elif emp_yoy >= 0 and wh_dev < 0:
        return 'GROWING'
    elif emp_yoy < 0 and wh_dev >= 0:
        return 'SQUEEZE'
    else:
        return 'WEAK'


def city_to_slug(primary_city: str) -> str:
    slug = primary_city.lower()
    slug = slug.replace(' ', '-')
    slug = re.sub(r'[^a-z0-9\-]', '', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug


def load_narrative(primary_city: str) -> str:
    """
    Load narrative text from city_reports_ft_cautious/*.md.
    Extracts the body after the first '---' separator.

    Report format:
      # Metro Name
      **Grade: ... | ...th percentile | Month Year**
      ---
      [Opening paragraph]
      **Metric Name**
      [2-3 sentences]
      ... (8 metric sections)
      [Closing paragraph]

    Metric section headers are rendered as <h4> elements.
    Plain paragraphs are wrapped in <p>.
    """
    slug = city_to_slug(primary_city)
    path = REPORTS_DIR / f'{slug}.md'
    if not path.exists():
        return '<p>Analysis not available.</p>'

    text  = path.read_text(encoding='utf-8')
    parts = re.split(r'\n---+\n', text, maxsplit=1)
    body  = parts[1].strip() if len(parts) > 1 else text.strip()

    paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]

    html_parts = []
    for p in paragraphs:
        # Paragraph starting with **Metric Name** — render as a section header
        header_match = re.match(r'^\*\*(.+?)\*\*\s*([\s\S]*)', p)
        if header_match:
            heading   = header_match.group(1)
            body_text = header_match.group(2).strip()
            html_parts.append(f'<h4 class="narrative-heading">{heading}</h4>')
            if body_text:
                html_parts.append(f'<p>{body_text}</p>')
        else:
            html_parts.append(f'<p>{p}</p>')

    return '\n'.join(html_parts) if html_parts else '<p>Analysis not available.</p>'


# ─── DATA PREPARATION ─────────────────────────────────────────────────────────

def prepare_city(metro: dict, rank_display: int) -> dict:
    raw   = metro['raw_values']
    pctl  = metro['percentile_scores']
    grade = metro['grade']['letter']

    emp_yoy = raw.get('107E_employment_growth_yoy')
    wh_dev  = raw.get('107E_wh_trend_deviation_pct')
    scenario = get_scenario(emp_yoy, wh_dev)

    # Metric bars
    metrics = []
    for code, label, weight in METRICS:
        score = int(round(pctl.get(code, 50)))
        metrics.append({
            'label':     label,
            'weight':    weight,
            'score':     score,
            'bar_color': bar_color(score),
        })

    # Key stats
    dom_level = raw.get('204A_dom_level_days')
    dom_yoy   = raw.get('204A_dom_yoy_pct')
    dom_str   = f'{int(dom_level)} days' if dom_level is not None else 'N/A'
    dom_yoy_str = fmt_pct(dom_yoy) if dom_yoy is not None else 'N/A'

    stats = {
        'unemp':      fmt_pct(raw.get('101A_unemployment'), plus=False),
        'earnings':   fmt_pct(raw.get('103B_earnings_yoy')),
        'emp_growth': fmt_pct(emp_yoy),
        'lfp':        fmt_pct(raw.get('102A_lfp'), plus=False),
        'permits':    fmt_pct(raw.get('200B_permits_yoy')),
        'dom':        dom_str,
        'dom_yoy':    dom_yoy_str,
    }

    return {
        'primary_city':    metro['primary_city'],
        'metro_name':      metro['metro_name'],
        'rank_display':    rank_display,
        'grade':           grade,
        'grade_color':     GRADE_COLORS.get(grade, '#64748B'),
        'grade_description': GRADE_DESCRIPTIONS.get(grade, ''),
        'score':           metro['weighted_percentile'],
        'metrics':         metrics,
        'stats':           stats,
        'scenario':        scenario,
        'scenario_color':  SCENARIO_COLORS[scenario],
        'scenario_desc':   SCENARIO_DESCS[scenario],
        'narrative':       load_narrative(metro['primary_city']),
        # Rankings table fields
        'unemp_fmt':       fmt_pct(raw.get('101A_unemployment'), plus=False),
        'earnings_fmt':    fmt_pct(raw.get('103B_earnings_yoy')),
        'emp_fmt':         fmt_pct(emp_yoy),
        'lfp_fmt':         fmt_pct(raw.get('102A_lfp'), plus=False),
        'dom_fmt':         dom_str,
    }


def build_grade_distribution(metros: list) -> list:
    grade_counts = {}
    for m in metros:
        g = m['grade']['letter']
        grade_counts[g] = grade_counts.get(g, 0) + 1

    result = []
    for tier_label, grades, color in GRADE_TIERS:
        count = sum(grade_counts.get(g, 0) for g in grades)
        result.append({'grade': tier_label, 'description': '', 'count': count, 'color': color})
    return result


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print('=' * 60)
    print('  U.S. METRO ECONOMIC HEALTH — PDF REPORT GENERATOR')
    print('=' * 60)

    # Load metrics
    print('\n→ Loading metrics data...')
    with open(METRICS_FILE, encoding='utf-8') as f:
        data = json.load(f)

    metros = sorted(data['metros'], key=lambda x: x['weighted_percentile'], reverse=True)
    print(f'  {len(metros)} metros loaded')

    calc_date = datetime.fromisoformat(data['calculation_timestamp']).strftime('%B %Y')

    # Prepare city data
    print('→ Preparing city data...')
    all_cities = [prepare_city(m, i + 1) for i, m in enumerate(metros)]

    # Cover page data
    top_cities    = all_cities[:7]
    bottom_cities = list(reversed(all_cities[-7:]))
    grade_dist    = build_grade_distribution(metros)

    template_data = {
        'calculation_date':   calc_date,
        'all_cities':         all_cities,
        'top_cities':         top_cities,
        'bottom_cities':      bottom_cities,
        'grade_distribution': grade_dist,
    }

    # Render HTML
    print('→ Rendering HTML template...')
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template('report.html')
    html_content = template.render(**template_data)

    # Save HTML for debugging
    html_path = OUTPUT_DIR / 'report_debug.html'
    html_path.write_text(html_content, encoding='utf-8')
    print(f'  Debug HTML saved: {html_path.name}')

    # Generate PDF via Playwright (headless Chromium)
    date_str = datetime.now().strftime('%Y-%m-%d')
    pdf_path = OUTPUT_DIR / f'city_economic_report_{date_str}.pdf'
    html_file_uri = html_path.as_uri()

    print(f'→ Generating PDF via Chromium (this takes ~30-60 seconds)...')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_file_uri, wait_until='networkidle')
        page.pdf(
            path=str(pdf_path),
            format='Letter',
            print_background=True,
            margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'},
        )
        browser.close()

    # Also write a fixed-name "latest" copy for CI tracking
    latest_path = OUTPUT_DIR / 'city_economic_report_latest.pdf'
    import shutil
    shutil.copy2(pdf_path, latest_path)

    print(f'\n✓ PDF saved:    {pdf_path.name}')
    print(f'✓ Latest copy:  {latest_path.name}')
    print(f'  Pages: cover + rankings + {len(metros)} city pages = ~{len(metros) + 2} total')

    # Generate website after PDF
    print('\n→ Generating website...')
    import subprocess
    subprocess.run([sys.executable, str(SCRIPT_DIR / 'generate_site.py')], check=True)

    print('\nDone.')


if __name__ == '__main__':
    main()
