#!/usr/bin/env python3
"""Export overlay vision feedback into reviewable CSV/JSON artifacts.

The overlay writes corrected card reads to:

    dataset/raw/overlay_session_*/vision_feedback/feedback.jsonl

This tool gathers those records, summarizes model accuracy, and creates a CSV
that can drive manual review or a future retraining pipeline.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Iterable


DEFAULT_INPUT = Path("dataset/raw")
DEFAULT_OUTPUT = Path("dataset/overlay_feedback_export")


def feedback_files(paths: Iterable[Path]) -> list[Path]:
    found: list[Path] = []
    for path in paths:
        path = Path(path)
        if path.is_file():
            found.append(path)
        elif path.is_dir():
            found.extend(path.glob("**/vision_feedback/feedback.jsonl"))
    return sorted(set(found))


def read_jsonl(path: Path) -> list[dict[str, object]]:
    records = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            if isinstance(record, dict):
                record["_source_file"] = str(path)
                records.append(record)
    return records


def load_feedback(paths: Iterable[Path]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in feedback_files(paths):
        records.extend(read_jsonl(path))
    return records


def _cards(value: object) -> str:
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value or "")


def _nested(record: dict[str, object], key: str) -> dict[str, object]:
    value = record.get(key)
    return value if isinstance(value, dict) else {}


def record_status(record: dict[str, object]) -> str:
    match = _nested(record, "match")
    if match.get("hero") and match.get("board") and match.get("street"):
        return "ok"
    missing = [key for key in ("hero", "board", "street") if not match.get(key)]
    return "fix_" + "_".join(missing)


def debug_image(record: dict[str, object]) -> str:
    for key in ("annotated_image", "failure_image", "image"):
        value = record.get(key)
        if value:
            return str(value)
    raw = _nested(record, "raw_vision")
    for key in ("annotated_image", "failure_image", "image"):
        value = raw.get(key)
        if value:
            return str(value)
    return ""


def feedback_row(record: dict[str, object]) -> dict[str, object]:
    detected = _nested(record, "detected")
    corrected = _nested(record, "corrected")
    match = _nested(record, "match")
    return {
        "timestamp": record.get("timestamp", ""),
        "status": record_status(record),
        "detected_hero": _cards(detected.get("hero_cards", [])),
        "corrected_hero": _cards(corrected.get("hero_cards", [])),
        "detected_board": _cards(detected.get("board_cards", [])),
        "corrected_board": _cards(corrected.get("board_cards", [])),
        "detected_street": detected.get("street", ""),
        "corrected_street": corrected.get("street", ""),
        "hero_match": bool(match.get("hero")),
        "board_match": bool(match.get("board")),
        "street_match": bool(match.get("street")),
        "confidence": detected.get("confidence", ""),
        "image": record.get("image", ""),
        "debug_image": debug_image(record),
        "source_file": record.get("_source_file", ""),
    }


def summarize(records: list[dict[str, object]]) -> dict[str, object]:
    statuses = Counter(record_status(record) for record in records)
    total = len(records)
    ok = statuses.get("ok", 0)
    return {
        "total": total,
        "ok": ok,
        "needs_review": total - ok,
        "ok_rate": round(ok / total, 4) if total else 0.0,
        "status_counts": dict(sorted(statuses.items())),
    }


def _rel_asset(path: str, base: Path) -> str:
    if not path:
        return ""
    p = Path(path)
    try:
        return html.escape(str(p.relative_to(base)))
    except ValueError:
        return html.escape(str(p))


def build_html_report(rows: list[dict[str, object]], summary: dict[str, object], out_dir: Path) -> str:
    status_items = "".join(
        f"<li><strong>{html.escape(str(key))}</strong>: {value}</li>"
        for key, value in summary.get("status_counts", {}).items()
    )
    body_rows = []
    for row in rows:
        image_path = str(row.get("copied_debug_image") or row.get("debug_image") or "")
        image_html = ""
        if image_path:
            image_html = (
                f'<a href="{_rel_asset(image_path, out_dir)}">'
                f'<img src="{_rel_asset(image_path, out_dir)}" alt="debug"></a>'
            )
        status = html.escape(str(row.get("status", "")))
        status_class = "ok" if status == "ok" else "review"
        search_text = html.escape(" ".join(str(row.get(key, "")) for key in (
            "status", "detected_hero", "corrected_hero", "detected_board",
            "corrected_board", "detected_street", "corrected_street",
        )).lower())
        body_rows.append(
            f'<tr data-status="{status}" data-search="{search_text}">'
            f'<td><span class="pill {status_class}">{status}</span></td>'
            f"<td>{html.escape(str(row.get('detected_hero', '')))}"
            f"<br><strong>{html.escape(str(row.get('corrected_hero', '')))}</strong></td>"
            f"<td>{html.escape(str(row.get('detected_board', '')))}"
            f"<br><strong>{html.escape(str(row.get('corrected_board', '')))}</strong></td>"
            f"<td>{html.escape(str(row.get('detected_street', '')))}"
            f"<br><strong>{html.escape(str(row.get('corrected_street', '')))}</strong></td>"
            f"<td>{html.escape(str(row.get('confidence', '')))}</td>"
            f"<td>{image_html}</td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <title>Overlay Feedback Report</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; background: #11161b; color: #e8eaed; }}
    h1 {{ margin: 0 0 8px; color: #5ad17a; }}
    .summary {{ display: flex; gap: 18px; flex-wrap: wrap; margin: 16px 0; }}
    .controls {{ display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin: 18px 0; }}
    input, select {{ background: #0f1216; color: #e8eaed; border: 1px solid #303945; border-radius: 6px; padding: 9px 10px; }}
    .box {{ background: #1b2129; border: 1px solid #303945; border-radius: 8px; padding: 12px 14px; }}
    table {{ width: 100%; border-collapse: collapse; background: #161c23; }}
    th, td {{ border-bottom: 1px solid #2b333d; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ color: #9aa3ad; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    img {{ max-width: 220px; max-height: 140px; border: 1px solid #39414b; border-radius: 6px; }}
    .pill {{ display: inline-block; padding: 4px 8px; border-radius: 999px; font-weight: 700; font-size: 12px; }}
    .ok {{ background: #163d25; color: #73e397; }}
    .review {{ background: #4b3512; color: #ffcf5a; }}
    strong {{ color: #ffffff; }}
  </style>
</head>
<body>
  <h1>Overlay Feedback Report</h1>
  <div class="summary">
    <div class="box"><strong>Total</strong><br>{summary.get("total", 0)}</div>
    <div class="box"><strong>OK</strong><br>{summary.get("ok", 0)}</div>
    <div class="box"><strong>Review</strong><br>{summary.get("needs_review", 0)}</div>
    <div class="box"><strong>OK rate</strong><br>{float(summary.get("ok_rate", 0.0)):.1%}</div>
    <div class="box"><strong>Status</strong><ul>{status_items}</ul></div>
  </div>
  <div class="controls">
    <label>Filtro status
      <select id="statusFilter">
        <option value="all">Tutti</option>
        <option value="review">Solo review</option>
        <option value="ok">Solo OK</option>
      </select>
    </label>
    <label>Cerca
      <input id="searchBox" type="search" placeholder="es. As Kh, fix_hero, flop">
    </label>
    <span id="visibleCount"></span>
  </div>
  <table>
    <thead>
      <tr><th>Status</th><th>Hero<br>detected/corrected</th><th>Board<br>detected/corrected</th><th>Street</th><th>Conf</th><th>Debug</th></tr>
    </thead>
    <tbody>
      {''.join(body_rows) if body_rows else '<tr><td colspan="6">No feedback records yet.</td></tr>'}
    </tbody>
  </table>
  <script>
    const statusFilter = document.getElementById('statusFilter');
    const searchBox = document.getElementById('searchBox');
    const visibleCount = document.getElementById('visibleCount');
    const rows = Array.from(document.querySelectorAll('tbody tr[data-status]'));
    function applyFilters() {{
      const status = statusFilter.value;
      const query = searchBox.value.trim().toLowerCase();
      let visible = 0;
      for (const row of rows) {{
        const rowStatus = row.dataset.status || '';
        const statusOk = status === 'all' || (status === 'review' ? rowStatus !== 'ok' : rowStatus === status);
        const queryOk = !query || (row.dataset.search || '').includes(query);
        const show = statusOk && queryOk;
        row.style.display = show ? '' : 'none';
        if (show) visible += 1;
      }}
      visibleCount.textContent = `${{visible}} / ${{rows.length}} righe visibili`;
    }}
    statusFilter.addEventListener('change', applyFilters);
    searchBox.addEventListener('input', applyFilters);
    applyFilters();
  </script>
</body>
</html>
"""


