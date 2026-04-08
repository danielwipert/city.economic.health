"""
generate_site.py
Generates the U.S. Metro Economic Health website from calculated_metrics_reconciled.json.
Writes all output to /site/ directory (served by GitHub Pages).

Usage:
    python generate_site.py          — standalone
    Called from generate_pdf_report.py after PDF generation.

Output:
    site/index.html
    site/rankings.html
    site/methodology.html
    site/metros/{slug}.html  (50 files)
    site/assets/style.css
    site/pdfs/city_economic_report_latest.pdf
"""

import sys
import json
import re
import shutil
from pathlib import Path
from datetime import datetime

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

# ─── PATHS ────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent
METRICS_FILE = SCRIPT_DIR / 'calculated_metrics_reconciled.json'
REPORTS_DIR  = SCRIPT_DIR / 'city_reports_ft_cautious'
PDF_DIR      = SCRIPT_DIR / 'pdf_output'
SITE_DIR     = SCRIPT_DIR / 'docs'

# ─── CONSTANTS ────────────────────────────────────────────────────────────────
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

GRADE_TIERS = [
    ('A Tier',  ['A+', 'A', 'A-'], '#0284C7', 'A+ / A / A-'),
    ('B Tier',  ['B+', 'B', 'B-'], '#4F46E5', 'B+ / B / B-'),
    ('C Tier',  ['C+', 'C', 'C-'], '#EA580C', 'C+ / C / C-'),
    ('D',       ['D'],             '#7C3AED', 'D'),
]

METRICS = [
    ('107E', 'Labor Demand',      '25%'),
    ('101A', 'Unemployment',      '20%'),
    ('103B', 'Wage Growth',       '15%'),
    ('104C', 'Cost of Living',    '12%'),
    ('102A', 'Labor Force YoY',  '10%'),
    ('200B', 'Bldg. Permits',     '10%'),
    ('204A', 'Days on Market',    ' 5%'),
    ('105C', 'Office Economy',    ' 3%'),
]

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

