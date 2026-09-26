#!/usr/bin/env python3
"""Plot the training loss of a Hugging Face job from its log.

Usage:
  scripts/loss_curve.py <job_id>                # writes outputs/curves/<job_id>.png and .csv
  scripts/loss_curve.py <job_id> --name act_v1  # nicer file name and title

Reads every "step:N ... loss:X" line the LeRobot trainer prints (one per log_freq steps).
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

ARM_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = ARM_DIR / "outputs" / "curves"
LINE = re.compile(r"step:(\d+)\s.*?\bloss:([\d.]+).*?\bl1_loss:([\d.]+)")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("job_id")
    ap.add_argument("--name", default=None)
    args = ap.parse_args()
    name = args.name or args.job_id

    proc = subprocess.run(["hf", "jobs", "logs", args.job_id], capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"FAIL: hf jobs logs {args.job_id}: {proc.stderr.strip()[:200]}")
    # progress bars use carriage returns, so split on both before matching
    segments = re.split(r"[\r\n]+", proc.stdout)
    rows = []
    for seg in segments:
        m = LINE.search(seg)
        if m:
            rows.append((int(m.group(1)), float(m.group(2)), float(m.group(3))))
    if not rows:
        sys.exit("FAIL: no 'step:N ... loss:X' lines in the log yet")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / f"{name}.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["step", "loss", "l1_loss"])
        w.writerows(rows)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    steps = [r[0] for r in rows]
    loss = [r[1] for r in rows]
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    ax.plot(steps, loss, color="#2563eb", linewidth=2)
    ax.set_title(f"Training loss, {name}", loc="left", fontsize=12, color="#111827")
    ax.set_xlabel("step", color="#4b5563")
    ax.set_ylabel("loss", color="#4b5563")
    ax.grid(True, color="#e5e7eb", linewidth=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#d1d5db")
    ax.tick_params(colors="#4b5563")
    ax.annotate(
        f"{loss[-1]:.2f}",
        (steps[-1], loss[-1]),
        textcoords="offset points",
        xytext=(6, 0),
        va="center",
        fontsize=9,
        color="#111827",
    )
    ax.set_xlim(left=0)
    fig.tight_layout()
    png_path = OUT_DIR / f"{name}.png"
    fig.savefig(png_path)
    print(f"{len(rows)} points, first loss {loss[0]:.3f} at step {steps[0]}")
    print(f"last loss {loss[-1]:.3f} at step {steps[-1]}")
    print(f"wrote {png_path.relative_to(ARM_DIR)} and {csv_path.relative_to(ARM_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
