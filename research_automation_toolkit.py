# ================================================
# Research Analytics Automation Toolkit
# Author: Mit Mehta | MSMRA @ MSU Eli Broad
# Description: Automates survey data ingestion via
# REST APIs, processing, segmentation analysis,
# statistical testing, and scheduled reporting
# ================================================

import pandas as pd
import numpy as np
from scipy import stats
import io
import json
import os
import zipfile
import requests
import schedule
import time
from datetime import datetime


# ================================================
# MODULE 1: API DATA INGESTION
# ================================================

def fetch_survey_responses_aytm(api_key, survey_id):
    """
    Fetch live survey responses directly from AYTM API.
    Eliminates manual CSV export step entirely.

    Args:
        api_key: AYTM API authentication key (falls back to the AYTM_API_KEY
                 environment variable when None)
        survey_id: unique survey identifier
    Returns:
        pandas DataFrame of raw responses
    """
    api_key = api_key or os.environ.get("AYTM_API_KEY")
    url = f"https://api.aytm.com/v1/surveys/{survey_id}/responses"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data.get('responses', []))
        print(f"✓ Fetched {len(df)} responses from AYTM API — Survey {survey_id}")
        return df

    except requests.exceptions.HTTPError as e:
        print(f"✗ API Error: {e}")
        return pd.DataFrame()

    except requests.exceptions.ConnectionError:
        print("✗ Connection failed — check API key and network")
        return pd.DataFrame()


def fetch_survey_responses_qualtrics(api_token, survey_id, data_center,
                                     poll_interval=2, max_wait=300):
    """
    Fetch survey responses from Qualtrics API (v3 export-responses flow:
    start export -> poll progress -> download the zipped JSON file).

    Args:
        api_token: Qualtrics API token (falls back to the QUALTRICS_API_TOKEN
                   environment variable when None)
        survey_id: Qualtrics survey ID (SV_xxxxxxxx)
        data_center: Qualtrics data center (e.g. 'fra1', 'iad1')
        poll_interval: seconds between export-progress checks
        max_wait: give up after this many seconds
    Returns:
        pandas DataFrame of raw responses (empty on failure)
    """
    api_token = api_token or os.environ.get("QUALTRICS_API_TOKEN")
    base_url = f"https://{data_center}.qualtrics.com/API/v3"
    headers = {
        "X-API-TOKEN": api_token,
        "Content-Type": "application/json"
    }

    try:
        # Start export
        export_response = requests.post(
            f"{base_url}/surveys/{survey_id}/export-responses",
            headers=headers,
            json={"format": "json"},
            timeout=30
        )
        export_response.raise_for_status()
        progress_id = export_response.json()['result']['progressId']

        # Poll export status until complete, failed, or timed out
        status_url = f"{base_url}/surveys/{survey_id}/export-responses/{progress_id}"
        waited = 0
        while True:
            status_response = requests.get(status_url, headers=headers, timeout=30)
            status_response.raise_for_status()
            result = status_response.json()['result']
            if result['status'] == "complete":
                break
            if result['status'] == "failed":
                raise RuntimeError("Qualtrics export failed")
            if waited >= max_wait:
                raise TimeoutError(f"Qualtrics export not ready after {max_wait}s")
            time.sleep(poll_interval)
            waited += poll_interval

        # Download file (Qualtrics returns a zip containing one JSON file)
        download_url = (f"{base_url}/surveys/{survey_id}/export-responses/"
                        f"{result['fileId']}/file")
        download = requests.get(download_url, headers=headers, timeout=60)
        download.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(download.content)) as zf:
            json_name = next(n for n in zf.namelist() if n.endswith(".json"))
            payload = json.loads(zf.read(json_name))

        df = pd.DataFrame([r['values'] for r in payload.get('responses', [])])
        print(f"✓ Fetched {len(df)} responses from Qualtrics — Survey {survey_id}")
        return df

    except Exception as e:
        print(f"✗ Qualtrics API Error: {e}")
        return pd.DataFrame()


def load_survey_data_csv(filepath):
    """
    Fallback: Load and clean raw survey data from CSV export.
    Used when API access is unavailable.

    Args:
        filepath: path to raw survey CSV file
    Returns:
        cleaned pandas DataFrame
    """
    df = pd.read_csv(filepath)
    df.columns = (df.columns.str.strip()
                            .str.lower()
                            .str.replace(' ', '_')
                            .str.replace(':', ''))
    str_cols = df.select_dtypes(include=['object', 'string']).columns
    df[str_cols] = df[str_cols].apply(lambda x: x.str.strip())
    df = df.dropna(how='all')
    df = df.drop_duplicates()
    print(f"✓ Loaded {len(df)} respondents from CSV — {filepath}")
    return df


# ================================================
# MODULE 2: DATA VALIDATION & CLEANING
# ================================================

