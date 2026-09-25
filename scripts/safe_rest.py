#!/usr/bin/env python3
"""Move the follower slowly to its rest pose, then switch torque off.

Usage:
  scripts/safe_rest.py           # move to rest over 3 s, then torque off
  scripts/safe_rest.py --show    # print the current joint values and exit (no motion)
  scripts/safe_rest.py --release # torque off where it is, no motion

Safety: refuses to move if any joint is more than max_joint_delta_deg (config/rest_pose.yaml)
away from the rest pose. Then it asks Tony to guide the arm closer by hand, so the arm never
sweeps across the desk. Tony is at the desk with the e-stop in reach before running this.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import yaml

ARM_DIR = Path(__file__).resolve().parent.parent
REST_YAML = ARM_DIR / "config" / "rest_pose.yaml"
JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]


def load_env() -> dict[str, str]:
    env = dict(os.environ)
    env_file = ARM_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())
    return env


def connect(env: dict[str, str]):
    from lerobot.robots.so_follower import SOFollower, SOFollowerRobotConfig

    port, rid = env.get("FOLLOWER_PORT"), env.get("FOLLOWER_ID")
    if not port or not rid or port.endswith("XXXX"):
        sys.exit("FAIL: FOLLOWER_PORT or FOLLOWER_ID missing in .env")
    if not Path(port).exists():
        sys.exit(f"FAIL: {port} not found. Is the follower board plugged in and powered?")
    cfg = SOFollowerRobotConfig(
        port=port, id=rid, use_degrees=True, disable_torque_on_disconnect=True
    )
    robot = SOFollower(cfg)
    try:
        robot.connect(calibrate=False)
    except Exception as e:  # noqa: BLE001
        sys.exit(
            f"FAIL: could not connect to the follower on {port}: {e}\n"
            "      Is it calibrated? See docs/calibration.md"
        )
    return robot


def current_pose(robot) -> dict[str, float]:
    obs = robot.get_observation()
    return {j: float(obs[f"{j}.pos"]) for j in JOINTS}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--show", action="store_true", help="print current joints, no motion")
    ap.add_argument("--release", action="store_true", help="torque off in place, no motion")
    args = ap.parse_args()

    cfg = yaml.safe_load(REST_YAML.read_text())
    rest = {j: float(cfg["pose"][j]) for j in JOINTS}
    max_delta = float(cfg.get("max_joint_delta_deg", 45.0))
    move_time = float(cfg.get("move_time_s", 3.0))

    robot = connect(load_env())
    try:
        now = current_pose(robot)
        print("current pose (deg, gripper 0-100):")
        for j in JOINTS:
            print(f"  {j:14} {now[j]:8.1f}   rest {rest[j]:8.1f}   delta {now[j] - rest[j]:+7.1f}")
        if args.show:
            return 0
        if args.release:
            robot.bus.disable_torque()
            print("torque off. The arm can be moved by hand.")
            return 0

        too_far = [j for j in JOINTS if j != "gripper" and abs(now[j] - rest[j]) > max_delta]
        if too_far:
            print(f"\nREFUSED: {', '.join(too_far)} more than {max_delta:.0f} deg from rest.")
            print("Guide the arm closer to the rest pose by hand (torque is off now), then rerun.")
            robot.bus.disable_torque()
            return 1

        print(f"\nmoving to rest over {move_time:.1f} s ...")
        steps = max(int(move_time * 30), 1)
        for i in range(1, steps + 1):
            a = i / steps
            target = {f"{j}.pos": now[j] + (rest[j] - now[j]) * a for j in JOINTS}
            robot.send_action(target)
            time.sleep(move_time / steps)
        time.sleep(0.3)
        final = current_pose(robot)
        worst = max(abs(final[j] - rest[j]) for j in JOINTS if j != "gripper")
        robot.bus.disable_torque()
        print(f"at rest (worst joint error {worst:.1f} deg). Torque off. Arm can be moved by hand.")
        return 0
    finally:
        try:
            robot.disconnect()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    sys.exit(main())
