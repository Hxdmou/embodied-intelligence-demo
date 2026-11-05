"""
Fine-tune ppo_kuka_reach_gpu_final.zip on the demo's own evaluation criteria.

- Loads the original model (never overwritten), continues PPO training with a
  small learning rate inside an env whose physics match the demo exactly.
- Every EVAL_INTERVAL steps: save temp checkpoint, evaluate the exact 50 demo
  grid targets in a subprocess (eval_headless.py), keep the best checkpoint.
- Stops early once success rate >= TARGET_RATE.

Usage:
    python finetune_ppo.py
"""
import os
import sys
import math
import shutil
import subprocess
import multiprocessing

os.environ['PYBULLET_DISABLE_WARNINGS'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'

import torch
# main process does gradient updates; leave cores for the 16 physics subprocesses
torch.set_num_threads(max(4, (os.cpu_count() or 8) // 2))

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor

from finetune_env import make_env

HERE = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable
EVAL_SCRIPT = os.path.join(HERE, 'eval_headless.py')

BASE_MODEL = os.path.join(HERE, 'ppo_kuka_reach_gpu_final.zip')   # untouched
BEST_MODEL = os.path.join(HERE, 'ppo_kuka_reach_finetuned_best.zip')
TMP_MODEL  = os.path.join(HERE, 'ppo_kuka_reach_finetune_tmp.zip')

N_ENVS        = 16
EVAL_INTERVAL = 50_000      # eval every rollout (rollout = n_steps*n_envs = 65,536)
MAX_NEW_STEPS = 2_000_000
LEARNING_RATE = 3e-5        # rollouts now exploit base behavior (see log_std fix
                            # below), so gradients are informative: 15x the old 2e-6,
                            # still 10x below the 3e-4 that caused full collapse
N_EPOCHS      = 4           # more reuse of each rollout; ratio stays near 1 because
                            # rollouts are near-deterministic now
BATCH_SIZE    = 512         # larger batch = fewer, more vectorized gradient steps
TARGET_RATE   = 98.0        # stop early once reached (49/50)

# Dual-metric checkpoint selection (anti-overfitting):
# the previous run hit 50/50 on grid points but collapsed on in-range random
# targets (77% -> 38%) because training sampled grid points too narrowly.
# A checkpoint is only accepted if the fixed random probe does not regress
# more than RANDOM_TOLERANCE points below the base model's random rate.
RANDOM_PROBE_N    = 100
RANDOM_PROBE_SEED = 12345
RANDOM_TOLERANCE  = 5       # percentage points


def run_eval(model_path, episodes=50, random=False):
    """Evaluate a checkpoint in a clean subprocess; returns (successes, total).
    random=True evaluates the fixed in-range random probe instead of the grid."""
    cmd = [PYTHON, EVAL_SCRIPT, model_path, str(episodes)]
    if random:
        cmd += ['--random', '--seed', str(RANDOM_PROBE_SEED)]
    r = subprocess.run(cmd,
                       capture_output=True, text=True, timeout=900, cwd=HERE)
    for line in r.stdout.splitlines():
        if line.startswith('FINAL:'):
            frac = line.split()[1]          # e.g. "41/50"
            s, t = frac.split('/')
            return int(s), int(t)
    raise RuntimeError(f"eval failed:\nstdout: {r.stdout[-800:]}\nstderr: {r.stderr[-800:]}")


def main():
    print("=" * 70)
    print(" Fine-tuning PPO KUKA reach — demo-matched physics")
    print(f" base model : {os.path.basename(BASE_MODEL)} (read-only)")
    print(f" n_envs={N_ENVS}  lr={LEARNING_RATE}  n_epochs={N_EPOCHS}  "
          f"eval every ~{EVAL_INTERVAL:,} steps")
    print("=" * 70, flush=True)

    env = SubprocVecEnv([make_env(i) for i in range(N_ENVS)])
    env = VecMonitor(env)

    print("Loading base model...", flush=True)
    model = PPO.load(BASE_MODEL, env=env, device='cpu', verbose=0)
    model.tensorboard_log = None  # zip stored a TB log dir; tensorboard not installed
    # conservative fine-tuning settings (optimizer already built by load).
    # IMPORTANT: PPO.train() re-applies lr_schedule to the optimizer every
    # iteration, and lr_schedule was frozen at load time from the saved
    # learning_rate (3e-4). Rebuild it AFTER overriding learning_rate, or the
    # fine-tuning silently runs at 3e-4 and destroys the base policy (this bug
    # caused the 82%->12% collapse and the earlier overfitted model).
    model.learning_rate = LEARNING_RATE
    model._setup_lr_schedule()
    for pg in model.policy.optimizer.param_groups:
        pg['lr'] = LEARNING_RATE
    model.n_epochs = N_EPOCHS
    model.batch_size = BATCH_SIZE

    # ROOT CAUSE of all earlier fine-tune failures (evidence chain):
    # the saved policy has log_std ~= 0 (std ~= 1.0) while the action space is
    # only [-0.05, 0.05] — the original 5M-step run trained with ent_coef=0.01
    # which kept exploration saturated at the action bounds (random bang-bang).
    # Any fine-tune rollout is therefore random thrashing, so PPO cannot build
    # on the base policy and just re-learns from scratch: lr 2e-6 eroded grid
    # 82->62->40 (0.25 grid weight) / 82->42->10 (0.5); lr 3e-4 collapsed to
    # 12% then re-learned to 76%. Fix: rollouts exploit the base behavior.
    # std=0.02 keeps local exploration; log_std frozen + ent_coef=0 so it stays.
    # Deterministic eval (demo) uses the action mean only -> unaffected.
    FINETUNE_STD = 0.02
    with torch.no_grad():
        model.policy.log_std.copy_(
            torch.full_like(model.policy.log_std, math.log(FINETUNE_STD)))
    model.policy.log_std.requires_grad = False
    model.ent_coef = 0.0
    print(f"Loaded. num_timesteps={model.num_timesteps:,}  "
          f"n_steps={model.n_steps}  batch_size={model.batch_size}", flush=True)

    base_s, base_t = run_eval(BASE_MODEL)
    base_rs, base_rt = run_eval(BASE_MODEL, episodes=RANDOM_PROBE_N, random=True)
    print(f"Baseline eval: grid {base_s}/{base_t} = {100.0*base_s/base_t:.1f}%  |  "
          f"random {base_rs}/{base_rt} = {100.0*base_rs/base_rt:.1f}%", flush=True)
    best_s, best_rs = base_s, base_rs
    shutil.copy(BASE_MODEL, BEST_MODEL)   # best so far = original

    start_ts = model.num_timesteps
    stop_reason = None
    while model.num_timesteps - start_ts < MAX_NEW_STEPS:
        model.learn(total_timesteps=model.num_timesteps + EVAL_INTERVAL,
                    progress_bar=False)
        new_steps = model.num_timesteps - start_ts

        model.save(TMP_MODEL)
        s, t = run_eval(TMP_MODEL)
        rs, rt = run_eval(TMP_MODEL, episodes=RANDOM_PROBE_N, random=True)
        rate = 100.0 * s / t
        random_ok = rs >= base_rs - RANDOM_TOLERANCE
        print(f"[{new_steps:>9,} new steps] grid {s}/{t} = {rate:.1f}%  |  "
              f"random {rs}/{rt} = {100.0*rs/rt:.1f}% "
              f"{'OK' if random_ok else 'REJECT(random)'}  "
              f"(best grid {best_s}/{t})", flush=True)

        if random_ok and (s > best_s or (s == best_s and rs > best_rs)):
            best_s, best_rs = s, rs
            model.save(BEST_MODEL)
            print(f"  -> new best checkpoint saved", flush=True)

        if rate >= TARGET_RATE and random_ok:
            stop_reason = f"target rate {TARGET_RATE}% reached with random probe OK"
            break

    if stop_reason is None:
        stop_reason = f"step budget {MAX_NEW_STEPS:,} exhausted"
    print(f"\nStopping: {stop_reason}", flush=True)

    if os.path.exists(TMP_MODEL):
        os.remove(TMP_MODEL)

    s, t = run_eval(BEST_MODEL)
    rs, rt = run_eval(BEST_MODEL, episodes=RANDOM_PROBE_N, random=True)
    print(f"FINAL BEST MODEL: grid {s}/{t} = {100.0*s/t:.1f}%  |  "
          f"random {rs}/{rt} = {100.0*rs/rt:.1f}%", flush=True)
    print(f"(baseline was: grid {base_s}/{base_t} = {100.0*base_s/base_t:.1f}%  |  "
          f"random {base_rs}/{base_rt} = {100.0*base_rs/base_rt:.1f}%)", flush=True)
    env.close()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