def validate_responses(df, min_responses=100):
    """
    Validate survey dataset quality.
    Flags low response counts and high missing data.

    Args:
        df: cleaned DataFrame
        min_responses: minimum acceptable sample size
    Returns:
        validation report as dictionary
    """
    report = {
        'total_responses': len(df),
        'meets_minimum': len(df) >= min_responses,
        'missing_data_pct': round(df.isnull().sum().sum() / df.size * 100, 2),
        'complete_responses': len(df.dropna()),
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M')
    }

    high_missing = df.columns[df.isnull().mean() > 0.1].tolist()
    report['high_missing_columns'] = high_missing

    print(f"✓ Validation complete — {report['total_responses']} responses, "
          f"{report['missing_data_pct']}% missing data")
    return report


# ================================================
# MODULE 3: DEMOGRAPHIC PROFILING & SEGMENTATION
# ================================================

def demographic_profile(df, demo_cols):
    """
    Generate demographic breakdown for survey respondents.

    Args:
        df: cleaned DataFrame
        demo_cols: list of demographic column names
    Returns:
        dictionary of frequency tables per demographic
    """
    profile = {}

    for col in demo_cols:
        if col in df.columns:
            freq = df[col].value_counts()
            pct = df[col].value_counts(normalize=True).round(3) * 100
            profile[col] = pd.DataFrame({
                'count': freq,
                'percentage': pct
            })
            print(f"✓ Profiled: {col}")

    return profile


def segment_respondents(df, segment_col, value_col):
    """
    Segment respondents and compare mean scores across segments.

    Args:
        df: cleaned DataFrame
        segment_col: column to segment by
        value_col: numeric column to compare across segments
    Returns:
        segmentation summary DataFrame
    """
    summary = df.groupby(segment_col)[value_col].agg([
        ('mean', 'mean'),
        ('median', 'median'),
        ('std', 'std'),
        ('count', 'count')
    ]).round(2)

    print(f"✓ Segmented {value_col} across {segment_col} — "
          f"{len(summary)} segments identified")
    return summary


# ================================================
# MODULE 4: STATISTICAL ANALYSIS
# ================================================

def run_ttest(df, group_col, value_col, group1, group2):
    """
    Run independent samples t-test between two groups.

    Args:
        df: cleaned DataFrame
        group_col: column defining the groups
        value_col: numeric column to compare
        group1, group2: group labels to compare
    Returns:
        t-statistic, p-value, and interpretation
    """
    g1 = df[df[group_col] == group1][value_col].dropna()
    g2 = df[df[group_col] == group2][value_col].dropna()

    t_stat, p_value = stats.ttest_ind(g1, g2)

    result = {
        'group1': group1,
        'group2': group2,
        'group1_mean': round(g1.mean(), 3),
        'group2_mean': round(g2.mean(), 3),
        't_statistic': round(t_stat, 3),
        'p_value': round(p_value, 4),
        'significant': p_value < 0.05,
        'interpretation': (
            f"Significant difference between {group1} and {group2} "
            f"(p={round(p_value, 4)})"
            if p_value < 0.05
            else f"No significant difference between {group1} and {group2} "
                 f"(p={round(p_value, 4)})"
        )
    }

    print(f"✓ T-test: {result['interpretation']}")
    return result


def calculate_cronbach_alpha(df, scale_cols):
    """
    Calculate Cronbach's Alpha for internal consistency
    of multi-item survey scales.

    Args:
        df: cleaned DataFrame
        scale_cols: list of columns forming the scale
    Returns:
        Cronbach's alpha coefficient and interpretation
    """
    scale_df = df[scale_cols].dropna()
    n_items = len(scale_cols)

    item_variances = scale_df.var(axis=0, ddof=1).sum()
    total_variance = scale_df.sum(axis=1).var(ddof=1)

    alpha = (n_items / (n_items - 1)) * (1 - item_variances / total_variance)
    alpha = round(alpha, 3)

    if alpha >= 0.9:
        interpretation = "Excellent"
    elif alpha >= 0.8:
        interpretation = "Good"
    elif alpha >= 0.7:
        interpretation = "Acceptable"
    elif alpha >= 0.6:
        interpretation = "Questionable"
    else:
        interpretation = "Poor"

    print(f"✓ Cronbach's Alpha: {alpha} — {interpretation} internal consistency")
    return {
        'alpha': alpha,
        'interpretation': interpretation,
        'n_items': n_items
    }


# ================================================
# MODULE 5: AUTOMATED REPORTING
# ================================================

def generate_summary_report(df, project_name, demo_cols, key_metrics):
    """
    Auto-generate a structured research summary report.

    Args:
        df: cleaned DataFrame
        project_name: name of the research project
        demo_cols: demographic columns to profile
        key_metrics: list of key metric columns to summarize
    Returns:
        report dictionary
    """
    report = {
        'project': project_name,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'sample_size': len(df),
        'demographics': {},
        'key_metrics': {},
        'data_quality': validate_responses(df)
    }

    for col in demo_cols:
        if col in df.columns:
            top_group = df[col].value_counts().index[0]
            top_pct = round(
                df[col].value_counts(normalize=True).iloc[0] * 100, 1
            )
            report['demographics'][col] = {
                'top_group': top_group,
                'top_group_pct': top_pct,
                'unique_values': df[col].nunique()
            }

    for metric in key_metrics:
        if metric in df.columns:
            report['key_metrics'][metric] = {
                'mean': round(df[metric].mean(), 2),
                'median': round(df[metric].median(), 2),
                'std': round(df[metric].std(), 2),
                'min': df[metric].min(),
                'max': df[metric].max()
            }

    print(f"\n{'='*50}")
    print(f"RESEARCH SUMMARY: {project_name}")
    print(f"{'='*50}")
    print(f"Sample size:  {report['sample_size']}")
    print(f"Generated:    {report['generated_at']}")
    print(f"{'='*50}\n")

    return report