# ─── CSS ──────────────────────────────────────────────────────────────────────
CSS = """\
:root {
  --color-primary:    #0D9488;
  --color-primary-dk: #0A7A70;
  --color-bg:         #FFFFFF;
  --color-bg-alt:     #F9FAFB;
  --color-text:       #111827;
  --color-text-muted: #6B7280;
  --color-border:     #E5E7EB;
  --color-green:      #059669;
  --color-amber:      #D97706;
  --color-red:        #DC2626;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: "Segoe UI", Inter, -apple-system, BlinkMacSystemFont, sans-serif;
  color: var(--color-text);
  background: var(--color-bg);
  font-size: 15px;
  line-height: 1.5;
}

a { color: var(--color-primary); text-decoration: none; }
a:hover { text-decoration: underline; color: var(--color-primary-dk); }

/* ── NAV ── */
.site-nav {
  position: sticky;
  top: 0;
  z-index: 100;
  background: #fff;
  border-bottom: 2px solid var(--color-primary);
  height: 56px;
  display: flex;
  align-items: center;
}
.nav-inner {
  max-width: 960px;
  margin: 0 auto;
  padding: 0 20px;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.nav-brand {
  font-weight: 700;
  font-size: 0.95rem;
  letter-spacing: 0.02em;
  color: var(--color-text);
  text-decoration: none;
}
.nav-brand:hover { color: var(--color-primary); text-decoration: none; }
.nav-links { display: flex; gap: 24px; }
.nav-links a { font-size: 0.9rem; font-weight: 500; color: var(--color-text-muted); }
.nav-links a:hover { color: var(--color-primary); text-decoration: none; }

/* ── SITE MAIN ── */
.site-main { min-height: calc(100vh - 56px - 120px); }

.content-wrap {
  max-width: 960px;
  margin: 0 auto;
  padding: 0 20px;
}

/* ── HERO ── */
.hero {
  background: var(--color-primary);
  padding: 60px 20px;
  color: #fff;
}
.hero-inner {
  max-width: 960px;
  margin: 0 auto;
}
.hero-eyebrow {
  font-size: 0.7rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  opacity: 0.8;
  margin-bottom: 10px;
}
.hero-title {
  font-size: 2.4rem;
  font-weight: 800;
  line-height: 1.1;
  margin-bottom: 8px;
}
.hero-subtitle {
  font-size: 1.05rem;
  opacity: 0.9;
  margin-bottom: 6px;
}
.hero-date {
  font-size: 0.85rem;
  opacity: 0.75;
  margin-bottom: 28px;
}
.hero-tagline {
  font-size: 0.95rem;
  opacity: 0.85;
  max-width: 500px;
  margin-bottom: 28px;
  line-height: 1.6;
}
.btn {
  display: inline-block;
  padding: 10px 22px;
  border-radius: 6px;
  font-weight: 600;
  font-size: 0.9rem;
  cursor: pointer;
  transition: opacity 0.15s;
}
.btn:hover { opacity: 0.88; text-decoration: none; }
.btn-white { background: #fff; color: var(--color-primary); }
.btn-teal { background: var(--color-primary); color: #fff; border: 1px solid rgba(255,255,255,0.3); }
.btn-outline { background: transparent; color: #fff; border: 2px solid rgba(255,255,255,0.6); }

/* ── PERFORMERS STRIPS ── */
.strip-section { padding: 40px 0; }
.strip-section + .strip-section { padding-top: 0; }
.strip-label {
  font-size: 0.65rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  font-weight: 700;
  margin-bottom: 14px;
  color: var(--color-text-muted);
}
.city-cards {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.city-card {
  background: var(--color-bg-alt);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 120px;
  flex: 1;
  text-decoration: none;
  color: var(--color-text);
  transition: box-shadow 0.15s;
}
.city-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-decoration: none; color: var(--color-text); }
.card-rank {
  font-size: 0.65rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}
.card-name { font-weight: 700; font-size: 0.9rem; line-height: 1.2; }
.card-bottom { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 2px; }
.card-score { font-size: 0.8rem; color: var(--color-text-muted); }

/* ── GRADE BADGE ── */
.grade-badge {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 4px;
  font-weight: 700;
  font-size: 0.8rem;
  color: #fff;
  white-space: nowrap;
}

/* ── GRADE DISTRIBUTION ── */
.grade-dist {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  padding: 36px 0;
  border-top: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
}
.grade-dist-block {
  flex: 1;
  min-width: 120px;
  text-align: center;
  padding: 20px 12px;
  background: var(--color-bg-alt);
  border-radius: 8px;
  border: 1px solid var(--color-border);
}
.dist-count {
  font-size: 2.5rem;
  font-weight: 800;
  line-height: 1;
  margin-bottom: 4px;
}
.dist-label {
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-muted);
  margin-bottom: 4px;
}
.dist-grades { font-size: 0.75rem; color: var(--color-text-muted); }

/* ── CTA ── */
.cta-section {
  padding: 40px 0;
  text-align: center;
  border-bottom: 1px solid var(--color-border);
}
.cta-section h2 {
  font-size: 1.2rem;
  font-weight: 700;
  margin-bottom: 8px;
}
.cta-section p {
  color: var(--color-text-muted);
  margin-bottom: 20px;
  font-size: 0.9rem;
}

/* ── RANKINGS TABLE ── */
.rankings-page { padding: 40px 0; }
.page-header { margin-bottom: 28px; }
.page-header h1 { font-size: 1.8rem; font-weight: 800; margin-bottom: 6px; }
.page-header p { color: var(--color-text-muted); font-size: 0.9rem; }

.rankings-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}
.rankings-table th {
  text-align: left;
  padding: 10px 12px;
  font-size: 0.65rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-muted);
  border-bottom: 2px solid var(--color-border);
  white-space: nowrap;
}
.rankings-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--color-border);
  vertical-align: middle;
}
.rankings-table tbody tr:hover { background: var(--color-bg-alt); }
.rankings-table tbody tr:hover td { }
.rank-num { color: var(--color-text-muted); font-size: 0.8rem; font-weight: 600; }
.metro-primary { font-weight: 700; }
.metro-secondary { font-size: 0.78rem; color: var(--color-text-muted); display: block; }
.score-val { font-weight: 700; }
.metric-val { color: var(--color-text-muted); }
td a { color: var(--color-text); font-weight: 700; }
td a:hover { color: var(--color-primary); text-decoration: none; }

/* ── CITY HEADER BAND ── */
.city-header {
  color: #fff;
  padding: 36px 20px;
}
.city-header-inner {
  max-width: 960px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
}
.city-header-left { flex: 1; }
.city-header-right {
  text-align: right;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}
.rank-label {
  font-size: 0.65rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  opacity: 0.8;
  margin-bottom: 8px;
}
.city-title { font-size: 2.5rem; font-weight: 700; line-height: 1.1; margin-bottom: 4px; }
.metro-name { font-size: 1rem; opacity: 0.85; }
.grade-letter { font-size: 4rem; font-weight: 800; line-height: 1; }
.grade-desc { font-size: 1rem; font-weight: 600; opacity: 0.9; text-transform: uppercase; letter-spacing: 0.05em; }
.percentile-score { font-size: 1.2rem; font-weight: 700; opacity: 0.9; margin-top: 4px; }
.rank-of { font-size: 0.85rem; opacity: 0.75; }

/* ── CITY BODY ── */
.city-body {
  max-width: 960px;
  margin: 0 auto;
  padding: 36px 20px;
}
.city-columns {
  display: grid;
  grid-template-columns: 55fr 45fr;
  gap: 40px;
  margin-bottom: 36px;
}

/* ── SCORECARD ── */
.section-title {
  font-size: 0.65rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--color-text-muted);
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border);
}
.metric-row {
  display: grid;
  grid-template-columns: 140px 1fr 32px;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.metric-label { }
.metric-name { font-size: 0.82rem; font-weight: 600; display: block; }
.metric-weight { font-size: 0.65rem; color: var(--color-text-muted); display: block; }
.metric-bar-track {
  height: 8px;
  background: var(--color-border);
  border-radius: 4px;
  overflow: hidden;
}
.metric-bar-fill { height: 8px; border-radius: 4px; }
.metric-score { font-size: 0.78rem; font-weight: 700; text-align: right; }

/* ── KEY INDICATORS ── */
.indicators-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.stat-tile {
  background: var(--color-bg-alt);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 14px 16px;
}
.stat-label {
  font-size: 0.62rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--color-text-muted);
  margin-bottom: 6px;
}
.stat-value { font-size: 1.5rem; font-weight: 800; line-height: 1; margin-bottom: 3px; }
.stat-sub { font-size: 0.7rem; color: var(--color-text-muted); }

/* ── SIGNAL ── */
.signal-section { margin-bottom: 28px; }
.signal-badge {
  display: inline-block;
  padding: 4px 14px;
  border-radius: 4px;
  font-weight: 700;
  font-size: 0.85rem;
  letter-spacing: 0.05em;
  color: #fff;
  margin-bottom: 8px;
}
.signal-desc { font-size: 0.88rem; color: var(--color-text-muted); }

/* ── ECONOMIC ANALYSIS ── */
.analysis-section { margin-bottom: 36px; }
.analysis-section p {
  font-size: 0.92rem;
  line-height: 1.7;
  color: var(--color-text);
  margin-bottom: 14px;
}
.analysis-section p:last-child { margin-bottom: 0; }

/* ── CITY NAVIGATION ── */
.city-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 0;
  border-top: 1px solid var(--color-border);
  font-size: 0.88rem;
}
.city-nav a { color: var(--color-primary); font-weight: 600; }
.city-nav-back { color: var(--color-text-muted); font-size: 0.82rem; }

/* ── METHODOLOGY ── */
.methodology-body { padding: 48px 0; }
.methodology-body h1 { font-size: 1.8rem; font-weight: 800; margin-bottom: 8px; }
.methodology-body .subtitle { color: var(--color-text-muted); margin-bottom: 40px; font-size: 0.9rem; }
.methodology-body h2 {
  font-size: 1rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text);
  margin: 36px 0 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-border);
}
.methodology-body p {
  font-size: 0.92rem;
  line-height: 1.7;
  color: var(--color-text);
  margin-bottom: 12px;
}
.methodology-body ul {
  margin: 0 0 16px 20px;
  font-size: 0.92rem;
  line-height: 1.7;
  color: var(--color-text);
}
.methodology-body li { margin-bottom: 6px; }
.meth-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
  margin-bottom: 20px;
}
.meth-table th {
  text-align: left;
  padding: 8px 12px;
  font-size: 0.65rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-text-muted);
  border-bottom: 2px solid var(--color-border);
}
.meth-table td {
  padding: 9px 12px;
  border-bottom: 1px solid var(--color-border);
}
.meth-table tr:last-child td { border-bottom: none; }
.grade-threshold-table { }
.weight-bold { font-weight: 700; }

/* ── FOOTER ── */
.site-footer {
  background: var(--color-bg-alt);
  border-top: 1px solid var(--color-border);
  padding: 24px 20px;
  margin-top: 0;
}
.footer-inner {
  max-width: 960px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.footer-sources { font-size: 0.75rem; color: var(--color-text-muted); line-height: 1.5; }
.footer-note { font-size: 0.72rem; color: var(--color-text-muted); opacity: 0.75; }

/* ── UTILITY ── */
.mt-8  { margin-top: 8px; }
.mt-16 { margin-top: 16px; }
.mt-24 { margin-top: 24px; }
.text-muted { color: var(--color-text-muted); }

/* ── HERO REDESIGN ── */
.hero { padding: 64px 20px; }
.hero-layout {
  max-width: 960px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 48px;
}
.hero-text { flex: 1; min-width: 0; }
.hero-pills {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}
.hero-pill {
  background: rgba(255,255,255,0.18);
  border: 1px solid rgba(255,255,255,0.35);
  color: #fff;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.04em;
}
.hero-buttons { display: flex; gap: 12px; flex-wrap: wrap; }
.hero-featured {
  flex: 0 0 220px;
  background: rgba(255,255,255,0.14);
  border: 1px solid rgba(255,255,255,0.3);
  border-radius: 12px;
  padding: 28px 24px;
  color: #fff;
  text-decoration: none;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  transition: background 0.2s;
}
.hero-featured:hover { background: rgba(255,255,255,0.22); text-decoration: none; color: #fff; }
.hf-eyebrow { font-size: 0.62rem; letter-spacing: 0.12em; text-transform: uppercase; opacity: 0.75; }
.hf-grade { font-size: 3.6rem; font-weight: 800; line-height: 1; margin: 4px 0; }
.hf-city { font-size: 1.15rem; font-weight: 700; }
.hf-metro { font-size: 0.78rem; opacity: 0.75; }
.hf-score { font-size: 0.85rem; opacity: 0.85; margin-top: 4px; }
.hf-signal {
  font-size: 0.65rem;
  letter-spacing: 0.08em;
  font-weight: 700;
  padding: 2px 10px;
  border-radius: 3px;
  color: #fff;
  background: rgba(255,255,255,0.25);
  margin-top: 2px;
}
.hf-label { font-size: 0.68rem; opacity: 0.65; margin-top: 6px; }

/* ── SNAPSHOT BAR ── */
.snapshot-bar {
  background: #fff;
  border-bottom: 1px solid var(--color-border);
  display: flex;
}
.snapshot-stat {
  flex: 1;
  padding: 24px 16px;
  text-align: center;
  border-right: 1px solid var(--color-border);
}
.snapshot-stat:last-child { border-right: none; }
.snapshot-num {
  font-size: 2rem;
  font-weight: 800;
  color: var(--color-primary);
  line-height: 1;
  margin-bottom: 5px;
}
.snapshot-label {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-text-muted);
  font-weight: 600;
}
.snapshot-sub { font-size: 0.75rem; color: var(--color-text-muted); margin-top: 2px; }

/* ── PERFORMERS SECTION ── */
.performers-section {
  padding: 48px 0;
  border-bottom: 1px solid var(--color-border);
}
.performers-section.top-section { background: #F0FDF9; }
.performers-section.pressure-section { background: #FFF8F6; }
.perf-section-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 20px;
}
.perf-section-title {
  font-size: 0.65rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-weight: 700;
}
.perf-section-title.green { color: #059669; }
.perf-section-title.red { color: #DC2626; }
.perf-section-link { font-size: 0.8rem; color: var(--color-primary); font-weight: 500; }
.perf-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 10px;
}
.perf-card {
  background: #fff;
  border: 1px solid var(--color-border);
  border-top-width: 3px;
  border-radius: 8px;
  padding: 14px 12px;
  display: flex;
  flex-direction: column;
  gap: 7px;
  text-decoration: none;
  color: var(--color-text);
  transition: box-shadow 0.15s, transform 0.15s;
}
.perf-card:hover {
  box-shadow: 0 4px 14px rgba(0,0,0,0.1);
  transform: translateY(-2px);
  text-decoration: none;
  color: var(--color-text);
}
.perf-rank-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.perf-rank-num { font-size: 0.65rem; color: var(--color-text-muted); font-weight: 600; }
.signal-mini {
  font-size: 0.5rem;
  letter-spacing: 0.06em;
  padding: 1px 5px;
  border-radius: 3px;
  color: #fff;
  font-weight: 700;
  text-transform: uppercase;
  white-space: nowrap;
}
.perf-name { font-weight: 700; font-size: 0.88rem; line-height: 1.2; }
.perf-score-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
}
.perf-score { font-size: 0.78rem; color: var(--color-text-muted); }

/* ── SIGNAL DISTRIBUTION ── */
.signal-dist-section {
  padding: 48px 0;
  background: var(--color-bg-alt);
  border-bottom: 1px solid var(--color-border);
}
.signal-dist-inner {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 40px;
  align-items: start;
}
.signal-dist-text h2 { font-size: 1.3rem; font-weight: 800; margin-bottom: 8px; }
.signal-dist-text p { font-size: 0.88rem; color: var(--color-text-muted); line-height: 1.6; }
.signal-bar-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.signal-bar-label {
  width: 72px;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  flex-shrink: 0;
}
.signal-bar-track {
  flex: 1;
  height: 22px;
  background: var(--color-border);
  border-radius: 4px;
  overflow: hidden;
}
.signal-bar-fill {
  height: 22px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  padding-left: 8px;
  transition: width 0.3s;
}
.signal-bar-fill-label { font-size: 0.7rem; font-weight: 700; color: #fff; white-space: nowrap; }
.signal-bar-count {
  width: 48px;
  text-align: right;
  font-size: 0.78rem;
  color: var(--color-text-muted);
  font-weight: 600;
  flex-shrink: 0;
}

/* ── HOW WE SCORE ── */
.how-section {
  padding: 56px 0;
  border-bottom: 1px solid var(--color-border);
}
.how-header { margin-bottom: 28px; }
.how-header h2 { font-size: 1.3rem; font-weight: 800; margin-bottom: 6px; }
.how-header p { font-size: 0.9rem; color: var(--color-text-muted); }
.how-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}
.how-card {
  background: var(--color-bg-alt);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 24px;
}
.how-number {
  font-size: 2rem;
  font-weight: 800;
  color: var(--color-primary);
  line-height: 1;
  margin-bottom: 10px;
}
.how-title { font-size: 0.92rem; font-weight: 700; margin-bottom: 8px; }
.how-desc { font-size: 0.85rem; color: var(--color-text-muted); line-height: 1.6; }

/* ── GRADE DISTRIBUTION REDESIGN ── */
.grade-dist {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  padding: 48px 0;
  border-bottom: 1px solid var(--color-border);
}
.grade-dist-header {
  width: 100%;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 4px;
}
.grade-dist-header h2 { font-size: 1.3rem; font-weight: 800; }
.grade-dist-blocks { display: flex; gap: 16px; flex-wrap: wrap; width: 100%; }
.grade-dist-block {
  flex: 1;
  min-width: 140px;
  text-align: center;
  padding: 24px 16px;
  background: var(--color-bg-alt);
  border-radius: 10px;
  border: 1px solid var(--color-border);
}
.dist-count {
  font-size: 3rem;
  font-weight: 800;
  line-height: 1;
  margin-bottom: 6px;
}
.dist-label {
  font-size: 0.65rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-muted);
  margin-bottom: 3px;
  font-weight: 600;
}
.dist-grades { font-size: 0.78rem; color: var(--color-text-muted); }
.dist-pct { font-size: 0.72rem; color: var(--color-text-muted); margin-top: 4px; opacity: 0.8; }

/* ── CTA ── */
.cta-section {
  padding: 56px 0;
  text-align: center;
}
.cta-section h2 {
  font-size: 1.5rem;
  font-weight: 800;
  margin-bottom: 10px;
}
.cta-section p {
  color: var(--color-text-muted);
  margin-bottom: 24px;
  font-size: 0.92rem;
  max-width: 440px;
  margin-left: auto;
  margin-right: auto;
}
.btn-large { padding: 14px 36px; font-size: 1rem; border-radius: 8px; }

/* ── MOBILE ── */
@media (max-width: 768px) {
  .hero-title { font-size: 1.7rem; }
  .hero-layout { flex-direction: column; gap: 28px; }
  .hero-featured { flex: none; width: 100%; flex-direction: row; text-align: left; align-items: center; padding: 20px; }
  .city-title { font-size: 1.8rem; }
  .grade-letter { font-size: 2.8rem; }
  .city-columns { grid-template-columns: 1fr; gap: 24px; }
  .city-header-inner { flex-direction: column; }
  .city-header-right { align-items: flex-start; text-align: left; }
  .city-cards { flex-direction: column; }
  .city-card { min-width: auto; }
  .grade-dist { gap: 10px; }
  .grade-dist-blocks { gap: 10px; }
  .indicators-grid { grid-template-columns: 1fr 1fr; }
  .perf-grid { grid-template-columns: repeat(2, 1fr); }
  .snapshot-bar { flex-wrap: wrap; }
  .snapshot-stat { flex: 0 0 50%; border-bottom: 1px solid var(--color-border); }
  .signal-dist-inner { grid-template-columns: 1fr; }
  .how-cards { grid-template-columns: 1fr; }

  /* Rankings: hide lower-priority columns */
  .hide-mobile { display: none; }

  .metric-row { grid-template-columns: 110px 1fr 28px; }
  .nav-links { gap: 14px; }
  .nav-brand { font-size: 0.8rem; }
}

@media (max-width: 480px) {
  .indicators-grid { grid-template-columns: 1fr; }
  .hero { padding: 36px 16px; }
  .city-header { padding: 24px 16px; }
  .city-body { padding: 24px 16px; }
  .perf-grid { grid-template-columns: repeat(2, 1fr); }
  .snapshot-stat { flex: 0 0 100%; }
}
"""

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def city_to_slug(primary_city: str) -> str:
    slug = primary_city.lower()
    slug = slug.replace(' ', '-')
    slug = re.sub(r'[^a-z0-9\-]', '', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug


def fmt_pct(val, decimals=1, plus=True) -> str:
    if val is None:
        return 'N/A'
    sign = '+' if (plus and val > 0) else ''
    return f'{sign}{val:.{decimals}f}%'


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


def bar_color(score: float) -> str:
    if score >= 60:
        return '#059669'
    elif score >= 40:
        return '#D97706'
    else:
        return '#EF4444'


def load_narrative(primary_city: str) -> str:
    slug = city_to_slug(primary_city)
    for reports_dir in [REPORTS_DIR, SCRIPT_DIR / 'city_reports_ft']:
        path = reports_dir / f'{slug}.md'
        if path.exists():
            text = path.read_text(encoding='utf-8')
            parts = re.split(r'\n---+\n', text, maxsplit=1)
            # Take the polished section (before the divider), strip any ## headers
            body_raw = parts[0].strip()
            lines = body_raw.split('\n')
            body_lines = [l for l in lines if not l.startswith('#')]
            body = '\n'.join(body_lines).strip()
            paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]
            return '\n'.join(f'<p>{p}</p>' for p in paragraphs)
    return '<p>Analysis not available.</p>'


