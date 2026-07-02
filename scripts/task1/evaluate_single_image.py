#!/usr/bin/env python3
"""
Evaluate a single-image Task 1 output directory.

This expects the layout produced by scripts/task1/process_single_image.py:
  output_dir/
    original.png
    model_<model-name>/
      diagram.xml
      rendered.png        # optional unless a renderer is available
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from eval.task1.metrics import ExecutionSuccessRate, XMLTokenCount
from src.renderer.drawio_renderer import DrawioRenderer


def get_model_dir_name(model_name: str) -> str:
    return model_name.split("/")[-1] if "/" in model_name else model_name


def evaluate_single_image(output_dir: Path, model: str, skip_render: bool = False) -> dict:
    model_dir = output_dir / f"model_{get_model_dir_name(model)}"
    xml_path = model_dir / "diagram.xml"
    rendered_path = model_dir / "rendered.png"

    renderer = DrawioRenderer(skip_render=skip_render)
    results = {
        "task": "task1_single_image",
        "model": model,
        "output_dir": str(output_dir),
        "created": datetime.now().isoformat(),
        "metrics": {},
    }

    for metric in (ExecutionSuccessRate(renderer=renderer), XMLTokenCount()):
        if metric.name == "execution_success_rate":
            result = metric(xml_path=xml_path, rendered_path=rendered_path if rendered_path.exists() else None)
        else:
            result = metric(xml_path=xml_path)

        results["metrics"][metric.name] = {
            "score": result.score,
            "success": result.success,
            "details": result.details,
            "error_message": result.error_message,
        }

    output_path = output_dir / "evaluation.json"
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate one Task 1 single-image output directory")
    parser.add_argument("--output", type=Path, required=True, help="Output directory from process_single_image.py")
    parser.add_argument("--model", default="gemini-3-pro-preview", help="Model name used for generation")
    parser.add_argument("--skip-render", action="store_true", help="Do not invoke Draw.io if rendered.png is absent")
    args = parser.parse_args()

    if not args.output.exists():
        parser.error(f"Output directory not found: {args.output}")

    results = evaluate_single_image(args.output.resolve(), args.model, skip_render=args.skip_render)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
