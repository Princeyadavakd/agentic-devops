"""Compares the Pipeline Agent's diagnoses with the ground truth saved by eval.inject_ci_bug.
  python -m eval.rca_accuracy
"""
from .common import load_jsonl


def compute():
    truth = load_jsonl("rca_ground_truth.jsonl")
    incidents = load_jsonl("incidents.jsonl")
    rows = []
    for t in truth:
        inc = next((i for i in reversed(incidents) if i.get("sha") == t["commit_sha"]), None)
        if not inc:
            rows.append({"bug": t["bug"], "analysed": False, "test_ok": False, "file_ok": False, "correct": False, "by": "-"})
            continue
        a = inc.get("analysis") or {}
        test_ok = t["expected_test"] in (a.get("failing_test") or "")
        file_ok = (a.get("file") or "").replace("\\", "/").endswith(t["expected_file"])
        rows.append({"bug": t["bug"], "analysed": True, "test_ok": test_ok, "file_ok": file_ok, "correct": test_ok and file_ok,
                     "by": "llm" if str(inc.get("source")) == "llm" else "fallback"})
    done = [r for r in rows if r["analysed"]]
    acc = (sum(r["correct"] for r in done) / len(done) * 100) if done else None
    return {"rows": rows, "analysed": len(done), "total": len(rows), "accuracy": acc}


def main():
    r = compute()
    print(f"{'bug':20s} {'analysed':9s} {'test':6s} {'file':6s} {'correct':8s} by")
    for x in r["rows"]:
        print(f"{x['bug']:20s} {str(x['analysed']):9s} {str(x['test_ok']):6s} {str(x['file_ok']):6s} {str(x['correct']):8s} {x['by']}")
    if r["accuracy"] is None:
        print("\nNo analysed incidents matched the injected bugs yet.")
    else:
        print(f"\nRCA accuracy: {r['accuracy']:.0f}%  ({sum(x['correct'] for x in r['rows'])}/{r['analysed']} analysed, {r['total']} injected)")


if __name__ == "__main__":
    main()
