#!/usr/bin/env python3
"""
Unified Economic Data Collection Script - FIXED TO RETURN ALL OBSERVATIONS
===========================================================================
Pulls BOTH national metrics AND all 50 metros in a single run

Structure:
1. First: Pull 2 national metrics (AWHAETP, MEDDAYONMARUS)
2. Then: Pull all 50 metros × 11 indicators = 550 metro calls
3. Output: Combined JSON with national benchmarks + all metro data
           NOW INCLUDES ALL 15 OBSERVATIONS per metric for historical analysis

FRED API Rate Limits:
- 120 requests per minute (hard limit)
- Script uses 1.5 second delay between calls = ~40 calls/minute (safe)
- Total calls: 2 (national) + 550 (metros) = 552 API calls
- Estimated runtime: ~14-16 minutes

Before running:
1. Create a .env file with: FRED_API_KEY=your_key_here
2. Ensure metro_data_config_v3.json is in the same directory
3. Have 15-20 minutes available
"""

import json
import requests
import time
from datetime import datetime
from dotenv import load_dotenv
import os
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# Get FRED API key from environment variable
FRED_API_KEY = os.getenv('FRED_API_KEY')

# FRED API base URL
FRED_API_BASE = "https://api.stlouisfed.org/fred/series/observations"

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent

# Rate limiting configuration - CONSERVATIVE AND SAFE
DELAY_BETWEEN_CALLS = 1.5  # seconds - safely under 120 req/min limit
MAX_RETRIES = 3
RETRY_BACKOFF = 2  # exponential backoff multiplier


class RateLimitedAPIClient:
    """Safe FRED API client with intelligent rate limiting"""
    
    def __init__(self):
        self.last_request_time = 0
        self.rate_limit_delay = DELAY_BETWEEN_CALLS
        self.consecutive_rate_limits = 0
        
    def wait_for_rate_limit(self):
        """Ensure we don't exceed FRED's rate limit"""
        time_since_last = time.time() - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def get_data(self, series_id, metric_name, retry_count=0):
        """
        Safely pull data from FRED API with rate limiting
        NOW RETURNS ALL 15 OBSERVATIONS
        
        Args:
            series_id: FRED series code
            metric_name: Human-readable name for logging
            retry_count: Current retry attempt
        
        Returns:
            Dictionary with all observations, or None if error
        """
        # Wait to ensure we don't exceed rate limit
        self.wait_for_rate_limit()
        
        if not FRED_API_KEY:
            return None
        
        # Build API request parameters
        params = {
            'series_id': series_id,
            'api_key': FRED_API_KEY,
            'file_type': 'json',
            'sort_order': 'desc',
            'limit': 15
        }
        
        try:
            response = requests.get(FRED_API_BASE, params=params, timeout=10)
            
            # Handle rate limiting with exponential backoff
            if response.status_code == 429:
                self.consecutive_rate_limits += 1
                if retry_count < MAX_RETRIES:
                    wait_time = DELAY_BETWEEN_CALLS * (RETRY_BACKOFF ** retry_count)
                    print(f"   ⚠️  Rate limited. Waiting {wait_time:.1f}s before retry...")
                    time.sleep(wait_time)
                    return self.get_data(series_id, metric_name, retry_count + 1)
                else:
                    print(f"   ❌ Max retries exceeded for rate limiting")
                    return None
            
            # Reset rate limit counter on success
            if response.status_code == 200:
                self.consecutive_rate_limits = 0
            
            # Handle other HTTP errors
            if response.status_code == 400:
                print(f"   ❌ Bad request - Series ID '{series_id}' may be invalid")
                return None
            elif response.status_code != 200:
                print(f"   ❌ HTTP {response.status_code}")
                return None
            
            # Parse JSON response
            data = response.json()
            
            # Check if we got observations
            if 'observations' not in data or len(data['observations']) == 0:
                print(f"   ⚠️  No data available")
                return None
            
            # Return ALL observations for historical processing
            observations = data['observations']
            
            return {
                'observations': observations,
                'count': len(observations),
                'series_id': series_id,
                'metric_name': metric_name
            }
            
        except requests.exceptions.Timeout:
            print(f"   ❌ Timeout")
            return None
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Request error: {str(e)}")
            return None
        except Exception as e:
            print(f"   ❌ Unexpected error: {str(e)}")
            return None


def load_metro_config():
    """Load the metro configuration JSON file"""
    config_path = SCRIPT_DIR / 'metro_data_config_v3.json'
    
    if not config_path.exists():
        print(f"❌ ERROR: Configuration file not found at: {config_path}")
        exit(1)
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    return config


