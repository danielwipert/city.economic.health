#!/usr/bin/env python3
"""
CALCULATE ECONOMIC METRICS - RECONCILED VERSION
================================================
Combines the best of both approaches:
- Original: Solid data reading, clean architecture
- New: 3-component Cost of Living, Percentile-based scoring

Why this works:
- Reads from processed_economic_data_v2.json (correct data structure)
- Uses percentile scoring (handles outliers better than z-scores)
- Implements 3-component COL (affordability + direction + volatility)
- Maintains the original's reliable metric extraction
"""

import json
from pathlib import Path
from statistics import mean, stdev
from datetime import datetime
from typing import Dict, List, Optional

SCRIPT_DIR = Path(__file__).parent


# ============================================================================
# STEP 1: CALCULATE 2-COMPONENT OFFICE WORKER RATIO METRIC
# ============================================================================

def calculate_owr_final_score(metro_data: Dict, all_metros: List[Dict]) -> float:
    """
    Calculate office worker ratio score (0-5 points):
    - Component 1 (YoY change using 3-month avg): 0-3 points
      Going UP = better (more office workers)
    - Component 2 (absolute percentage): 0-2 points
      Higher % = better
    Total: 0-5 points (higher is better)
    
    Note: Component 1 uses 3month_avg_yoy from raw office_workers data
    """
    owr_metric = metro_data['data'].get('office_worker_ratio')
    if not owr_metric:
        return None
    
    # Component 1: YoY change (3-month average comparison from office_workers)
    # Get the raw office_workers data which has 3month_avg_yoy
    office_workers_metric = metro_data['data'].get('office_workers')
    yoy_3mo = office_workers_metric.get('3month_avg_yoy') if office_workers_metric else None
    yoy_pct_change = yoy_3mo.get('pct_change') if yoy_3mo else None
    
    # Collect all YoY changes for percentile calculation
    yoy_changes = []
    for metro in all_metros:
        office_workers = metro['data'].get('office_workers')
        if office_workers:
            yoy_3mo_other = office_workers.get('3month_avg_yoy')
            if yoy_3mo_other:
                yoy_pct = yoy_3mo_other.get('pct_change')
                if yoy_pct is not None:
                    yoy_changes.append(yoy_pct)
    
    # Calculate Component 1 score (0-3)
    if yoy_pct_change is not None and yoy_changes:
        # Higher YoY change is better
        better_count = sum(1 for v in yoy_changes if v < yoy_pct_change)
        yoy_percentile = (better_count / len(yoy_changes)) * 100.0
        c1_score = (yoy_percentile / 100.0) * 3.0
    else:
        c1_score = 1.5  # Default middle value
    
    # Component 2: Absolute office worker percentage
    abs_pct = owr_metric.get('latest_value')
    
    # Collect all absolute percentages
    abs_pcts = []
    for metro in all_metros:
        owr = metro['data'].get('office_worker_ratio')
        if owr:
            latest = owr.get('latest_value')
            if latest is not None:
                abs_pcts.append(latest)
    
    # Calculate Component 2 score (0-2)
    if abs_pct is not None and abs_pcts:
        # Higher percentage is better
        better_count = sum(1 for v in abs_pcts if v < abs_pct)
        abs_percentile = (better_count / len(abs_pcts)) * 100.0
        c2_score = (abs_percentile / 100.0) * 2.0
    else:
        c2_score = 1.0  # Default middle value
    
    total = c1_score + c2_score
    return min(5.0, max(0.0, total))


# ============================================================================
# STEP 1B: CALCULATE 3-COMPONENT COST OF LIVING METRIC
# ============================================================================

def calculate_col_component1(metro_data: Dict) -> float:
    """
    Component 1: Absolute Affordability
    Price per square foot ÷ Hourly earnings (higher = worse affordability)
    """
    if 'price_per_sqft' not in metro_data['data']:
        return None
    if 'hourly_earnings' not in metro_data['data']:
        return None
    
    psf = metro_data['data']['price_per_sqft'].get('latest_value')
    earnings = metro_data['data']['hourly_earnings'].get('latest_value')
    
    if psf is None or earnings is None or earnings == 0:
        return None
    
    col_index = psf / earnings
    return col_index


