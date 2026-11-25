"""Deployment Agent: build -> deploy -> health check -> (diagnose -> approval -> rollback) -> report.

Usage (from project root, venv active, Docker Desktop running):
  python -m agent.deployment_agent deploy                 # normal release
  python -m agent.deployment_agent deploy --bug crash     # faulty release (demo)
  python -m agent.deployment_agent deploy --bug crash --yes   # no approval prompt
  python -m agent.deployment_agent status
"""
import argparse
import time
from datetime import datetime
from typing import Any, Dict, TypedDict

from langgraph.graph import END, StateGraph

from . import tools_docker as T


class State(TypedDict, total=False):
    tag: str
    bug: str
    auto_yes: bool
    build_ok: bool
    t_start: float
    t_fail: float
    healthy: bool
    health_msg: str
    detect_s: float
    logs: str
    previous: Any
    diagnosis: Dict[str, Any]
    source: str
    approved: bool
    outcome: str
    recover_s: float


def build(state):
    print(f"[build] building image {T.IMAGE}:{state['tag']} ...")
    rc, out = T.build_image(state["tag"])
    if rc != 0:
        print("[build] FAILED\n" + "\n".join(out.splitlines()[-15:]))
        return {"build_ok": False, "outcome": "build_failed"}
    return {"build_ok": True}


def deploy(state):
    print(f"[deploy] starting container (BUG_MODE={state['bug']}) on port {T.HOST_PORT} ...")
    t0 = time.time()
    rc, out = T.run_container(state["tag"], state["bug"])
    if rc != 0:
        print("[deploy] docker run failed: " + out[-300:])
    return {"t_start": t0}


def health(state):
    ok, msg = T.health_check()
    print(f"[health] {'HEALTHY' if ok else 'UNHEALTHY'}: {msg}")
    if ok:
        return {"healthy": True, "health_msg": msg}
    return {"healthy": False, "health_msg": msg, "detect_s": round(time.time() - state["t_start"], 1), "t_fail": time.time()}


def route_health(state):
    return "mark_good" if state["healthy"] else "diagnose"


def mark_good(state):
    old = T.load_state()
    if state["bug"] != "none":
        print("[deploy] fault-injected release is running but NOT promoted to 'last good'")
        T.save_state({**old, "current_tag": state["tag"]})
        return {"outcome": "healthy_not_promoted"}
    T.save_state({"last_good_tag": state["tag"], "current_tag": state["tag"], "previous_good_tag": old.get("last_good_tag")})
    return {"outcome": "healthy"}


def llm_diagnose(state, logs):
    prompt = f"""You are a DevOps assistant. A new release of a web app failed its health check right after deployment.
Release tag: {state['tag']}
BUG_MODE environment variable of the new container: {state['bug']}
Health check result: {state['health_msg']}
Container logs (tail):
{logs[-3000:]}

Return ONLY a JSON object with keys:
- diagnosis: string, one or two sentences
- likely_cause: string
- recommended_action: "rollback" or "investigate"
- confidence: "low", "medium" or "high"
Do not invent facts that are not in the data above."""
    try:
        from . import llm
        return llm.ask_json(prompt), "llm"
    except Exception as e:
        return ({"diagnosis": f"Health endpoint answered: {state['health_msg']}", "likely_cause": "unknown (LLM unavailable)",
                 "recommended_action": "rollback", "confidence": "low"}, f"fallback ({type(e).__name__})")


def diagnose(state):
    logs = T.container_logs()
    d, src = llm_diagnose(state, logs)
    prev = T.load_state().get("last_good_tag")
    print(f"[diagnose] ({src}) {d.get('diagnosis')}")
    print(f"[diagnose] likely cause: {d.get('likely_cause')} | recommended: {d.get('recommended_action')} | confidence: {d.get('confidence')}")
    return {"logs": logs, "diagnosis": d, "source": src, "previous": prev}


def approval(state):
    prev = state.get("previous")
    if not prev:
        print("[approval] no previous good version to roll back to")
        return {"approved": False, "outcome": "failed_no_previous"}
    if not T.image_exists(prev):
        print(f"[approval] previous image {prev} no longer exists")
        return {"approved": False, "outcome": "previous_image_missing"}
    if state.get("auto_yes"):
        print(f"[approval] auto-approved (--yes): rollback to {prev}")
        return {"approved": True}
    ans = input(f"[approval] Roll back to last good version '{prev}'? [y/N]: ").strip().lower()
    if ans == "y":
        return {"approved": True}
    return {"approved": False, "outcome": "rollback_declined"}


def route_approval(state):
    return "rollback" if state.get("approved") else "report"


def rollback(state):
    prev = state["previous"]
    print(f"[rollback] restoring {prev} ...")
    T.run_container(prev, "none")
    ok, msg = T.health_check()
    rec = round(time.time() - state["t_fail"], 1)
    print(f"[rollback] {'HEALTHY' if ok else 'STILL UNHEALTHY'}: {msg}")
    if ok:
        st = T.load_state(); st["current_tag"] = prev; T.save_state(st)
    return {"outcome": "rolled_back" if ok else "rollback_failed", "recover_s": rec}


def report(state):
    out = state.get("outcome", "unknown")
    print("\n" + "=" * 60)
    print(f"DEPLOYMENT REPORT  release {state['tag']}  (BUG_MODE={state['bug']})")
    print("=" * 60)
    print(f"Outcome            : {out}")
    if state.get("detect_s") is not None:
        print(f"Failure detected in: {state['detect_s']}s after start")
    if state.get("recover_s") is not None:
        print(f"Recovered in       : {state['recover_s']}s after detection")
    if state.get("diagnosis"):
        print(f"Diagnosis          : {state['diagnosis'].get('diagnosis')}")
    entry = {"tag": state["tag"], "bug": state["bug"], "outcome": out, "detect_seconds": state.get("detect_s"),
             "recover_seconds": state.get("recover_s"), "diagnosis": state.get("diagnosis"), "analysed_by": state.get("source")}
    T.audit(entry)
    return {}


def build_graph():
    g = StateGraph(State)
    for name, fn in [("build", build), ("deploy", deploy), ("health", health), ("mark_good", mark_good), ("diagnose", diagnose),
                     ("approval", approval), ("rollback", rollback), ("report", report)]:
        g.add_node(name, fn)
    g.set_entry_point("build")
    g.add_conditional_edges("build", lambda s: "deploy" if s.get("build_ok") else "report", {"deploy": "deploy", "report": "report"})
    g.add_edge("deploy", "health")
    g.add_conditional_edges("health", route_health, {"mark_good": "mark_good", "diagnose": "diagnose"})
    g.add_edge("mark_good", "report")
    g.add_edge("diagnose", "approval")
    g.add_conditional_edges("approval", route_approval, {"rollback": "rollback", "report": "report"})
    g.add_edge("rollback", "report")
    g.add_edge("report", END)
    return g.compile()


def main():
    ap = argparse.ArgumentParser(description="Deployment Agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("deploy")
    d.add_argument("--bug", default="none", choices=["none", "crash", "leak", "slow"])
    d.add_argument("--tag")
    d.add_argument("--yes", action="store_true", help="approve rollback automatically")
    sub.add_parser("status")
    a = ap.parse_args()
    if a.cmd == "status":
        print(T.load_state()); return
    if not T.docker_available():
        print("Docker is not running. Start Docker Desktop and try again."); return
    tag = a.tag or datetime.now().strftime("%Y%m%d-%H%M%S")
    build_graph().invoke({"tag": tag, "bug": a.bug, "auto_yes": a.yes})


if __name__ == "__main__":
    main()
