# Phase 4: Monitoring Agent

Agent Prometheus se metrics (up, error rate, p95 latency, memory) padhta hai. Anomaly mile to LLM se explain karwata hai,
approval maangta hai, phir restart ya rollback karta hai. Agar restart se same problem wapas aaye to khud rollback par escalate karta hai.

## 1. Files copy karo
Zip ko project folder mein extract karo. Ye files overwrite hongi: `agent/tools_docker.py`, `agent/deployment_agent.py`
(ab fault-injected release "last good" nahi banta). Naya: `agent/prom.py`, `agent/monitoring_agent.py`, `agent/load_gen.py`,
`monitoring/prometheus.yml`, `docker-compose.monitoring.yml`.

## 2. Prometheus chalu karo (Docker Desktop running ho)
    docker compose -p monitoring -f docker-compose.monitoring.yml up -d
Browser: http://localhost:9090/targets  -> job "app" ka state UP hona chahiye (app pehle deploy karni padegi, step 3).
Grafana optional (zyada RAM): `docker compose -p monitoring -f docker-compose.monitoring.yml --profile grafana up -d`
-> http://localhost:3000 (admin/admin) -> Data source Prometheus, URL `http://prometheus:9090`.

## 3. Normal release deploy karo (last good ban jayega)
    python -m agent.deployment_agent deploy

## 4. Demo A: memory leak  (2 terminals, dono mein venv active)
Terminal 1:
    python -m agent.monitoring_agent watch
Terminal 2:
    python -m agent.deployment_agent deploy --bug leak
    python -m agent.load_gen --seconds 120 --rps 1
Terminal 1 mein memory badhti dikhegi; 100 MB cross hone par `memory_leak` detect -> explain -> "Do 'restart' now? [y/N]" -> y.
Leak (BUG_MODE=leak) restart ke baad bhi wapas aayega, to agent agli baar `rollback` plan karega -> y -> healthy.

## 5. Demo B: service down
    docker kill agentic-app
Agent `service_down` dekhega -> restart -> healthy.

## 6. Demo C: slow release
    python -m agent.deployment_agent deploy --bug slow
    python -m agent.load_gen --seconds 60 --rps 1
`high_latency` -> rollback.

## MTTR numbers
`watch --yes` chalao (approval ke bina). Har incident `data/monitoring_incidents.jsonl` mein jaata hai (mttr_seconds, anomaly, action).
Thresholds badalne ke liye env vars: MEM_THRESHOLD_MB, ERR_THRESHOLD, LAT_THRESHOLD_S, CONSECUTIVE_BAD, COOLDOWN_S.

## Band karna
    docker compose -p monitoring -f docker-compose.monitoring.yml down
