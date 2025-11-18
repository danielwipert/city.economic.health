#!/usr/bin/env python3
"""
Process Historical Economic Data - V2 (11 Metrics)
==================================================
Processes 15 observations per metric and calculates:

EMPLOYMENT METRICS (65% weight):
- 101A: Unemployment Rate (MSA Average)
- 102A: Labor Force Participation Rate (MSA Average) 
- 103B: Hourly Earnings (Year over Year)
- 104C: Cost of Living (MSA Average) - CALCULATED: Price/Sqft ÷ Hourly Earnings
- 105C: Office Worker Ratio (MSA Average) - CALCULATED: Office Workers ÷ Civilian Pop
- 106D: Weekly Hours (National Average comparison)

HOUSING METRICS (35% weight):
- 200B: Building Permits (3-Month Year over Year)
- 201: Home Price Index Growth (Year over Year)
- 202: Price per Sqft Growth (3-Month Year over Year)
- 203: Housing Price Growth (3-Month Year over Year) - COLLECT ONLY (weight=0)
- 204A: Median Days on Market (MSA Average)

Input: economic_data_combined.json (from pull_economic_data_unified_FIXED.py)
Output: processed_economic_data_v2.json
"""

import json
from pathlib import Path
from datetime import datetime
from statistics import mean, stdev
from typing import Optional

SCRIPT_DIR = Path(__file__).parent


