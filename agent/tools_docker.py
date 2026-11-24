"""Docker + health-check tools used by the Deployment Agent (the agent's 'hands')."""
import json
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGE = "devops-demo-app"
CONTAINER = "agentic-app"
HOST_PORT = 5001
HEALTH_URL = f"http://localhost:{HOST_PORT}/health"
DATA = ROOT / "data"
STATE_FILE = DATA / "deploy_state.json"
AUDIT_FILE = DATA / "deployments.jsonl"


def _run(args, timeout=300):
    p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).strip()


def docker_available():
    try:
        return _run(["docker", "info"], 30)[0] == 0
    except Exception:
        return False


def build_image(tag):
    return _run(["docker", "build", "-t", f"{IMAGE}:{tag}", "."], 600)


def image_exists(tag):
    return _run(["docker", "image", "inspect", f"{IMAGE}:{tag}"], 30)[0] == 0


def remove_container():
    _run(["docker", "rm", "-f", CONTAINER], 60)


def run_container(tag, bug="none"):
    remove_container()
    return _run(["docker", "run", "-d", "--name", CONTAINER, "-p", f"{HOST_PORT}:5000", "-m", "256m",
                 "-e", f"BUG_MODE={bug}", f"{IMAGE}:{tag}"], 120)


def container_logs(lines=40):
    return _run(["docker", "logs", "--tail", str(lines), CONTAINER], 60)[1]


def health_check(retries=6, delay=2, url=HEALTH_URL):
    """Return (healthy, message). Healthy only if /health answers HTTP 200."""
    last = "no response"
    for _ in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                body = r.read().decode(errors="replace")
                if r.status == 200:
                    return True, f"200 {body.strip()}"
                last = f"{r.status} {body.strip()}"
        except urllib.error.HTTPError as e:
            last = f"{e.code} {e.read().decode(errors='replace').strip()}"
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(delay)
    return False, last


def load_state(path=STATE_FILE):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {"last_good_tag": None, "current_tag": None}


def save_state(state, path=STATE_FILE):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(state, indent=2), encoding="utf-8")


def audit(entry, path=AUDIT_FILE):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    entry = {"time": datetime.now(timezone.utc).isoformat(), **entry}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
