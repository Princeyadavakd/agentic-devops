"""Streamlit dashboard for the Agentic DevOps platform.  Run:  streamlit run dashboard/app.py"""
import sys
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_utils as D  # noqa: E402
from agent import prom  # noqa: E402

st.set_page_config(page_title="Agentic DevOps Platform", layout="wide")
st.title("Agentic AI-Based DevOps Automation Platform")
st.caption("Live view of the Pipeline, Deployment and Monitoring agents")

auto = st.sidebar.checkbox("Auto refresh (10 s)", value=True)
st.sidebar.button("Refresh now")
st.sidebar.markdown("Data folder: `" + str(D.DATA) + "`")

ci, dep, mon = D.ci_table(), D.deploy_table(), D.monitor_table()

st.subheader("Live service metrics (Prometheus)")
Q = {"Service up": 'up{job="app"}', "Memory (MB)": 'process_resident_memory_bytes{job="app"} / 1024 / 1024',
     "Error rate": 'sum(rate(app_requests_total{endpoint!="/metrics",status=~"5.."}[30s])) / sum(rate(app_requests_total{endpoint!="/metrics"}[30s]))',
     "p95 latency (s)": 'histogram_quantile(0.95, sum(rate(app_request_latency_seconds_bucket{endpoint!="/metrics"}[30s])) by (le))'}
try:
    cols = st.columns(len(Q))
    for col, (name, q) in zip(cols, Q.items()):
        v = prom.query(q)
        col.metric(name, "n/a" if v is None else f"{v:.2f}")
except prom.PromUnavailable:
    st.warning("Prometheus is not reachable on " + prom.URL + ". Start it with docker compose (see PHASE4.md).")

st.subheader("Summary")
k = st.columns(5)
k[0].metric("CI failures analysed", len(ci))
k[1].metric("Deployments", len(dep))
k[2].metric("Rollbacks", int((dep["outcome"] == "rolled_back").sum()) if len(dep) else 0)
k[3].metric("Monitoring incidents", len(mon))
mt = mon["mttr_seconds"].dropna() if len(mon) else []
k[4].metric("Avg monitoring MTTR (s)", f"{mt.mean():.1f}" if len(mt) else "n/a")

state = D.DATA / "deploy_state.json"
if state.exists():
    st.info("Deployment state: " + state.read_text(encoding="utf-8").replace("\n", " "))

t1, t2, t3, t4, t5 = st.tabs(["Timeline / audit log", "CI failures (Pipeline Agent)", "Deployments", "Monitoring incidents", "MTTR chart"])
with t1:
    tl = D.timeline()
    st.dataframe(tl, use_container_width=True) if len(tl) else st.write("No events yet.")
with t2:
    st.dataframe(ci, use_container_width=True) if len(ci) else st.write("No CI failures analysed yet.")
with t3:
    st.dataframe(dep, use_container_width=True) if len(dep) else st.write("No deployments yet.")
with t4:
    st.dataframe(mon, use_container_width=True) if len(mon) else st.write("No monitoring incidents yet.")
with t5:
    if len(mon) and mon["mttr_seconds"].notna().any():
        st.bar_chart(mon.reset_index()[["index", "mttr_seconds"]].set_index("index"))
    else:
        st.write("MTTR chart appears after the first recovered monitoring incident.")

if auto:
    time.sleep(10)
    st.rerun()