def log_progress(message, filename='collection_progress.log'):
    """Log progress to both console and file"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    
    with open(SCRIPT_DIR / filename, 'a', encoding='utf-8') as f:
        f.write(log_message + '\n')


def pull_national_metrics(api_client, config):
    """
    Pull national-level metrics for comparison benchmarks
    
    Returns:
        Dictionary with national metrics data
    """
    print("\n" + "=" * 80)
    print("STEP 1: PULLING NATIONAL METRICS")
    print("=" * 80)
    print()
    
    national_metrics = config.get('_national_metrics', {})
    metric_items = {k: v for k, v in national_metrics.items() if k != 'description'}
    
    national_data = {}
    
    for metric_key, metric_data in metric_items.items():
        fred_code = metric_data.get('fred_code')
        description = metric_data.get('description')
        
        print(f"Pulling {metric_key}...")
        print(f"  FRED Code: {fred_code}")
        
        result = api_client.get_data(fred_code, metric_key)
        
        if result:
            national_data[metric_key] = result
            print(f"  ✅ {result['metric_name']}: {result['count']} observations retrieved")
        else:
            print(f"  ❌ Failed to retrieve {metric_key}")
        
        print()
    
    print(f"National Metrics Summary: {len(national_data)}/{len(metric_items)} retrieved")
    print()
    
    return national_data


def estimate_time_remaining(current_metro, total_metros):
    """Estimate remaining time based on current progress"""
    metros_remaining = total_metros - current_metro
    minutes_per_metro = (DELAY_BETWEEN_CALLS * 11) / 60  # 11 metrics per metro
    minutes_remaining = metros_remaining * minutes_per_metro
    return minutes_remaining


def pull_metro_data(api_client, config):
    """
    Pull all 50 metro economic data - NOW WITH ALL 15 OBSERVATIONS
    
    Returns:
        List of metro results
    """
    print("\n" + "=" * 80)
    print("STEP 2: PULLING ALL 50 METROS")
    print("=" * 80)
    print()
    
    metros = config.get('metros', [])
    
    print(f"📊 Total Metros to Pull: {len(metros)}")
    print(f"📈 Metrics per Metro: 11")
    print(f"📡 Total API Calls: {len(metros) * 11}")
    print(f"⏱️  Estimated Time: ~{(len(metros) * 11 * DELAY_BETWEEN_CALLS) / 60:.1f} minutes")
    print(f"💾 Data: 15 observations per metric (for historical analysis)")
    print()
    
    all_results = []
    total_successful = 0
    total_failed = 0
    
    start_time = time.time()
    
    for i, metro in enumerate(metros, 1):
        rank = metro['rank']
        metro_name = metro['msa_name']
        primary_city = metro['primary_city']
        
        # Progress indicator
        progress_pct = (i / len(metros)) * 100
        elapsed_minutes = (time.time() - start_time) / 60
        remaining_minutes = estimate_time_remaining(i, len(metros))
        
        print(f"\n[{i:2d}/50 - {progress_pct:5.1f}%] Elapsed: {elapsed_minutes:5.1f}m | Est. Remaining: {remaining_minutes:5.1f}m")
        print(f"Rank #{rank}: {primary_city} ({metro_name})")
        
        results = {}
        successful = 0
        failed = 0
        
        fred_codes = metro['fred_codes']
        metrics = [
            ('unemployment_rate', 'Unemployment Rate'),
            ('civilian_labor_force', 'Civilian Labor Force'),
            ('all_employees', 'All Employees'),
            ('hourly_earnings', 'Hourly Earnings'),
            ('weekly_hours', 'Weekly Hours'),
            ('office_workers', 'Office Workers'),
            ('building_permits', 'Building Permits'),
            ('home_price_index', 'Home Price Index'),
            ('price_per_sqft', 'Price per Sqft'),
            ('housing_price', 'Median Housing Price'),
            ('median_days_on_market', 'Median Days on Market'),
        ]
        
        for metric_key, metric_name in metrics:
            if metric_key not in fred_codes:
                print(f"   ⚠️  Metric {metric_key} not in config")
                failed += 1
                continue
            
            code = fred_codes[metric_key]['code']
            result = api_client.get_data(code, metric_name)
            
            if result:
                results[metric_key] = result
                successful += 1
                print(f"   ✅ {metric_name} ({result['count']} obs)")
            else:
                failed += 1
                print(f"   ❌ {metric_name} (Code: {code})")
        
        total_successful += successful
        total_failed += failed
        
        metro_result = {
            'rank': rank,
            'metro_name': metro_name,
            'primary_city': primary_city,
            'successful': successful,
            'failed': failed,
            'data': results
        }
        all_results.append(metro_result)
        
        running_total = total_successful + total_failed
        success_rate = (total_successful / running_total * 100) if running_total > 0 else 0
        print(f"  Result: {successful}/11 successful | Running Total: {total_successful}/{running_total} ({success_rate:.1f}%)")
    
    elapsed_time = time.time() - start_time
    elapsed_minutes = elapsed_time / 60
    
    print("\n" + "=" * 80)
    print("METRO DATA COLLECTION SUMMARY")
    print("=" * 80)
    total_calls = len(metros) * 11
    success_rate = (total_successful / total_calls * 100) if total_calls > 0 else 0
    print(f"✅ Total Successful: {total_successful}/{total_calls}")
    print(f"❌ Total Failed: {total_failed}/{total_calls}")
    print(f"📊 Success Rate: {success_rate:.1f}%")
    print(f"⏱️  Total Time: {elapsed_minutes:.1f} minutes")
    print()
    
    return all_results


def save_combined_results(national_data, metro_data):
    """Save combined national and metro data to JSON file"""
    
    output_data = {
        'collection_timestamp': datetime.now().isoformat(),
        'collection_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'note': 'Each metric now contains 15 observations for historical analysis',
        'national_metrics': national_data,
        'metros': metro_data,
        'summary': {
            'total_metros': len(metro_data),
            'national_metrics_collected': len(national_data),
            'observations_per_metric': 15,
            'total_metro_data_points': sum(len(m['data']) for m in metro_data),
            'total_metro_expected': len(metro_data) * 11
        }
    }
    
    # Save to JSON
    output_file = SCRIPT_DIR / 'economic_data_combined.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"✅ Combined data saved to: {output_file}")
    
    return output_file


def main():
    """Main execution"""
    print("\n" + "🌟" * 40)
    print("UNIFIED ECONOMIC DATA COLLECTION (FIXED - ALL OBSERVATIONS)")
    print("National Metrics + All 50 Metros + 15 Observations per Metric")
    print("🌟" * 40 + "\n")
    
    # Check API key
    if not FRED_API_KEY:
        print("❌ ERROR: FRED_API_KEY not found!")
        print()
        print("Please set up your API key:")
        print("  Create a .env file with: FRED_API_KEY=your_key_here")
        print()
        print("Get your key at: https://fred.stlouisfed.org/docs/api/")
        return
    
    print("✓ FRED_API_KEY loaded successfully")
    print(f"  Key: {FRED_API_KEY[:10]}...{FRED_API_KEY[-10:]}")
    print()
    
    # Load configuration
    print("Loading configuration...")
    config = load_metro_config()
    metros = config.get('metros', [])
    print(f"✓ Loaded {len(metros)} metros from config")
    print()
    
    # Clear progress log
    progress_file = SCRIPT_DIR / 'collection_progress.log'
    progress_file.unlink(missing_ok=True)
    
    log_progress("=" * 80)
    log_progress("UNIFIED ECONOMIC DATA COLLECTION (FIXED)")
    log_progress("=" * 80)
    log_progress(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_progress(f"FRED API Rate Limit: 120 requests/minute")
    log_progress(f"Script Delay: {DELAY_BETWEEN_CALLS} seconds between calls")
    log_progress(f"Expected Runtime: ~14-16 minutes")
    log_progress(f"Total API Calls: 552 (2 national + 550 metros)")
    log_progress(f"Observations per metric: 15 (for historical analysis)")
    log_progress("")
    
    # Initialize API client
    api_client = RateLimitedAPIClient()
    
    # Pull national metrics
    national_data = pull_national_metrics(api_client, config)
    
    # Pull metro data
    metro_data = pull_metro_data(api_client, config)
    
    # Save combined results
    print("\n" + "=" * 80)
    print("SAVING RESULTS")
    print("=" * 80)
    print()
    
    output_file = save_combined_results(national_data, metro_data)
    
    # Final summary
    print("\n" + "=" * 80)
    print("COLLECTION COMPLETE")
    print("=" * 80)
    print()
    
    total_metro_calls = len(metro_data) * 11
    metro_success = sum(len(m['data']) for m in metro_data)
    
    print(f"📊 National Metrics: {len(national_data)}/2 collected")
    print(f"📊 Metro Data: {metro_success}/{total_metro_calls}")
    print(f"📊 Total Success: {len(national_data) + metro_success}/{len(national_data) + total_metro_calls}")
    print()
    print(f"💾 Each metric contains 15 observations (not just latest value)")
    print(f"✅ Output file: {output_file}")
    print(f"📄 Progress log: {progress_file}")
    print()
    print("Ready for next step! 🚀")
    print("Next: Run process_historical_data.py")
    print()
    
    log_progress("")
    log_progress("=" * 80)
    log_progress("COLLECTION COMPLETE")
    log_progress("=" * 80)
    log_progress(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_progress(f"National Metrics Collected: {len(national_data)}")
    log_progress(f"Metro Data Points Collected: {metro_success}")


if __name__ == '__main__':
    main()
