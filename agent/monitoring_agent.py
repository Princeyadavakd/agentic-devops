"""Monitoring Agent: watches Prometheus metrics, detects anomalies, explains them with an LLM,
asks for approval and then restarts or rolls back the service.

Usage (project root, venv active, Prometheus + app running):
  python -m agent.monitoring_agent watch            # asks approval before acting
  python -m agent.monitoring_agent watch --yes      # acts automatically (for MTTR measurement)
  python -m agent.monitoring_agent once             # print current metrics once
"""
import argparse
import os
import time
from typing import Any, Dict, Optional, TypedDict

from langgraph.graph import END, StateGraph

from . import prom
from . import tools_docker as T

MEM_MB = float(os.getenv("MEM_THRESHOLD_MB", "100"))
ERR_RATE = float(os.getenv("ERR_THRESHOLD", "0.2"))
LAT_S = float(os.getenv("LAT_THRESHOLD_S", "1.5"))
CONSECUTIVE = int(os.getenv("CONSECUTIVE_BAD", "2"))
COOLDOWN_S = int(os.getenv("COOLDOWN_S", "20"))
ESCALATE_WINDOW_S = 300
MON_AUDIT = T.DATA / "monitoring_incidents.jsonl"

QUERIES = {
    "up": 'up{job="app"}',
    "error_rate": 'sum(rate(app_requests_total{endpoint!="/metrics",status=~"5.."}[30s])) / sum(rate(app_requests_total{endpoint!="/metrics"}[30s]))',
    "p95": 'histogram_quantile(0.95, sum(rate(app_request_latency_seconds_bucket{endpoint!="/metrics"}[30s])) by (le))',
    "mem_mb": 'process_resident_memory_bytes{job="app"} / 1024 / 1024',
}
ACTIONS = {"service_down": "restart", "memory_leak": "restart", "high_error_rate": "rollback", "high_latency": "rollback"}

# memory that survives between monitoring cycles
MEM: Dict[str, Any] = {"bad": 0, "first_bad": None, "last": None, "cooldown_until": 0.0}


def collect_metrics():
    return {k: prom.query(q) for k, q in QUERIES.items()}


def classify(m, mem_mb=MEM_MB, err=ERR_RATE, lat=LAT_S) -> Optional[str]:
    """Pure function: metrics dict -> anomaly name (or None)."""
    if m.get("up") is not None and m["up"] < 1:
        return "service_down"
    if m.get("error_rate") is not None and m["error_rate"] > err:
        return "high_error_rate"
    if m.get("mem_mb") is not None and m["mem_mb"] > mem_mb:
        return "memory_leak"
    if m.get("p95") is not None and m["p95"] > lat:
        return "high_latency"
    return None


def choose_action(anomaly, last=None, now=None, has_previous=True):
    """Policy: base action per anomaly; if a restart did not fix the same anomaly recently, escalate to rollback."""
    now = now or time.time()
    action = ACTIONS[anomaly]
    if action == "restart" and last and last["anomaly"] == anomaly and last["action"] == "restart" \
            and now - last["t"] < ESCALATE_WINDOW_S:
        action = "rollback"
    if action == "rollback" and not has_previous:
        action = "restart"
    return action


class State(TypedDict, total=False):
    auto_yes: bool
    metrics: Dict[str, Any]
    anomaly: Optional[str]
    confirmed: bool
    action: str
    explanation: Dict[str, Any]
    source: str
    approved: bool
    healthy: bool
    outcome: str
    mttr: float


def _fmt(v, nd=2):
    return "n/a" if v is None else f"{v:.{nd}f}"


def collect(state):
    m = collect_metrics()
    anomaly = classify(m)
    now = time.time()
    if anomaly:
        MEM["bad"] += 1
        MEM["first_bad"] = MEM["first_bad"] or now
    else:
        MEM["bad"], MEM["first_bad"] = 0, None
    confirmed = bool(anomaly) and MEM["bad"] >= CONSECUTIVE and now >= MEM["cooldown_until"]
    print(f"[{time.strftime('%H:%M:%S')}] up={_fmt(m['up'], 0)} err={_fmt(m['error_rate'])} p95={_fmt(m['p95'])}s "
          f"mem={_fmt(m['mem_mb'], 1)}MB -> {anomaly or 'ok'}" + (f" ({MEM['bad']}/{CONSECUTIVE})" if anomaly else ""))
    return {"metrics": m, "anomaly": anomaly, "confirmed": confirmed}


def route_collect(state):
    return "diagnose" if state["confirmed"] else "end"


