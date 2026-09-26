# Training in the cloud

The Mac mini has no NVIDIA GPU. Every training run goes to a rented GPU. Record on the Mac, push the dataset to the Hub, train in the cloud, the policy lands on the Hub, pull it to the Mac and run it on the arm.

## First choice: Hugging Face Jobs

LeRobot submits the job itself when `--job.target` is set. Our wrapper:

```bash
scripts/train_cloud.sh <dataset> <policy_name> [steps] [flavor]
scripts/train_status.py <job_id>
scripts/train_status.py <job_id> --logs
```

Needs once: `hf auth login` with a write token, and prepaid credits on the account (Add Credits at https://huggingface.co/settings/billing). $10 of credits was enough to start; no PRO subscription was needed.

Defaults: ACT, 20,000 steps, flavor `l4x1`, timeout 4 h, wandb off, checkpoint pushed to `$HF_USER/<policy_name>`.

## Hardware flavors and price (from `hf jobs hardware`, Sept 2026)

ACT needs 2 to 6 GB of VRAM. The T4 is the cheapest GPU but old and slow for the ResNet backbone. L4 is the sweet spot.

| Flavor | GPU | Price per hour | Use |
|---|---|---|---|
| t4-small | T4 16 GB | $0.40 | avoid, slow |
| l4x1 | L4 24 GB | $0.80 | ACT, default |
| a10g-small | A10G 24 GB | $1.00 | ACT, a bit faster |
| a10g-large | A10G 24 GB, 12 vCPU | $1.50 | SmolVLA |
| a100-large | A100 80 GB | $2.50 | only if a run is too slow |

Measured: 4.6 steps per second on an L4 with batch size 8 and 2 cameras. So 20k steps is about 75 minutes, about $1 per full ACT run, plus 2 minutes of container start. Cheap enough to train after every data round.

## Runs so far

| Date | Dataset | Policy | Steps | Flavor | Wall time | Cost | Result |
|---|---|---|---|---|---|---|---|
| 2026-09-26 | lerobot/svla_so101_pickplace (50 ep) | ChaptTwoTonyStark/act_smoke_test | 200 | l4x1 | 3 min submit to done, about 1.5 min billed | about $0.02 at $0.0133/min (confirm on the billing page) | done, loss 6.39 at step 200, 4.6 steps/s, 3.7 GB GPU memory |

## Fallback: RunPod

Same command, different machine. Eight steps:

1. Sign up at runpod.io and add credit.
2. Deploy a pod: template "PyTorch 2.x", GPU RTX 4090 or A5000 (24 GB), 50 GB volume.
3. Open the web terminal (or SSH).
4. `pip install "lerobot[training,dataset]"`
5. `hf auth login` with the write token (paste, do not save it in a file on the pod).
6. Run the same command without the `--job.*` flags:
   ```bash
   lerobot-train --dataset.repo_id=$HF_USER/<dataset> --policy.type=act \
     --policy.repo_id=$HF_USER/<policy> --policy.push_to_hub=true \
     --policy.device=cuda --output_dir=outputs/train/<policy> --job_name=<policy> \
     --steps=20000 --wandb.enable=false
   ```
7. Wait for "pushed to hub" in the log, then check https://huggingface.co/$HF_USER/<policy>.
8. Stop the pod. It bills while it exists, not only while it trains.

## Pull the policy to the Mac

```bash
source scripts/env.sh
python -c "from lerobot.policies.act.modeling_act import ACTPolicy; ACTPolicy.from_pretrained('$HF_USER/<policy>')"
```

On the Mac this warns that cuda is not available and switches to mps. That is expected. First load downloads the ResNet-18 backbone (45 MB) once.

## Rules

- Start with the default ACT config and 20k steps. Do not tune anything until there is a 20-trial score.
- One dataset version, one policy version, same number. `so101_block_to_cup_v1` trains `act_block_to_cup_v1`.
- Write every run into the table above with its cost. The cost per skill matters for the plan.
