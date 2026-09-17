"""Eval runner using execution accuracy.

Reads evals/eval_set.jsonl, calls the agent at AGENT_URL on each question,
then compares the agent's SQL output to the gold SQL by *executed rows*
(canonicalized: sorted, stringified, None-coerced to empty).

Helpers (run_sql / canonicalize / matches) are provided. You implement
eval_one() and summarize().

Run:
    uv run python evals/run_eval.py --out results/eval_baseline.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVAL_FILE = ROOT / "evals" / "eval_set.jsonl"
DEFAULT_OUT_FILE = ROOT / "results" / "eval_baseline.json"
DB_DIR = ROOT / "data" / "bird"
AGENT_URL_DEFAULT = "http://localhost:8001/answer"


# ---------- Helpers (provided) -----------------------------------------

def run_sql(db_id: str, sql: str, timeout: float = 5.0) -> tuple[bool, list[tuple] | None, str | None]:
    """Run sql against db_id in read-only mode. Returns (ok, rows, error)."""
    path = DB_DIR / f"{db_id}.sqlite"
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=timeout) as conn:
            cur = conn.execute(sql)
            rows = cur.fetchall()
            return True, rows, None
    except Exception as e:  # noqa: BLE001
        return False, None, f"{type(e).__name__}: {e}"


def canonicalize(rows: list[tuple] | None) -> list[tuple] | None:
    """Sort rows; coerce cells to str; None -> ''."""
    if rows is None:
        return None
    return sorted(tuple("" if c is None else str(c) for c in row) for row in rows)


def matches(gold_rows: list[tuple] | None, pred_rows: list[tuple] | None) -> bool:
    if gold_rows is None or pred_rows is None:
        return False
    return canonicalize(gold_rows) == canonicalize(pred_rows)


# ---------- Implement these (Phase 5) ----------------------------------

def eval_one(question: dict, agent_url: str) -> dict:
    """Score one question. Return a dict capturing per-iteration correctness."""
    db_id = question["db_id"]
    gold_sql = question["gold_sql"]
    gold_ok, gold_rows, gold_error = run_sql(db_id, gold_sql)

    result = {
        "question": question["question"],
        "db_id": db_id,
        "gold_sql": gold_sql,
        "gold_ok": gold_ok,
        "gold_error": gold_error,
        "agent_sql": "",
        "agent_ok": False,
        "agent_error": None,
        "iterations": 0,
        "correct": False,
        "iteration_results": [],
    }

    try:
        response = httpx.post(
            agent_url,
            json={
                "question": question["question"],
                "db": db_id,
                "metadata": {"eval": "baseline"},
                "tags": ["eval", "baseline"],
            },
            timeout=300.0,
        )
        response.raise_for_status()
        answer = response.json()
    except (httpx.HTTPError, ValueError) as error:
        result["agent_error"] = f"{type(error).__name__}: {error}"
        return result

    result["agent_sql"] = answer.get("sql", "")
    result["agent_ok"] = answer.get("ok") is True
    result["agent_error"] = answer.get("error")
    result["iterations"] = int(answer.get("iterations", 0))

    attempts = [
        entry.get("sql", "")
        for entry in answer.get("history", [])
        if entry.get("node") in {"generate_sql", "revise"}
    ]
    if not attempts and result["agent_sql"]:
        attempts = [result["agent_sql"]]

    for iteration, sql in enumerate(attempts):
        pred_ok, pred_rows, pred_error = run_sql(db_id, sql)
        result["iteration_results"].append({
            "iteration": iteration,
            "sql": sql,
            "ok": pred_ok,
            "error": pred_error,
            "correct": gold_ok and pred_ok and matches(gold_rows, pred_rows),
        })

    if result["iteration_results"]:
        result["correct"] = result["iteration_results"][-1]["correct"]
    return result


def summarize(results: list[dict]) -> dict:
    """Aggregate per-question results.

    Per-iteration carry-forward: if the agent terminated at iteration j < k
    (verify said ok at j, or it hit MAX_ITERATIONS at j < k), treat the
    question's iteration-k result as identical to its iteration-j result.
    The agent stopped emitting; whatever it had at termination is what
    would have been served had we polled at iteration k.
    """
    total = len(results)
    passed = sum(result.get("correct") is True for result in results)
    max_iteration = max(
        (
            max(
                int(result.get("iterations", 0)),
                len(result.get("iteration_results", [])) - 1,
            )
            for result in results
        ),
        default=0,
    )

    pass_rate_by_iteration: dict[str, float] = {}
    passed_by_iteration: dict[str, int] = {}
    for iteration in range(max_iteration + 1):
        iteration_passed = 0
        for result in results:
            attempts = result.get("iteration_results", [])
            if not attempts:
                continue
            carried_result = attempts[min(iteration, len(attempts) - 1)]
            iteration_passed += carried_result.get("correct") is True
        passed_by_iteration[str(iteration)] = iteration_passed
        pass_rate_by_iteration[str(iteration)] = iteration_passed / total if total else 0.0

    return {
        "total": total,
        "passed": passed,
        "pass_rate": passed / total if total else 0.0,
        "average_iterations": (
            sum(int(result.get("iterations", 0)) for result in results) / total
            if total
            else 0.0
        ),
        "passed_by_iteration": passed_by_iteration,
        "pass_rate_by_iteration": pass_rate_by_iteration,
    }


# ---------- Main (provided) --------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-set", type=Path, default=DEFAULT_EVAL_FILE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_FILE)
    parser.add_argument("--agent-url", default=AGENT_URL_DEFAULT)
    args = parser.parse_args()

    questions = [json.loads(line) for line in args.eval_set.read_text().splitlines() if line.strip()]
    print(f"Loaded {len(questions)} eval questions from {args.eval_set}")

    results: list[dict] = []
    t0 = time.monotonic()
    for i, q in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] {q['db_id']}: {q['question'][:60]}...", flush=True)
        results.append(eval_one(q, args.agent_url))
    elapsed = time.monotonic() - t0

    summary = summarize(results)
    out = {
        "summary": summary,
        "wall_clock_seconds": elapsed,
        "results": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print(f"Wrote {args.out}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
