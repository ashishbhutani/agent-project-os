#!/usr/bin/env python3
"""Bootstrap empty phase planning files from templates."""

from __future__ import annotations

import argparse
from pathlib import Path


TEMPLATES = {
    "tasks": "jira_tasks.template.csv",
    "deps": "jira_dependencies.template.csv",
    "tracker": "jira_tracker.template.csv",
    "parallel": "parallelization.template.md",
}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--phase", required=True, help="Example: P2")
    p.add_argument("--out", required=True, help="Output directory, e.g. planning")
    args = p.parse_args()

    phase = args.phase.upper()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    base = Path("modules/agent-project-os/planning/templates")
    files = {
        out_dir / f"jira_phase{phase[1:].lower()}.csv": TEMPLATES["tasks"],
        out_dir / f"jira_phase{phase[1:].lower()}_dependencies.csv": TEMPLATES["deps"],
        out_dir / f"jira_phase{phase[1:].lower()}_tracker.csv": TEMPLATES["tracker"],
        out_dir / f"parallelization_phase{phase[1:].lower()}.md": TEMPLATES["parallel"],
    }

    for output_path, template_name in files.items():
        content = (base / template_name).read_text(encoding="utf-8")
        content = content.replace("P?", phase).replace("Phase?", f"Phase{phase[1:]}").replace("Phase ?", f"Phase {phase[1:]}")
        output_path.write_text(content, encoding="utf-8")
        print(output_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
