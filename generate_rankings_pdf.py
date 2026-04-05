"""
generate_rankings_pdf.py
Generates a standalone single-page rankings PDF of all 50 U.S. metros.
Landscape letter format. Uses full readable column headers (no abbreviations).

Output: pdf_output/city_rankings_YYYY-MM-DD.pdf
        pdf_output/city_rankings_latest.pdf
"""

import sys
import json
import re
import shutil
from pathlib import Path
from datetime import datetime

# Ensure UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

# ─── PATHS ────────────────────────────────────────────────────────────────────
SCRIPT_DIR    = Path(__file__).parent
METRICS_FILE  = SCRIPT_DIR / 'calculated_metrics_reconciled.json'
TEMPLATES_DIR = SCRIPT_DIR / 'templates'
OUTPUT_DIR    = SCRIPT_DIR / 'pdf_output'
OUTPUT_DIR.mkdir(exist_ok=True)

# ─── GRADE COLORS ─────────────────────────────────────────────────────────────
GRADE_COLORS = {
    'A+': '#059669', 'A':  '#0D9488', 'A-': '#0284C7',
    'B+': '#2563EB', 'B':  '#4F46E5', 'B-': '#64748B',
    'C+': '#D97706', 'C':  '#EA580C', 'C-': '#DC2626',
    'D':  '#7C3AED',
}

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def fmt_pct(val, decimals=1, plus=True) -> str:
    if val is None:
        return 'N/A'
    sign = '+' if (plus and val > 0) else ''
    return f'{sign}{val:.{decimals}f}%'


def prepare_city(metro: dict, rank: int) -> dict:
    raw   = metro['raw_values']
    pctl  = metro['percentile_scores']
    grade = metro['grade']['letter']

    emp_yoy   = raw.get('107E_employment_growth_yoy')
    dom_level = raw.get('204A_dom_level_days')

    return {
        'primary_city': metro['primary_city'],
        'metro_name':   metro['metro_name'],
        'rank':         rank,
        'grade':        grade,
        'grade_color':  GRADE_COLORS.get(grade, '#64748B'),
        'score':        metro['weighted_percentile'],
        'unemp_fmt':    fmt_pct(raw.get('101A_unemployment'), plus=False),
        'earnings_fmt': fmt_pct(raw.get('103B_earnings_yoy')),
        'emp_fmt':      fmt_pct(emp_yoy),
        'lfp_fmt':      fmt_pct(raw.get('102A_lfp'), plus=False),
        'dom_fmt':      f'{int(dom_level)} days' if dom_level is not None else 'N/A',
    }


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print('=' * 60)
    print('  U.S. METRO ECONOMIC HEALTH — RANKINGS PDF GENERATOR')
    print('=' * 60)

    print('\n→ Loading metrics data...')
    with open(METRICS_FILE, encoding='utf-8') as f:
        data = json.load(f)

    metros = sorted(data['metros'], key=lambda x: x['weighted_percentile'], reverse=True)
    print(f'  {len(metros)} metros loaded')

    calc_date = datetime.fromisoformat(data['calculation_timestamp']).strftime('%B %Y')

    print('→ Preparing city data...')
    all_cities = [prepare_city(m, i + 1) for i, m in enumerate(metros)]

    print('→ Rendering HTML template...')
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template('rankings_only.html')
    html_content = template.render(
        calculation_date=calc_date,
        all_cities=all_cities,
    )

    html_path = OUTPUT_DIR / 'rankings_debug.html'
    html_path.write_text(html_content, encoding='utf-8')
    print(f'  Debug HTML saved: {html_path.name}')

    date_str = datetime.now().strftime('%Y-%m-%d')
    pdf_path = OUTPUT_DIR / f'city_rankings_{date_str}.pdf'

    print('→ Generating PDF via Chromium...')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.as_uri(), wait_until='networkidle')
        page.pdf(
            path=str(pdf_path),
            format='Letter',
            landscape=True,
            print_background=True,
            margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'},
        )
        browser.close()

    latest_path = OUTPUT_DIR / 'city_rankings_latest.pdf'
    shutil.copy2(pdf_path, latest_path)

    print(f'\n✓ PDF saved:    {pdf_path.name}')
    print(f'✓ Latest copy:  {latest_path.name}')
    print('\nDone.')


if __name__ == '__main__':
    main()
