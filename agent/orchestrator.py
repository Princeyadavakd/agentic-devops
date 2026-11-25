"""Orchestrator: one process that runs the CI watcher and the Monitoring Agent, listens to Telegram
commands and routes every event to the right agent. Risky actions are approved on Telegram.

  python -m agent.orchestrator run                 # everything
  python -m agent.orchestrator run --no-monitor    # only CI watcher + Telegram
Telegram commands: /status  /deploy [none|crash|leak|slow]  /help
"""
import argparse
import json
import threading
from datetime import datetime
from pathlib import Path

from . import notify
from . import tools_docker as T

DATA = T.DATA
ACTION_LOCK = threading.Lock()     # one deployment / monitoring action at a time
BUGS = ("none", "crash", "leak", "slow")


def read_lines(name):
    p = Path(DATA) / name
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def handle_ci_failure(bot, run):
    from .pipeline_agent import analyze_run
    bot.send(f"CI failed (run #{run['run_number']}). Pipeline Agent is analysing the log ...")
    analyze_run(run)
    inc = next((i for i in reversed(read_lines("incidents.jsonl")) if i.get("run_id") == run["id"]), None)
    if not inc:
        bot.send("Analysis finished, but no incident was recorded."); return
    a = inc.get("analysis") or {}
    bot.send(f"CI failure analysis ({inc.get('source')})\nTest: {a.get('failing_test')}\nLocation: {a.get('file')} line {a.get('line')}\n"
             f"Root cause: {a.get('root_cause')}\nFix: {a.get('suggested_fix')}\nConfidence: {a.get('confidence')}\n{inc.get('run_url')}")


def ci_watcher(bot, interval, stop):
    from . import github_client
    try:
        seen = {r["id"] for r in github_client.list_runs(10)}
    except Exception as e:
        print(f"[ci-watcher] cannot reach GitHub: {e}"); seen = set()
    print(f"[ci-watcher] watching for new failed CI runs every {interval}s")
    while not stop.is_set():
        try:
            for run in github_client.list_runs(10):
                if run["status"] == "completed" and run["id"] not in seen:
                    seen.add(run["id"])
                    if run["conclusion"] == "failure":
                        handle_ci_failure(bot, run)
        except Exception as e:
            print(f"[ci-watcher] {type(e).__name__}: {e}")
        stop.wait(interval)


def monitor_loop(bot, interval, stop):
    from . import monitoring_agent as M
    from . import prom
    graph = M.build_graph()
    done = len(read_lines("monitoring_incidents.jsonl"))
    print(f"[monitor] watching metrics every {interval}s")
    while not stop.is_set():
        try:
            with ACTION_LOCK:
                graph.invoke({"auto_yes": False})
        except prom.PromUnavailable as e:
            print(f"[monitor] Prometheus not reachable: {e}")
        except Exception as e:
            print(f"[monitor] {type(e).__name__}: {e}")
        rows = read_lines("monitoring_incidents.jsonl")
        for r in rows[done:]:
            bot.send(f"Monitoring incident: {r.get('anomaly')} -> {r.get('action')} -> {r.get('outcome')}\nMTTR: {r.get('mttr_seconds')}s\n"
                     f"{(r.get('explanation') or {}).get('explanation', '')}")
        done = len(rows)
        stop.wait(interval)


def cmd_status(bot):
    def fn(args):
        st = T.load_state()
        lines = [f"Current release: {st.get('current_tag')}", f"Last good release: {st.get('last_good_tag')}"]
        try:
            from . import monitoring_agent as M
            m = M.collect_metrics()
            lines.append(f"up={m['up']} error_rate={m['error_rate']} p95={m['p95']} mem_mb={m['mem_mb']}")
        except Exception as e:
            lines.append(f"metrics unavailable: {type(e).__name__}")
        bot.send("\n".join(lines))
    return fn


def cmd_deploy(bot):
    def fn(args):
        bug = args[0].lower() if args else "none"
        if bug not in BUGS:
            bot.send("Usage: /deploy [none|crash|leak|slow]"); return
        from .deployment_agent import build_graph
        bot.send(f"Deploying a new release (BUG_MODE={bug}) ...")
        with ACTION_LOCK:
            build_graph().invoke({"tag": datetime.now().strftime("%Y%m%d-%H%M%S"), "bug": bug, "auto_yes": False})
        last = (read_lines("deployments.jsonl") or [{}])[-1]
        bot.send(f"Deployment finished: {last.get('outcome')}\ndetect: {last.get('detect_seconds')}s  recover: {last.get('recover_seconds')}s")
    return fn


def run(args):
    bot = notify.get_bot()
    stop = threading.Event()
    if bot.enabled:
        notify.install_input_hook(bot)
        bot.on("status", cmd_status(bot)); bot.on("deploy", cmd_deploy(bot))
        bot.on("help", lambda a: bot.send("Commands: /status, /deploy [none|crash|leak|slow]"))
        bot.start()
        bot.send("Orchestrator online. Commands: /status, /deploy [none|crash|leak|slow]")
    else:
        print("Telegram not configured: approvals will be asked in this console.")
    threads = []
    if not args.no_ci:
        threads.append(threading.Thread(target=ci_watcher, args=(bot, args.ci_interval, stop), daemon=True))
    if not args.no_monitor:
        threads.append(threading.Thread(target=monitor_loop, args=(bot, args.monitor_interval, stop), daemon=True))
    for t in threads:
        t.start()
    print("Orchestrator running. Ctrl+C to stop.")
    try:
        while True:
            stop.wait(1)
    except KeyboardInterrupt:
        print("\nStopping ..."); stop.set(); bot.stop()


def main():
    ap = argparse.ArgumentParser(description="Agentic DevOps orchestrator")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--no-ci", action="store_true"); r.add_argument("--no-monitor", action="store_true")
    r.add_argument("--ci-interval", type=int, default=30); r.add_argument("--monitor-interval", type=int, default=3)
    run(ap.parse_args())


if __name__ == "__main__":
    main()