# ─── DATA ─────────────────────────────────────────────────────────────────────

def load_data():
    with open(METRICS_FILE, encoding='utf-8') as f:
        data = json.load(f)
    metros = sorted(data['metros'], key=lambda x: x['weighted_percentile'], reverse=True)
    ts = data.get('calculation_timestamp', '')
    if ts:
        calc_date = datetime.fromisoformat(ts).strftime('%B %Y')
    else:
        calc_date = data.get('calculation_date', 'April 2026')
    return metros, calc_date


def prepare_city(metro: dict, rank: int) -> dict:
    raw  = metro['raw_values']
    pctl = metro['percentile_scores']
    grade = metro['grade']['letter']

    emp_yoy = raw.get('107E_employment_growth_yoy')
    wh_dev  = raw.get('107E_wh_trend_deviation_pct')
    scenario = get_scenario(emp_yoy, wh_dev)

    metrics = []
    for code, label, weight in METRICS:
        score = int(round(pctl.get(code, 50)))
        metrics.append({
            'label':     label,
            'weight':    weight,
            'score':     score,
            'bar_color': bar_color(score),
        })

    dom_level = raw.get('204A_dom_level_days')
    dom_str   = f'{int(dom_level)} days' if dom_level is not None else 'N/A'
    dom_yoy   = raw.get('204A_dom_yoy_pct')

    slug = city_to_slug(metro['primary_city'])

    return {
        'primary_city':      metro['primary_city'],
        'metro_name':        metro['metro_name'],
        'slug':              slug,
        'rank':              rank,
        'grade':             grade,
        'grade_color':       GRADE_COLORS.get(grade, '#64748B'),
        'grade_description': GRADE_DESCRIPTIONS.get(grade, ''),
        'score':             metro['weighted_percentile'],
        'metrics':           metrics,
        'scenario':          scenario,
        'scenario_color':    SCENARIO_COLORS[scenario],
        'scenario_desc':     SCENARIO_DESCS[scenario],
        'narrative':         load_narrative(metro['primary_city']),
        # Formatted stats for key indicators
        'unemp':      fmt_pct(raw.get('101A_unemployment'), plus=False),
        'earnings':   fmt_pct(raw.get('103B_earnings_yoy')),
        'emp_growth': fmt_pct(emp_yoy),
        'lfp':        fmt_pct(raw.get('102A_clf_yoy'), plus=True),
        'permits':    fmt_pct(raw.get('200B_permits_yoy')),
        'dom':        dom_str,
        'dom_yoy':    fmt_pct(dom_yoy) if dom_yoy is not None else 'N/A',
    }


