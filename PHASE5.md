# Phase 5: Orchestrator + Telegram approval + Dashboard

Ek process (orchestrator) jo CI failures, monitoring aur Telegram commands ko sahi agent tak route karta hai.
Risky actions (rollback / restart / deploy) ka approval Telegram ke Approve/Reject buttons se hota hai. Sab kuch audit log (data/*.jsonl) mein jaata hai
aur Streamlit dashboard usse live dikhata hai.

## 1. Files copy karo
Zip ko project folder mein extract karo. Naya: agent/notify.py, agent/orchestrator.py, dashboard/, requirements-phase5.txt.
(.env.example overwrite hoga: wo sirf khali template hai, apni .env ko kuch nahi hota.)

    python -m pip install -r requirements-phase5.txt

## 2. Telegram bot banao (free, 2 minute)
1. Telegram mein @BotFather kholo -> /newbot -> naam aur username do -> wo TOKEN dega.
2. `.env` kholo (notepad .env) aur ye line daalo (token chat mein mat bhejna):
       TELEGRAM_BOT_TOKEN=<token>
3. Apne naye bot ko Telegram mein kholo, Start dabao aur "hi" bhejo.
4. Chat id nikalo:
       python -m agent.notify setup
   Jo `chat id: 123456789` aaye use `.env` mein daalo:  TELEGRAM_CHAT_ID=123456789
5. Test:
       python -m agent.notify test
   Telegram mein Approve dabao -> terminal mein APPROVED dikhna chahiye.
Bot sirf tumhari chat id ki baat sunta hai (doosra koi command nahi de sakta).
Telegram set na ho to bhi sab chalega: approval terminal mein poocha jayega.

## 3. Sab chalao (Docker Desktop + Prometheus + app deployed hona chahiye: Phase 3/4 steps)
Terminal 1 (venv active):
    python -m agent.orchestrator run
Terminal 2:
    streamlit run dashboard/app.py
Dashboard: http://localhost:8501

## 4. Demo
- Telegram mein `/status` -> current/last good release + metrics.
- `/deploy crash` -> health fail -> diagnosis -> Telegram pe "Approval needed: Roll back ...?" -> Approve -> rollback -> healthy.
- `/deploy leak`, phir terminal 3 mein `python -m agent.load_gen --seconds 120 --rps 1`
  -> monitoring memory leak pakadta hai -> Telegram approval -> restart/rollback.
- Koi test jaanbujhkar todke push karo -> Telegram pe CI failure ka root cause + fix aata hai.
- Dashboard mein Timeline tab sab agents ka audit log dikhata hai.

## Dhyan do
- Approval hook agents ke `[approval] ... [y/N]:` wale prompts ko Telegram par bhejta hai. Agar tumne agents ke prompt text badle hain, `[approval]` rakhna.
- Ek waqt mein ek hi action chalta hai (lock), isliye deploy ke dauraan monitoring pause rehta hai (false alarm nahi).
- Screenshots lo: Telegram approval message, dashboard (summary + timeline), orchestrator terminal.
