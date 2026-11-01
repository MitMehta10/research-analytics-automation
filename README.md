# Research Analytics Automation Toolkit
### Python Toolkit for Survey Data Processing, API Integration & Scheduled Reporting
### Mit Mehta | MSMRA @ MSU Eli Broad

## Overview
A reusable Python library that automates end-to-end survey data processing —
from live API ingestion to segmentation analysis, statistical testing, and
scheduled reporting.

Built to cut repetitive setup work in survey research: pulling exports, cleaning
columns, profiling respondents and producing the same summary each time. It grew out
of my coursework and client-study work in market research; the code here is a
general-purpose version and contains no client data.

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

## Quality checks
- 18 automated tests (`pytest`) run in GitHub Actions on every push. They use fake survey data and mocked HTTP responses, so they need no network access or API keys.
- Statistical helpers are tested against known cases (identical items give Cronbach's alpha of 1.0; clearly separated groups give a significant t-test).
- The Qualtrics export flow is tested for success, a failed export and a timeout.

> **Not yet verified:** the AYTM endpoint in `fetch_survey_responses_aytm` is written from my own assumptions about their API, so confirm the URL and response shape against AYTM's current documentation before relying on it. The tests prove the code handles the response shape it expects, not that AYTM returns it.

## Tech Stack
Python · pandas · NumPy · SciPy · Requests · Schedule · JSON

## Usage

```python
from research_automation_toolkit import run_full_pipeline

# Run once from CSV
report = run_full_pipeline(
    filepath="survey_data.csv",
    project_name="Donor Insights Study",
    demo_cols=["gender", "region", "income_bracket", "age"],
    key_metrics=["donation_likelihood", "brand_awareness", "interest_score"]
)

# Run from AYTM API directly
report = run_full_pipeline(
    filepath=None,
    project_name="Consumer Insights Study",
    demo_cols=["gender", "age_group", "region"],
    key_metrics=["trust_score", "platform_preference", "purchase_intent"],
    use_api=True,
    api_config={
        "platform": "aytm",
        "api_key": None,  # or set the AYTM_API_KEY environment variable
        "survey_id": "your_survey_id"
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

## Background
The workflow follows the steps I used on survey projects during my master's program (a donor-insights study and a consumer-insights study of about 400 respondents each): export, clean, profile, segment, test, report. Findings, client names beyond the project titles, and data are intentionally not included here.

## Run the tests
```bash
pip install -r requirements.txt pytest
pytest -q
```

## Files
- `research_automation_toolkit.py` — Python toolkit with 6 modules (single file, importable as shown above)
- `tests/test_toolkit.py` — unit tests with mocked HTTP
- `.github/workflows/ci.yml` — runs the tests on push

## Limitations
- Statistics are limited to an independent-samples t-test and Cronbach's alpha (no multiple-comparison correction, no effect sizes).
- The scheduler is a simple in-process loop (`schedule` library); use cron or a task runner for anything production-grade.
- Reports are JSON only.

## About
Mit Mehta | MS Marketing Research & Analytics @ MSU Eli Broad 
Seeking full-time roles in Business Analysis, Product, and Consumer Insights / Marketing Analytics.
[LinkedIn](https://linkedin.com/in/mitmehta10) | [GitHub](https://github.com/MitMehta10)
