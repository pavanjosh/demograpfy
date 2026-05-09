"""
Eval runner + pytest unit tests for the Demografy LLM agent.

Unit tests (fast, no real LLM calls):
    pytest eval/run_eval.py -v

Full integration eval (calls the real agent + judge):
    python -m eval.run_eval
"""
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import pytest
    _parametrize = pytest.mark.parametrize
except ImportError:
    pytest = None

    def _parametrize(*args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

from eval.judge import judge_response

_DATASET_PATH = os.path.join(os.path.dirname(__file__), "golden_dataset.json")
_REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")

SCORE_LABELS = {5: "PERFECT", 4: "GOOD", 3: "OK", 2: "POOR", 1: "FAIL", 0: "ERROR"}
SCORE_COLORS = {5: "#16a34a", 4: "#65a30d", 3: "#ca8a04", 2: "#ea580c", 1: "#dc2626", 0: "#9ca3af"}
SCORE_BG     = {5: "#f0fdf4", 4: "#f7fee7", 3: "#fefce8", 2: "#fff7ed", 1: "#fef2f2", 0: "#f9fafb"}


def _load_dataset() -> list[dict]:
    with open(_DATASET_PATH) as f:
        return json.load(f)


def _unit_test_cases() -> list[dict]:
    return [c for c in _load_dataset() if "simulated_answer" in c]


def _integration_cases() -> list[dict]:
    return [c for c in _load_dataset() if "simulated_answer" not in c]


# ---------------------------------------------------------------------------
# Pytest unit tests — judge is called with simulated answers, no real agent
# ---------------------------------------------------------------------------

def _unit_test_ids(cases: list[dict]) -> list[str]:
    return [f"id{c['id']}_{c['test_label']}" for c in cases]


_ALL_UNIT_CASES = _unit_test_cases()
_HIGH_SCORE_CASES   = [c for c in _ALL_UNIT_CASES if c["expected_score_range"][0] >= 4]
_LOW_SCORE_CASES    = [c for c in _ALL_UNIT_CASES if c["expected_score_range"][1] <= 2]
_MEDIUM_SCORE_CASES = [
    c for c in _ALL_UNIT_CASES
    if c not in _HIGH_SCORE_CASES and c not in _LOW_SCORE_CASES
]


@_parametrize("case", _HIGH_SCORE_CASES, ids=_unit_test_ids(_HIGH_SCORE_CASES))
def test_judge_scores_high_quality_answers(case):
    """Good simulated answers should receive a score of 4 or 5."""
    verdict = judge_response(
        question=case["question"],
        answer=case["simulated_answer"],
        golden_answer=case["golden_answer"],
    )
    score = verdict.get("score", 0)
    lo, hi = case["expected_score_range"]
    assert lo <= score <= hi, (
        f"[{case['test_label']}] Expected score {lo}-{hi}, got {score}.\n"
        f"Reasoning: {verdict.get('reasoning', '-')}"
    )


@_parametrize("case", _LOW_SCORE_CASES, ids=_unit_test_ids(_LOW_SCORE_CASES))
def test_judge_scores_low_quality_answers(case):
    """Bad simulated answers should receive a score of 1 or 2."""
    verdict = judge_response(
        question=case["question"],
        answer=case["simulated_answer"],
        golden_answer=case["golden_answer"],
    )
    score = verdict.get("score", 0)
    lo, hi = case["expected_score_range"]
    assert lo <= score <= hi, (
        f"[{case['test_label']}] Expected score {lo}-{hi}, got {score}.\n"
        f"Reasoning: {verdict.get('reasoning', '-')}"
    )


@_parametrize("case", _MEDIUM_SCORE_CASES, ids=_unit_test_ids(_MEDIUM_SCORE_CASES))
def test_judge_scores_medium_quality_answers(case):
    """Partial simulated answers should receive a score of 2, 3, or 4."""
    verdict = judge_response(
        question=case["question"],
        answer=case["simulated_answer"],
        golden_answer=case["golden_answer"],
    )
    score = verdict.get("score", 0)
    lo, hi = case["expected_score_range"]
    assert lo <= score <= hi, (
        f"[{case['test_label']}] Expected score {lo}-{hi}, got {score}.\n"
        f"Reasoning: {verdict.get('reasoning', '-')}"
    )


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _score_badge(score: int) -> str:
    color = SCORE_COLORS.get(score, "#9ca3af")
    bg    = SCORE_BG.get(score, "#f9fafb")
    label = SCORE_LABELS.get(score, "UNKNOWN")
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:12px;'
        f'font-weight:700;font-size:13px;color:{color};background:{bg};'
        f'border:1px solid {color};">{score}/5 {label}</span>'
    )


