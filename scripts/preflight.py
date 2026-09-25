#!/usr/bin/env python3
"""Preflight: run before every session. Exit code 0 only if everything passes.

Usage:
  scripts/preflight.py            # full check, asks about the e-stop
  scripts/preflight.py --no-ask   # skip the e-stop question (CI, or a check with no arm)

Checks: .env complete, both serial ports present, both cameras found and giving frames,
fps sanity over 5 s, calibration files for both ids, 20 GB free disk, HF token valid,
and "E-stop tested this session? (y/n)". Runs in under 30 s.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ARM_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = ARM_DIR / ".env"
CAMERAS_YAML = ARM_DIR / "config" / "cameras.yaml"
CHECK_CAMERAS = ARM_DIR / "scripts" / "check_cameras.py"
REQUIRED_ENV = ["HF_USER", "FOLLOWER_PORT", "LEADER_PORT", "FOLLOWER_ID", "LEADER_ID"]
MIN_FREE_GB = 20

failures: list[str] = []
skipped: list[str] = []


def ok(msg: str) -> None:
    print(f"  ok    {msg}")


def fail(msg: str, fix: str) -> None:
    failures.append(f"{msg}\n        fix: {fix}")
    print(f"  FAIL  {msg}")


def skip(msg: str) -> None:
    skipped.append(msg)
    print(f"  skip  {msg}")


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if not ENV_FILE.exists():
        fail(".env missing", "cp .env.example .env and fill it in")
        return env
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    missing = [
        k
        for k in REQUIRED_ENV
        if not env.get(k) or env[k].endswith("XXXX") or env[k].endswith("YYYY")
    ]
    if missing:
        fail(f".env incomplete: {', '.join(missing)}", "edit .env, see .env.example")
    else:
        ok(".env complete")
    return env


def check_ports(env: dict[str, str]) -> None:
    for key in ("FOLLOWER_PORT", "LEADER_PORT"):
        port = env.get(key, "")
        if not port or port.endswith(("XXXX", "YYYY")):
            skip(f"{key} not set yet (boards not delivered?)")
            continue
        if Path(port).exists():
            ok(f"{key} {port} present")
        else:
            fail(
                f"{key} {port} not found",
                "check the USB cable and hub, then lerobot-find-port and update .env",
            )


def check_cameras() -> None:
    if not CHECK_CAMERAS.exists():
        fail("scripts/check_cameras.py missing", "git checkout scripts/check_cameras.py")
        return
    t0 = time.monotonic()
    proc = subprocess.run(
        [sys.executable, str(CHECK_CAMERAS), "--no-window", "--seconds", "5"],
        capture_output=True,
        text=True,
    )
    dt = time.monotonic() - t0
    lines = [ln for ln in proc.stdout.splitlines() if ln[:8].strip() in ("PASS", "FAIL", "SKIPPED")]
    for ln in lines:
        status, rest = ln[:8].strip(), ln[8:].strip()
        if status == "PASS":
            ok(f"camera {rest}")
        elif status == "SKIPPED":
            skip(f"camera {rest}")
        else:
            fail(
                f"camera {rest}",
                "replug it into its hub port and rerun. Names: scripts/check_cameras.py --list",
            )
    if not lines:
        fail(
            "camera check gave no result",
            f"run scripts/check_cameras.py by hand. Output:\n{proc.stdout}{proc.stderr}",
        )
    print(f"        (camera check took {dt:.1f} s)")


def check_calibration(env: dict[str, str]) -> None:
    cal_dir = Path(
        os.getenv("HF_LEROBOT_CALIBRATION", "~/.cache/huggingface/lerobot/calibration")
    ).expanduser()
    for key, kind in (("FOLLOWER_ID", "robots"), ("LEADER_ID", "teleoperators")):
        rid = env.get(key)
        if not rid:
            skip(f"{key} not set")
            continue
        matches = list(cal_dir.glob(f"{kind}/*/{rid}.json"))
        if matches:
            ok(f"calibration {rid}: {matches[0]}")
        else:
            fail(
                f"calibration for {rid} not found under {cal_dir}/{kind}/",
                "scripts/backup_calibration.sh --restore <folder>, or see docs/calibration.md",
            )


def check_disk() -> None:
    free_gb = shutil.disk_usage(ARM_DIR).free / 1e9
    if free_gb >= MIN_FREE_GB:
        ok(f"disk free {free_gb:.0f} GB")
    else:
        fail(
            f"disk free {free_gb:.0f} GB, need {MIN_FREE_GB}",
            "move old outputs/ and datasets to an external drive",
        )


def check_hf_token(env: dict[str, str]) -> None:
    try:
        from huggingface_hub import HfApi

        info = HfApi().whoami()
    except Exception as e:  # noqa: BLE001
        fail(
            f"HF token invalid or missing ({type(e).__name__})",
            "hf auth login  (token needs write access)",
        )
        return
    name = info.get("name", "?")
    ok(f"HF login as {name}")
    if env.get("HF_USER") and env["HF_USER"] != name:
        fail(
            f"HF_USER in .env is {env['HF_USER']} but the token belongs to {name}",
            "set HF_USER={name} in .env",
        )


def ask_estop() -> None:
    try:
        answer = input("  E-stop tested this session? (y/n) ").strip().lower()
    except EOFError:
        answer = ""
    if answer == "y":
        ok("e-stop tested")
    else:
        fail(
            "e-stop not tested this session",
            "press the e-stop during teleop, confirm both arms go limp, then rerun",
        )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--no-ask", action="store_true", help="skip the e-stop question")
    args = ap.parse_args()
    t0 = time.monotonic()
    print("Preflight")
    env = load_env()
    check_ports(env)
    check_cameras()
    check_calibration(env)
    check_disk()
    check_hf_token(env)
    if not args.no_ask:
        ask_estop()
    dt = time.monotonic() - t0
    print()
    if failures:
        print(f"FAIL ({len(failures)} problem(s), {dt:.0f} s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    tail = f", {len(skipped)} skipped" if skipped else ""
    print(f"PASS ({dt:.0f} s{tail})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
