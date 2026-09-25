# How it fits together

Diagrams for people who want to learn from this build, not only run it. They render on GitHub. To change one, edit the text block, there are no image files.

Read them in order. Each one answers one question.

## 1. What is connected to what

Thick arrows are power. Thin arrows are data. The e-stop sits on the power side only, so the software keeps talking to the boards and can report the loss.

```mermaid
flowchart TB
    subgraph mac["Mac mini M4, no GPU"]
        tools["LeRobot tools and the scripts in this repo"]
    end

    subgraph hub["Powered USB hub"]
        scene["Scene camera<br>USB webcam, 640x480 at 30 fps"]
        wrist["Wrist camera<br>IMX179 on the gripper"]
        bF["Driver board F<br>Waveshare bus servo adapter"]
        bL["Driver board L<br>Waveshare bus servo adapter"]
    end

    subgraph follower["Follower arm, SO-101"]
        fs["6 STS3215 servos<br>IDs 1 to 6, one cable, daisy chained"]
    end

    subgraph leader["Leader arm, SO-101"]
        ls["6 STS3215 servos<br>IDs 1 to 6, one cable, daisy chained"]
    end

    psuF["12V 3A adapter"] ==> estop
    psuL["12V 3A adapter"] ==> estop
    estop{{"E-stop<br>two NC contacts, one per board"}} ==> bF
    estop ==> bL

    tools --- hub
    bF -.->|"serial bus"| fs
    bL -.->|"serial bus"| ls
```

What to notice:

- Both arms use the same servo, the same board and the same cable. The only difference is the software role: the leader is read, the follower is driven.
- The cameras and the boards share one hub. MJPEG at 640x480 keeps two video streams inside USB 2 bandwidth. If frames drop, the fix is in `docs/usb-map.md`, not in code.
- One adapter per board. A shared adapter sags when six servos move at once.

## 2. From printed parts to a policy that runs

```mermaid
flowchart LR
    subgraph once["Once per arm"]
        ids["Set motor IDs<br>lerobot-setup-motors"] --> asm["Assemble"] --> cal["Calibrate<br>lerobot-calibrate"] --> bak["Back up calibration<br>backup_calibration.sh"]
    end

    subgraph session["Every session"]
        pre["Preflight<br>preflight.py"] --> est["E-stop test"] --> cam["Camera check<br>check_cameras.py"]
    end

    subgraph skill["Per skill"]
        tele["Teleop feasibility<br>teleop.sh, 10 tries by hand"] --> rec["Record 50+ episodes<br>record.sh"] --> rep["Dataset report<br>dataset_report.py"]
    end

    subgraph cloud["Cloud GPU"]
        train["Train ACT<br>train_cloud.sh"] --> policy["Policy on the Hub"]
    end

    subgraph eval["Back on the Mac"]
        roll["Run the policy<br>lerobot-rollout"] --> trials["20 trials under a fixed protocol"] --> score["Score, honest"]
    end

    bak --> pre
    cam --> tele
    rep -->|"push to Hub"| train
    policy --> roll
    score -->|"score too low: fix the data first"| rec
```

What to notice:

- The loop at the end goes back to recording, not to model tuning. On a small dataset, more and better demonstrations beat hyperparameters.
- Nothing is recorded for a task a human cannot do with the leader arm 8 times out of 10. If the person fails, the data will be bad.
- The Mac never trains. It collects data and runs the policy. Training is a rented GPU for a few dollars.

## 3. One session, in order

The order is the safety rule. Motors move only after preflight and the e-stop test.

```mermaid
flowchart TD
    start(["Sit down, e-stop within reach"]) --> pf["preflight.py"]
    pf --> ok{"PASS?"}
    ok -->|"no"| fix["Fix what it names<br>ports, cameras, calibration, disk, token"] --> pf
    ok -->|"yes"| es["Press the e-stop during teleop<br>both arms go limp"]
    es --> esok{"Limp at once?"}
    esok -->|"no"| stop(["Stop. Fix the wiring. No motion today."])
    esok -->|"yes"| cc["check_cameras.py<br>writes a 30 minute stamp"]
    cc --> work["teleop.sh or record.sh<br>they refuse without a fresh stamp"]
    work --> done["Ctrl-C"] --> rest["safe_rest.py<br>slow move to rest, torque off"] --> off(["Power off at the e-stop"])
```

What to notice:

- The camera check leaves a time stamp. The wrappers read it and refuse after 30 minutes. A tool that refuses is better than a doc that asks.
- Safe rest refuses to move if any joint is far from the rest pose. The person guides the arm closer by hand first, so the arm never sweeps across the desk on its own.

## 4. The joint chain and the motor IDs

Six motors in a chain. The ID is set into each motor before assembly and taped on. Leader and follower use the same IDs, so joint 3 on one is joint 3 on the other.

```mermaid
flowchart LR
    base["Base plate"] --> m1["ID 1<br>shoulder_pan<br>turns the arm left and right"]
    m1 --> m2["ID 2<br>shoulder_lift<br>raises the upper arm"]
    m2 --> m3["ID 3<br>elbow_flex<br>bends the elbow"]
    m3 --> m4["ID 4<br>wrist_flex<br>tilts the wrist"]
    m4 --> m5["ID 5<br>wrist_roll<br>rotates the gripper"]
    m5 --> m6["ID 6<br>gripper<br>opens and closes"]
    m6 -.- camw["Wrist camera<br>bolted to the gripper plate"]
```

What to notice:

- A joint value is one number in degrees. The gripper is 0 to 100. Calibration maps the raw motor ticks to these numbers and stores the map in one JSON file per arm.
- The two classic mistakes are both about this chain: IDs in the wrong slots, and a calibration that did not reach both ends of a joint.

## 5. What one recorded frame holds

Recording runs a loop 30 times a second. Each pass writes one frame to the dataset.

```mermaid
sequenceDiagram
    participant L as Leader arm
    participant R as lerobot-record
    participant F as Follower arm
    participant C as Cameras
    participant D as Dataset

    loop every 33 ms
        R->>L: read 6 joint positions
        L-->>R: action, 6 numbers
        R->>F: send action
        R->>F: read 6 joint positions
        F-->>R: observation.state
        R->>C: read latest frames
        C-->>R: scene image, wrist image
        R->>D: frame = state + 2 images + action + timestamp
    end
    R->>D: encode images to video, one file per camera per episode
    R->>D: push to the Hugging Face Hub
```

What to notice:

- The action is where the leader is. The observation is where the follower is and what the cameras see. The policy learns to predict the next actions from the observation.
- The wrist camera is what makes grasping work. The scene camera tells the policy where things are. Drop either and the score falls.
- `dataset_report.py` reads the timestamps back and checks the loop really ran at 30 fps. Frames that arrive late are counted as drops.

## 6. What the policy does at run time

```mermaid
flowchart LR
    obs["Observation<br>6 joint values + scene image + wrist image"] --> act["ACT policy<br>on the Mac, MPS"]
    act --> chunk["Action chunk<br>the next N joint targets"]
    chunk --> lim["Step limit<br>max_relative_target"]
    lim --> arm["Follower arm"]
    arm --> obs
    stopk["Stop key, timeout, e-stop"] -. "ends the loop" .-> lim
```

What to notice:

- ACT predicts a short chunk of future actions, not one step. That is why it moves smoothly on a small dataset.
- The step limit is a robot setting, not a policy setting. It caps how far any joint may move per step, so a confused policy moves slowly instead of fast.
- The loop runs on the Mac. Inference for ACT is light enough for the M4 without a GPU.
