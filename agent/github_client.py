"""Small GitHub REST client: runs, failed job logs, repo files."""
import re

import requests

from . import config

API = "https://api.github.com"
_TS = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ", re.M)


def _headers(raw=False):
    h = {
        "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if config.GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"
    return h


def _get(path, **kw):
    r = requests.get(f"{API}/repos/{config.GITHUB_REPO}{path}", headers=_headers(), timeout=30, **kw)
    r.raise_for_status()
    return r


def list_runs(limit=10):
    return _get("/actions/runs", params={"per_page": limit}).json()["workflow_runs"]


def get_run(run_id):
    return _get(f"/actions/runs/{run_id}").json()


def latest_failed_run():
    for run in list_runs(20):
        if run.get("conclusion") == "failure":
            return run
    return None


def clean_log(text, max_chars=9000):
    text = _TS.sub("", text)
    tail = "\n".join(text.splitlines()[-300:])
    return tail[-max_chars:]


def failed_job_log(run_id):
    """Return ({'job','step'}, cleaned_log_tail) for the first failed job of a run."""
    jobs = _get(f"/actions/runs/{run_id}/jobs").json()["jobs"]
    failed = [j for j in jobs if j.get("conclusion") == "failure"]
    if not failed:
        return None, ""
    job = failed[0]
    step = next((s["name"] for s in job["steps"] if s.get("conclusion") == "failure"), "unknown")
    text = _get(f"/actions/jobs/{job['id']}/logs").text
    return {"job": job["name"], "step": step}, clean_log(text)


def get_file(path, ref):
    r = requests.get(
        f"{API}/repos/{config.GITHUB_REPO}/contents/{path}",
        headers=_headers(raw=True), params={"ref": ref}, timeout=30,
    )
    return r.text[:6000] if r.status_code == 200 else None
