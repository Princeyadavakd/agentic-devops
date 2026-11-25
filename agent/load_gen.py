"""Sends steady traffic to the app so that metrics have data (needed for the leak / slow demos).
Usage: python -m agent.load_gen --seconds 90 --rps 1
"""
import argparse
import time
import urllib.error
import urllib.request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--rps", type=float, default=1.0)
    ap.add_argument("--url", default="http://localhost:5001/")
    a = ap.parse_args()
    end, n, bad, last = time.time() + a.seconds, 0, 0, time.time()
    while time.time() < end:
        try:
            urllib.request.urlopen(a.url, timeout=8).read()
        except Exception:
            bad += 1
        n += 1
        if time.time() - last >= 5:
            print(f"sent {n} requests ({bad} failed)"); last = time.time()
        time.sleep(1.0 / a.rps)
    print(f"done: {n} requests, {bad} failed")


if __name__ == "__main__":
    main()
