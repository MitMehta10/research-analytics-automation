# Research Analytics Automation Toolkit
### Python Toolkit for Survey Data Processing, API Integration & Scheduled Reporting
### Mit Mehta | MSMRA @ MSU Eli Broad

## Overview
A reusable Python library that automates end-to-end survey data processing —
from live API ingestion to segmentation analysis, statistical testing, and
scheduled reporting.

Built to eliminate 15+ hours/week of manual analytics setup across research
projects — directly inspired by automation work on client studies including
NexGen Archery (n=401) and Archive (n≈400).

## What It Does

### Module 1 — Live API Data Ingestion
- Fetches live survey responses directly from AYTM REST API
- Fetches responses from Qualtrics API with async export handling
- Eliminates manual CSV export step entirely
- Falls back to CSV ingestion when API unavailable

### Module 2 — Data Validation & Cleaning
- Validates sample size against minimum thresholds
- Flags columns with high missing data automatically
- Standardizes column names across export formats
- Removes duplicates and empty rows

### Module 3 — Demographic Profiling & Segmentation
- Generates frequency tables for all demographic variables
- Segments respondents and compares mean scores across groups
- Returns clean DataFrames ready for visualization

### Module 4 — Statistical Analysis
- Independent samples t-tests with plain-English interpretation
- Cronbach's Alpha for scale reliability (Excellent / Good / Acceptable)
- Significance testing at p < 0.05 threshold

### Module 5 — Automated Reporting
- Generates structured JSON summary reports from raw data
- Includes data quality validation built-in
- Exports to JSON for sharing, archiving, and downstream use

### Module 6 — Workflow Scheduling & Automation
- Full end-to-end pipeline in a single function call
- Supports both CSV and live API ingestion
- Schedules pipeline to run automatically daily via schedule library
- Eliminates manual triggering of recurring research reports

## Key Results
- 60% reduction in content production time
- 50% reduction in per-project analytics setup time
- Eliminated 15+ hrs/week of manual data processing
- Reused across 4+ research projects

## Tech Stack
Python · pandas · NumPy · SciPy · Requests · Schedule · JSON

## Usage

```python
from research_automation_toolkit import run_full_pipeline

# Run once from CSV
report = run_full_pipeline(
    filepath="survey_data.csv",
    project_name="NexGen Archery Donor Insights Study",
    demo_cols=["gender", "region", "income_bracket", "age"],
    key_metrics=["donation_likelihood", "brand_awareness", "interest_score"]
)

# Run from AYTM API directly
report = run_full_pipeline(
    filepath=None,
    project_name="Archive Consumer Insights Study",
    demo_cols=["gender", "age_group", "region"],
    key_metrics=["trust_score", "platform_preference", "purchase_intent"],
    use_api=True,
    api_config={
        "platform": "aytm",
        "api_key": "your_api_key_here",
        "survey_id": "your_survey_id_here"
    }
)

# Schedule to run automatically every day at 9am
schedule_daily_pipeline(
    filepath="survey_data.csv",
    project_name="Daily Research Monitor",
    demo_cols=["gender", "region"],
    key_metrics=["score"],
    run_time="09:00"
)
```

## Connection to Real Projects

**NexGen Archery (completed)** — Donor insights study (n=401).
Toolkit used to automate demographic profiling and segmentation analysis,
identifying 3 high-value donor segments that reshaped the client's
go-to-market messaging strategy.

**Archive (completed)** — Consumer insights study (n≈400) for a B2B
recommerce platform powering resale for 100+ consumer brands.
Pipeline automates live AYTM API data ingestion and reporting
workflows for ongoing fieldwork.

## Files
- `research_automation_toolkit.py` — Full Python toolkit with 6 modules

## About
Mit Mehta | MS Marketing Research & Analytics @ MSU Eli Broad (Aug 2026)
Seeking full-time roles in Consumer Insights, Marketing Analytics, and Growth Analytics.
[LinkedIn](https://linkedin.com/in/mitmehta10) | [GitHub](https://github.com/MitMehta10)
