# USB map

Which physical port each device uses. Keep it fixed. A device on a different port can get a different camera index or serial name, and then nothing matches the config.

Status: PLAN. Confirmed rows are marked. Everything else is to be tested when the parts are on the desk.

## Rules

1. Reachy Mini on its own Mac port. Never on the camera hub. It streams audio and video and must not share bandwidth.
2. Both cameras on the powered 4-port hub, MJPEG at 640x480, 30 fps. MJPEG keeps two streams inside USB 2 bandwidth.
3. Both driver boards on the hub or on Mac ports, whichever leaves the cameras stable. Test both layouts with `scripts/check_cameras.py --seconds 60` and write the winner below.
4. Label every cable at the plug end with the device name.

## Map

| Device | Where it plugs in | Cable label | Confirmed |
|---|---|---|---|
| Reachy Mini Lite | Mac mini, rear USB-C port 1 | REACHY | no |
| Powered hub uplink | Mac mini, rear USB-C port 2 | HUB | no |
| Scene webcam | Hub port 1 | SCENE | no |
| Wrist camera (IMX179) | Hub port 2 | WRIST | no |
| Follower driver board | Hub port 3 (test A) or Mac port 3 (test B) | FOLLOWER | no |
| Leader driver board | Hub port 4 (test A) or Mac port 4 (test B) | LEADER | no |

Mac mini M4 ports: 2 x USB-C front (USB 3), 3 x Thunderbolt 4 rear. Adjust the table to the ports that are actually used.

## Test results

Fill in after the boards arrive.

| Layout | Cameras fps over 60 s | Drops | Serial errors in 10 min teleop | Winner |
|---|---|---|---|---|
| A: boards on hub | | | | |
| B: boards on Mac ports | | | | |

## Known facts so far

- macOS reassigns OpenCV camera indexes after a replug. `scripts/check_cameras.py` matches by device name and rewrites `config/cameras.yaml`.
- Serial port names on macOS look like `/dev/tty.usbmodemXXXX`. The number can change with the port. If it changes, update `.env`.
