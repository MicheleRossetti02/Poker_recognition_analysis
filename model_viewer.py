#!/usr/bin/env python3
"""
Model viewer (N7): load the trained YOLO card-detector and visualise its
detections on an image (or a folder of images), saving annotated copies and
printing the detected classes + confidences.

Lets you eyeball the *current* model (POKER_GTO_BOT_V3/weights/best.pt) on the
kept dataset without running the whole live-vision stack.

Examples:
  python model_viewer.py --image "Poker-GTO-Production databasev3/test/images/foo.jpg"
  python model_viewer.py --dir "Poker-GTO-Production databasev3/test/images" --limit 5
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

DEFAULT_MODEL = "POKER_GTO_BOT_V3/weights/best.pt"
DEFAULT_OUT = "data/model_viewer_out"


def _load_model(path: str):
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    from ultralytics import YOLO
    return YOLO(path)


def annotate(model, image_path: str, out_dir: str, conf: float) -> dict:
    import cv2
    res = model(image_path, conf=conf, verbose=False)[0]
    counts: dict[str, int] = {}
    for box in res.boxes:
        name = res.names[int(box.cls[0])]
        counts[name] = counts.get(name, 0) + 1
    os.makedirs(out_dir, exist_ok=True)
    annotated = res.plot()  # BGR ndarray with boxes drawn
    out_path = os.path.join(out_dir, "annotated_" + Path(image_path).name)
    cv2.imwrite(out_path, annotated)
    return {"image": image_path, "out": out_path,
            "detections": sum(counts.values()), "classes": counts}


def main():
    ap = argparse.ArgumentParser(description="Visualise the YOLO model's detections.")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--image", default=None)
    ap.add_argument("--dir", default=None)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    if not os.path.exists(args.model):
        print(f"Model not found: {args.model}", file=sys.stderr)
        sys.exit(1)
    if not args.image and not args.dir:
        print("Provide --image or --dir", file=sys.stderr)
        sys.exit(1)

    print(f"Loading model {args.model} ...")
    model = _load_model(args.model)

    images = []
    if args.image:
        images.append(args.image)
    if args.dir:
        exts = {".jpg", ".jpeg", ".png", ".bmp"}
        for p in sorted(Path(args.dir).iterdir()):
            if p.suffix.lower() in exts:
                images.append(str(p))
                if len(images) >= args.limit:
                    break

    print(f"Running on {len(images)} image(s), conf>={args.conf}\n")
    for img in images:
        try:
            r = annotate(model, img, args.out, args.conf)
            top = ", ".join(f"{k}×{v}" for k, v in sorted(
                r["classes"].items(), key=lambda kv: -kv[1])[:8])
            print(f"  {Path(img).name}: {r['detections']} det -> {top}")
            print(f"      saved {r['out']}")
        except Exception as e:
            print(f"  {img}: ERROR {e}")

    print(f"\nAnnotated images in {args.out}/")


if __name__ == "__main__":
    main()