def calculate_col_component2(metro_data: Dict) -> float:
    """
    Component 2: Direction of Affordability
    Is affordability getting better or worse? (change in COL ratio)
    """
    if 'price_per_sqft' not in metro_data['data'] or 'hourly_earnings' not in metro_data['data']:
        return 0
    
    psf_metric = metro_data['data']['price_per_sqft']
    earnings_metric = metro_data['data']['hourly_earnings']
    
    # Current COL ratio
    psf_current = psf_metric.get('latest_value')
    earnings_current = earnings_metric.get('latest_value')
    
    if psf_current is None or earnings_current is None or earnings_current == 0:
        return 0
    
    col_current = psf_current / earnings_current
    
    # Historical COL ratio (12 months ago if available)
    psf_yoy = psf_metric.get('yoy_change')
    earnings_yoy = earnings_metric.get('yoy_change')
    
    if psf_yoy and earnings_yoy:
        psf_prev = psf_yoy.get('current') - psf_yoy.get('change')
        earnings_prev = earnings_yoy.get('current') - earnings_yoy.get('change')
        
        if psf_prev and earnings_prev and earnings_prev != 0:
            col_prev = psf_prev / earnings_prev
            col_change = col_current - col_prev
            return col_change
    
    return 0


def calculate_col_component3(metro_data: Dict) -> float:
    """
    Component 3: Stability/Volatility
    Lower volatility = more stable (better for planning)
    Uses recent months to measure stability
    """
    if 'price_per_sqft' not in metro_data['data']:
        return None
    
    psf_metric = metro_data['data']['price_per_sqft']
    earnings_metric = metro_data['data']['hourly_earnings']
    
    psf_current = psf_metric.get('latest_value')
    earnings_current = earnings_metric.get('latest_value')
    
    if psf_current is None or earnings_current is None or earnings_current == 0:
        return None
    
    # We'll estimate volatility as the range of recent changes
    # In real data, this would use multiple observations
    # For now, use a proxy: if data is stable, volatility is low
    
    psf_yoy = psf_metric.get('yoy_change')
    earnings_yoy = earnings_metric.get('yoy_change')
    
    if psf_yoy and earnings_yoy:
        psf_pct = abs(psf_yoy.get('pct_change', 0))
        earnings_pct = abs(earnings_yoy.get('pct_change', 0))
        volatility = (psf_pct + earnings_pct) / 2
        return volatility
    
    return 0


def calculate_col_final_score(metro_data: Dict, all_metros: List[Dict], 
                             col_component2_all: Dict, col_component3_all: Dict) -> float:
    """
    Combine 3 COL components into final 0-10 score:
    - Component 1 (absolute affordability): 0-3 points
    - Component 2 (direction): 0-4 points  
    - Component 3 (stability): 0-3 points
    Total: 0-10 points (lower is better affordability)
    """
    metro_name = metro_data['metro_name']
    
    # Component 1: Absolute affordability (0-3 points)
    col_index = calculate_col_component1(metro_data)
    if col_index is None:
        return None
    
    # Find where this metro ranks in affordability
    col_indices = []
    for metro in all_metros:
        idx = calculate_col_component1(metro)
        if idx is not None:
            col_indices.append(idx)
    
    if not col_indices:
        return None
    
    # Normalize to 0-3 scale (higher is worse affordability)
    min_col = min(col_indices)
    max_col = max(col_indices)
    
    if max_col > min_col:
        c1_score = ((col_index - min_col) / (max_col - min_col)) * 3.0
    else:
        c1_score = 1.5
    
    # Component 2: Direction of change (0-4 points)
    col_change = col_component2_all.get(metro_name, 0)
    if col_change < 0:
        # Affordability improving (negative change is good)
        c2_score = 4.0
    elif col_change > 0:
        # Affordability worsening (positive change is bad)
        c2_score = 0.0
    else:
        c2_score = 2.0
    
    # Component 3: Volatility (0-3 points)
    volatility = col_component3_all.get(metro_name, 0)
    if volatility > 5:
        c3_score = 0.0  # High volatility = bad
    elif volatility < 1:
        c3_score = 3.0  # Low volatility = good
    else:
        c3_score = (5 - volatility) / 2.5 * 0.6  # Scale between 0-3
    
    total = c1_score + c2_score + c3_score
    return min(10.0, max(0.0, total))


# ============================================================================
# STEP 2: PERCENTILE-BASED SCORING
# ============================================================================