def diagnose(state):
    prev = T.load_state().get("last_good_tag")
    action = choose_action(state["anomaly"], MEM["last"], has_previous=bool(prev and T.image_exists(prev)))
    m = state["metrics"]
    prompt = f"""You are a DevOps/SRE assistant. Monitoring detected an anomaly in a web service.
Anomaly type: {state['anomaly']}
Metrics: up={m['up']}, error_rate={m['error_rate']}, p95_latency_seconds={m['p95']}, memory_mb={m['mem_mb']}
Thresholds: memory>{MEM_MB}MB, error_rate>{ERR_RATE}, p95>{LAT_S}s
Planned action: {action}
Return ONLY a JSON object with keys:
- explanation: string, 1-2 sentences about what the metrics show
- likely_cause: string
- action_ok: true or false (is the planned action sensible?)
- confidence: "low", "medium" or "high"
Do not invent facts that are not in the data."""
    try:
        from . import llm
        exp, src = llm.ask_json(prompt), "llm"
    except Exception as e:
        exp, src = ({"explanation": f"{state['anomaly']} detected from metrics", "likely_cause": "unknown (LLM unavailable)",
                     "action_ok": True, "confidence": "low"}, f"fallback ({type(e).__name__})")
    print(f"[diagnose] ({src}) {exp.get('explanation')} | cause: {exp.get('likely_cause')} | confidence: {exp.get('confidence')}")
    print(f"[diagnose] planned action: {action.upper()}")
    return {"action": action, "explanation": exp, "source": src}


def approval(state):
    if state.get("auto_yes"):
        print(f"[approval] auto-approved (--yes): {state['action']}")
        return {"approved": True}
    ans = input(f"[approval] Do '{state['action']}' now? [y/N]: ").strip().lower()
    if ans != "y":
        MEM["cooldown_until"] = time.time() + 60
        print("[approval] declined; will not ask again for 60s")
    return {"approved": ans == "y"}


def route_approval(state):
    return "act" if state["approved"] else "end"


def act(state):
    action = state["action"]
    if action == "rollback":
        prev = T.load_state().get("last_good_tag")
        print(f"[act] rolling back to {prev} ...")
        T.run_container(prev, "none")
    else:
        print("[act] restarting container ...")
        T.restart_container()
    ok, msg = T.health_check(retries=8)
    mttr = round(time.time() - MEM["first_bad"], 1) if MEM["first_bad"] else None
    print(f"[verify] {'HEALTHY' if ok else 'STILL UNHEALTHY'}: {msg}")
    return {"healthy": ok, "mttr": mttr, "outcome": "recovered" if ok else "not_recovered"}


def report(state):
    print("\n" + "=" * 60)
    print(f"INCIDENT REPORT: {state['anomaly']}  ->  {state['action']}  ->  {state['outcome']}")
    if state.get("mttr") is not None:
        print(f"MTTR (first bad sample -> healthy): {state['mttr']}s")
    print("=" * 60 + "\n")
    T.audit({"anomaly": state["anomaly"], "action": state["action"], "outcome": state["outcome"], "mttr_seconds": state.get("mttr"),
             "metrics": state["metrics"], "explanation": state.get("explanation"), "analysed_by": state.get("source")}, MON_AUDIT)
    MEM["last"] = {"anomaly": state["anomaly"], "action": state["action"], "t": time.time()}
    MEM["cooldown_until"] = time.time() + COOLDOWN_S
    MEM["bad"], MEM["first_bad"] = 0, None
    return {}


def build_graph():
    g = StateGraph(State)
    for name, fn in [("collect", collect), ("diagnose", diagnose), ("approval", approval), ("act", act), ("report", report)]:
        g.add_node(name, fn)
    g.set_entry_point("collect")
    g.add_conditional_edges("collect", route_collect, {"diagnose": "diagnose", "end": END})
    g.add_edge("diagnose", "approval")
    g.add_conditional_edges("approval", route_approval, {"act": "act", "end": END})
    g.add_edge("act", "report")
    g.add_edge("report", END)
    return g.compile()


def main():
    ap = argparse.ArgumentParser(description="Monitoring Agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch")
    w.add_argument("--yes", action="store_true", help="approve actions automatically")
    w.add_argument("--interval", type=int, default=3, help="seconds between checks")
    sub.add_parser("once")
    a = ap.parse_args()
    if a.cmd == "once":
        m = collect_metrics(); print(m, "->", classify(m) or "ok"); return
    graph = build_graph()
    print(f"Monitoring (mem>{MEM_MB}MB, err>{ERR_RATE}, p95>{LAT_S}s, {CONSECUTIVE} bad checks in a row). Ctrl+C to stop.")
    try:
        while True:
            try:
                graph.invoke({"auto_yes": a.yes})
            except prom.PromUnavailable as e:
                print(f"[monitor] Prometheus not reachable ({e}). Is it running on {prom.URL}?")
            time.sleep(a.interval)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
