import os
import time

from flask import Flask, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

app = Flask(__name__)

REQUESTS = Counter("app_requests_total", "Total requests", ["endpoint", "status"])
LATENCY = Histogram("app_request_latency_seconds", "Request latency", ["endpoint"])

USERS = {
    1: {"name": "Aman", "email": "aman@example.com"},
    2: {"name": "Riya", "email": "riya@example.com"},
}

_leak = []  # used only when BUG_MODE=leak


def get_discount(price, percent):
    """Return price after applying a percentage discount."""
    return price - (price * percent / 100)


@app.before_request
def _start_timer():
    request._start = time.time()


@app.after_request
def _record_metrics(resp):
    REQUESTS.labels(request.path, resp.status_code).inc()
    LATENCY.labels(request.path).observe(time.time() - request._start)
    return resp


@app.route("/")
def home():
    # Runtime faults for the monitoring demo (set BUG_MODE env var).
    mode = os.getenv("BUG_MODE", "none")
    if mode == "crash":
        return jsonify(error="simulated crash"), 500
    if mode == "leak":
        _leak.append(bytearray(5 * 1024 * 1024))  # leak 5 MB per request
    if mode == "slow":
        time.sleep(2)
    return jsonify(message="Demo app is running", bug_mode=mode)


@app.route("/health")
def health():
    if os.getenv("BUG_MODE", "none") == "crash":
        return jsonify(status="unhealthy"), 500
    return jsonify(status="ok")


@app.route("/users/<int:uid>")
def get_user(uid):
    return jsonify(USERS[uid])


@app.route("/discount/<int:price>/<int:percent>")
def discount(price, percent):
    return jsonify(final_price=get_discount(price, percent))


@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
