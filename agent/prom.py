"""Tiny Prometheus HTTP API client (no extra dependencies)."""
import json
import math
import os
import urllib.parse
import urllib.request

URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")


class PromUnavailable(Exception):
    pass


def query(expr):
    """Run an instant query and return the first value as float, or None if there is no data."""
    url = f"{URL}/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.load(r)
    except Exception as e:
        raise PromUnavailable(str(e))
    result = data.get("data", {}).get("result", [])
    if not result:
        return None
    value = float(result[0]["value"][1])
    return None if math.isnan(value) else value
