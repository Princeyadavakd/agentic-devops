# Agentic AI-Based DevOps Automation Platform: Phase 1

Sample Flask app + Docker + GitHub Actions CI. Later phases add the AI agents on top of this.

## 1. One-time setup (Windows)
Install: Python 3.11, Git, VS Code, Docker Desktop (WSL2 backend).

Limit WSL2 memory (important for 8 GB RAM). Create `C:\Users\<YourName>\.wslconfig`:

    [wsl2]
    memory=3GB
    processors=4
    swap=2GB

Then run `wsl --shutdown` in PowerShell and restart Docker Desktop.

## 2. Run tests locally (PowerShell, inside this folder)
    python -m venv venv
    venv\Scripts\activatex
    pip install -r requirements-dev.txt
    pytest -v

All 5 tests should pass.

## 3. Run with Docker
    docker compose up --build

Open: http://localhost:5000/ , /health , /users/1 , /metrics

Stop with Ctrl+C, then `docker compose down`.

## 4. Push to GitHub (public repo, so Actions is free)
Create an empty repo on github.com, then:

    git init
    git add .
    git commit -m "Phase 1: sample app, Docker, CI"
    git branch -M main
    git remote add origin https://github.com/<username>/<repo>.git
    git push -u origin main

Open the Actions tab; the CI should go green.

## 5. Fault modes (used in the demo later)
PowerShell:

    $env:BUG_MODE="crash"; docker compose up -d --build   # / and /health return 500
    $env:BUG_MODE="leak";  docker compose up -d --build   # each / call leaks 5 MB
    $env:BUG_MODE="slow";  docker compose up -d --build   # / takes 2 s
    $env:BUG_MODE="none";  docker compose up -d --build   # back to normal

## 6. CI-failure demo bug
In `app/app.py`, inside `get_user`, replace the body with:

    return jsonify(USERS[uid])

(removes the "user not found" check). Push to GitHub: `test_missing_user_returns_404`
fails in CI because unknown users now crash with a KeyError. The Pipeline Agent (Phase 2)
will read that CI log and explain the fix.