def export_feedback(
    records: list[dict[str, object]],
    out_dir: Path = DEFAULT_OUTPUT,
    copy_images: bool = False,
) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [feedback_row(record) for record in records]

    csv_path = out_dir / "feedback.csv"
    fieldnames = [
        "timestamp",
        "status",
        "detected_hero",
        "corrected_hero",
        "detected_board",
        "corrected_board",
        "detected_street",
        "corrected_street",
        "hero_match",
        "board_match",
        "street_match",
        "confidence",
        "image",
        "debug_image",
        "source_file",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    ok_rows = [row for row in rows if row["status"] == "ok"]
    review_rows = [row for row in rows if row["status"] != "ok"]
    ok_csv_path = out_dir / "ok.csv"
    review_csv_path = out_dir / "needs_review.csv"
    for path, subset in ((ok_csv_path, ok_rows), (review_csv_path, review_rows)):
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(subset)

    summary = summarize(records)
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest_path = out_dir / "manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    if copy_images:
        images_dir = out_dir / "images"
        images_dir.mkdir(exist_ok=True)
        for idx, row in enumerate(rows, start=1):
            source = Path(str(row["debug_image"]))
            if not source.exists():
                continue
            status = str(row["status"])
            dest = images_dir / f"{idx:05d}_{status}_{source.name}"
            shutil.copy2(source, dest)
            row["copied_debug_image"] = str(dest)
        copied_csv = out_dir / "feedback_with_images.csv"
        with copied_csv.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames + ["copied_debug_image"])
            writer.writeheader()
            writer.writerows(rows)

    report_path = out_dir / "report.html"
    report_path.write_text(build_html_report(rows, summary, out_dir), encoding="utf-8")

    return {
        "csv": csv_path,
        "ok_csv": ok_csv_path,
        "needs_review_csv": review_csv_path,
        "summary": summary_path,
        "manifest": manifest_path,
        "report": report_path,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export overlay vision feedback.")
    parser.add_argument("inputs", nargs="*", type=Path, default=[DEFAULT_INPUT])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--copy-images", action="store_true")
    args = parser.parse_args()

    records = load_feedback(args.inputs)
    outputs = export_feedback(records, args.out, copy_images=args.copy_images)
    summary = summarize(records)
    print(f"Feedback records: {summary['total']}")
    print(f"OK rate: {summary['ok_rate']:.1%}")
    print(f"CSV: {outputs['csv']}")
    print(f"Needs review CSV: {outputs['needs_review_csv']}")
    print(f"OK CSV: {outputs['ok_csv']}")
    print(f"Summary: {outputs['summary']}")
    print(f"Report: {outputs['report']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