# ─── HTML COMPONENTS ──────────────────────────────────────────────────────────

def nav_html(css_prefix: str, active: str = '') -> str:
    def link(href, label, key):
        cls = ' style="color:var(--color-primary);"' if active == key else ''
        return f'<a href="{css_prefix}{href}"{cls}>{label}</a>'
    return f'''\
<nav class="site-nav">
  <div class="nav-inner">
    <a class="nav-brand" href="{css_prefix}index.html">U.S. METRO ECONOMIC HEALTH</a>
    <div class="nav-links">
      {link("rankings.html", "Rankings", "rankings")}
      {link("methodology.html", "Methodology", "methodology")}
    </div>
  </div>
</nav>'''


def footer_html(date: str) -> str:
    return f'''\
<footer class="site-footer">
  <div class="footer-inner">
    <div class="footer-sources">
      Data sources: BLS LAUS / SAE &middot; Census Bureau / FRED &middot; Realtor.com / FRED
      &middot; 85% Employment / 15% Housing composite &middot; {date} &middot; U.S. Metro Economic Health Report
    </div>
    <div class="footer-note">
      Scores reflect conditions at time of data collection. Not investment advice.
      &copy; U.S. Metro Economic Health Report
    </div>
  </div>
</footer>'''


def page_shell(title: str, css_path: str, nav: str, main_content: str, footer: str) -> str:
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | U.S. Metro Economic Health Report</title>
  <link rel="stylesheet" href="{css_path}assets/style.css">
</head>
<body>
  {nav}
  <main class="site-main">
    {main_content}
  </main>
  {footer}
</body>
</html>'''


# ─── WRITE CSS ────────────────────────────────────────────────────────────────

def write_css(site_dir: Path):
    assets_dir = site_dir / 'assets'
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / 'style.css').write_text(CSS, encoding='utf-8')
    print('  ✓ style.css')


# ─── COPY PDF ─────────────────────────────────────────────────────────────────

def copy_pdf(site_dir: Path) -> str:
    """Copy latest PDF to site/pdfs/. Returns PDF filename or empty string."""
    pdfs_dir = site_dir / 'pdfs'
    pdfs_dir.mkdir(parents=True, exist_ok=True)

    # Find most recently modified dated PDF
    dated = sorted(PDF_DIR.glob('city_economic_report_2*.pdf'),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    latest = PDF_DIR / 'city_economic_report_latest.pdf'

    src = dated[0] if dated else (latest if latest.exists() else None)
    if src and src.exists():
        dest = pdfs_dir / 'city_economic_report_latest.pdf'
        shutil.copy2(src, dest)
        print(f'  ✓ pdfs/city_economic_report_latest.pdf (from {src.name})')
        return 'pdfs/city_economic_report_latest.pdf'
    else:
        print('  ⚠ No PDF found — download button will be omitted')
        return ''


# ─── WRITE HOMEPAGE ───────────────────────────────────────────────────────────

def write_homepage(cities: list, date: str, pdf_rel_path: str, site_dir: Path):
    top7    = cities[:7]
    bottom7 = list(reversed(cities[-7:]))
    top1    = cities[0]

    # Summary stats
    total       = len(cities)
    median_score = cities[total // 2]['score']
    ab_count    = sum(1 for c in cities if c['grade'] in ['A+','A','A-','B+','B','B-'])
    strong_count = sum(1 for c in cities if c['scenario'] == 'STRONG')
    growing_count = sum(1 for c in cities if c['scenario'] in ['STRONG','GROWING'])

    # Grade distribution
    grade_counts = {}
    for c in cities:
        g = c['grade']
        grade_counts[g] = grade_counts.get(g, 0) + 1

    # Signal distribution
    signal_order  = ['STRONG', 'GROWING', 'SQUEEZE', 'WEAK', 'N/A']
    signal_counts = {s: sum(1 for c in cities if c['scenario'] == s) for s in signal_order}

    # PDF button
    pdf_btn = ''
    if pdf_rel_path:
        pdf_btn = f'<a href="{pdf_rel_path}" class="btn btn-white" download>&#8595; Download PDF</a>'

    # ── Hero featured city card ──
    hero_featured = f'''\
<a class="hero-featured" href="metros/{top1['slug']}.html">
  <div class="hf-eyebrow">#1 Ranked Metro &mdash; {date}</div>
  <div class="hf-grade">{top1['grade']}</div>
  <div class="hf-city">{top1['primary_city']}</div>
  <div class="hf-metro">{top1['metro_name']}</div>
  <div class="hf-score">{top1['score']:.1f} composite score</div>
  <div class="hf-signal">{top1['scenario']}</div>
  <div class="hf-label">Click to view full analysis &rarr;</div>
</a>'''

    # ── Performer cards ──
    def perf_card(city):
        return f'''\
<a class="perf-card" href="metros/{city['slug']}.html" style="border-top-color:{city['grade_color']};">
  <div class="perf-rank-row">
    <span class="perf-rank-num">#{city['rank']}</span>
    <span class="signal-mini" style="background:{city['scenario_color']};">{city['scenario']}</span>
  </div>
  <div class="perf-name">{city['primary_city']}</div>
  <div class="perf-score-row">
    <span class="grade-badge" style="background:{city['grade_color']};">{city['grade']}</span>
    <span class="perf-score">{city['score']:.1f}</span>
  </div>
</a>'''

    top_cards    = '\n'.join(perf_card(c) for c in top7)
    bottom_cards = '\n'.join(perf_card(c) for c in bottom7)

    # ── Signal distribution bars ──
    max_sig = max(signal_counts.values()) or 1
    signal_bars = ''
    for sig in signal_order:
        count = signal_counts[sig]
        color = SCENARIO_COLORS[sig]
        pct   = int(count / max_sig * 100)
        metros_label = 'metro' if count == 1 else 'metros'
        signal_bars += f'''\
<div class="signal-bar-row">
  <div class="signal-bar-label" style="color:{color};">{sig}</div>
  <div class="signal-bar-track">
    <div class="signal-bar-fill" style="width:{pct}%;background:{color};">
      <span class="signal-bar-fill-label">{count} {metros_label}</span>
    </div>
  </div>
  <div class="signal-bar-count">{count}</div>
</div>
'''

    # ── Grade distribution blocks ──
    dist_blocks = ''
    for tier_label, grades, color, grade_str in GRADE_TIERS:
        count = sum(grade_counts.get(g, 0) for g in grades)
        pct   = round(count / total * 100)
        dist_blocks += f'''\
<div class="grade-dist-block">
  <div class="dist-count" style="color:{color};">{count}</div>
  <div class="dist-label">{tier_label}</div>
  <div class="dist-grades">{grade_str}</div>
  <div class="dist-pct">{pct}% of metros</div>
</div>
'''

    main_content = f'''\
