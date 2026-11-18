"""
city_page.py
Builds the editorial-style city page (one section per metric).

generate_site.py calls render_city_main() for each metro and writes the
result inside the shared page shell. The page's styles live in CITY_CSS,
which generate_site.py writes to docs/assets/city.css.

Layout, top to bottom:
  1. Header      — rank, city name, overall grade
  2. Summary     — the brief's opening paragraph + an "at a glance" list
  3. 8 sections  — one per metric: name, plain explanation, headline number,
                   score bar, and the brief's two sentences for that metric
  4. Bottom line — the brief's closing paragraph
"""

import html
import re
from pathlib import Path

# Shown once near the top of every city page.
SCORE_SCALE_NOTE = ('Scores run 0&ndash;100. A score of 80 means this city '
                    'beats 80% of the 50 metros; 50 is the middle.')

# Metric order matches the scorecard and the brief headings.
# (code, name, weight, plain one-line explanation)
CITY_METRICS = [
    ('107E', 'Labor Demand',       '25%',
     'Whether employers are adding jobs, based on job growth over the past year and changes in weekly work hours.'),
    ('101A', 'Unemployment',       '20%',
     "The share of people who want a job but can't find one; lower is better."),
    ('103B', 'Wage Growth',        '15%',
     'How much average hourly pay rose over the past year.'),
    ('104C', 'Cost of Living',     '12%',
     "How many hours a local worker needs to work to pay for one square foot of a home, and whether that's improving."),
    ('102A', 'Labor Force Growth', '10%',
     'Whether the number of people working or looking for work is growing.'),
    ('200B', 'Building Permits',   '10%',
     'How many new homes builders got approval for, compared with a year ago.'),
    ('204A', 'Days on Market',     '5%',
     'How long a typical home for sale takes to find a buyer; about 35 to 80 days is healthiest.'),
    ('105C', 'Office Economy',     '3%',
     'The share of jobs in office-based fields like tech, finance and professional services.'),
]

METRIC_EXPLAINERS = {name: text for _, name, _, text in CITY_METRICS}

LABOR_SIGNAL_TEXT = {
    'STRONG':  'Jobs and weekly hours are both rising.',
    'GROWING': 'Jobs are growing while weekly hours ease a little.',
    'SQUEEZE': 'Jobs are being cut while remaining workers put in more hours.',
    'WEAK':    'Jobs and weekly hours are both falling.',
}


# ─── SMALL HELPERS ────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    return html.escape(text, quote=False)


def _signed(val, decimals=1, suffix='%'):
    if val is None:
        return None
    return f'{val:+.{decimals}f}{suffix}'.replace('-', '&minus;')


def score_band(score: int):
    """(css class, label) for a 0-100 score."""
    if score >= 60:
        return 'strength', 'Strength'
    if score <= 40:
        return 'weakness', 'Weakness'
    return 'average', 'About average'


