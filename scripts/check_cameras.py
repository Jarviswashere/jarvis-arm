#!/usr/bin/env python3
"""Check every camera in config/cameras.yaml: find it by name, measure real fps, pass or fail.

Usage:
  scripts/check_cameras.py                # 20 s test, windows shown
  scripts/check_cameras.py --seconds 60   # longer test (the sprint gate uses 60)
  scripts/check_cameras.py --no-window    # headless, for preflight
  scripts/check_cameras.py --list         # only print the cameras macOS sees

On macOS the OpenCV index can change after a replug. This tool matches cameras by the
device name macOS reports, rewrites the index in the YAML when it moved, and writes
.state/cameras_ok on a full pass so teleop.sh knows the check is fresh.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import yaml

ARM_DIR = Path(__file__).resolve().parent.parent
CONFIG = ARM_DIR / "config" / "cameras.yaml"
STAMP = ARM_DIR / ".state" / "cameras_ok"
FFMPEG = Path("/opt/homebrew/opt/ffmpeg@8/bin/ffmpeg")
FPS_MIN, FPS_MAX, DROP_MAX = 28.0, 31.0, 0.01
LATE_S = 0.050  # a frame later than (1/fps + 50 ms) counts as a drop


@dataclass
class Result:
    key: str
    status: str  # PASS, FAIL, SKIPPED
    reason: str = ""
    fps: float = 0.0
    frames: int = 0
    drops: int = 0
    samples: list[float] = field(default_factory=list)


def list_os_cameras() -> list[str]:
    """Names of video devices in AVFoundation order. That order is the OpenCV index on macOS."""
    if not FFMPEG.exists():
        sys.exit(f"FAIL: {FFMPEG} not found. Run: brew install ffmpeg@8")
    proc = subprocess.run(
        [str(FFMPEG), "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        capture_output=True,
        text=True,
    )
    names: list[str] = []
    in_video = False
    for line in proc.stderr.splitlines():
        if "AVFoundation video devices" in line:
            in_video = True
            continue
        if "AVFoundation audio devices" in line:
            break
        if in_video and "] [" in line:
            names.append(line.split("] ", 2)[-1].strip())
    return [n for n in names if not n.startswith("Capture screen")]


def resolve_index(key: str, cam: dict, os_names: list[str]) -> tuple[int | None, str]:
    """Return (index, message). index None means the camera is not connected."""
    name = (cam.get("name") or "").strip()
    last = int(cam.get("index", -1))
    if not name:
        return None, (
            f"{key}: no name in {CONFIG.name}. Plug the camera in, run --list, and copy its "
            "name into the YAML."
        )
    if 0 <= last < len(os_names) and os_names[last] == name:
        return last, f"{key}: found '{name}' at index {last} (unchanged)"
    for idx, os_name in enumerate(os_names):
        if os_name == name:
            return idx, f"{key}: '{name}' moved from index {last} to {idx}, YAML updated"
    return None, f"{key}: '{name}' not connected. Replug it and rerun."


def measure(key: str, cam: dict, index: int, seconds: float, window: bool, out: Result) -> None:
    cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
    if not cap.isOpened():
        out.status = "FAIL"
        out.reason = (
            "could not open. Allow camera access for this terminal app in System Settings > "
            "Privacy & Security > Camera, restart it, and close any app using the camera."
        )
        return
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(cam["width"]))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(cam["height"]))
    cap.set(cv2.CAP_PROP_FPS, int(cam["fps"]))
    target = 1.0 / float(cam["fps"])
    ok, frame = cap.read()
    if not ok:
        cap.release()
        out.status, out.reason = "FAIL", "opened but gave no frame"
        return
    h, w = frame.shape[:2]
    if (w, h) != (int(cam["width"]), int(cam["height"])):
        out.reason = f"size is {w}x{h}, wanted {cam['width']}x{cam['height']}; "
    t_end = time.monotonic() + seconds
    last = time.monotonic()
    while time.monotonic() < t_end:
        ok, frame = cap.read()
        now = time.monotonic()
        if not ok:
            out.drops += 1
            continue
        gap = now - last
        last = now
        out.samples.append(gap)
        if gap > target + LATE_S:
            out.drops += 1
        if window:
            cv2.putText(frame, key, (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            cv2.imshow(key, frame)
            cv2.waitKey(1)
    cap.release()
    out.frames = len(out.samples)
    elapsed = sum(out.samples) or 1e-9
    out.fps = out.frames / elapsed
    drop_rate = out.drops / max(out.frames, 1)
    if FPS_MIN <= out.fps <= FPS_MAX and drop_rate <= DROP_MAX:
        out.status = "PASS"
    else:
        out.status = "FAIL"
        out.reason += f"fps {out.fps:.1f} (want {FPS_MIN:.0f}-{FPS_MAX:.0f}), drops {drop_rate:.1%}"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--seconds", type=float, default=20.0, help="measure for this long (default 20)"
    )
    ap.add_argument("--no-window", action="store_true", help="do not show camera windows")
    ap.add_argument("--list", action="store_true", help="only list the cameras macOS sees")
    args = ap.parse_args()

    os_names = list_os_cameras()
    print("Cameras macOS sees (index: name):")
    for i, n in enumerate(os_names):
        print(f"  {i}: {n}")
    if not os_names:
        print("  none. Plug a camera in. If one is plugged in, allow camera access for this")
        print("  terminal app: System Settings > Privacy & Security > Camera, then restart it.")
    if args.list:
        return 0

    if not CONFIG.exists():
        sys.exit(f"FAIL: {CONFIG} missing")
    cfg = yaml.safe_load(CONFIG.read_text())
    cams: dict = cfg["cameras"]

    results: dict[str, Result] = {}
    threads: list[threading.Thread] = []
    changed = False
    for key, cam in cams.items():
        idx, msg = resolve_index(key, cam, os_names)
        print(msg)
        res = Result(key=key, status="FAIL", reason=msg)
        results[key] = res
        if idx is None:
            if not cam.get("required", True):
                res.status = "SKIPPED"
            continue
        if idx != int(cam.get("index", -1)):
            cam["index"] = idx
            changed = True
        t = threading.Thread(
            target=measure,
            args=(key, cam, idx, args.seconds, not args.no_window),
            kwargs={"out": res},
        )
        threads.append(t)

    if threads:
        print(f"Measuring {len(threads)} camera(s) for {args.seconds:.0f} s ...")
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if not args.no_window:
            cv2.destroyAllWindows()

    if changed:
        CONFIG.write_text(yaml.safe_dump(cfg, sort_keys=False))
        print(f"Rewrote {CONFIG.relative_to(ARM_DIR)} with new index values")

    print()
    all_ok = True
    for key, r in results.items():
        line = f"{r.status:8} {key}"
        if r.status == "PASS":
            line += f"  {r.fps:.1f} fps, {r.frames} frames, {r.drops} drops"
        else:
            line += f"  {r.reason}"
        print(line)
        if r.status == "FAIL":
            all_ok = False

    if all_ok:
        STAMP.parent.mkdir(exist_ok=True)
        STAMP.write_text(f"{time.time():.0f}\n")
        print("\nPASS")
        return 0
    print("\nFAIL: fix the cameras above and rerun")
    return 1


if __name__ == "__main__":
    sys.exit(main())