<!-- HERO -->
<div class="hero">
  <div class="hero-layout">
    <div class="hero-text">
      <div class="hero-pills">
        <span class="hero-pill">50 Metro Areas</span>
        <span class="hero-pill">8 Indicators</span>
        <span class="hero-pill">{date}</span>
      </div>
      <h1 class="hero-title">U.S. Metro Economic Health</h1>
      <p class="hero-tagline">
        A composite economic health score for the 50 largest U.S. metros &mdash;
        ranking labor demand, unemployment, wage growth, cost of living, and housing
        into a single 0&ndash;100 grade.
      </p>
      <div class="hero-buttons">
        {pdf_btn}
        <a href="rankings.html" class="btn btn-outline">View Full Rankings</a>
      </div>
    </div>
    {hero_featured}
  </div>
</div>

<!-- SNAPSHOT BAR -->
<div class="snapshot-bar">
  <div class="snapshot-stat">
    <div class="snapshot-num">{median_score:.1f}</div>
    <div class="snapshot-label">Median Score</div>
    <div class="snapshot-sub">across 50 metros</div>
  </div>
  <div class="snapshot-stat">
    <div class="snapshot-num">{ab_count}</div>
    <div class="snapshot-label">A &amp; B Grade Markets</div>
    <div class="snapshot-sub">healthy or above average</div>
  </div>
  <div class="snapshot-stat">
    <div class="snapshot-num">{growing_count}</div>
    <div class="snapshot-label">Growing Markets</div>
    <div class="snapshot-sub">STRONG or GROWING signal</div>
  </div>
  <div class="snapshot-stat">
    <div class="snapshot-num">{total}</div>
    <div class="snapshot-label">Metros Scored</div>
    <div class="snapshot-sub">largest U.S. MSAs</div>
  </div>
</div>

<!-- TOP PERFORMERS -->
<div class="performers-section top-section">
  <div class="content-wrap">
    <div class="perf-section-header">
      <div class="perf-section-title green">&#9650; Top Performing Markets &mdash; {date}</div>
      <a class="perf-section-link" href="rankings.html">See all 50 &rarr;</a>
    </div>
    <div class="perf-grid">{top_cards}</div>
  </div>
</div>

<!-- MARKETS UNDER PRESSURE -->
<div class="performers-section pressure-section">
  <div class="content-wrap">
    <div class="perf-section-header">
      <div class="perf-section-title red">&#9660; Markets Under Pressure</div>
      <a class="perf-section-link" href="rankings.html">See all 50 &rarr;</a>
    </div>
    <div class="perf-grid">{bottom_cards}</div>
  </div>
</div>

<!-- SIGNAL DISTRIBUTION -->
<div class="signal-dist-section">
  <div class="content-wrap">
    <div class="signal-dist-inner">
      <div class="signal-dist-text">
        <h2>Labor Market Signal Distribution</h2>
        <p>
          Each metro is classified by its labor market scenario &mdash; combining employment
          growth direction with weekly hours deviation from each city's own 12-month baseline.
          The signal captures what employment alone cannot: whether growth is genuine demand
          or a survivor squeeze.
        </p>
        <p style="margin-top:12px;">
          <a href="methodology.html">Learn how signals are calculated &rarr;</a>
        </p>
      </div>
      <div class="signal-dist-bars">
        {signal_bars}
      </div>
    </div>
  </div>
</div>

<!-- HOW WE SCORE -->
<div class="how-section">
  <div class="content-wrap">
    <div class="how-header">
      <h2>How the Score Works</h2>
      <p>A composite of 8 economic indicators, weighted by their signal quality and data timeliness.</p>
    </div>
    <div class="how-cards">
      <div class="how-card">
        <div class="how-number">8</div>
        <div class="how-title">Indicators, One Score</div>
        <div class="how-desc">
          Labor demand, unemployment, wage growth, cost of living, labor force growth,
          building permits, days on market, and office economy &mdash; combined into a single
          weighted composite.
        </div>
      </div>
      <div class="how-card">
        <div class="how-number">0&ndash;100</div>
        <div class="how-title">Percentile-Ranked</div>
        <div class="how-desc">
          Every metric is scored as a percentile rank across all 50 metros simultaneously.
          A score of 75 means this city outperforms 75% of its peers on that measure.
          Immune to outliers and self-calibrating as conditions change.
        </div>
      </div>
      <div class="how-card">
        <div class="how-number">85 / 15</div>
        <div class="how-title">Employment / Housing Split</div>
        <div class="how-desc">
          85% of the score comes from employment metrics &mdash; the direct measure of labor
          market health. Housing gets 15%, capturing whether workers can afford to live where
          businesses need them.
        </div>
      </div>
    </div>
  </div>
</div>

<!-- GRADE DISTRIBUTION -->
<div class="content-wrap">
  <div class="grade-dist">
    <div class="grade-dist-header">
      <h2>Grade Distribution &mdash; {total} Metros</h2>
      <a href="methodology.html" style="font-size:0.85rem;color:var(--color-primary);">Grade thresholds &rarr;</a>
    </div>
    <div class="grade-dist-blocks">
      {dist_blocks}
    </div>
  </div>
</div>

<!-- CTA -->
<div class="content-wrap">
  <div class="cta-section">
    <h2>Explore All 50 Metro Areas</h2>
    <p>Full rankings table with scores, grades, and key economic metrics for every metropolitan area.</p>
    <a href="rankings.html" class="btn btn-teal btn-large">View Full Rankings &rarr;</a>
  </div>
</div>'''

    html = page_shell(
        title='Home',
        css_path='',
        nav=nav_html('', 'home'),
        main_content=main_content,
        footer=footer_html(date),
    )
    (site_dir / 'index.html').write_text(html, encoding='utf-8')
    print('  ✓ index.html')


# ─── WRITE RANKINGS ───────────────────────────────────────────────────────────

def write_rankings(cities: list, date: str, site_dir: Path):
    rows = ''
    for c in cities:
        rows += f'''\
<tr>
  <td class="rank-num">{c['rank']}</td>
  <td>
    <a href="metros/{c['slug']}.html">
      <span class="metro-primary">{c['primary_city']}</span>
    </a>
    <span class="metro-secondary">{c['metro_name']}</span>
  </td>
  <td><span class="grade-badge" style="background:{c['grade_color']};">{c['grade']}</span></td>
  <td class="score-val">{c['score']:.1f}</td>
  <td class="metric-val hide-mobile">{c['unemp']}</td>
  <td class="metric-val hide-mobile">{c['earnings']}</td>
  <td class="metric-val hide-mobile">{c['emp_growth']}</td>
  <td class="metric-val hide-mobile">{c['lfp']}</td>
  <td class="metric-val hide-mobile">{c['dom']}</td>
</tr>
'''

    main_content = f'''\
<div class="content-wrap rankings-page">
  <div class="page-header">
    <h1>Full Rankings</h1>
    <p>50 metropolitan statistical areas ranked by composite economic health score &mdash; {date}</p>
  </div>
  <table class="rankings-table">
    <thead>
      <tr>
        <th>#</th>
        <th>Metro</th>
        <th>Grade</th>
        <th>Score</th>
        <th class="hide-mobile">Unemp.</th>
        <th class="hide-mobile">Wage YoY</th>
        <th class="hide-mobile">Emp. YoY</th>
        <th class="hide-mobile">LF YoY</th>
        <th class="hide-mobile">DOM</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</div>'''

    html = page_shell(
        title='Rankings',
        css_path='',
        nav=nav_html('', 'rankings'),
        main_content=main_content,
        footer=footer_html(date),
    )
    (site_dir / 'rankings.html').write_text(html, encoding='utf-8')
    print('  ✓ rankings.html')


# ─── WRITE CITY PAGES ─────────────────────────────────────────────────────────

def write_city(city: dict, all_cities: list, site_dir: Path):
    rank = city['rank']
    total = len(all_cities)

    prev_link = ''
    next_link = ''
    if rank > 1:
        prev = all_cities[rank - 2]
        prev_link = f'<a href="{prev["slug"]}.html">&larr; #{prev["rank"]} {prev["primary_city"]}</a>'
    if rank < total:
        nxt = all_cities[rank]
        next_link = f'<a href="{nxt["slug"]}.html">#{nxt["rank"]} {nxt["primary_city"]} &rarr;</a>'

    # Metric scorecard rows
    metric_rows = ''
    for m in city['metrics']:
        metric_rows += f'''\
<div class="metric-row">
  <div class="metric-label">
    <span class="metric-name">{m['label']}</span>
    <span class="metric-weight">{m['weight']} weight</span>
  </div>
  <div class="metric-bar-track">
    <div class="metric-bar-fill" style="width:{m['score']}%;background:{m['bar_color']};"></div>
  </div>
  <div class="metric-score" style="color:{m['bar_color']};">{m['score']}</div>
