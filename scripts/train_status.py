#!/usr/bin/env python3
"""Show the state of a Hugging Face training job and the policy repo link.

Usage:
  scripts/train_status.py <job_id>          # one job
  scripts/train_status.py                   # the last job submitted by train_cloud.sh
  scripts/train_status.py <job_id> --logs   # also print the last 40 log lines
  scripts/train_status.py <job_id> --wait   # poll every 30 s until done or failed
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
import time
from pathlib import Path

ARM_DIR = Path(__file__).resolve().parent.parent
JOBS_LOG = ARM_DIR / ".state" / "jobs.log"
WORDS = {"RUNNING": "running", "COMPLETED": "done", "ERROR": "failed", "CANCELED": "cancelled"}


def last_job() -> tuple[str, str]:
    try:
        parts = JOBS_LOG.read_text().splitlines()[-1].split()
        return parts[1], parts[3]
    except (FileNotFoundError, IndexError):
        sys.exit("usage: train_status.py <job_id> [--logs] [--wait]  (no jobs submitted yet)")


def policy_for(job_id: str) -> str:
    try:
        for line in JOBS_LOG.read_text().splitlines():
            parts = line.split()
            if len(parts) > 3 and parts[1] == job_id:
                return parts[3]
    except FileNotFoundError:
        pass
    return ""


def show(job_id: str) -> str:
    from huggingface_hub import HfApi

    try:
        job = HfApi().inspect_job(job_id=job_id)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"FAIL: cannot inspect {job_id}: {type(e).__name__}: {e}")
    stage = getattr(job.status, "stage", "?") or "?"
    msg = getattr(job.status, "message", "") or ""
    created = job.created_at
    elapsed = ""
    if created:
        now = dt.datetime.now(dt.UTC)
        elapsed = f"  ({(now - created).total_seconds() / 60:.0f} min since submit)"
    print(f"Job:     {job_id}")
    print(f"State:   {WORDS.get(stage, stage.lower())}" + (f"  {msg}" if msg else "") + elapsed)
    print(f"Flavor:  {job.flavor}")
    policy = policy_for(job_id)
    if policy:
        ready = "ready" if stage == "COMPLETED" else "not ready yet"
        print(f"Policy:  https://huggingface.co/{policy}  ({ready})")
    print(f"Page:    https://huggingface.co/jobs/{job.owner.name}/{job_id}")
    return stage


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("job_id", nargs="?")
    ap.add_argument("--logs", action="store_true")
    ap.add_argument("--wait", action="store_true")
    args = ap.parse_args()
    job_id = args.job_id or last_job()[0]
    while True:
        stage = show(job_id)
        if args.logs:
            print("\n--- last 40 log lines:")
            subprocess.run(["hf", "jobs", "logs", "--tail", "40", job_id], check=False)
        if not args.wait or stage in ("COMPLETED", "ERROR", "CANCELED"):
            break
        time.sleep(30)
        print()
    return 0 if stage != "ERROR" else 1


if __name__ == "__main__":
    sys.exit(main())