def calculate_percentile_score(value: float, all_values: List[float], 
                              invert: bool = False) -> float:
    """
    Calculate percentile score for a single value (0-100 scale)
    
    invert=False: Higher value = higher percentile (good for earnings, permits, etc)
    invert=True:  Lower value = higher percentile (good for unemployment, days_on_market)
    """
    if not all_values or len(all_values) < 2:
        return 50.0
    
    valid_values = [v for v in all_values if v is not None]
    if not valid_values:
        return 50.0
    
    sorted_vals = sorted(valid_values)
    
    if invert:
        # For inverted metrics: lower is better
        # Count how many values are WORSE (higher) than this one
        better_count = sum(1 for v in sorted_vals if v > value)
    else:
        # For normal metrics: higher is better
        # Count how many values are WORSE (lower) than this one
        better_count = sum(1 for v in sorted_vals if v < value)
    
    percentile = (better_count / len(sorted_vals)) * 100.0
    return max(0, min(100, percentile))


# ============================================================================
# STEP 3: MAIN CALCULATION FUNCTION
# ============================================================================

def calculate_metrics():
    """Main calculation logic"""
    
    print("\n" + "=" * 80)
    print("CALCULATING ECONOMIC METRICS (RECONCILED VERSION)")
    print("=" * 80)
    
    # Load processed data
    print("\nSTEP 1: Loading processed economic data...")
    processed_path = SCRIPT_DIR / 'processed_economic_data_v2.json'
    
    if not processed_path.exists():
        print(f"❌ ERROR: {processed_path} not found")
        return None
    
    try:
        with open(processed_path, 'r', encoding='utf-8') as f:
            processed_data = json.load(f)
        print(f"✓ Loaded {len(processed_data['metros'])} metros")
    except Exception as e:
        print(f"❌ ERROR loading data: {e}")
        return None
    
    all_metros = list(processed_data['metros'].values())
    
    # Calculate COL components for all metros
    print("\nSTEP 2: Calculating 3-component Cost of Living...")
    
    col_component2_all = {}
    col_component3_all = {}
    
    for metro in all_metros:
        metro_name = metro['metro_name']
        col_component2_all[metro_name] = calculate_col_component2(metro)
        col_component3_all[metro_name] = calculate_col_component3(metro)
    
    print("✓ Calculated COL components")
    
    # Collect all metric values for percentile calculation
    print("\nSTEP 3: Collecting metrics for percentile ranking...")
    
    # Pre-calculate OWR scores for all metros
    owr_scores_all = {}
    for metro in all_metros:
        owr_score = calculate_owr_final_score(metro, all_metros)
        owr_scores_all[metro['metro_name']] = owr_score
    
    metrics_data = {
        '101A': [],  # Unemployment rate
        '102A': [],  # Labor force participation
        '103B': [],  # Hourly earnings YoY
        '104C': [],  # Cost of living (final score)
        '105C': [],  # Office worker ratio (new 2-component score)
        '106D': [],  # Weekly hours
        '200B': [],  # Building permits YoY
        '201': [],   # Home price index YoY
        '202': [],   # Price per sqft YoY
        '204A': [],  # Median days on market
    }
    
    for metro in all_metros:
        data = metro['data']
        
        # Extract latest values for each metric
        unemp = data.get('unemployment_rate', {}).get('latest_value')
        lfp = data.get('civilian_labor_force', {}).get('latest_value')
        earnings_yoy = data.get('hourly_earnings', {}).get('yoy_change', {}).get('pct_change')
        col_score = calculate_col_final_score(metro, all_metros, col_component2_all, col_component3_all)
        owr = owr_scores_all.get(metro['metro_name'])
        weekly_hours = data.get('weekly_hours', {}).get('latest_value')
        permits_yoy = data.get('building_permits', {}).get('3month_avg_yoy', {}).get('pct_change')  # SMOOTHED 3-month YoY
        hpi_yoy = data.get('home_price_index', {}).get('yoy_change', {}).get('pct_change')
        psf_yoy = data.get('price_per_sqft', {}).get('3month_avg_yoy', {}).get('pct_change')  # SMOOTHED 3-month YoY
        days = data.get('median_days_on_market', {}).get('latest_value')
        
        # Add to collections (only if not None)
        if unemp is not None:
            metrics_data['101A'].append(unemp)
        if lfp is not None:
            metrics_data['102A'].append(lfp)
        if earnings_yoy is not None:
            metrics_data['103B'].append(earnings_yoy)
        if col_score is not None:
            metrics_data['104C'].append(col_score)
        if owr is not None:
            metrics_data['105C'].append(owr)
        if weekly_hours is not None:
            metrics_data['106D'].append(weekly_hours)
        if permits_yoy is not None:
            metrics_data['200B'].append(permits_yoy)
        if hpi_yoy is not None:
            metrics_data['201'].append(hpi_yoy)
        if psf_yoy is not None:
            metrics_data['202'].append(psf_yoy)
        if days is not None:
            metrics_data['204A'].append(days)
    
    print(f"✓ Collected metrics from {len(all_metros)} metros")
    
    # Weight configuration
    weights = {
        '101A': 15,  # Unemployment (lower is better)
        '102A': 15,  # LFP (higher is better)
        '103B': 10,  # Earnings growth (higher is better)
        '104C': 10,  # Cost of living (lower is better)
        '105C': 5,   # Office worker ratio (higher is better)
        '106D': 10,  # Weekly hours (higher is better)
        '200B': 10,  # Permits growth (higher is better)
        '201': 10,   # HPI growth (higher is better)
        '202': 10,   # PSF growth (higher is better)
        '204A': 5,   # Days on market (lower is better)
    }
    
    # Calculate percentile scores for each metro
    print("\nSTEP 4: Calculating percentile scores...")
    
    results = []
    
    for i, metro in enumerate(all_metros):
        metro_name = metro['metro_name']
        rank = metro.get('rank', i + 1)
        primary_city = metro.get('primary_city', '')
        data = metro['data']
        
        # Extract values
        unemp = data.get('unemployment_rate', {}).get('latest_value')
        lfp = data.get('civilian_labor_force', {}).get('latest_value')
        earnings_yoy = data.get('hourly_earnings', {}).get('yoy_change', {}).get('pct_change')
        col_score = calculate_col_final_score(metro, all_metros, col_component2_all, col_component3_all)
        owr = owr_scores_all.get(metro_name)
        weekly_hours = data.get('weekly_hours', {}).get('latest_value')
        permits_yoy = data.get('building_permits', {}).get('3month_avg_yoy', {}).get('pct_change')  # SMOOTHED 3-month YoY
        hpi_yoy = data.get('home_price_index', {}).get('yoy_change', {}).get('pct_change')
        psf_yoy = data.get('price_per_sqft', {}).get('3month_avg_yoy', {}).get('pct_change')  # SMOOTHED 3-month YoY
        days = data.get('median_days_on_market', {}).get('latest_value')
        
        # Calculate percentile scores
        percentiles = {
            '101A': calculate_percentile_score(unemp, metrics_data['101A'], invert=True) if unemp else 50,
            '102A': calculate_percentile_score(lfp, metrics_data['102A'], invert=False) if lfp else 50,
            '103B': calculate_percentile_score(earnings_yoy, metrics_data['103B'], invert=False) if earnings_yoy is not None else 50,
            '104C': calculate_percentile_score(col_score, metrics_data['104C'], invert=True) if col_score else 50,  # Lower COL = better
            '105C': calculate_percentile_score(owr, metrics_data['105C'], invert=False) if owr is not None else 50,  # Higher OWR score = better
            '106D': calculate_percentile_score(weekly_hours, metrics_data['106D'], invert=False) if weekly_hours else 50,
            '200B': calculate_percentile_score(permits_yoy, metrics_data['200B'], invert=False) if permits_yoy is not None else 50,
            '201': calculate_percentile_score(hpi_yoy, metrics_data['201'], invert=False) if hpi_yoy is not None else 50,
            '202': calculate_percentile_score(psf_yoy, metrics_data['202'], invert=False) if psf_yoy is not None else 50,
            '204A': calculate_percentile_score(days, metrics_data['204A'], invert=True) if days else 50,  # Fewer days = better
        }
        
        # Calculate weighted percentile score
        total_weight = sum(weights.values())
        weighted_percentile = sum(percentiles[code] * weights[code] for code in weights) / total_weight
        weighted_score = int(round(weighted_percentile))
        
        # Assign grade based on percentile
        if weighted_percentile >= 90:
            grade_letter, emoji, description = "A+", "🚀", "Excellent"
        elif weighted_percentile >= 80:
            grade_letter, emoji, description = "A", "✅", "Very Good"
        elif weighted_percentile >= 70:
            grade_letter, emoji, description = "A-", "👍", "Good"
        elif weighted_percentile >= 60:
            grade_letter, emoji, description = "B+", "📈", "Above Average"
        elif weighted_percentile >= 50:
            grade_letter, emoji, description = "B", "➡️", "Average"
        elif weighted_percentile >= 40:
            grade_letter, emoji, description = "B-", "⚠️", "Below Average"
        elif weighted_percentile >= 30:
            grade_letter, emoji, description = "C+", "📉", "Poor"
        elif weighted_percentile >= 20:
            grade_letter, emoji, description = "C", "⛔", "Very Poor"
        elif weighted_percentile >= 10:
            grade_letter, emoji, description = "C-", "🚨", "Critical"
        else:
            grade_letter, emoji, description = "D", "💥", "Emergency"
        
        results.append({
            "metro_name": metro_name,
            "rank": rank,
            "primary_city": primary_city,
            "raw_values": {
                "101A_unemployment": round(unemp, 2) if unemp else None,
                "102A_lfp": round(lfp, 2) if lfp else None,
                "103B_earnings_yoy": round(earnings_yoy, 2) if earnings_yoy is not None else None,
                "104C_col": round(col_score, 2) if col_score else None,
                "105C_owr": round(owr, 2) if owr is not None else None,
                "106D_weekly_hours": round(weekly_hours, 1) if weekly_hours else None,
                "200B_permits_yoy": round(permits_yoy, 2) if permits_yoy is not None else None,
                "201_hpi_yoy": round(hpi_yoy, 2) if hpi_yoy is not None else None,
                "202_psf_yoy": round(psf_yoy, 2) if psf_yoy is not None else None,
                "204A_days_on_market": round(days, 0) if days else None,
            },
            "percentile_scores": {code: round(p, 1) for code, p in percentiles.items()},
            "scores_100": {code: int(round(p)) for code, p in percentiles.items()},
            "weighted_percentile": round(weighted_percentile, 1),
            "weighted_score": weighted_score,
            "grade": {
                "letter": grade_letter,
                "emoji": emoji,
                "description": description,
                "percentile": round(weighted_percentile, 1)
            },
            "grade_display": f"{emoji} {grade_letter}"
        })
    
    print(f"✓ Calculated percentile scores for {len(results)} metros")
    
    # Create output
    output = {
        "calculation_timestamp": datetime.now().isoformat(),
        "calculation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version": "4.2",
        "scoring_method": "Percentile-Based (Rank Order)",
        "rubric": "10-Metric Percentile System with 3-Component COL, 2-Component OWR, and Smoothed Metrics",
        "note": "Percentile scoring: Score of 75 = Better than 75% of metros. 105C OWR uses YoY growth (3pts) + absolute % (2pts). 104C COL uses absolute affordability (3pts) + direction (4pts) + volatility (3pts). 200B Building Permits and 202 PSF both use 3-month average YoY (smoothed).",
        "weight_configuration": weights,
        "score_codes": {
            "101A": "unemployment_rate (15)",
            "102A": "labor_force_participation (15)",
            "103B": "hourly_earnings_yoy (10)",
            "104C": "cost_of_living_3component (10)",
            "105C": "office_worker_ratio_2component (5)",
            "106D": "weekly_hours (10)",
            "200B": "building_permits_3month_smoothed_yoy (10)",
            "201": "home_price_index_yoy (10)",
            "202": "price_per_sqft_3month_smoothed_yoy (10)",
            "204A": "median_days_on_market (5)",
        },
        "metros": results
    }
    
    return output