</div>
'''

    # Key indicators grid
    indicators = [
        ('Unemployment',          city['unemp'],      'unemployment rate'),
        ('Wage Growth YoY',       city['earnings'],   'avg hourly earnings'),
        ('Employment Growth',     city['emp_growth'], 'nonfarm payrolls YoY'),
        ('Labor Force YoY',       city['lfp'],        'civilian labor force YoY'),
        ('Building Permits',      city['permits'],    'permits YoY'),
        ('Days on Market',        city['dom'],        'median days on market'),
    ]
    tiles = ''
    for label, value, sub in indicators:
        tiles += f'''\
<div class="stat-tile">
  <div class="stat-label">{label}</div>
  <div class="stat-value">{value}</div>
  <div class="stat-sub">{sub}</div>
</div>
'''

    main_content = f'''\
<div class="city-header" style="background-color:{city['grade_color']};">
  <div class="city-header-inner">
    <div class="city-header-left">
      <div class="rank-label">U.S. METRO ECONOMIC HEALTH &middot; RANK #{city['rank']} OF {total}</div>
      <div class="city-title">{city['primary_city']}</div>
      <div class="metro-name">{city['metro_name']}</div>
    </div>
    <div class="city-header-right">
      <div class="grade-letter">{city['grade']}</div>
      <div class="grade-desc">{city['grade_description']}</div>
      <div class="percentile-score">{city['score']:.1f} score</div>
      <div class="rank-of">Rank {city['rank']} of {total} metros</div>
    </div>
  </div>
</div>

<div class="city-body">

  <div class="city-columns">

    <div class="scorecard">
      <div class="section-title">Metric Scorecard</div>
      {metric_rows}
    </div>

    <div class="key-indicators">
      <div class="section-title">Key Indicators</div>
      <div class="indicators-grid">
        {tiles}
      </div>
    </div>

  </div>

  <div class="signal-section">
    <div class="section-title">Labor Market Signal</div>
    <div class="signal-badge" style="background:{city['scenario_color']};">{city['scenario']}</div>
    <div class="signal-desc">{city['scenario_desc']}</div>
  </div>

  <div class="analysis-section">
    <div class="section-title">Economic Analysis</div>
    {city['narrative']}
  </div>

  <div class="city-nav">
    <div>{prev_link}</div>
    <div class="city-nav-back"><a href="../rankings.html">&#8592; All Rankings</a></div>
    <div>{next_link}</div>
  </div>

</div>'''

    html = page_shell(
        title=city['primary_city'],
        css_path='../',
        nav=nav_html('../', ''),
        main_content=main_content,
        footer=footer_html('April 2026'),
    )
    metros_dir = site_dir / 'metros'
    metros_dir.mkdir(parents=True, exist_ok=True)
    (metros_dir / f"{city['slug']}.html").write_text(html, encoding='utf-8')


# ─── WRITE METHODOLOGY ────────────────────────────────────────────────────────

def write_methodology(date: str, site_dir: Path):
    metric_data = [
        ('107E', 'Labor Demand',      'Labor Demand Composite',        '25%', 'Employment', 'BLS SAE &mdash; Employment &amp; Weekly Hours'),
        ('101A', 'Unemployment',      'Unemployment Rate',              '20%', 'Employment', 'BLS Local Area Unemployment Statistics (LAUS)'),
        ('103B', 'Wage Growth',       'Hourly Earnings YoY',            '15%', 'Employment', 'BLS SAE &mdash; State &amp; Metro Area Earnings'),
        ('104C', 'Cost of Living',    'Cost of Living Composite',       '12%', 'Employment', 'Realtor.com / FRED / Census Bureau'),
        ('102A', 'Labor Force YoY',  'Civilian Labor Force YoY % Change', '10%', 'Employment', 'BLS Local Area Unemployment Statistics (LAUS)'),
        ('200B', 'Bldg. Permits',     'Building Permits YoY',           '10%', 'Housing',    'Census Bureau Building Permits Survey / FRED'),
        ('204A', 'Days on Market',    'Days on Market Composite',       ' 5%', 'Housing',    'Realtor.com / FRED'),
        ('105C', 'Office Economy',    'Office Worker Ratio Composite',  ' 3%', 'Employment', 'BLS SAE &mdash; Industry Employment'),
    ]

    metric_rows = ''
    for code, scorecard_label, full_name, weight, category, source in metric_data:
        metric_rows += f'''\
<tr>
  <td><strong>{code}</strong></td>
  <td>{scorecard_label}</td>
  <td>{full_name}</td>
  <td class="weight-bold">{weight.strip()}</td>
  <td>{category}</td>
  <td>{source}</td>
</tr>
'''

    grade_rows = ''
    grade_thresholds = [
        ('68+',      'A+', 'Excellent'),
        ('63&ndash;67.9',  'A',  'Very Good'),
        ('59&ndash;62.9',  'A-', 'Good'),
        ('55&ndash;58.9',  'B+', 'Above Average'),
        ('50&ndash;54.9',  'B',  'Average'),
        ('44&ndash;49.9',  'B-', 'Below Average'),
        ('38&ndash;43.9',  'C+', 'Poor'),
        ('32&ndash;37.9',  'C',  'Very Poor'),
        ('26&ndash;31.9',  'C-', 'Critical'),
        ('Below 26', 'D',  'Emergency'),
    ]
    for threshold, grade, desc in grade_thresholds:
        color = GRADE_COLORS.get(grade, '#64748B')
        grade_rows += f'''\
<tr>
  <td>{threshold}</td>
  <td><span class="grade-badge" style="background:{color};">{grade}</span></td>
  <td>{desc}</td>
</tr>
'''

    signal_rows = ''
    signal_data = [
        ('STRONG',  '#059669', 'Employment growing &amp; hours above trend',  'Genuine demand confirmation. Employers are adding headcount <em>and</em> running existing workers above their normal hours — a double confirmation of labor demand.'),
        ('GROWING', '#0284C7', 'Employment growing &amp; hours below trend',  'Healthy expansion with some moderation. Payrolls are rising but hours are softening, suggesting growth is broadening rather than concentrating on a shrinking workforce.'),
        ('SQUEEZE', '#D97706', 'Employment falling &amp; hours above trend',  'Survivor squeeze. Payrolls are contracting while remaining workers carry elevated hours &mdash; a warning signal that the labor pool is thinning and demand may be masking layoffs.'),
        ('WEAK',    '#DC2626', 'Employment falling &amp; hours below trend',  'Broad contraction. Both job counts and weekly hours are declining together, indicating generalized demand weakness rather than a transitional squeeze.'),
        ('N/A',     '#9CA3AF', 'Insufficient data',                           'One or both underlying data series (employment growth or weekly hours deviation) were unavailable for this metro at the time of calculation.'),
    ]
    for sig, color, condition, desc in signal_data:
        signal_rows += f'''\
<tr>
  <td><span class="signal-badge" style="background:{color};font-size:0.75rem;padding:2px 10px;">{sig}</span></td>
  <td>{condition}</td>
  <td>{desc}</td>
</tr>
'''

    main_content = f'''\
