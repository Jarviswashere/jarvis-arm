#!/usr/bin/env python3
"""Report on a LeRobot dataset and check it against the quality rules.

Usage:
  scripts/dataset_report.py <repo_id>            # e.g. tony/so101_block_to_cup_v1
  scripts/dataset_report.py <repo_id> --max-s 22 # episode length limit (default 22)

Prints episodes, frames, fps per episode from timestamps, durations, cameras per episode,
drop estimate, task strings, and PASS or FAIL against: fps 29 to 31, no episode under 5 s or
over the limit, every camera in every episode, drops under 1%, task string set.
Downloads only the parquet data and metadata, not the videos.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from itertools import pairwise

FPS_MIN, FPS_MAX, MIN_S, DROP_MAX = 29.0, 31.0, 5.0, 0.01


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("repo_id")
    ap.add_argument("--max-s", type=float, default=22.0)
    ap.add_argument("--root", default=None, help="local dataset folder instead of the Hub")
    args = ap.parse_args()

    from huggingface_hub import HfApi
    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    try:
        ds = LeRobotDataset(
            args.repo_id, root=args.root, download_videos=False, video_backend="pyav"
        )
    except Exception as e:  # noqa: BLE001
        sys.exit(f"FAIL: cannot load {args.repo_id}: {type(e).__name__}: {e}")
    meta = ds.meta
    fps = meta.fps
    cams = list(meta.camera_keys)
    print(f"Dataset:  {args.repo_id}")
    print(f"Episodes: {meta.total_episodes}   Frames: {meta.total_frames}   Declared fps: {fps}")
    print(f"Cameras:  {cams}")
    print(f"Robot:    {meta.robot_type}")

    cols = ds.hf_dataset.select_columns(["episode_index", "timestamp"]).with_format(None)
    ep_ts: dict[int, list[float]] = defaultdict(list)
    for e, t in zip(cols["episode_index"], cols["timestamp"], strict=True):
        ep_ts[int(e)].append(float(t))

    tasks: set[str] = set()
    if meta.episodes is not None and "tasks" in meta.episodes.column_names:
        for t in meta.episodes["tasks"]:
            tasks.update(t if isinstance(t, list) else [t])
    elif meta.tasks is not None:
        tasks.update(str(t) for t in meta.tasks.index)
    print(f"Tasks:    {sorted(tasks) or 'NONE'}")

    problems: list[str] = []
    total_drops = 0
    total_gaps = 0
    print("\nep   frames   dur_s   fps    drops  cameras")
    for ep in sorted(ep_ts):
        ts = sorted(ep_ts[ep])
        n = len(ts)
        dur = (ts[-1] - ts[0]) + 1.0 / fps if n > 1 else 0.0
        ep_fps = (n - 1) / (ts[-1] - ts[0]) if n > 1 and ts[-1] > ts[0] else 0.0
        gaps = [b - a for a, b in pairwise(ts)]
        drops = sum(1 for g in gaps if g > 1.5 / fps)
        total_drops += drops
        total_gaps += len(gaps)
        missing = []
        for cam in cams:
            try:
                p = meta.get_video_file_path(ep, cam)
                if args.root is None:
                    pass  # on the Hub: existence is checked below in one API call
                elif not (ds.root / p).exists():
                    missing.append(cam)
            except Exception:  # noqa: BLE001
                missing.append(cam)
        cam_note = "ok" if not missing else f"MISSING {missing}"
        flag = ""
        if not (FPS_MIN <= ep_fps <= FPS_MAX):
            flag += " fps!"
        if dur < MIN_S:
            flag += " short!"
        if dur > args.max_s:
            flag += " long!"
        if missing:
            flag += " camera!"
        if flag:
            problems.append(f"episode {ep}:{flag}")
        print(f"{ep:<4} {n:<8} {dur:<7.1f} {ep_fps:<6.1f} {drops:<6} {cam_note}{flag}")

    if args.root is None and cams:
        files = set(HfApi().list_repo_files(args.repo_id, repo_type="dataset"))
        for ep in sorted(ep_ts):
            for cam in cams:
                p = str(meta.get_video_file_path(ep, cam))
                if p not in files:
                    problems.append(f"episode {ep}: video for {cam} not on the Hub ({p})")

    drop_rate = total_drops / max(total_gaps, 1)
    print(f"\nDrop estimate: {total_drops} late frames of {total_gaps} ({drop_rate:.2%})")
    if drop_rate > DROP_MAX:
        problems.append(f"drops {drop_rate:.2%} over {DROP_MAX:.0%}")
    if not tasks:
        problems.append("no task string")
    if meta.total_episodes != len(ep_ts):
        problems.append(f"metadata says {meta.total_episodes} episodes, data has {len(ep_ts)}")

    print("\nVisualize:")
    print(f"  lerobot-dataset-viz --repo-id {args.repo_id} --episode-index 0")
    print(f"  https://huggingface.co/spaces/lerobot/visualize_dataset?dataset={args.repo_id}")

    if problems:
        print(f"\nFAIL ({len(problems)}):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
