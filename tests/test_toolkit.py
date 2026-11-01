"""Tests use fake data and mocked HTTP: no network calls, no real API keys."""
import io
import json
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import research_automation_toolkit as t  # noqa: E402


@pytest.fixture
def survey_df():
    rng = np.random.default_rng(0)
    n = 200
    return pd.DataFrame({
        "respondent_id": range(n),
        "gender": rng.choice(["F", "M"], n),
        "region": rng.choice(["West", "South", "East"], n),
        "score": rng.integers(1, 8, n).astype(float),
    })


def resp(json_data=None, content=None, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_data
    r.content = content
    if status >= 400:
        r.raise_for_status.side_effect = requests.exceptions.HTTPError(f"{status} error")
    return r


# ---- CSV loading and validation -------------------------------------------------
def test_csv_loader_cleans(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("Gender, Score Value\n F ,5\n F ,5\n,\nM,3\n")
    df = t.load_survey_data_csv(p)
    assert list(df.columns) == ["gender", "score_value"]
    assert len(df) == 2                       # blank row and duplicate dropped
    assert df.gender.tolist() == ["F", "M"]  # whitespace stripped


def test_validate_flags_small_sample_and_missing():
    df = pd.DataFrame({"a": [1, None, None, None], "b": [1, 2, 3, 4]})
    rep = t.validate_responses(df, min_responses=10)
    assert rep["meets_minimum"] is False
    assert rep["high_missing_columns"] == ["a"]
    assert rep["missing_data_pct"] == 37.5


# ---- profiling, segmentation, stats ---------------------------------------------
def test_demographic_profile_percentages(survey_df):
    prof = t.demographic_profile(survey_df, ["gender", "not_a_column"])
    assert list(prof) == ["gender"]
    assert prof["gender"]["count"].sum() == 200
    assert abs(prof["gender"]["percentage"].sum() - 100) < 0.2


def test_segment_respondents_known_means():
    df = pd.DataFrame({"g": ["a", "a", "b", "b"], "v": [1, 3, 5, 7]})
    out = t.segment_respondents(df, "g", "v")
    assert out.loc["a", "mean"] == 2 and out.loc["b", "mean"] == 6


def test_ttest_detects_obvious_difference():
    df = pd.DataFrame({"g": ["a"] * 30 + ["b"] * 30,
                       "v": list(np.linspace(1, 3, 30)) + list(np.linspace(6, 8, 30))})
    res = t.run_ttest(df, "g", "v", "a", "b")
    assert res["significant"] and res["p_value"] < 0.001


def test_ttest_no_difference():
    vals = list(np.linspace(1, 5, 30))
    df = pd.DataFrame({"g": ["a"] * 30 + ["b"] * 30, "v": vals + vals})
    assert not t.run_ttest(df, "g", "v", "a", "b")["significant"]


def test_cronbach_alpha_known_values():
    # identical items -> perfectly consistent
    base = np.arange(1, 21)
    same = pd.DataFrame({"i1": base, "i2": base, "i3": base})
    assert t.calculate_cronbach_alpha(same, ["i1", "i2", "i3"])["alpha"] == 1.0
    # uncorrelated items -> low alpha
    rng = np.random.default_rng(1)
    noise = pd.DataFrame(rng.normal(size=(500, 3)), columns=["i1", "i2", "i3"])
    assert t.calculate_cronbach_alpha(noise, ["i1", "i2", "i3"])["interpretation"] in ("Poor", "Questionable")


# ---- reporting and pipeline -----------------------------------------------------
def test_summary_report_and_export(survey_df, tmp_path):
    rep = t.generate_summary_report(survey_df, "P", ["gender"], ["score"])
    assert rep["sample_size"] == 200
    assert 1 <= rep["key_metrics"]["score"]["mean"] <= 7
    out = tmp_path / "r.json"
    t.export_report(rep, out)
    assert json.loads(out.read_text())["project"] == "P"


def test_full_pipeline_from_csv(survey_df, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    survey_df.to_csv("s.csv", index=False)
    rep = t.run_full_pipeline("s.csv", "Demo Study", ["gender", "region"], ["score"])
    assert rep["sample_size"] == 200
    assert (tmp_path / "demo_study_report.json").exists()


def test_pipeline_aborts_on_empty_data(tmp_path, monkeypatch):
    monkeypatch.setattr(t, "fetch_survey_responses_aytm", lambda *a, **k: pd.DataFrame())
    assert t.run_full_pipeline(None, "X", ["a"], ["b"], use_api=True,
                               api_config={"platform": "aytm", "api_key": "k", "survey_id": "s"}) is None


def test_pipeline_rejects_unknown_platform_and_missing_config():
    assert t.run_full_pipeline(None, "X", [], [], use_api=True, api_config={"platform": "nope"}) is None
    assert t.run_full_pipeline(None, "X", [], [], use_api=True) is None


# ---- API ingestion (mocked) -----------------------------------------------------
def test_aytm_success(monkeypatch):
    monkeypatch.setattr(t.requests, "get",
                        lambda *a, **k: resp({"responses": [{"q1": 1}, {"q1": 2}]}))
    assert len(t.fetch_survey_responses_aytm("key", "sv")) == 2


def test_aytm_http_error_returns_empty(monkeypatch):
    monkeypatch.setattr(t.requests, "get", lambda *a, **k: resp(status=401))
    assert t.fetch_survey_responses_aytm("bad", "sv").empty


def test_aytm_uses_env_key(monkeypatch):
    seen = {}

    def fake_get(url, headers=None, **k):
        seen["auth"] = headers["Authorization"]
        return resp({"responses": []})
    monkeypatch.setattr(t.requests, "get", fake_get)
    monkeypatch.setenv("AYTM_API_KEY", "from-env")
    t.fetch_survey_responses_aytm(None, "sv")
    assert seen["auth"] == "Bearer from-env"


def make_zip(payload):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("survey.json", json.dumps(payload))
    return buf.getvalue()


def test_qualtrics_happy_path(monkeypatch):
    monkeypatch.setattr(t.time, "sleep", lambda s: None)
    monkeypatch.setattr(t.requests, "post",
                        lambda *a, **k: resp({"result": {"progressId": "p1"}}))
    statuses = iter([{"result": {"status": "inProgress"}},
                     {"result": {"status": "complete", "fileId": "f1"}}])
    zipped = make_zip({"responses": [{"values": {"Q1": 1}}, {"values": {"Q1": 2}}]})

    def fake_get(url, **k):
        return resp(content=zipped) if url.endswith("/file") else resp(next(statuses))
    monkeypatch.setattr(t.requests, "get", fake_get)
    df = t.fetch_survey_responses_qualtrics("tok", "SV_1", "iad1")
    assert df["Q1"].tolist() == [1, 2]


def test_qualtrics_failed_export(monkeypatch):
    monkeypatch.setattr(t.time, "sleep", lambda s: None)
    monkeypatch.setattr(t.requests, "post",
                        lambda *a, **k: resp({"result": {"progressId": "p1"}}))
    monkeypatch.setattr(t.requests, "get",
                        lambda *a, **k: resp({"result": {"status": "failed"}}))
    assert t.fetch_survey_responses_qualtrics("tok", "SV_1", "iad1").empty


def test_qualtrics_times_out(monkeypatch):
    monkeypatch.setattr(t.time, "sleep", lambda s: None)
    monkeypatch.setattr(t.requests, "post",
                        lambda *a, **k: resp({"result": {"progressId": "p1"}}))
    monkeypatch.setattr(t.requests, "get",
                        lambda *a, **k: resp({"result": {"status": "inProgress"}}))
    assert t.fetch_survey_responses_qualtrics("tok", "SV_1", "iad1", poll_interval=1, max_wait=3).empty


# ---- scheduler ------------------------------------------------------------------
def test_schedule_registers_daily_job(monkeypatch):
    t.schedule.clear()

    def stop(_):
        raise KeyboardInterrupt
    monkeypatch.setattr(t.time, "sleep", stop)
    with pytest.raises(KeyboardInterrupt):
        t.schedule_daily_pipeline("x.csv", "P", ["a"], ["b"], run_time="09:00")
    jobs = t.schedule.get_jobs()
    assert len(jobs) == 1 and jobs[0].at_time.strftime("%H:%M") == "09:00"
    t.schedule.clear()