# ============================================================================
# STEP 4: CREATE EXCEL FILE WITH RESULTS
# ============================================================================

def create_excel_from_metrics(output_data):
    """Create Excel file with all metrics organized in 5 sheets"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    
    print("\nSTEP 5: Creating Excel file...")
    
    # Create workbook
    wb = Workbook()
    wb.remove(wb.active)
    
    # Define styles
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Color mapping for grades
    grade_colors = {
        'A+': 'C6EFCE', 'A': 'C6EFCE', 'A-': 'D4EDDA',
        'B+': 'D1E7DD', 'B': 'E2F0E1', 'B-': 'FFF2CC',
        'C+': 'FFEB9C', 'C': 'FFE699', 'C-': 'F8CBAD', 'D': 'F4B084'
    }
    
    def style_cell(cell, fill_color=None, bold=False, center=False):
        cell.border = border
        if fill_color:
            cell.fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")
        if bold:
            cell.font = Font(bold=True)
        if center:
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    
    # ========== SHEET 1: SUMMARY ==========
    ws_summary = wb.create_sheet("Summary", 0)
    
    headers = ['Rank', 'Metro Name', 'Primary City', 'Weighted Score', 'Grade', 'Percentile', 'Description']
    for col, header in enumerate(headers, 1):
        cell = ws_summary.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        style_cell(cell, center=True)
    
    sorted_metros = sorted(output_data['metros'], key=lambda x: x['weighted_score'], reverse=True)
    
    for row, metro in enumerate(sorted_metros, 2):
        ws_summary.cell(row=row, column=1, value=metro['rank'])
        ws_summary.cell(row=row, column=2, value=metro['metro_name'])
        ws_summary.cell(row=row, column=3, value=metro['primary_city'])
        ws_summary.cell(row=row, column=4, value=metro['weighted_score'])
        ws_summary.cell(row=row, column=5, value=metro['grade']['letter'])
        ws_summary.cell(row=row, column=6, value=metro['grade']['percentile'])
        ws_summary.cell(row=row, column=7, value=metro['grade']['description'])
        
        grade_color = grade_colors.get(metro['grade']['letter'], 'FFFFFF')
        for col in range(1, len(headers) + 1):
            cell = ws_summary.cell(row=row, column=col)
            style_cell(cell, fill_color=grade_color)
            if col == 4:
                cell.font = Font(bold=True)
            if col in [1, 4, 6]:
                cell.alignment = Alignment(horizontal='center')
    
    ws_summary.column_dimensions['A'].width = 8
    ws_summary.column_dimensions['B'].width = 35
    ws_summary.column_dimensions['C'].width = 18
    ws_summary.column_dimensions['D'].width = 15
    ws_summary.column_dimensions['E'].width = 10
    ws_summary.column_dimensions['F'].width = 12
    ws_summary.column_dimensions['G'].width = 15
    
    # ========== SHEET 2: METRIC SCORES ==========
    ws_scores = wb.create_sheet("Metric Scores", 1)
    
    metric_codes = ['101A', '102A', '103B', '104C', '105C', '106D', '200B', '201', '202', '204A']
    metric_names = {
        '101A': 'Unemployment', '102A': 'LFP', '103B': 'Earnings YoY', '104C': 'COL',
        '105C': 'Office Workers', '106D': 'Weekly Hours', '200B': 'Permits YoY',
        '201': 'HPI YoY', '202': 'PSF YoY', '204A': 'Days on Market'
    }
    
    headers_scores = ['Metro Name', 'Weighted Score'] + [f"{code}\n({metric_names[code]})" for code in metric_codes]
    for col, header in enumerate(headers_scores, 1):
        cell = ws_scores.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        style_cell(cell, center=True)
    
    for row, metro in enumerate(sorted_metros, 2):
        ws_scores.cell(row=row, column=1, value=metro['metro_name'])
        ws_scores.cell(row=row, column=2, value=metro['weighted_score'])
        style_cell(ws_scores.cell(row=row, column=2), bold=True)
        
        for col, code in enumerate(metric_codes, 3):
            score = metro['scores_100'].get(code)
            cell = ws_scores.cell(row=row, column=col, value=score)
            style_cell(cell, center=True)
            if score:
                color = 'C6EFCE' if score >= 70 else ('FFF2CC' if score >= 50 else 'F8CBAD')
                cell.fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
    
    ws_scores.column_dimensions['A'].width = 35
    ws_scores.column_dimensions['B'].width = 15
    for col in range(3, len(metric_codes) + 3):
        ws_scores.column_dimensions[get_column_letter(col)].width = 14
    
    # ========== SHEET 3: RAW VALUES ==========
    ws_raw = wb.create_sheet("Raw Values", 2)
    
    raw_metric_names = {
        '101A_unemployment': 'Unemployment %', '102A_lfp': 'LFP %',
        '103B_earnings_yoy': 'Earnings YoY %', '104C_col': 'COL Score',
        '105C_owr': 'Office Worker %', '106D_weekly_hours': 'Weekly Hours',
        '200B_permits_yoy': 'Permits YoY %', '201_hpi_yoy': 'HPI YoY %',
        '202_psf_yoy': 'PSF YoY %', '204A_days_on_market': 'Days on Market'
    }
    
    raw_keys = list(raw_metric_names.keys())
    headers_raw = ['Metro Name', 'Score/Grade'] + [raw_metric_names[k] for k in raw_keys]
    
    for col, header in enumerate(headers_raw, 1):
        cell = ws_raw.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        style_cell(cell, center=True)
    
    for row, metro in enumerate(sorted_metros, 2):
        ws_raw.cell(row=row, column=1, value=metro['metro_name'])
        score_grade = f"{metro['weighted_score']} ({metro['grade']['letter']})"
        cell = ws_raw.cell(row=row, column=2, value=score_grade)
        style_cell(cell, bold=True, center=True)
        
        for col, key in enumerate(raw_keys, 3):
            value = metro['raw_values'].get(key)
            cell = ws_raw.cell(row=row, column=col, value=value)
            style_cell(cell, center=True)
    
    ws_raw.column_dimensions['A'].width = 35
    ws_raw.column_dimensions['B'].width = 15
    for col in range(3, len(raw_keys) + 3):
        ws_raw.column_dimensions[get_column_letter(col)].width = 16
    
    # ========== SHEET 4: BY RANK ==========
    ws_rank = wb.create_sheet("By Rank", 3)
    
    by_rank = sorted(output_data['metros'], key=lambda x: x['rank'])
    headers_rank = ['Rank', 'Metro Name', 'Primary City', 'Weighted Score', 'Grade', 'Percentile', 
                    'Unemployment', 'LFP %', 'Earnings YoY', 'COL Score']
    
    for col, header in enumerate(headers_rank, 1):
        cell = ws_rank.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        style_cell(cell, center=True)
    
    for row, metro in enumerate(by_rank, 2):
        ws_rank.cell(row=row, column=1, value=metro['rank'])
        ws_rank.cell(row=row, column=2, value=metro['metro_name'])
        ws_rank.cell(row=row, column=3, value=metro['primary_city'])
        ws_rank.cell(row=row, column=4, value=metro['weighted_score'])
        ws_rank.cell(row=row, column=5, value=metro['grade']['letter'])
        ws_rank.cell(row=row, column=6, value=metro['grade']['percentile'])
        ws_rank.cell(row=row, column=7, value=metro['raw_values']['101A_unemployment'])
        ws_rank.cell(row=row, column=8, value=metro['raw_values']['102A_lfp'])
        ws_rank.cell(row=row, column=9, value=metro['raw_values']['103B_earnings_yoy'])
        ws_rank.cell(row=row, column=10, value=metro['raw_values']['104C_col'])
        
        grade_color = grade_colors.get(metro['grade']['letter'], 'FFFFFF')
        for col in range(1, len(headers_rank) + 1):
            cell = ws_rank.cell(row=row, column=col)
            style_cell(cell, fill_color=grade_color)
            if col in [1, 4, 6, 7, 8, 9, 10]:
                cell.alignment = Alignment(horizontal='center')
    
    ws_rank.column_dimensions['A'].width = 8
    ws_rank.column_dimensions['B'].width = 35
    ws_rank.column_dimensions['C'].width = 18
    for col in range(4, 11):
        ws_rank.column_dimensions[get_column_letter(col)].width = 14
    
    # ========== SHEET 5: TOP VS BOTTOM ==========
    ws_compare = wb.create_sheet("Top vs Bottom", 4)
    
    ws_compare.cell(row=1, column=1, value="TOP 10 METROS")
    top_header = ws_compare.cell(row=1, column=1)
    top_header.fill = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")
    top_header.font = Font(bold=True, color="FFFFFF", size=12)
    
    ws_compare.cell(row=1, column=8, value="BOTTOM 10 METROS")
    bottom_header = ws_compare.cell(row=1, column=8)
    bottom_header.fill = PatternFill(start_color="FF6B6B", end_color="FF6B6B", fill_type="solid")
    bottom_header.font = Font(bold=True, color="FFFFFF", size=12)
    
    headers_compare = ['#', 'Metro', 'Score', 'Grade', '#', 'Metro', 'Score', 'Grade']
    for col, header in enumerate(headers_compare[:4], 1):
        cell = ws_compare.cell(row=2, column=col, value=header)
        cell.fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
        style_cell(cell, bold=True, center=True)
    
    for col, header in enumerate(headers_compare[4:], 5):
        cell = ws_compare.cell(row=2, column=col, value=header)
        cell.fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
        style_cell(cell, bold=True, center=True)
    
    for idx, metro in enumerate(sorted_metros[:10], 1):
        row = idx + 2
        ws_compare.cell(row=row, column=1, value=idx)
        ws_compare.cell(row=row, column=2, value=metro['metro_name'])
        ws_compare.cell(row=row, column=3, value=metro['weighted_score'])
        ws_compare.cell(row=row, column=4, value=metro['grade']['letter'])
        
        for col in range(1, 5):
            cell = ws_compare.cell(row=row, column=col)
            cell.fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
            style_cell(cell, center=True)
    
    for idx, metro in enumerate(sorted_metros[-10:], 1):
        row = idx + 2
        ws_compare.cell(row=row, column=5, value=idx)
        ws_compare.cell(row=row, column=6, value=metro['metro_name'])
        ws_compare.cell(row=row, column=7, value=metro['weighted_score'])
        ws_compare.cell(row=row, column=8, value=metro['grade']['letter'])
        
        for col in range(5, 9):
            cell = ws_compare.cell(row=row, column=col)
            cell.fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
            style_cell(cell, center=True)
    
    for col in range(1, 9):
        ws_compare.column_dimensions[get_column_letter(col)].width = 18
    
    # Save workbook
    excel_path = SCRIPT_DIR / 'Economic_Metrics_All_Metros.xlsx'
    wb.save(excel_path)
    print(f"✓ Excel file created: {excel_path}")
    return excel_path


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main entry point"""
    output = calculate_metrics()
    
    if not output:
        print("\n❌ Failed to calculate metrics")
        return
    
    # Save JSON output
    json_path = SCRIPT_DIR / 'calculated_metrics_reconciled.json'
    
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)
        print(f"\n✓ JSON saved to: {json_path}")
    except Exception as e:
        print(f"\n❌ ERROR saving JSON: {e}")
        return
    
    # Create Excel file (YOUR RECEIPT!)
    try:
        excel_path = create_excel_from_metrics(output)
    except Exception as e:
        print(f"\n❌ ERROR creating Excel file: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Show summary
    print("\n" + "=" * 80)
    print("SUMMARY - PERCENTILE-BASED SCORING WITH 3-COMPONENT COL & 2-COMPONENT OWR")
    print("=" * 80)
    
    sorted_metros = sorted(output['metros'], key=lambda x: x['weighted_score'], reverse=True)
    
    print("\nTOP 10 METROS (by percentile score):")
    for i, metro in enumerate(sorted_metros[:10], 1):
        col_score = metro['raw_values']['104C_col']
        owr_score = metro['raw_values']['105C_owr']
        percentile = metro['weighted_percentile']
        print(f"  {i:2d}. {metro['metro_name']:<40} {metro['grade_display']:8s} ({percentile:5.1f}th percentile) | COL: {col_score:.2f} OWR: {owr_score:.2f}")
    
    print("\nBOTTOM 5 METROS:")
    for i, metro in enumerate(sorted_metros[-5:], 1):
        col_score = metro['raw_values']['104C_col']
        owr_score = metro['raw_values']['105C_owr']
        percentile = metro['weighted_percentile']
        print(f"  {i}. {metro['metro_name']:<40} {metro['grade_display']:8s} ({percentile:5.1f}th percentile) | COL: {col_score:.2f} OWR: {owr_score:.2f}")
    
    print("\n" + "=" * 80)
    print("📊 OUTPUT FILES GENERATED")
    print("=" * 80)
    print(f"✓ JSON Data ......... calculated_metrics_reconciled.json")
    print(f"✓ Excel Receipt ..... Economic_Metrics_All_Metros.xlsx")
    print("\n📈 Your Excel Receipt includes:")
    print("   • Sheet 1: Summary (all metros sorted by score)")
    print("   • Sheet 2: Metric Scores (individual 0-100 scores)")
    print("   • Sheet 3: Raw Values (actual metrics for verification)")
    print("   • Sheet 4: By Rank (original MSA ranking)")
    print("   • Sheet 5: Top vs Bottom (leaders vs laggards)")
    print("\n✅ READY FOR LINKEDIN CONTENT GENERATION\n")
    print("📊 Scoring Changes in V4.2 (V6):")
    print("  • 202 PSF: Now uses 3-month average YoY (smoothed)")
    print("    - Reduces monthly volatility noise")
    print("    - More stable trend indicator")
    print("  • 200B Permits: Uses 3-month average YoY (smoothed)")
    print("    - Reduces monthly volatility noise")
    print("  • 105C OWR: 2-component scoring")
    print("    - Component 1: YoY growth (3-mo avg vs prev year) = 3 points")
    print("    - Component 2: Absolute % office workers = 2 points")
    print("  • 104C COL: Updated weighting")
    print("    - Component 1: Absolute affordability = 3 points")
    print("    - Component 2: Direction of change = 4 points")
    print("    - Component 3: Volatility = 3 points\n")


if __name__ == '__main__':
    main()
