"""Injects a known bug into app/app.py, commits and pushes it, so CI fails and the Pipeline Agent can be scored.
The ground truth (which test must fail, which file) is saved for eval.rca_accuracy.

  python -m eval.inject_ci_bug list
  python -m eval.inject_ci_bug apply user_lookup      # commit + push the bug
  python -m eval.inject_ci_bug revert                 # restore app/app.py, commit + push
Add --no-push to only commit locally.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone

from .common import DATA, ROOT, append_jsonl

APP = ROOT / "app" / "app.py"
STATE = DATA / "eval_state.json"
BUGS = {
    "user_lookup": dict(
        find='    user = USERS.get(uid)\n    if user is None:\n        return jsonify(error="user not found"), 404\n    return jsonify(user)',
        replace="    return jsonify(USERS[uid])", test="test_missing_user_returns_404"),
    "discount_formula": dict(
        find="return price - (price * percent / 100)", replace="return price - percent", test="test_discount_calculation"),
    "health_status": dict(
        find='return jsonify(status="ok")', replace='return jsonify(status="up")', test="test_health_ok"),
    "home_status_code": dict(
        find='return jsonify(message="Demo app is running", bug_mode=mode)',
        replace='return jsonify(message="Demo app is running", bug_mode=mode), 201', test="test_home_ok"),
    "user_name": dict(
        find='1: {"name": "Aman"', replace='1: {"name": "Amaan"', test="test_existing_user"),
}


def git(*a, check=True):
    p = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    if check and p.returncode != 0:
        sys.exit(f"git {' '.join(a)} failed:\n{p.stdout}{p.stderr}")
    return p.stdout.strip()


def apply(name, push):
    if name not in BUGS:
        sys.exit(f"unknown bug '{name}'. Available: {', '.join(BUGS)}")
    if STATE.exists():
        sys.exit("A bug is already injected. Run: python -m eval.inject_ci_bug revert")
    if git("status", "--porcelain", "app/app.py"):
        sys.exit("app/app.py has uncommitted changes. Commit or restore it first.")
    raw = APP.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
    b = BUGS[name]
    if b["find"] not in text:
        sys.exit("The expected code was not found in app/app.py (file changed?). Bug not applied.")
    new = text.replace(b["find"], b["replace"], 1)
    APP.write_bytes((new.replace("\n", "\r\n") if crlf else new).encode("utf-8"))
    base = git("rev-parse", "HEAD")
    git("add", "app/app.py"); git("commit", "-m", f"eval: inject bug {name}", "--", "app/app.py")
    sha = git("rev-parse", "HEAD")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"bug": name, "base_sha": base, "bug_sha": sha}), encoding="utf-8")
    append_jsonl("rca_ground_truth.jsonl", {"bug": name, "commit_sha": sha, "expected_test": b["test"], "expected_file": "app/app.py",
                                           "time": datetime.now(timezone.utc).isoformat()})
    if push:
        git("push")
    print(f"Injected '{name}' (commit {sha[:7]}). Expected failing test: {b['test']}")
    print("Next: wait for the red cross on GitHub Actions, run the Pipeline Agent, then: python -m eval.inject_ci_bug revert")


def revert(push):
    if not STATE.exists():
        sys.exit("No injected bug to revert.")
    st = json.loads(STATE.read_text(encoding="utf-8"))
    git("checkout", st["base_sha"], "--", "app/app.py")
    if git("status", "--porcelain", "app/app.py"):
        git("add", "app/app.py"); git("commit", "-m", f"eval: restore app after {st['bug']}", "--", "app/app.py")
        if push:
            git("push")
    STATE.unlink()
    print(f"Restored app/app.py (before '{st['bug']}').")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "apply", "revert"])
    ap.add_argument("name", nargs="?")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()
    if a.cmd == "list":
        for k, v in BUGS.items():
            print(f"{k:18s} -> test that fails: {v['test']}")
    elif a.cmd == "apply":
        apply(a.name or "", not a.no_push)
    else:
        revert(not a.no_push)


if __name__ == "__main__":
    main()