def slugify(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


# ─── BRIEF PARSING ────────────────────────────────────────────────────────────

def parse_brief(path: Path) -> dict:
    """
    Split a city brief (.md) into its parts:
      {'opening': str, 'closing': str, 'sections': {metric name: str}}
    Missing parts come back as empty strings.
    """
    result = {'opening': '', 'closing': '', 'sections': {}}
    if not path.exists():
        return result

    text = path.read_text(encoding='utf-8')
    parts = re.split(r'\n---+\n', text, maxsplit=1)
    body = parts[1] if len(parts) > 1 else parts[0]
    paragraphs = [p.strip() for p in body.strip().split('\n\n') if p.strip()]
    paragraphs = [p for p in paragraphs if not p.startswith('#')]

    seen_section = False
    loose = []  # plain paragraphs, in order
    for p in paragraphs:
        m = re.match(r'^\*\*(.+?)\*\*\s*([\s\S]*)', p)
        if m and m.group(1) in METRIC_EXPLAINERS:
            seen_section = True
            result['sections'][m.group(1)] = m.group(2).strip()
        else:
            loose.append((seen_section, p))

    before = [p for after, p in loose if not after]
    after = [p for after, p in loose if after]
    result['opening'] = ' '.join(before)
    result['closing'] = ' '.join(after)
    return result


# ─── HEADLINE NUMBERS ─────────────────────────────────────────────────────────

def headline_numbers(raw: dict, proc: dict) -> dict:
    """
    One big number per metric, in everyday terms:
      {metric name: (big value, what it is, optional small detail)}
    """
    def latest(key):
        return (proc.get(key) or {}).get('latest_value')

    def yoy(key):
        return ((proc.get(key) or {}).get('yoy_change') or {}).get('pct_change')

    out = {}

    emp = raw.get('107E_employment_growth_yoy')
    hrs = raw.get('107E_wh_trend_deviation_pct')
    out['Labor Demand'] = (
        _signed(emp) or 'N/A', 'change in jobs over the past year',
        f'Weekly hours {_signed(hrs)} vs. their usual level' if hrs is not None else '')

    unemp = raw.get('101A_unemployment')
    unemp_chg = raw.get('101A_unemp_yoy_pp')
    detail = ''
    if unemp_chg is not None:
        if abs(unemp_chg) < 0.05:
            detail = 'Unchanged from a year ago'
        else:
            word = 'Down' if unemp_chg < 0 else 'Up'
            detail = f'{word} {abs(unemp_chg):.1f} points from a year ago'
    out['Unemployment'] = (f'{unemp:.1f}%' if unemp is not None else 'N/A',
                           'unemployment rate', detail)

    pay = latest('hourly_earnings')
    out['Wage Growth'] = (
        _signed(raw.get('103B_earnings_yoy')) or 'N/A', 'change in hourly pay over the past year',
        f'Average pay is ${pay:.2f} an hour' if pay else '')

    psf = latest('price_per_sqft')
    if psf and pay:
        psf_chg = yoy('price_per_sqft')
        chg = f' ({_signed(psf_chg)} in a year)' if psf_chg is not None else ''
        out['Cost of Living'] = (
            f'{psf / pay:.1f} hrs', 'of pay to buy one square foot of home',
            f'${psf:,.0f} per sq. ft.{chg} &middot; ${pay:.2f} an hour')
    else:
        out['Cost of Living'] = ('N/A', 'of pay to buy one square foot of home', '')

    out['Labor Force Growth'] = (
        _signed(raw.get('102A_clf_yoy')) or 'N/A',
        'change in people working or looking for work', '')

    out['Building Permits'] = (
        _signed(raw.get('200B_permits_yoy')) or 'N/A',
        'change in new home approvals vs. a year ago', '')

    days = raw.get('204A_dom_level_days')
    days_chg = raw.get('204A_dom_yoy_pct')
    out['Days on Market'] = (
        f'{int(days)} days' if days is not None else 'N/A', 'for a typical home to sell',
        f'{_signed(days_chg)} vs. a year ago' if days_chg is not None else '')

    owr = latest('office_worker_ratio')
    out['Office Economy'] = (
        f'{owr:.0f} in 100' if owr else 'N/A', 'residents work in office-based jobs', '')

    return out


# ─── PAGE PIECES ──────────────────────────────────────────────────────────────

def _score_bar(score: int) -> str:
    band, label = score_band(score)
    return f'''\
<div class="cp-score">
  <div class="cp-bar" role="img" aria-label="Score {score} out of 100, {label.lower()}">
    <div class="cp-bar-mid"></div>
    <div class="cp-bar-fill cp-{band}" style="width:{max(score, 2)}%"></div>
  </div>
  <div class="cp-score-label"><strong class="cp-{band}-text">{score}</strong>/100 &middot; {label}</div>
</div>'''


def _glance(city: dict) -> str:
    rows = ''
    for code, name, _, _ in CITY_METRICS:
        score = city['scores'][code]
        band, _ = score_band(score)
        rows += f'''\
<a class="cp-glance-row" href="#{slugify(name)}">
  <span class="cp-glance-name">{name}</span>
  <span class="cp-glance-bar"><span class="cp-bar-fill cp-{band}" style="width:{max(score, 2)}%"></span></span>
  <span class="cp-glance-score cp-{band}-text">{score}</span>
</a>
'''
    return rows


def _metric_section(code, name, weight, explainer, city, brief, numbers) -> str:
    score = city['scores'][code]
    big, what, detail = numbers.get(name, ('N/A', '', ''))
    text = brief['sections'].get(name, '')
    signal = ''
    if name == 'Labor Demand' and city['scenario'] in LABOR_SIGNAL_TEXT:
        signal = (f'<p class="cp-signal"><span class="cp-signal-tag">{city["scenario"].title()}</span> '
                  f'{LABOR_SIGNAL_TEXT[city["scenario"]]}</p>')
    detail_html = f'<div class="cp-num-detail">{detail}</div>' if detail else ''
    text_html = f'<p class="cp-text">{_esc(text)}</p>' if text else ''
    return f'''\
<section class="cp-metric" id="{slugify(name)}">
  <div class="cp-metric-head">
    <h2>{name}</h2>
    <span class="cp-weight">{weight} of grade</span>
  </div>
  <p class="cp-explainer">{explainer}</p>
  <div class="cp-metric-body">
    <div class="cp-num">
      <div class="cp-num-big">{big}</div>
      <div class="cp-num-what">{what}</div>
      {detail_html}
    </div>
    {_score_bar(score)}
  </div>
  {signal}
  {text_html}
</section>
'''


def render_city_main(city: dict, total: int, date: str, brief: dict,
                     numbers: dict, prev_link: str, next_link: str) -> str:
    """Return the <main> contents for one city page."""
    sections = ''.join(
        _metric_section(code, name, weight, expl, city, brief, numbers)
        for code, name, weight, expl in CITY_METRICS
    )
    opening = f'<p class="cp-lead">{_esc(brief["opening"])}</p>' if brief['opening'] else ''
    closing = ''
    if brief['closing']:
        closing = f'''\
<section class="cp-bottom">
  <h2>The bottom line</h2>
  <p>{_esc(brief["closing"])}</p>
</section>'''

    return f'''\
<article class="cp">
  <header class="cp-header">
    <div class="cp-header-text">
      <div class="cp-kicker">Rank {city['rank']} of {total} &middot; {date}</div>
      <h1>{city['primary_city']}</h1>
      <div class="cp-metro">{city['metro_name']} metro area</div>
    </div>
    <div class="cp-grade" style="--grade:{city['grade_color']}">
      <div class="cp-grade-letter">{city['grade']}</div>
      <div class="cp-grade-desc">{city['grade_description']}</div>
      <div class="cp-grade-score">Overall score {city['score']:.1f}/100</div>
    </div>
  </header>

  <div class="cp-summary">
    <div class="cp-summary-text">
      {opening}
    </div>
    <aside class="cp-glance">
      <div class="cp-label">At a glance</div>
      {_glance(city)}
      <p class="cp-scale">{SCORE_SCALE_NOTE}</p>
    </aside>
  </div>

  {sections}
  {closing}

  <nav class="cp-pager">
    <div>{prev_link}</div>
    <div><a href="../rankings.html">All rankings</a></div>
    <div>{next_link}</div>
  </nav>
</article>'''


# ─── STYLES ───────────────────────────────────────────────────────────────────

CITY_CSS = """\
/* City page — editorial layout. Loaded only on city pages. */
/* Colors and fonts come from site.css (site_style.py), loaded first. */

.cp {
  max-width: 760px;
  margin: 0 auto;
  padding: 48px 16px 64px;
  font-family: "Inter", "Segoe UI", -apple-system, sans-serif;
  font-size: 16px;
  line-height: 1.6;
}
.cp h1, .cp h2, .cp-lead, .cp-num-big, .cp-grade-letter {
  font-family: "Source Serif 4", Georgia, "Times New Roman", serif;
}
.cp a { color: var(--cp-accent); }

/* Header */
.cp-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 24px;
  padding-bottom: 24px;
  border-bottom: 3px solid var(--cp-ink);
}
.cp-kicker, .cp-label, .cp-weight {
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--cp-muted);
  font-weight: 600;
}
.cp h1 {
  font-size: clamp(2.4rem, 7vw, 3.6rem);
  line-height: 1.05;
  font-weight: 700;
  margin: 6px 0 4px;
}
.cp-metro { color: var(--cp-muted); }
.cp-grade { text-align: right; flex-shrink: 0; }
.cp-grade-letter {
  font-size: 3.6rem;
  line-height: 1;
  font-weight: 700;
  color: var(--grade);
}
.cp-grade-desc { font-weight: 600; margin-top: 4px; }
.cp-grade-score { font-size: 0.85rem; color: var(--cp-muted); }

/* Summary */
.cp-summary {
  display: grid;
  grid-template-columns: 1fr 260px;
  gap: 40px;
  padding: 32px 0 40px;
  border-bottom: 1px solid var(--cp-rule);
}
.cp-lead { font-size: 1.25rem; line-height: 1.5; }
.cp-glance .cp-label { margin-bottom: 10px; }
.cp-glance-row {
  display: grid;
  grid-template-columns: 1fr 70px 26px;
  align-items: center;
  gap: 10px;
  padding: 5px 0;
  font-size: 0.85rem;
  color: var(--cp-ink) !important;
  text-decoration: none !important;
  border-bottom: 1px solid var(--cp-rule);
}
.cp-glance-row:hover .cp-glance-name { text-decoration: underline; }
.cp-glance-bar { height: 6px; background: var(--cp-track); border-radius: 3px; overflow: hidden; }
.cp-glance-bar .cp-bar-fill { display: block; height: 100%; }
.cp-glance-score { text-align: right; font-weight: 700; font-variant-numeric: tabular-nums; }
.cp-scale { font-size: 0.78rem; color: var(--cp-muted); margin-top: 10px; line-height: 1.45; }

/* Metric sections */
.cp-metric { padding: 36px 0; border-bottom: 1px solid var(--cp-rule); scroll-margin-top: 72px; }
.cp-metric-head { display: flex; justify-content: space-between; align-items: baseline; gap: 16px; }
.cp h2 { font-size: 1.6rem; font-weight: 700; line-height: 1.2; }
.cp-explainer { color: var(--cp-muted); margin: 6px 0 20px; font-size: 0.95rem; }
.cp-metric-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 32px;
  align-items: end;
  margin-bottom: 18px;
}
.cp-num-big { font-size: 2.6rem; font-weight: 700; line-height: 1; font-variant-numeric: tabular-nums; }
.cp-num-what { font-size: 0.9rem; margin-top: 6px; }
.cp-num-detail { font-size: 0.82rem; color: var(--cp-muted); margin-top: 2px; }
.cp-bar { position: relative; height: 10px; background: var(--cp-track); border-radius: 5px; overflow: hidden; }
.cp-bar-fill { height: 100%; border-radius: 5px; }
.cp-bar-mid { position: absolute; left: 50%; top: 0; bottom: 0; width: 2px; background: var(--cp-paper); z-index: 1; }
.cp-score-label { font-size: 0.85rem; color: var(--cp-muted); margin-top: 8px; }
.cp-score-label strong { font-size: 1.1rem; }
.cp-strength { background: var(--cp-strength); }
.cp-average  { background: var(--cp-average); }
.cp-weakness { background: var(--cp-weakness); }
.cp-strength-text { color: var(--cp-strength); }
.cp-average-text  { color: var(--cp-average); }
.cp-weakness-text { color: var(--cp-weakness); }
.cp-signal { font-size: 0.9rem; margin-bottom: 10px; }
.cp-signal-tag {
  display: inline-block;
  font-size: 0.7rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  font-weight: 700;
  border: 1px solid var(--cp-ink);
  padding: 1px 7px;
  margin-right: 6px;
}
.cp-text { max-width: 65ch; }

/* Bottom line + pager */
.cp-bottom { padding: 36px 0; border-bottom: 3px solid var(--cp-ink); }
.cp-bottom p { font-size: 1.1rem; margin-top: 10px; max-width: 65ch; }
.cp-pager {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 12px;
  padding-top: 24px;
  font-size: 0.9rem;
  font-weight: 600;
}
.cp-pager div:nth-child(2) { text-align: center; }
.cp-pager div:last-child { text-align: right; }

/* Phones */
@media (max-width: 640px) {
  .cp { padding-top: 28px; }
  .cp-header { flex-direction: column; align-items: flex-start; }
  .cp-grade { text-align: left; }
  .cp-summary { grid-template-columns: 1fr; gap: 28px; }
  .cp-metric-body { grid-template-columns: 1fr; gap: 16px; }
  .cp-metric-head { flex-direction: column; gap: 2px; }
  .cp-pager { grid-template-columns: 1fr; text-align: center; }
  .cp-pager div:last-child { text-align: center; }
}
"""
