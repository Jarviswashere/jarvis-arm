# Emergency stop

The e-stop cuts motor power. It does not cut USB. So the software sees "motors lost", not "port gone", and can report it cleanly.

Status: PLAN. Wiring photo and test results are added once the switch is on the desk.

## Wiring

Two 12V 3A adapters, one per driver board. Each adapter's 12V line goes through one normally closed (NC) contact of one mushroom e-stop switch (22 mm panel type, two NC contacts). Pressing the switch opens both contacts, so both boards lose motor power at the same moment.

```
adapter A  +12V ──[ NC contact 1 ]── driver board A (follower)
adapter B  +12V ──[ NC contact 2 ]── driver board B (leader)
GND lines stay connected. USB stays connected.
```

Parts: mushroom switch with 2 NC blocks, 2 barrel jack extension cables (cut the +12V wire, crimp to the contact), a small box or the desk edge to mount it.

Day-1 fallback: a power strip with a big physical switch. Both adapters plug into it. Same effect, one step slower to reach.

## Placement

Within reach of Tony's seated position without looking. Not inside the taped workspace. Test the click before every session.

## What the software does on e-stop

During teleop the process raises a motor communication error within a few seconds. Expected: it prints the error and exits, or exits on one Ctrl-C. If it hangs, that is a bug to fix in `scripts/teleop.sh`.

After release: `scripts/teleop.sh` again. Mirroring works within 60 s without recalibration, because calibration lives in a file, not in the motors' volatile state.

## Test (safety gate SG1, every session)

1. Teleop running. Press the e-stop. Both arms go limp at once. USB devices are still listed by the OS.
2. Teleop process reports the loss within 5 s and exits or can be exited with one Ctrl-C.
3. Release, run `scripts/teleop.sh` again. Mirroring within 60 s.
4. Repeat 1 three times. All three pass.

## Results

| Date | Limp at once | Software report time | Restart time | Notes |
|---|---|---|---|---|
| | | | | not tested yet |

## Photo

(add `docs/img/estop-wiring.jpg`)
