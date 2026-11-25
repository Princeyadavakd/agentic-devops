"""Stopwatch for the MANUAL baseline: you fix the problem by hand while the clock runs.
  python -m eval.manual_baseline record crash          # faulty release is running; restore the good one yourself
  python -m eval.manual_baseline record service_down   # container is killed; bring it back yourself
  python -m eval.manual_baseline record ci_failure     # read the failed CI log; stop when you know test + file
  python -m eval.manual_baseline list
Be fair: use the same effort you would normally use (browser, docker commands), no copy-pasted scripts.
"""
import argparse
import time
from datetime import datetime, timezone

from .common import append_jsonl, load_jsonl


def _wait_healthy():
    from agent import tools_docker as T
    while True:
        input("Press Enter when you think the service is healthy again ... ")
        ok, msg = T.health_check(retries=1, delay=0)
        print(f"health check: {msg}")
        if ok:
            return
        print("Still unhealthy. Keep fixing, then press Enter again (timer keeps running).")


def record(scenario):
    t0 = None
    if scenario in ("crash", "service_down"):
        from agent import tools_docker as T
        good = T.load_state().get("last_good_tag")
        if not good or not T.image_exists(good):
            print("No last good image found. Run a normal deploy first (python -m agent.deployment_agent deploy)."); return
        if scenario == "crash":
            T.run_container(good, "crash")
            print(f"A faulty release (BUG_MODE=crash) is now running. Last good image: {T.IMAGE}:{good}")
        else:
            T.run_container(good, "none"); T.health_check()
            T._run(["docker", "kill", T.CONTAINER], 60)
            print("The container was killed.")
        input("Press Enter to START the timer, then fix it manually ... ")
        t0 = time.time()
        _wait_healthy()
    else:
        input("Open the latest failed run on GitHub Actions. Press Enter to START the timer ... ")
        t0 = time.time()
        input("Press Enter when you have identified the failing test AND the file/cause ... ")
    secs = round(time.time() - t0, 1)
    append_jsonl("manual_baseline.jsonl", {"scenario": scenario, "seconds": secs, "time": datetime.now(timezone.utc).isoformat()})
    print(f"Recorded: {scenario} = {secs}s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["record", "list"])
    ap.add_argument("scenario", nargs="?", choices=["crash", "service_down", "ci_failure"])
    a = ap.parse_args()
    if a.cmd == "list":
        for r in load_jsonl("manual_baseline.jsonl"):
            print(r["scenario"], r["seconds"], r["time"])
    elif a.scenario:
        record(a.scenario)
    else:
        ap.error("scenario required")


if __name__ == "__main__":
    main()
