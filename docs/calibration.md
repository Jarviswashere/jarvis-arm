# Motor setup and calibration

Do this once per arm, and again only if a joint moves the wrong way, a motor was replaced, or the calibration file is lost. Back up first, every time.

Everything below moves motors. Tony is at the desk with the e-stop in reach before any command runs.

## 0. Before you start

```bash
cd arm && source scripts/env.sh
```

`.env` has `FOLLOWER_PORT`, `LEADER_PORT`, `FOLLOWER_ID=follower_a`, `LEADER_ID=leader_a`.

## 1. Find the ports

One driver board at a time, powered, USB connected with a data cable.

```bash
lerobot-find-port
```

It asks you to unplug the board and press Enter, then prints the port name. Write it into `.env`. Repeat for the second board. Port names on macOS look like `/dev/tty.usbmodemXXXX` and can change if the board moves to another USB port. Keep the USB map fixed (`docs/usb-map.md`).

## 2. Set motor IDs

Each arm has 6 motors. Each needs a unique ID 1 to 6. Plug one motor at a time into the board, run the tool, and follow its order.

```bash
lerobot-setup-motors --robot.type=so101_follower --robot.port=$FOLLOWER_PORT
lerobot-setup-motors --teleop.type=so101_leader --teleop.port=$LEADER_PORT
```

Order, and the ID the tool gives: gripper 6, wrist_roll 5, wrist_flex 4, elbow_flex 3, shoulder_lift 2, shoulder_pan 1. Put a tape label with the ID on each motor before it goes into the arm. The tool also sets the baud rate. If a motor is not found, check the cable and that only one motor is plugged in.

## 3. Assemble

Follow the SO-101 assembly guide. Motors go in by their ID. The wrist camera plate goes on before the gripper motor is closed in.

## 4. Calibrate

Follower first, then leader.

```bash
lerobot-calibrate --robot.type=so101_follower --robot.port=$FOLLOWER_PORT --robot.id=$FOLLOWER_ID
lerobot-calibrate --teleop.type=so101_leader --teleop.port=$LEADER_PORT --teleop.id=$LEADER_ID
```

The tool asks you to:

1. Move the arm to the middle of every joint's range and press Enter. Do not skip this. It sets the zero.
2. Move every joint slowly through its full range, both ends, then press Enter. Reach the real limits. A joint that did not reach its limit gets a wrong range and moves the wrong way or too little in teleop.

Files land in `~/.cache/huggingface/lerobot/calibration/robots/so101_follower/follower_a.json` and `.../teleoperators/so101_leader/leader_a.json`.

## 5. Back up

```bash
scripts/backup_calibration.sh
```

Prints the backup folder. Do this right after calibration and before any recalibration.

## 6. Check

```bash
lerobot-teleoperate --robot.type=so101_follower --robot.port=$FOLLOWER_PORT --robot.id=$FOLLOWER_ID \
  --teleop.type=so101_leader --teleop.port=$LEADER_PORT --teleop.id=$LEADER_ID
```

Every joint of the follower mirrors the leader in the same direction across the full range. The gripper opens and closes fully. Then 10 minutes of teleop: no motor error, no comms error, no servo too hot to touch.

## Restore from a backup

```bash
scripts/backup_calibration.sh --restore calibration_backups/<folder>
```

Then a 5-trial smoke test before anything else.

## The two mistakes people make

1. **Wrong motor ID order.** Motor 1 in the gripper slot. Teleop then maps joints wrong. Fix: check the tape labels against the order in step 2, redo setup for the wrong motor.
2. **Not reaching the joint limits during calibration.** The range is too small. The follower moves less than the leader, or hits an end and hums. Fix: recalibrate that arm, slowly, all the way to both ends of every joint.

## Known limits

- One calibration per arm id. A second arm needs its own id (`follower_b`).
- If a motor is replaced, that arm must be recalibrated.
