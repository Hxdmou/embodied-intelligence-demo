"""
Headless evaluation — EXACT replica of demo_trained_agent.py physics & success criteria.
Only difference: p.DIRECT instead of p.GUI (no rendering), no keyboard/HUD, no inter-episode pause.
Inter-episode pause in demo cannot affect results because reset_to_home() hard-resets joint states.

Usage:
    python eval_headless.py [model.zip] [episodes]
Default model: ppo_kuka_reach_gpu_final.zip, episodes: 50 (same grid as demo)
"""
import os, sys, time
os.environ['PYBULLET_DISABLE_WARNINGS'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'

import numpy as np
import pybullet as p
import pybullet_data

# ──────────── CONFIG: IDENTICAL to demo_trained_agent.py ────────────
NUM_JOINTS       = 7
JOINT_INDICES    = list(range(NUM_JOINTS))
EE_LINK          = 6
ACTION_SCALE     = 2.0
JOINT_FORCE      = 200.0
SIM_DT           = 1.0/960.0
MAX_STEP_DELTA   = 96.0 * SIM_DT          # 0.10 rad/step
ANGULAR_DAMPING  = 0.10
LINEAR_DAMPING   = 0.10
DISTANCE_THRESHOLD = 0.05
STABLE_COUNT     = 2
MAX_EPISODE_STEPS = 1500
GRID_RESOLUTION  = 9
EPISODES_TO_RUN  = 50
TARGET_MIN = np.array([0.40, -0.10, 0.30])
TARGET_MAX = np.array([0.50,  0.10, 0.40])
JOINT_LIMITS_LOW  = np.array([-2.967,-2.094,-2.967,-2.094,-2.967,-2.094,-3.054], dtype=np.float64)
JOINT_LIMITS_HIGH = np.array([ 2.967, 2.094, 2.967, 2.094, 2.967, 2.094, 3.054], dtype=np.float64)


def sanitize_target(target_q, current_q):
    """Replica of SafetyController.check (layers 2 & 3; layers 1/4/5 never block)."""
    q = np.clip(target_q, JOINT_LIMITS_LOW, JOINT_LIMITS_HIGH)
    dq = q - current_q
    if np.max(np.abs(dq)) > MAX_STEP_DELTA * 1.01:
        q = current_q + np.clip(dq, -MAX_STEP_DELTA, MAX_STEP_DELTA)
        q = np.clip(q, JOINT_LIMITS_LOW, JOINT_LIMITS_HIGH)
    return q


def reset_to_home(robot_id):
    for j in range(NUM_JOINTS):
        p.resetJointState(robot_id, j, 0.0, 0.0)
        p.setJointMotorControl2(robot_id, j, p.POSITION_CONTROL,
                                targetPosition=0.0, force=JOINT_FORCE)
    for _ in range(60):
        p.stepSimulation()


def build_grid_targets(episodes):
    xs = np.linspace(TARGET_MIN[0], TARGET_MAX[0], GRID_RESOLUTION)
    ys = np.linspace(TARGET_MIN[1], TARGET_MAX[1], GRID_RESOLUTION)
    zs = np.linspace(TARGET_MIN[2], TARGET_MAX[2], GRID_RESOLUTION)
    targets = []
    for x in xs:
        for y in ys:
            for z in zs:
                targets.append(np.array([x, y, z], dtype=np.float64))
    return targets[:episodes]


def build_random_targets(n, seed):
    """Uniform random targets inside the demo operating range (generalization probe)."""
    rng = np.random.RandomState(seed)
    return [rng.uniform(TARGET_MIN, TARGET_MAX) for _ in range(n)]


def evaluate(model_path, episodes=EPISODES_TO_RUN, verbose=True, targets=None):
    from stable_baselines3 import PPO
    model = PPO.load(model_path, device='cpu', verbose=0)

    p.connect(p.DIRECT)
    p.setAdditionalSearchPath(pybullet_data.getDataPath())
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(SIM_DT)
    p.setPhysicsEngineParameter(fixedTimeStep=SIM_DT, numSolverIterations=10, numSubSteps=1)

    p.loadURDF('plane.urdf')
    _flags = p.URDF_USE_SELF_COLLISION_EXCLUDE_ALL_PARENTS
    robot_id = p.loadURDF('kuka_iiwa/model.urdf', [0, 0, 0], useFixedBase=True, flags=_flags)

    for j in range(NUM_JOINTS):
        p.changeDynamics(robot_id, j,
                         angularDamping=ANGULAR_DAMPING,
                         linearDamping=LINEAR_DAMPING,
                         lateralFriction=1.0,
                         jointDamping=ANGULAR_DAMPING)
    p.changeDynamics(robot_id, -1, linearDamping=0.04, angularDamping=0.04)

    if targets is None:
        targets = build_grid_targets(episodes)
    episodes = len(targets)

    successes = 0
    results = []
    t0 = time.time()
    for ep in range(episodes):
        reset_to_home(robot_id)
        target_pos = targets[ep]
        # demo does one stepSimulation after spawning the (non-collidable) target;
        # visual-only body has zero physics effect, so we just step once.
        p.stepSimulation()

        success = False
        min_dist = 9.99
        stable_count = 0
        steps_taken = 0

        for step in range(MAX_EPISODE_STEPS):
            states = p.getJointStates(robot_id, JOINT_INDICES)
            current_q = np.array([s[0] for s in states], dtype=np.float64)
            ee_pos = np.array(p.getLinkState(robot_id, EE_LINK)[0], dtype=np.float32)
            dist = float(np.linalg.norm(ee_pos - target_pos))
            if dist < min_dist:
                min_dist = dist

            obs = np.concatenate([
                current_q.astype(np.float32),
                ee_pos,
                target_pos.astype(np.float32)
            ])
            action, _ = model.predict(obs, deterministic=True)
            action = action.astype(np.float64) * ACTION_SCALE
            action = np.clip(action, -MAX_STEP_DELTA, MAX_STEP_DELTA)

            safe_target = sanitize_target(current_q + action, current_q)
            for i in range(NUM_JOINTS):
                p.setJointMotorControl2(robot_id, i, p.POSITION_CONTROL,
                                        targetPosition=float(safe_target[i]),
                                        force=JOINT_FORCE)
            p.stepSimulation()
            steps_taken += 1

            if dist < DISTANCE_THRESHOLD:
                stable_count += 1
                if stable_count >= STABLE_COUNT:
                    success = True
                    break
            else:
                stable_count = 0

        if success:
            successes += 1
        results.append((ep + 1, success, min_dist, steps_taken))
        if verbose:
            tag = 'SUCCESS' if success else 'TIMEOUT'
            print(f"Episode {ep+1}: {tag}  min_dist={min_dist*100:.2f}cm  "
                  f"steps={steps_taken}  success_rate={successes}/{ep+1}", flush=True)

    p.disconnect()
    rate = 100.0 * successes / episodes
    elapsed = time.time() - t0
    print(f"\nFINAL: {successes}/{episodes} = {rate:.1f}% success rate.  "
          f"(eval wall time {elapsed:.1f}s)", flush=True)
    return successes, episodes, results


if __name__ == '__main__':
    # python eval_headless.py model.zip episodes [--random --seed S]
    model_path = sys.argv[1] if len(sys.argv) > 1 else 'ppo_kuka_reach_gpu_final.zip'
    n_eps = int(sys.argv[2]) if len(sys.argv) > 2 else EPISODES_TO_RUN
    targets = None
    if '--random' in sys.argv:
        seed = int(sys.argv[sys.argv.index('--seed') + 1]) if '--seed' in sys.argv else 12345
        targets = build_random_targets(n_eps, seed)
    evaluate(model_path, episodes=n_eps, targets=targets)
