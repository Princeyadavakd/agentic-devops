# Phase 2: Pipeline Agent

## 1. Files copy karo
Is zip ko project folder mein extract karo (`agent/`, `.env.example`, `.gitignore`, `PHASE2.md` aayenge; `.gitignore` overwrite hoga, theek hai).

## 2. Tokens
- GitHub: Settings > Developer settings > Personal access tokens > Fine-grained tokens > Generate.
  Repository access: Only select repositories > agentic-devops.
  Permissions: Actions = Read-only, Contents = Read-only. Expiry 30-90 din.
- Gemini: aistudio.google.com > Get API key.

## 3. .env banao (PowerShell, project folder mein)
    copy .env.example .env
    notepad .env
GITHUB_TOKEN, GITHUB_REPO (username/agentic-devops) aur GEMINI_API_KEY bharo. Save karo.
`.env` GitHub pe push NAHI hogi (.gitignore mein hai). Key kisi ko mat dikhao.

## 4. Install (venv active ho)
    python -m pip install -r agent/requirements.txt

## 5. CI ko jaanbujhkar fail karo
`app/app.py` mein `get_user` function ki body ko is se replace karo:

    def get_user(uid):
        return jsonify(USERS[uid])

Phir:
    git add . ; git commit -m "break user lookup (demo)" ; git push
GitHub Actions mein red cross aayega (1-2 min).

## 6. Agent chalao
    python -m agent.pipeline_agent --latest-failed
Ya continuous mode (naye failures apne aap pakdega):
    python -m agent.watch

Output data/incidents.jsonl mein bhi save hota hai (audit log + MTTR numbers ke liye).

## Troubleshooting
- 404 model not found: AI Studio mein dekho kaunsa Gemini model available hai, .env mein GEMINI_MODEL badlo.
- 401/403 GitHub: token permissions ya GITHUB_REPO spelling check karo.
- "fallback" source dikhe: LLM call fail hui; agent rule-based analysis pe chala gaya (ye feature hai).