<div class="content-wrap">
  <div class="methodology-body">
    <h1>Methodology</h1>
    <div class="subtitle">How the U.S. Metro Economic Health Score is calculated &mdash; {date}</div>

    <h2>What This System Measures</h2>
    <p>
      This system produces an economic health score for each of the top 50 U.S. metropolitan
      statistical areas (MSAs). The score answers a specific question: <strong>how healthy is this
      city&rsquo;s labor market and cost environment</strong> for businesses considering locating or
      expanding there?
    </p>
    <p>
      It is not a quality-of-life index, a population growth ranking, or a real estate investment
      guide. It is a signal of current and near-term economic conditions from the perspective of
      employers and workers making location decisions.
    </p>

    <h2>Geographic Scope</h2>
    <p>
      The report covers the 50 largest U.S. Metropolitan Statistical Areas (MSAs) by population,
      as defined by the Office of Management and Budget (OMB). Each MSA is represented by its
      primary city name. All 50 metros are scored simultaneously &mdash; each city&rsquo;s percentile rank
      reflects its position relative to the other 49.
    </p>

    <h2>Core Mechanism: Percentile Ranking</h2>
    <p>
      Every metric is scored as a <strong>percentile rank across all 50 metros simultaneously</strong>.
      A score of 75 means that metro outperforms 75% of the other 49 cities on that specific metric.
      A score of 20 means it underperforms 80% of them. The median city scores 50 on any given metric.
    </p>
    <p>
      Percentile ranks are bounded 0&ndash;100, immune to outliers pulling the scale, and immediately
      interpretable without knowing what a &ldquo;normal&rdquo; absolute value looks like. They are also
      self-calibrating: as conditions shift, rankings update naturally without manual threshold
      recalibration.
    </p>

    <h2>Metric Framework</h2>
    <p>
      Eight metrics are combined into a single weighted composite. The split is
      <strong>85% Employment / 15% Housing</strong> &mdash; employment metrics directly measure labor
      market conditions; housing metrics capture whether workers can afford to live where businesses
      need them. The table below maps each scorecard label (shown on city pages) to its full
      technical name, weight, and data source.
    </p>
    <table class="meth-table">
      <thead>
        <tr>
          <th>Code</th>
          <th>Scorecard Label</th>
          <th>Full Name</th>
          <th>Weight</th>
          <th>Category</th>
          <th>Data Source</th>
        </tr>
      </thead>
      <tbody>
        {metric_rows}
        <tr style="border-top:2px solid var(--color-border);">
          <td></td><td></td>
          <td><strong>Total</strong></td>
          <td class="weight-bold">100%</td>
          <td></td><td></td>
        </tr>
      </tbody>
    </table>

    <h2>The 8 Metrics Explained</h2>

    <h2>Labor Demand &mdash; 107E &mdash; 25%</h2>
    <p>
      <strong>What it measures:</strong> A 2-component composite combining total nonfarm
      employment growth year-over-year (70% of the composite) with weekly hours deviation from
      each city&rsquo;s own 12-month baseline (30%).
    </p>
    <p>
      <strong>Why it&rsquo;s the top-weighted metric:</strong> Labor demand is the central question this
      system is designed to answer. Employment growth tells you whether payrolls are expanding or
      contracting. Weekly hours deviation provides context &mdash; but the direction of that signal
      flips depending on whether employment is growing or shrinking. Hours above trend during job
      growth confirm genuine demand. Hours above trend during job losses signal a &ldquo;survivor
      squeeze&rdquo; where remaining workers absorb the load of eliminated positions &mdash; a warning,
      not a positive. This employment-conditional logic is what makes 107E a composite rather
      than two standalone metrics.
    </p>
    <p>
      <strong>Scored higher when:</strong> Payrolls are growing and hours are running above
      each city&rsquo;s own recent baseline.
    </p>

    <h2>Unemployment &mdash; 101A &mdash; 20%</h2>
    <p>
      <strong>What it measures:</strong> The share of the civilian labor force that is unemployed
      and actively seeking work. Sourced from BLS Local Area Unemployment Statistics (LAUS),
      which provides monthly metro-level estimates.
    </p>
    <p>
      <strong>Why 20% weight:</strong> Unemployment is the most widely tracked, most politically
      salient, and most directly actionable labor market signal. A 0.5 percentage point difference
      represents tens of thousands of workers in a large metro. It is the single most powerful
      indicator of labor market health in this system.
    </p>
    <p>
      <strong>Scored higher when:</strong> Unemployment is lower. This metric is inverted &mdash;
      a 3.0% unemployment rate scores better than a 5.0% rate.
    </p>
    <p>
      <strong>Limitation:</strong> Unemployment is a lagging indicator. It peaks after recessions
      have already begun and falls after recoveries are underway. It also misses discouraged workers
      who have left the labor force entirely, which is why Civilian Labor Force Growth (102A)
      complements it.
    </p>

    <h2>Wage Growth &mdash; 103B &mdash; 15%</h2>
    <p>
      <strong>What it measures:</strong> The year-over-year percent change in average hourly
      earnings for all private-sector employees in the metro. Sourced from BLS State and Metro
      Area Employment, Hours, and Earnings (SAE).
    </p>
    <p>
      <strong>Why 15% weight:</strong> Rising wages are a real-time demand signal &mdash; employers
      bid up labor prices when they need workers and expect revenue growth. Wage growth also
      directly affects worker purchasing power and a city&rsquo;s ability to attract and retain talent.
      BLS earnings data updates monthly and captures genuine labor market tightness more dynamically
      than annual-anchored metrics.
    </p>
    <p>
      <strong>Scored higher when:</strong> Wage growth is stronger. A city with +5.0% YoY
      earnings growth scores better than one at +1.5%.
    </p>

    <h2>Cost of Living &mdash; 104C &mdash; 12%</h2>
    <p>
      <strong>What it measures:</strong> A 3-component composite assessing housing cost burden
      relative to local wages. The underlying unit is price per square foot of housing divided
      by average hourly earnings &mdash; a ratio measuring how many hours of local work it takes
      to buy one square foot of housing. This normalizes costs against local wages rather than
      using a national price index.
    </p>
    <p>
      <strong>The three components:</strong>
    </p>
    <ul>
      <li><strong>Absolute affordability (50%):</strong> Where this metro sits on the min-max
      range of the PSF/earnings ratio across all 50 cities. Anchors the composite to actual
      affordability level so improving-but-expensive cities can&rsquo;t outscore genuinely
      affordable ones.</li>
      <li><strong>Trend direction (30%):</strong> Year-over-year change in the ratio, scored on
      a graduated linear scale from &minus;5% (strongly improving) to +5% (strongly worsening).
      Graduated rather than binary to avoid over-penalizing cities with tiny cost upticks.</li>
      <li><strong>Peer-relative trend (20%):</strong> How this city&rsquo;s affordability trend
      compares to the national median. A city worsening when peers are also worsening is less
      alarming than one bucking a broad national improvement.</li>
    </ul>
    <p>
      <strong>Scored higher when:</strong> The PSF/earnings ratio is lower (more affordable),
      improving, and improving faster than peers.
    </p>

    <h2>Labor Force Growth &mdash; 102A &mdash; 10%</h2>
    <p>
      <strong>What it measures:</strong> The year-over-year percent change in the civilian labor
      force &mdash; the total count of people who are either employed or actively seeking work.
      Sourced from BLS Local Area Unemployment Statistics (LAUS).
    </p>
    <p>
      <strong>Why it complements unemployment:</strong> A city can report low unemployment
      simply because discouraged workers stopped looking &mdash; they exit the labor force and
      disappear from unemployment counts. Tracking the growth rate of the labor force captures
      whether the workforce supply is expanding (workers moving in or re-engaging) or
      contracting (discouraged workers exiting or population decline).
    </p>
    <p>
      <strong>Why YoY % change instead of the participation rate:</strong> The traditional LFP
      rate uses an annual population benchmark from BLS as its denominator, meaning the
      denominator only updates meaningfully once per year. This makes the rate a slow-moving
      structural snapshot rather than a dynamic monthly signal. The YoY % change in the raw
      civilian labor force count avoids this denominator problem entirely and tracks supply-side
      momentum directly.
    </p>
    <p>
      <strong>Scored higher when:</strong> Civilian labor force is growing faster year-over-year.
      A city attracting workers or seeing re-engagement scores better than one where the labor
      pool is shrinking.
    </p>

    <h2>Building Permits &mdash; 200B &mdash; 10%</h2>
    <p>
      <strong>What it measures:</strong> The year-over-year percent change in residential
      building permits, using a 3-month smoothed average to reduce monthly volatility. Sourced
      from the Census Bureau Building Permits Survey via FRED.
    </p>
    <p>
      <strong>Why it matters:</strong> Rising permits indicate developer confidence in future
      demand and will eventually translate into housing supply &mdash; relevant both as a measure
      of current economic activity and as a leading indicator of future housing availability
      for workers. A city that is attracting investment in new housing is signaling expectations
      of continued population and employment growth.
    </p>
    <p>
      <strong>Why smoothed:</strong> Building permits are volatile month-to-month due to project
      timing, seasonal factors, and batch-approval effects. The 3-month smoothed YoY compares
      the 3-month average ending this month to the 3-month average ending 12 months ago,
      substantially reducing noise without losing the trend signal.
    </p>
    <p>
      <strong>Scored higher when:</strong> Permit growth is stronger year-over-year.
    </p>

    <h2>Days on Market &mdash; 204A &mdash; 5%</h2>
    <p>
      <strong>What it measures:</strong> A 2-component composite assessing housing market
      accessibility for workers, using median days a listing spends on market before going
      under contract. Sourced from Realtor.com via FRED.
    </p>
    <p>
      <strong>The 60-day inflection point:</strong> The direction of the trend signal depends
      on where the market currently sits. This matters because the same directional change
      has opposite economic meaning depending on context:
    </p>
    <ul>
      <li><strong>Below 60 days (tight market):</strong> Rising DoM is <em>good</em> &mdash; the market
      is gaining inventory and accessibility for incoming workers.</li>
      <li><strong>Above 60 days (soft market):</strong> Rising DoM is <em>bad</em> &mdash; demand is
      softening, buyers can&rsquo;t or won&rsquo;t transact, and labor mobility is impaired because
      homeowners who can&rsquo;t sell are unable to relocate.</li>
    </ul>
    <p>
      <strong>The level component (40%):</strong> Scores the absolute DoM against a
      &ldquo;healthy market&rdquo; anchor using a bell-curve scale peaked at 35&ndash;80 days.
      Markets below 15 days are too competitive for incoming workers; markets above 130 days
      signal demand destruction. Both extremes score low.
    </p>
    <p>
      <strong>Scored higher when:</strong> Days on market is in the healthy accessible range
      and trending in the appropriate direction for its current level.
    </p>

    <h2>Office Economy &mdash; 105C &mdash; 3%</h2>
    <p>
      <strong>What it measures:</strong> A 2-component composite assessing the concentration
      and growth of professional/office-based employment as a proxy for knowledge-economy
      job density. Underlying data is BLS employment in Information, Financial Activities,
      and Professional and Business Services sectors as a share of total nonfarm payroll.
    </p>
    <p>
      <strong>The two components:</strong>
    </p>
    <ul>
      <li><strong>YoY growth (60%):</strong> Whether knowledge-economy jobs are expanding
      in this market, based on the growth rate in the 3-month smoothed office worker count.</li>
      <li><strong>Absolute share (40%):</strong> The structural depth of the professional
      economy &mdash; what percentage of all jobs are office-based, independent of recent trends.</li>
    </ul>
    <p>
      <strong>Why only 3% weight:</strong> Office worker density is a useful tiebreaker
      signal &mdash; it differentiates knowledge-economy metros from industrial, logistics,
      and energy-dominated metros. However, it structurally penalizes legitimate economic
      models (energy, logistics, distribution) that carry fewer office workers by industry
      composition, not by economic weakness. At 3%, it provides directional signal without
      meaningfully distorting scores for non-office economies.
    </p>
    <p>
      <strong>Scored higher when:</strong> Office-sector employment is a larger share of
      total jobs and growing.
    </p>

    <h2>Labor Market Signal</h2>
    <p>
      Each metro page displays a <strong>Labor Market Signal</strong> &mdash; a classification
      derived from two components of the Labor Demand metric: employment growth year-over-year
      and weekly hours deviation from each city&rsquo;s own 12-month baseline. The signal captures
      what employment growth alone cannot: whether strong hours reflect genuine demand or a
      workforce being squeezed after layoffs.
    </p>
    <table class="meth-table">
      <thead>
        <tr>
          <th>Signal</th>
          <th>Condition</th>
          <th>Interpretation</th>
        </tr>
      </thead>
      <tbody>
        {signal_rows}
      </tbody>
    </table>

    <h2>Composite Score Calculation</h2>
    <p>
      The composite score is a weighted average of each metro&rsquo;s 8 individual percentile scores:
    </p>
    <p style="font-family:monospace; background:var(--color-bg-alt); padding:12px 16px; border-radius:6px; border:1px solid var(--color-border); font-size:0.9rem;">
      weighted_score = &sum;(percentile[metric] &times; weight[metric])
    </p>
    <p>
      Since all weights sum to 100, the result is a single number on a 0&ndash;100 scale.
      The practical range observed across 50 metros is approximately 21&ndash;79 &mdash; the
      distribution compresses because no city can plausibly average 90+ across all 8 metrics
      simultaneously, and no city averages below 20.
    </p>

    <h2>Grade Thresholds</h2>
    <p>
      Thresholds are calibrated to the actual achievable range of scores, not the theoretical
      0&ndash;100. They are set so the grade distribution is meaningful and discriminating across
      the full spectrum of metros.
    </p>
    <table class="meth-table grade-threshold-table" style="max-width:420px;">
      <thead>
        <tr>
          <th>Score Threshold</th>
          <th>Grade</th>
          <th>Description</th>
        </tr>
      </thead>
      <tbody>
        {grade_rows}
      </tbody>
    </table>

    <h2>Data Sources</h2>
    <ul>
      <li><strong>BLS LAUS</strong> &mdash; Local Area Unemployment Statistics: unemployment rate, civilian labor force</li>
      <li><strong>BLS SAE</strong> &mdash; State and Metro Area Employment, Hours, and Earnings: employment growth, hourly earnings, weekly hours, industry employment</li>
      <li><strong>Census Bureau / FRED</strong> &mdash; residential building permits</li>
      <li><strong>Realtor.com / FRED</strong> &mdash; median days on market, housing price per square foot</li>
    </ul>

    <h2>Update Cadence</h2>
    <p>
      The pipeline runs monthly, timed to BLS data release schedules. BLS LAUS and SAE data
      typically releases in the third or fourth week of each month for the prior month.
      Building permit data from Census releases approximately 16&ndash;18 days after month-end.
      Realtor.com housing data updates monthly.
    </p>
    <p>
      Each run recalculates all 50 metro scores simultaneously. Percentile ranks are recomputed
      from scratch &mdash; a city&rsquo;s score can change without any change in its own absolute
      data if conditions in other cities shift the distribution.
    </p>

    <h2>Limitations</h2>
    <ul>
      <li><strong>Not a forecast.</strong> The score reflects current and trailing conditions. It is a lagging-to-coincident indicator, not a prediction of future economic performance.</li>
      <li><strong>Not size-adjusted.</strong> All metrics are rates and percentages. A metro with 500,000 workers and one with 5,000,000 are compared on the same basis &mdash; the question is health, not scale.</li>
      <li><strong>Structural composition effects.</strong> Civilian labor force growth reflects both economic conditions and migration patterns. A city growing its labor pool through in-migration looks similar to one recovering from discouraged-worker exit. The percentile ranking captures relative momentum but does not distinguish between these drivers.</li>
      <li><strong>Not a quality-of-life index.</strong> Amenities, climate, culture, and livability are not measured. A city can score highly and still be expensive, congested, or climatically challenging.</li>
      <li><strong>Data lags.</strong> Some BLS metro-level series lag national estimates by 1&ndash;2 months. Scores reflect the most recently available data, which may not be the same calendar month for all metros.</li>
    </ul>

  </div>
