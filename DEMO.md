# Live demo script (viva / presentation) - 6 minute flow

## Demo se pehle (10 min pehle)
- [ ] Docker Desktop "Engine running", `docker compose -p monitoring -f docker-compose.monitoring.yml up -d` (Prometheus)
- [ ] `python -m agent.deployment_agent deploy` (normal release = last good)
- [ ] Terminal 1: `python -m agent.orchestrator run`      Terminal 2: `streamlit run dashboard/app.py` (browser mein khula rakho)
- [ ] Telegram phone par khula; `python -m agent.notify test` ek baar pass karke dekh lo
- [ ] Internet check (Gemini). Backup: screenshots/video taiyaar rakho, API key screen pe na dikhe (.env band rakho)
- [ ] app/app.py theek hai aur GitHub Actions green hai

## Flow
1. **Idea (30 s)**: "DevOps mein pipelines fixed scripts hote hain. Humne LLM agents banaye jo failure samajhte hain, tools se action lete hain, aur risky kaam ke liye insaan se approval maangte hain."
2. **Architecture (30 s)**: PPT ka architecture slide: Orchestrator -> Pipeline / Deployment / Monitoring agents -> Telegram + Dashboard.
3. **CI failure (1.5 min)**: `python -m eval.inject_ci_bug apply user_lookup` (ya koi test todke push). Red cross dikhao.
   Telegram par root cause + fix aata hai. Bolo: "agent ne log padha, test aur file khud nikali."  Baad mein `inject_ci_bug revert`.
4. **Faulty deploy + rollback (2 min)**: Telegram mein `/deploy crash` -> health fail -> diagnosis -> Telegram par Approve/Reject -> Approve -> rollback -> healthy.
   Bolo: "risky action par agent akela nahi karta, human-in-the-loop."
5. **Monitoring (1.5 min)**: `/deploy leak` + `python -m agent.load_gen --seconds 90 --rps 1` -> memory leak detect -> approval -> restart -> dobara leak -> rollback (escalation).
   Ya chhota: `docker kill agentic-app` -> service_down -> restart.
6. **Dashboard + results (1 min)**: Timeline/audit log dikhao, phir results table (MTTR manual vs agent, RCA accuracy). Sirf apne asli numbers.
7. **Limitations + future (30 s)**: chhota sample, free-tier LLM; future: Kubernetes, security agent, self-learning from past incidents.

## Agar demo mein kuch fail ho
- Gemini slow/fail: agent rule-based fallback par chalta hai: "yeh humne design kiya hai, LLM down ho to bhi system kaam karta hai."
- Telegram na aaye: terminal mein approval prompt aayega (y likho).
- Sab fail ho to backup screenshots/video dikhao aur calmly explain karo.

## Viva ke 10 sawal (short answers)
1. *Agentic kya hai, chatbot se kaise alag?* Chatbot sirf jawab deta hai; agent tools call karke action leta hai aur result dekh kar agla step decide karta hai.
2. *LLM hallucinate kare to?* Approval gate, confidence level, tests dobara chalana, aur rule-based fallback.
3. *LangGraph kyun?* Agent flow ko nodes aur conditional edges ke graph ki tarah likhne deta hai (loops: analyse -> files maango -> dobara analyse).
4. *Security?* Read-only token, keys sirf .env mein (git mein nahi), Telegram sirf apni chat id sunta hai, risky action par approval.
5. *MTTR kaise naapa?* Audit logs mein timestamps; manual baseline stopwatch script se. Chhota sample hai, indicative.
6. *RCA accuracy kaise naapi?* 5 known bugs inject kiye; test aur file dono sahi hone par correct.
7. *Cloud kyun nahi?* Zero budget: sab laptop par Docker mein; Prometheus/Grafana open source; Gemini free tier + Ollama fallback.
8. *Restart vs rollback kab?* Policy: crash/slow release -> rollback; leak/down -> pehle restart, wapas aaye to rollback (escalation).
9. *Scale kaise karoge?* Kubernetes, multi-service, queue-based events, per-service agents.
10. *Is project ki limitation?* Demo app chhota hai, free LLM rate limit, sirf kuch fault types, sample size chhota.