def _dist_bar(count: int, total: int, color: str) -> str:
    pct = (count / total * 100) if total else 0
    return (
        f'<div style="display:flex;align-items:center;gap:8px;">'
        f'<div style="flex:1;background:#f3f4f6;border-radius:4px;height:12px;">'
        f'<div style="width:{pct:.1f}%;background:{color};height:100%;border-radius:4px;"></div>'
        f'</div>'
        f'<span style="min-width:28px;font-size:12px;color:#6b7280;">{count}</span>'
        f'</div>'
    )


def _generate_html_report(results: list[dict], avg: float, scores: list[int], timestamp: str) -> str:
    total = len(results)
    passed = sum(1 for s in scores if s >= 4)
    failed = sum(1 for s in scores if s <= 2)

    rows = ""
    for r in results:
        v     = r["verdict"]
        score = v.get("score", 0)
        answer_preview = r["answer"][:400] + ("…" if len(r["answer"]) > 400 else "")
        answer_preview = answer_preview.replace("<", "&lt;").replace(">", "&gt;")
        rows += f"""
        <tr style="border-bottom:1px solid #f3f4f6;">
          <td style="padding:14px 12px;vertical-align:top;width:32px;color:#9ca3af;font-size:13px;">#{r['id']}</td>
          <td style="padding:14px 12px;vertical-align:top;">
            <div style="font-weight:600;font-size:14px;color:#111827;margin-bottom:6px;">{r['question']}</div>
            <div style="font-size:12px;color:#6b7280;background:#f9fafb;padding:8px 10px;border-radius:6px;white-space:pre-wrap;">{answer_preview}</div>
          </td>
          <td style="padding:14px 12px;vertical-align:top;text-align:center;">{_score_badge(score)}</td>
          <td style="padding:14px 12px;vertical-align:top;font-size:12px;color:#374151;">
            <div><b>Relevance:</b> {v.get('relevance','-')}</div>
            <div style="margin-top:4px;"><b>Groundedness:</b> {v.get('groundedness','-')}</div>
            <div style="margin-top:4px;"><b>Completeness:</b> {v.get('completeness','-')}</div>
            <div style="margin-top:6px;font-style:italic;color:#6b7280;">{v.get('reasoning','-')}</div>
          </td>
        </tr>"""

    dist_rows = ""
    for s in [5, 4, 3, 2, 1, 0]:
        count = scores.count(s)
        if count == 0:
            continue
        color = SCORE_COLORS[s]
        label = SCORE_LABELS[s]
        dist_rows += f"""
        <tr>
          <td style="padding:6px 12px;font-size:13px;font-weight:600;color:{color};width:100px;">{s} — {label}</td>
          <td style="padding:6px 12px;">{_dist_bar(count, total, color)}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Demografy Eval Report — {timestamp}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin:0; background:#f8fafc; color:#111827; }}
    h1   {{ margin:0; font-size:22px; }}
    table{{ border-collapse:collapse; width:100%; }}
    th   {{ text-align:left; padding:10px 12px; font-size:12px; color:#6b7280; text-transform:uppercase; letter-spacing:.05em; border-bottom:2px solid #e5e7eb; }}
  </style>
</head>
<body>
<div style="max-width:1100px;margin:32px auto;padding:0 16px;">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#7c3aed,#4f46e5);border-radius:16px;padding:28px 32px;color:#fff;margin-bottom:24px;">
    <h1>Demografy LLM Eval Report</h1>
    <div style="margin-top:6px;opacity:.8;font-size:14px;">Generated {timestamp}</div>
    <div style="margin-top:20px;display:flex;gap:32px;flex-wrap:wrap;">
      <div>
        <div style="font-size:36px;font-weight:800;">{avg:.2f}<span style="font-size:18px;font-weight:400;opacity:.7"> / 5</span></div>
        <div style="font-size:12px;opacity:.7;margin-top:2px;">Average Score</div>
      </div>
      <div>
        <div style="font-size:36px;font-weight:800;">{total}</div>
        <div style="font-size:12px;opacity:.7;margin-top:2px;">Questions</div>
      </div>
      <div>
        <div style="font-size:36px;font-weight:800;color:#86efac;">{passed}</div>
        <div style="font-size:12px;opacity:.7;margin-top:2px;">Passed (≥4)</div>
      </div>
      <div>
        <div style="font-size:36px;font-weight:800;color:#fca5a5;">{failed}</div>
        <div style="font-size:12px;opacity:.7;margin-top:2px;">Failed (≤2)</div>
      </div>
    </div>
  </div>

  <!-- Score Distribution -->
  <div style="background:#fff;border-radius:12px;border:1px solid #e5e7eb;padding:20px 24px;margin-bottom:24px;">
    <div style="font-weight:700;font-size:15px;margin-bottom:14px;">Score Distribution</div>
    <table>{dist_rows}</table>
  </div>

  <!-- Per-question Results -->
  <div style="background:#fff;border-radius:12px;border:1px solid #e5e7eb;overflow:hidden;">
    <div style="padding:16px 20px;border-bottom:1px solid #e5e7eb;font-weight:700;font-size:15px;">
      Question Results
    </div>
    <table>
      <thead>
        <tr style="background:#f9fafb;">
          <th>#</th><th>Question &amp; Answer</th><th style="text-align:center;">Score</th><th>Judge Breakdown</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <div style="margin-top:16px;text-align:center;font-size:12px;color:#9ca3af;">
    Demografy Eval · LLM-as-Judge (Gemini 2.5 Flash) · {timestamp}
  </div>
</div>
</body>
</html>"""


