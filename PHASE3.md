# Phase 3: Deployment Agent

Agent ka kaam: naya release build + deploy karna, /health check karna, fail hone par diagnose karke (approval ke baad) purane good version par rollback karna.

## 0. Pehle (agar nahi kiya)
app.py ka demo bug wapas theek karo, taaki CI green rahe:
    git log --oneline -5
    git revert <hash-of-"break user lookup (demo)"> --no-edit
    git push

## 1. Files copy karo
Zip ko project folder mein extract karo. `agent/tools_docker.py`, `agent/deployment_agent.py`, `PHASE3.md` aayenge aur `Dockerfile` overwrite hoga
(sirf `--access-logfile -` add hua hai, taaki container logs mein requests dikhein).

## 2. Docker Desktop chalu karo (Engine running)
Agent apna alag container `agentic-app` port **5001** par chalata hai, purana `devops-demo-app` (port 5000) chhedta nahi.

## 3. Demo (PowerShell, project folder, venv active)
1) Normal release: ye "last good" ban jayega
    python -m agent.deployment_agent deploy
   Browser: http://localhost:5001/health  ->  {"status":"ok"}

2) Faulty release (health fail hoga):
    python -m agent.deployment_agent deploy --bug crash
   Agent: health fail dekhega -> logs padhke LLM se diagnosis -> poochega "Roll back? [y/N]" -> y likho
   -> purana version wapas chalega -> health OK.

3) Bina poochhe (MTTR measure karne ke liye):
    python -m agent.deployment_agent deploy --bug crash --yes

4) State dekhna:
    python -m agent.deployment_agent status

Audit log: data/deployments.jsonl (detect_seconds, recover_seconds, outcome).

## Notes
- `--bug crash` health fail karta hai. `leak` aur `slow` health check mein nahi pakde jaate; unhe Phase 4 (Monitoring Agent) pakdega.
- Pehli baar `deploy` chalane par image build mein 1-2 minute lag sakte hain.
- Pehla deploy hamesha normal (`--bug none`) karo, warna rollback ke liye koi purana good version nahi hoga.
