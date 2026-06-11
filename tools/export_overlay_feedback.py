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

    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summarize(records), ensure_ascii=False, indent=2), encoding="utf-8")

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

    return {
        "csv": csv_path,
        "summary": summary_path,
        "manifest": manifest_path,
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
    print(f"Summary: {outputs['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