def _save_reports(results: list[dict], avg: float, scores: list[int]) -> str:
    os.makedirs(_REPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    readable_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # HTML report
    html = _generate_html_report(results, avg, scores, readable_ts)
    html_path = os.path.join(_REPORTS_DIR, f"eval_report_{timestamp}.html")
    latest_path = os.path.join(_REPORTS_DIR, "latest.html")
    with open(html_path, "w") as f:
        f.write(html)
    with open(latest_path, "w") as f:
        f.write(html)

    # JSON report
    json_payload = {
        "timestamp": readable_ts,
        "summary": {
            "total": len(results),
            "average_score": round(avg, 2),
            "passed": sum(1 for s in scores if s >= 4),
            "failed": sum(1 for s in scores if s <= 2),
            "distribution": {str(s): scores.count(s) for s in range(6)},
        },
        "results": results,
    }
    json_path = os.path.join(_REPORTS_DIR, f"eval_report_{timestamp}.json")
    with open(json_path, "w") as f:
        json.dump(json_payload, f, indent=2)

    return html_path


# ---------------------------------------------------------------------------
# Full integration eval — calls the real agent for every base test case
# ---------------------------------------------------------------------------

def run_eval():
    from agent.prompts import ask_question

    cases = _integration_cases()
    results = []

    print("=" * 70)
    print("DEMOGRAFY AGENT EVALUATION  (golden_dataset.json)")
    print("=" * 70)

    for i, case in enumerate(cases, 1):
        question = case["question"]
        golden_answer = case.get("golden_answer")
        print(f"\n[{i}/{len(cases)}] {question}")
        print("-" * 60)

        answer = ask_question(question)
        print(f"Answer: {answer[:300]}{'...' if len(answer) > 300 else ''}")

        verdict = judge_response(question, answer, golden_answer=golden_answer)
        score = verdict.get("score", 0)
        label = SCORE_LABELS.get(score, "UNKNOWN")

        print(f"Score:        {score}/5  ({label})")
        print(f"Relevance:    {verdict.get('relevance', '-')}")
        print(f"Groundedness: {verdict.get('groundedness', '-')}")
        print(f"Completeness: {verdict.get('completeness', '-')}")
        print(f"Reasoning:    {verdict.get('reasoning', '-')}")

        results.append({"id": case["id"], "question": question, "answer": answer, "verdict": verdict})

    scores = [r["verdict"].get("score", 0) for r in results]
    valid_scores = [s for s in scores if s > 0]
    avg = sum(valid_scores) / len(valid_scores) if valid_scores else 0

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Questions evaluated : {len(results)}")
    print(f"Average score       : {avg:.2f} / 5")
    print("Score distribution  :")
    for label_score in [5, 4, 3, 2, 1, 0]:
        count = scores.count(label_score)
        if count:
            bar = "█" * count
            print(f"  {label_score} ({SCORE_LABELS[label_score]:<7}): {bar} {count}")

    failed = [r for r in results if r["verdict"].get("score", 0) <= 2]
    if failed:
        print(f"\nLow-scoring questions (score ≤ 2):")
        for r in failed:
            print(f"  [{r['verdict'].get('score')}] {r['question']}")

    report_path = _save_reports(results, avg, scores)
    print(f"\nReport saved → {report_path}")
    print(f"Latest HTML  → {os.path.join(_REPORTS_DIR, 'latest.html')}")

    return results


if __name__ == "__main__":
    run_eval()