def export_report(report, output_path):
    """
    Export report to JSON file for sharing or archiving.

    Args:
        report: report dictionary
        output_path: file path for JSON output
    """
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=4, default=str)
    print(f"✓ Report exported to {output_path}")


# ================================================
# MODULE 6: WORKFLOW SCHEDULING & AUTOMATION
# ================================================

def run_full_pipeline(filepath, project_name, demo_cols, key_metrics,
                      use_api=False, api_config=None):
    """
    Run the complete research analytics pipeline end-to-end.
    Supports both CSV and live API data ingestion.

    Args:
        filepath: path to raw survey CSV (used if use_api=False)
        project_name: name of the research project
        demo_cols: demographic columns
        key_metrics: key metric columns
        use_api: if True, fetch from API instead of CSV
        api_config: dict with api_key, survey_id, platform
    Returns:
        complete analysis report
    """
    print(f"\nStarting pipeline: {project_name}")
    print("="*50)

    # Step 1 — Ingest data
    if use_api and not api_config:
        print("✗ Pipeline aborted — use_api=True requires api_config")
        return None
    if use_api:
        platform = api_config.get('platform', 'aytm')
        if platform == 'aytm':
            df = fetch_survey_responses_aytm(
                api_config.get('api_key'),
                api_config['survey_id']
            )
        elif platform == 'qualtrics':
            df = fetch_survey_responses_qualtrics(
                api_config.get('api_token'),
                api_config['survey_id'],
                api_config['data_center']
            )
        else:
            print(f"✗ Pipeline aborted — unknown platform: {platform}")
            return None
    else:
        df = load_survey_data_csv(filepath)

    if df.empty:
        print("✗ Pipeline aborted — no data loaded")
        return None

    # Step 2 — Validate
    validation = validate_responses(df)
    if not validation['meets_minimum']:
        print("⚠ Warning: Sample size below minimum threshold")

    # Step 3 — Profile demographics
    demo_profile = demographic_profile(df, demo_cols)

    # Step 4 — Segment analysis
    if len(demo_cols) > 0 and len(key_metrics) > 0:
        segment_respondents(df, demo_cols[0], key_metrics[0])

    # Step 5 — Generate and export report
    report = generate_summary_report(
        df, project_name, demo_cols, key_metrics
    )
    output_path = f"{project_name.lower().replace(' ', '_')}_report.json"
    export_report(report, output_path)

    print(f"\n✓ Pipeline complete: {project_name}")
    return report


def schedule_daily_pipeline(filepath, project_name, demo_cols,
                             key_metrics, run_time="09:00"):
    """
    Schedule pipeline to run automatically every day.
    Eliminates manual triggering of daily research reports.

    Args:
        filepath: path to survey data file
        project_name: name of the research project
        demo_cols: demographic columns
        key_metrics: key metric columns
        run_time: time to run daily (24hr format, default 09:00)
    """
    def job():
        print(f"\n[SCHEDULED RUN] {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        run_full_pipeline(filepath, project_name, demo_cols, key_metrics)

    schedule.every().day.at(run_time).do(job)
    print(f"✓ Pipeline scheduled daily at {run_time} for: {project_name}")
    print("Running scheduler — press Ctrl+C to stop\n")

    while True:
        schedule.run_pending()
        time.sleep(60)


# ================================================
# EXAMPLE USAGE
# ================================================

if __name__ == "__main__":

    # Option A — Run once from CSV
    report = run_full_pipeline(
        filepath="survey_data.csv",
        project_name="Donor Insights Study",
        demo_cols=["gender", "region", "income_bracket", "age"],
        key_metrics=["donation_likelihood", "brand_awareness", "interest_score"]
    )

    # Option B — Run once from AYTM API
    # report = run_full_pipeline(
    #     filepath=None,
    #     project_name="Consumer Insights Study",
    #     demo_cols=["gender", "age_group", "region"],
    #     key_metrics=["trust_score", "platform_preference", "purchase_intent"],
    #     use_api=True,
    #     api_config={
    #         "platform": "aytm",
    #         "api_key": "your_api_key_here",
    #         "survey_id": "your_survey_id_here"
    #     }
    # )

    # Option C — Schedule to run daily at 9am
    # schedule_daily_pipeline(
    #     filepath="survey_data.csv",
    #     project_name="Daily Research Monitor",
    #     demo_cols=["gender", "region"],
    #     key_metrics=["score"],
    #     run_time="09:00"
    # )