class HistoricalDataProcessor:
    """Process raw FRED observations into 11-metric scorecard"""
    
    def __init__(self):
        self.raw_data = None
        self.processed_data = {}
        self.national_metrics = {}
        self.config = None
        self.metro_values = {}  # For calculating MSA averages
    
    def load_raw_data(self, input_file='economic_data_combined.json'):
        """Load the combined economic data from pull_economic_data_unified_FIXED.py"""
        input_path = SCRIPT_DIR / input_file
        
        if not input_path.exists():
            print(f"❌ ERROR: Input file not found at: {input_path}")
            return False
        
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                self.raw_data = json.load(f)
            print(f"✅ Loaded raw data from: {input_file}")
            return True
        except Exception as e:
            print(f"❌ ERROR loading data: {str(e)}")
            return False
    
    def load_config(self, config_file='metro_data_config_v3.json'):
        """Load metro configuration with Census population data"""
        config_path = SCRIPT_DIR / config_file
        
        if not config_path.exists():
            print(f"❌ ERROR: Config file not found at: {config_path}")
            return False
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            print(f"✅ Loaded config from: {config_file}")
            return True
        except Exception as e:
            print(f"❌ ERROR loading config: {str(e)}")
            return False
    
    def get_civilian_population(self, metro_name: str) -> Optional[float]:
        """Get civilian population for a metro from config"""
        if not self.config:
            return None
        
        metros = self.config.get('metros', [])
        for metro in metros:
            if metro.get('msa_name') == metro_name:
                return metro.get('civilian_population')
        
        return None
    
    def safe_float(self, value) -> Optional[float]:
        """Safely convert value to float"""
        if value is None or value == '.' or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def calculate_3month_average(self, observations):
        """Average of last 3 observations"""
        if not observations or len(observations) < 3:
            return None
        
        last_3_values = []
        for i in range(3):
            value = self.safe_float(observations[i].get('value'))
            if value is not None:
                last_3_values.append(value)
        
        return mean(last_3_values) if len(last_3_values) == 3 else None
    
    def calculate_yoy_change(self, observations):
        """Year-over-year change (current vs 12 months ago)"""
        if not observations or len(observations) < 13:
            return None
        
        current = self.safe_float(observations[0].get('value'))
        previous_year = self.safe_float(observations[12].get('value'))
        
        if current is None or previous_year is None or previous_year == 0:
            return None
        
        change = current - previous_year
        pct_change = (change / abs(previous_year)) * 100
        
        return {
            'current': round(current, 4),
            'change': round(change, 4),
            'pct_change': round(pct_change, 2)
        }
    
    def calculate_3month_avg_yoy(self, observations):
        """3-month average YoY (current 3-mo vs previous year 3-mo)"""
        if not observations or len(observations) < 15:
            return None
        
        current_3mo = self.calculate_3month_average(observations[:3])
        previous_3mo = self.calculate_3month_average(observations[12:15])
        
        if current_3mo is None or previous_3mo is None or previous_3mo == 0:
            return None
        
        change = current_3mo - previous_3mo
        pct_change = (change / abs(previous_3mo)) * 100
        
        return {
            'current_3mo': round(current_3mo, 4),
            'change': round(change, 4),
            'pct_change': round(pct_change, 2)
        }
    
    def get_latest_value(self, observations):
        """Get most recent observation"""
        if not observations:
            return None
        
        value = self.safe_float(observations[0].get('value'))
        return round(value, 4) if value is not None else None
    
    def process_metro_metric(self, metro_data, metric_key, metro_name=None):
        """Process a single metric for a metro"""
        if metric_key not in metro_data:
            return None
        
        metric_info = metro_data[metric_key]
        observations = metric_info.get('observations', [])
        
        if not observations:
            return None
        
        # Special handling for labor force participation rate (calculate from raw count)
        if metric_key == 'civilian_labor_force' and metro_name:
            civilian_pop = self.get_civilian_population(metro_name)
            if civilian_pop:
                return self._calculate_lfp_rate(observations, civilian_pop, metric_info)
        
        # Standard processing
        processed = {
            'latest_value': self.get_latest_value(observations),
            'latest_date': observations[0].get('date') if observations else None,
            'series_id': metric_info.get('series_id'),
            'metric_name': metric_info.get('metric_name'),
            '3month_average': self.calculate_3month_average(observations),
            'yoy_change': self.calculate_yoy_change(observations),
            '3month_avg_yoy': self.calculate_3month_avg_yoy(observations)
        }
        
        return processed
    
    def _calculate_lfp_rate(self, observations, civilian_pop, metric_info):
        """Calculate labor force participation rate as percentage"""
        if not observations or civilian_pop == 0:
            return None
        
        lfp_observations = []
        for obs in observations:
            labor_force = self.safe_float(obs.get('value'))
            if labor_force is not None and labor_force > 0:
                lfp_pct = (labor_force / civilian_pop) * 100
                lfp_observations.append({
                    'value': str(round(lfp_pct, 4)),
                    'date': obs.get('date')
                })
        
        if not lfp_observations:
            return None
        
        processed = {
            'latest_value': self.get_latest_value(lfp_observations),
            'latest_date': lfp_observations[0].get('date'),
            'series_id': metric_info.get('series_id'),
            'metric_name': 'Labor Force Participation Rate',
            '3month_average': self.calculate_3month_average(lfp_observations),
            'yoy_change': self.calculate_yoy_change(lfp_observations),
            '3month_avg_yoy': self.calculate_3month_avg_yoy(lfp_observations),
            'note': 'Calculated as (Civilian Labor Force / Civilian Population) × 100'
        }
        
        return processed
    
    def calculate_cost_of_living(self, price_sqft_metric, earnings_metric):
        """Calculate Cost of Living = Price/Sqft ÷ Hourly Earnings"""
        if not price_sqft_metric or not earnings_metric:
            return None
        
        price_latest = price_sqft_metric.get('latest_value')
        earnings_latest = earnings_metric.get('latest_value')
        
        if price_latest is None or earnings_latest is None or earnings_latest == 0:
            return None
        
        col_value = price_latest / earnings_latest
        
        # Calculate 3-month average
        price_3mo = price_sqft_metric.get('3month_average')
        earnings_3mo = earnings_metric.get('3month_average')
        col_3mo = (price_3mo / earnings_3mo) if (price_3mo and earnings_3mo and earnings_3mo != 0) else None
        
        # Calculate YoY if available
        price_yoy = price_sqft_metric.get('yoy_change')
        earnings_yoy = earnings_metric.get('yoy_change')
        col_yoy = None
        
        if price_yoy and earnings_yoy:
            price_prev = price_yoy.get('current') - price_yoy.get('change')
            earnings_prev = earnings_yoy.get('current') - earnings_yoy.get('change')
            
            if price_prev and earnings_prev and earnings_prev != 0:
                col_prev = price_prev / earnings_prev
                col_current = price_latest / earnings_latest
                col_change = col_current - col_prev
                col_pct = (col_change / col_prev * 100) if col_prev != 0 else None
                
                col_yoy = {
                    'current': round(col_current, 4),
                    'change': round(col_change, 4),
                    'pct_change': round(col_pct, 2) if col_pct else None
                }
        
        processed = {
            'latest_value': round(col_value, 4),
            'latest_date': price_sqft_metric.get('latest_date'),
            'series_id': None,
            'metric_name': 'Cost of Living',
            '3month_average': round(col_3mo, 4) if col_3mo else None,
            'yoy_change': col_yoy,
            'note': 'Calculated as (Price per Sqft / Hourly Earnings)'
        }
        
        return processed
    
    def calculate_office_worker_ratio(self, office_workers_metric, civilian_pop):
        """Calculate Office Worker Ratio = (Office Workers / Civilian Pop) × 100
        
        NOTE: FRED returns employment data in thousands of persons.
        We must multiply by 1000 to convert to actual employee count before calculating ratio.
        """
        if not office_workers_metric or civilian_pop is None or civilian_pop == 0:
            return None
        
        office_latest = office_workers_metric.get('latest_value')
        
        if office_latest is None:
            return None
        
        # FRED returns office_workers data in thousands, so multiply by 1000
        office_value = office_latest * 1000
        owr_value = (office_value / civilian_pop) * 100
        
        # Calculate 3-month average
        office_3mo = office_workers_metric.get('3month_average')
        owr_3mo = None
        if office_3mo:
            office_3mo_val = office_3mo * 1000  # Also in thousands
            owr_3mo = (office_3mo_val / civilian_pop) * 100
        
        # Calculate YoY
        office_yoy = office_workers_metric.get('yoy_change')
        owr_yoy = None
        
        if office_yoy:
            office_current = office_yoy.get('current')
            office_change = office_yoy.get('change')
            
            if office_current and office_change is not None:
                office_current_val = office_current * 1000  # In thousands
                office_change_val = office_change * 1000    # In thousands
                office_prev_val = office_current_val - office_change_val
                
                owr_current = (office_current_val / civilian_pop) * 100
                owr_prev = (office_prev_val / civilian_pop) * 100
                owr_change = owr_current - owr_prev
                owr_pct = (owr_change / owr_prev * 100) if owr_prev != 0 else None
                
                owr_yoy = {
                    'current': round(owr_current, 4),
                    'change': round(owr_change, 4),
                    'pct_change': round(owr_pct, 2) if owr_pct else None
                }
        
        processed = {
            'latest_value': round(owr_value, 4),
            'latest_date': office_workers_metric.get('latest_date'),
            'series_id': office_workers_metric.get('series_id'),
            'metric_name': 'Office Worker Ratio',
            '3month_average': round(owr_3mo, 4) if owr_3mo else None,
            'yoy_change': owr_yoy,
            'note': 'Calculated as (Office Workers × 1000 / Civilian Population) × 100'
        }
        
        return processed
    
    def process_all_metros(self):
        """Process all metros with 11 metrics"""
        print("\n" + "=" * 80)
        print("PROCESSING HISTORICAL DATA (11 METRICS)")
        print("=" * 80)
        print()
        
        metros = self.raw_data.get('metros', [])
        print(f"Processing {len(metros)} metros...\n")
        
        for i, metro in enumerate(metros, 1):
            rank = metro.get('rank')
            metro_name = metro.get('metro_name')
            primary_city = metro.get('primary_city')
            metro_raw_data = metro.get('data', {})
            civilian_pop = self.get_civilian_population(metro_name)
            
            print(f"[{i:2d}/{len(metros)}] Rank #{rank}: {primary_city}")
            
            processed_metrics = {}
            
            # Process standard metrics
            for metric_key in metro_raw_data.keys():
                result = self.process_metro_metric(metro_raw_data, metric_key, metro_name)
                if result:
                    processed_metrics[metric_key] = result
            
            # Calculate Cost of Living (104C)
            if 'price_per_sqft' in processed_metrics and 'hourly_earnings' in processed_metrics:
                col_result = self.calculate_cost_of_living(
                    processed_metrics['price_per_sqft'],
                    processed_metrics['hourly_earnings']
                )
                if col_result:
                    processed_metrics['cost_of_living'] = col_result
            
            # Calculate Office Worker Ratio (105C)
            if 'office_workers' in processed_metrics and civilian_pop:
                owr_result = self.calculate_office_worker_ratio(
                    processed_metrics['office_workers'],
                    civilian_pop
                )
                if owr_result:
                    processed_metrics['office_worker_ratio'] = owr_result
            
            # Store metro data
            processed_metro = {
                'rank': rank,
                'metro_name': metro_name,
                'primary_city': primary_city,
                'civilian_population': civilian_pop,
                'metrics_processed': len(processed_metrics),
                'data': processed_metrics
            }
            
            self.processed_data[metro_name] = processed_metro
        
        print(f"\n✅ Processed {len(self.processed_data)} metros")
        return True
    
    def calculate_msa_averages(self):
        """Calculate MSA averages for each metric"""
        print("\nCalculating MSA comparison benchmarks...")
        
        if not self.processed_data:
            print("❌ No processed data")
            return False
        
        # Metrics to average
        metrics_to_average = [
            'unemployment_rate', 'civilian_labor_force', 'hourly_earnings',
            'cost_of_living', 'office_worker_ratio', 'building_permits',
            'home_price_index', 'price_per_sqft', 'housing_price', 'median_days_on_market'
        ]
        
        for metric in metrics_to_average:
            values = []
            for metro_data in self.processed_data.values():
                if metric in metro_data['data']:
                    latest = metro_data['data'][metric].get('latest_value')
                    if latest is not None:
                        values.append(latest)
            
            if values:
                self.national_metrics[metric] = {
                    'msa_average': round(mean(values), 4),
                    'metros_with_data': len(values)
                }
        
        print(f"✅ Calculated MSA averages for {len(self.national_metrics)} metrics")
        return True
    
    def save_processed_data(self, output_file='processed_economic_data_v2.json'):
        """Save all processed data to JSON"""
        output_data = {
            'processing_timestamp': datetime.now().isoformat(),
            'processing_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'version': 2,
            'metrics_count': 11,
            'metrics_scored': 10,
            'metrics_collected_only': 1,
            'source_data': self.raw_data.get('collection_date'),
            'msa_averages': self.national_metrics,
            'metros': self.processed_data,
            'summary': {
                'total_metros_processed': len(self.processed_data),
                'total_metrics': len(self.national_metrics)
            }
        }
        
        output_path = SCRIPT_DIR / output_file
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2)
            print(f"✅ Processed data saved to: {output_path}")
            return output_path
        except Exception as e:
            print(f"❌ ERROR saving data: {str(e)}")
            return None


