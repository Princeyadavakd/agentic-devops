"""Pipeline Agent: reads a failed CI run, finds the root cause, suggests a fix.

LangGraph flow:
  fetch_logs -> analyze -> (needs more files?) -> fetch_files -> analyze ... -> report
"""
import argparse
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, TypedDict

from langgraph.graph import END, StateGraph

from . import config, github_client, llm

MAX_ITER = 2


class State(TypedDict, total=False):
    run: Dict[str, Any]
    job: Dict[str, Any]
    log: str
    files: Dict[str, str]
    analysis: Dict[str, Any]
    iterations: int
    source: str


def build_prompt(state):
    run = state["run"]
    msg = (run.get("head_commit") or {}).get("message", "")
    files = "\n\n".join(f"--- {p} ---\n{c}" for p, c in state["files"].items()) or "(none yet)"
    return f"""You are a DevOps assistant analysing a FAILED GitHub Actions CI run.
Repo: {config.GITHUB_REPO}
Commit message: {msg}
Failed job: {state['job'].get('job')}, failed step: {state['job'].get('step')}

CI LOG (tail):
{state['log']}

SOURCE FILES ALREADY FETCHED:
{files}

Return ONLY a JSON object with these keys:
- root_cause: string, one or two sentences
- failing_test: string or null
- file: string or null (repo path, e.g. app/app.py)
- line: integer or null
- suggested_fix: string, a concrete code change
- confidence: "low", "medium" or "high"
- need_files: list of up to 3 repo file paths you must see to be sure (empty list if you already have enough)
Rules: only use file paths that appear in the log or in the fetched files. Do not invent. If unsure, set confidence to low."""


def rule_based(log):
    """Fallback when the LLM is unavailable: simple regex analysis."""
    failed = re.search(r"FAILED (\S+)", log)
    err = re.search(r"^E\s+(.*)$", log, re.M) or re.search(r"(\w+Error[^\n]*)", log)
    loc = re.search(r"(\S+\.py):(\d+)", log)
    return {
        "root_cause": err.group(1).strip() if err else "Could not determine automatically",
        "failing_test": failed.group(1) if failed else None,
        "file": loc.group(1) if loc else None,
        "line": int(loc.group(2)) if loc else None,
        "suggested_fix": "Open the file/line above and check the error message (rule-based fallback, no LLM).",
        "confidence": "low",
        "need_files": [],
    }


def fetch_logs(state):
    job, log = github_client.failed_job_log(state["run"]["id"])
    return {"job": job or {}, "log": log, "files": {}, "iterations": 0}


def analyze(state):
    try:
        analysis, source = llm.ask_json(build_prompt(state)), "llm"
    except Exception as e:
        analysis, source = rule_based(state["log"]), f"fallback ({type(e).__name__})"
    return {"analysis": analysis, "iterations": state["iterations"] + 1, "source": source}


def route(state):
    wants = state["analysis"].get("need_files")
    if state["source"] == "llm" and wants and state["iterations"] < MAX_ITER:
        return "fetch_files"
    return "report"


def fetch_files(state):
    files = dict(state["files"])
    for path in state["analysis"].get("need_files", [])[:3]:
        if path not in files:
            files[path] = github_client.get_file(path, state["run"]["head_sha"]) or "(file not found)"
    return {"files": files}


def _parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def report(state):
    run, a = state["run"], state["analysis"]
    now = datetime.now(timezone.utc)
    secs = round((now - _parse(run["updated_at"])).total_seconds())
    print("\n" + "=" * 60)
    print(f"CI FAILURE ANALYSIS  (run #{run['run_number']}, analysed by: {state['source']})")
    print("=" * 60)
    print(f"Run URL    : {run['html_url']}")
    print(f"Failed step: {state['job'].get('job')} / {state['job'].get('step')}")
    print(f"Test       : {a.get('failing_test')}")
    print(f"Location   : {a.get('file')} line {a.get('line')}")
    print(f"Root cause : {a.get('root_cause')}")
    print(f"Fix        : {a.get('suggested_fix')}")
    print(f"Confidence : {a.get('confidence')}")
    print(f"Time from failure to diagnosis: {secs}s")
    os.makedirs(config.DATA_DIR, exist_ok=True)
    entry = {"time": now.isoformat(), "run_id": run["id"], "run_url": run["html_url"], "sha": run["head_sha"],
             "source": state["source"], "analysis": a, "seconds_to_diagnose": secs}
    with open(os.path.join(config.DATA_DIR, "incidents.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return {}


def build_graph():
    g = StateGraph(State)
    g.add_node("fetch_logs", fetch_logs)
    g.add_node("analyze", analyze)
    g.add_node("fetch_files", fetch_files)
    g.add_node("report", report)
    g.set_entry_point("fetch_logs")
    g.add_edge("fetch_logs", "analyze")
    g.add_conditional_edges("analyze", route, {"fetch_files": "fetch_files", "report": "report"})
    g.add_edge("fetch_files", "analyze")
    g.add_edge("report", END)
    return g.compile()


def analyze_run(run):
    return build_graph().invoke({"run": run})


def main():
    ap = argparse.ArgumentParser(description="Analyse a failed GitHub Actions run")
    ap.add_argument("--run-id", type=int)
    ap.add_argument("--latest-failed", action="store_true")
    args = ap.parse_args()
    if args.run_id:
        run = github_client.get_run(args.run_id)
    elif args.latest_failed:
        run = github_client.latest_failed_run()
    else:
        ap.error("use --latest-failed or --run-id N")
    if not run:
        print("No failed run found.")
        return
    analyze_run(run)


if __name__ == "__main__":
    main()