</div>'''

    html = page_shell(
        title='Methodology',
        css_path='',
        nav=nav_html('', 'methodology'),
        main_content=main_content,
        footer=footer_html(date),
    )
    (site_dir / 'methodology.html').write_text(html, encoding='utf-8')
    print('  ✓ methodology.html')


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print('=' * 60)
    print('  U.S. METRO ECONOMIC HEALTH — WEBSITE GENERATOR')
    print('=' * 60)

    # Setup
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / 'metros').mkdir(parents=True, exist_ok=True)

    # Load data
    print('\n→ Loading data...')
    metros, calc_date = load_data()
    print(f'  {len(metros)} metros loaded  |  date: {calc_date}')

    # Prepare city objects
    print('→ Preparing city data...')
    all_cities = [prepare_city(m, i + 1) for i, m in enumerate(metros)]

    # Write CSS
    print('\n→ Writing CSS...')
    write_css(SITE_DIR)

    # Copy PDF
    print('→ Copying PDF...')
    pdf_rel = copy_pdf(SITE_DIR)

    # Write pages
    print('→ Writing pages...')
    write_homepage(all_cities, calc_date, pdf_rel, SITE_DIR)
    write_rankings(all_cities, calc_date, SITE_DIR)
    write_methodology(calc_date, SITE_DIR)

    # Write city pages
    print(f'→ Writing {len(all_cities)} city pages...')
    for city in all_cities:
        write_city(city, all_cities, SITE_DIR)
    print(f'  ✓ {len(all_cities)} metro pages written to site/metros/')

    print(f'\n✓ Site written to: {SITE_DIR}')
    print(f'  Pages: index + rankings + methodology + {len(all_cities)} metros = {len(all_cities) + 3} total')
    print('\nNext step: commit site/ to GitHub and enable GitHub Pages from /site/ folder.')
    print('Done.')


if __name__ == '__main__':
    main()