def main():
    """Main execution"""
    print("\n" + "🔄" * 40)
    print("HISTORICAL DATA PROCESSOR - V2 (11 METRICS)")
    print("🔄" * 40 + "\n")
    
    processor = HistoricalDataProcessor()
    
    # Load config
    print("STEP 1: Loading config with Census population data")
    print("-" * 80)
    if not processor.load_config():
        return
    print()
    
    # Load raw data
    print("STEP 2: Loading raw data from pull_economic_data_unified_FIXED.py")
    print("-" * 80)
    if not processor.load_raw_data():
        return
    print()
    
    # Process all metros
    print("STEP 3: Processing historical data for all metros")
    print("-" * 80)
    if not processor.process_all_metros():
        return
    print()
    
    # Calculate MSA averages
    print("STEP 4: Calculating MSA comparison benchmarks")
    print("-" * 80)
    if not processor.calculate_msa_averages():
        return
    print()
    
    # Save processed data
    print("STEP 5: Saving processed data")
    print("-" * 80)
    output_file = processor.save_processed_data()
    if not output_file:
        return
    print()
    
    print("\n" + "=" * 80)
    print("PROCESSING COMPLETE")
    print("=" * 80)
    print()
    print("✅ Ready for next step: calculate_metrics with 11-metric z-score system")
    print()


if __name__ == '__main__':
    main()
