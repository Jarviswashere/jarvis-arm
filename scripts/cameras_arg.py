#!/usr/bin/env python3
"""Print the --robot.cameras value built from config/cameras.yaml.

Used by teleop.sh and record.sh so the indexes are always the latest ones check_cameras.py wrote.
Cameras with required: false and no name are left out. Exit 1 if no camera is usable.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parent.parent / "config" / "cameras.yaml"


def main() -> int:
    cams = yaml.safe_load(CONFIG.read_text())["cameras"]
    parts = []
    for key, cam in cams.items():
        if not (cam.get("name") or "").strip():
            if cam.get("required", True):
                print(f"FAIL: camera '{key}' has no name in {CONFIG.name}", file=sys.stderr)
                return 1
            continue
        parts.append(
            f"{key}: {{type: opencv, index_or_path: {int(cam['index'])}, "
            f"width: {int(cam['width'])}, height: {int(cam['height'])}, fps: {int(cam['fps'])}}}"
        )
    if not parts:
        print("FAIL: no usable camera in cameras.yaml", file=sys.stderr)
        return 1
    print("{" + ", ".join(parts) + "}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
