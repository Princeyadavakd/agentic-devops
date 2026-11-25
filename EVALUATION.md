# Phase 6: Evaluation (real numbers for the report)

Goal: agent-assisted vs manual handling, aur Pipeline Agent ka RCA accuracy. Ye numbers report/PPT ke "Results" slide ke liye hain.
Fake ya andaze ke numbers kabhi mat likhna, sirf `python -m eval.summarize` ka output.

## 0. Setup
Zip ko project folder mein extract karo.   `python -m pip install -r requirements-phase6.txt`   (matplotlib, chart ke liye)
Docker Desktop + Prometheus (Phase 4) running ho, aur ek normal release deployed ho:   `python -m agent.deployment_agent deploy`
    
## A. RCA accuracy (Pipeline Agent) - 5 bugs, ~20 min
Terminal 1 mein agent chalta rakho (naye failures khud pakdega, time bhi sahi aayega):   `python -m agent.watch`
Terminal 2, har bug ke liye (user_lookup, discount_formula, health_status, home_status_code, user_name):
    python -m eval.inject_ci_bug apply user_lookup     # bug commit + push (ground truth save hota hai)
    -> GitHub Actions mein red cross ka wait karo; agent output Terminal 1 mein aayega
    python -m eval.inject_ci_bug revert                # app wapas theek + push
    -> green tick ka wait karo, phir agla bug
Phir:   `python -m eval.rca_accuracy`    (test aur file dono sahi = correct)
Dhyan: `python -m eval.inject_ci_bug list` se saare bugs dikhte hain. Working tree mein app/app.py par uncommitted change nahi hona chahiye.

## B. Manual baseline (aap haath se karo, stopwatch script naapegi)
Har scenario kam se kam 3 baar:
    python -m eval.manual_baseline record crash          # faulty release chal raha hai, purana good version haath se wapas lao
    python -m eval.manual_baseline record service_down   # container kill hai, haath se wapas lao
    python -m eval.manual_baseline record ci_failure     # failed CI log padho, jab test + file mil jaye tab Enter
Ye sab ek-ek kar ke, normal tareeke se (browser, docker commands). Scripts/copy-paste shortcuts mat banao, nahi to baseline unfair hoga.
(ci_failure ke liye pehle koi bug inject karke CI red karo.)

## C. Agent runs (same scenarios, 3 baar)
    python -m agent.deployment_agent deploy --bug crash --yes         # detect + rollback time (--yes: insaan ka delay nahi judta)
Service down: Terminal 1 mein `python -m agent.monitoring_agent watch --yes`, Terminal 2 mein `docker kill agentic-app`
Memory leak (optional, 2 baar): monitoring `watch --yes` chalu rakho, phir
    python -m agent.deployment_agent deploy --bug leak
    python -m agent.load_gen --seconds 120 --rps 1
Har run ke baad agent normal state mein wapas aata hai; agla run se pehle `python -m agent.deployment_agent status` dekh lo.

## D. Results
    python -m eval.summarize
Banega: eval/results/results.md (table), results.csv, mttr_chart.png (manual vs agent bar chart).
CI diagnosis time mein sirf wo runs aate hain jo 600 s se tez the (`--max-diagnose` se badlo): agent late chalaya ho to us run ko ginna unfair hai.

## Report mein likhne ke liye honest limitations
- Chhota sample (har scenario mein kuch hi runs); results indicative hain, statistical proof nahi.
- Manual baseline ek aisa insaan hai jo screen dekh raha hai; asli on-call mein detection ka delay zyada hota hai.
- Agent ka time Gemini free tier ki speed/availability par depend karta hai.
- Test app chhota hai (Flask demo), production system nahi.
