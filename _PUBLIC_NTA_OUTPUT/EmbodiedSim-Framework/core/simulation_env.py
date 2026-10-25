"""
PyBullet通用仿真环境（核心框架版）
================================================
提供标准的：
  - 仿真生命周期管理（init/reset/step/close）
  - 机器人加载 + 关节控制接口
  - 场景物体加载 + 碰撞对象管理
  - 相机渲染 + 状态观测获取

说明：本文件为工程应用框架，不包含任何RL算法训练逻辑，
      专注于「仿真环境作为一个服务」的系统集成能力。
"""

from __future__ import annotations

import os
import time
import math
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Any

try:
    import pybullet as p
    import pybullet_data
    HAS_PYBULLET = True
except ImportError:
    HAS_PYBULLET = False


# ============================================================
# 配置数据类
# ============================================================
@dataclass
class SimConfig:
    """仿真环境配置（通用示例版）"""
    mode: str = "gui"                       # gui / direct / share_memory
    gravity: float = -9.81                  # 重力加速度
    time_step: float = 0.002                # 仿真步长
    render_width: int = 1280                # 渲染宽度
    render_height: int = 720                # 渲染高度
    auto_start: bool = True                 # 构造时自动连接
    verbose: bool = True                    # 打印启动信息


@dataclass
class RobotState:
    """机器人状态快照（标准接口）"""
    joint_positions: List[float] = field(default_factory=list)
    joint_velocities: List[float] = field(default_factory=list)
    joint_torques: List[float] = field(default_factory=list)
    end_effector_pos: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    end_effector_orn: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    timestamp_s: float = 0.0


# ============================================================
# 核心仿真环境类
# ============================================================
class PyBulletSimulationEnv:
    """
    PyBullet通用仿真环境（框架版）
    ------------------------------------------------
    用法示例：
        >>> from core.simulation_env import PyBulletSimulationEnv, SimConfig
        >>> env = PyBulletSimulationEnv(SimConfig(mode="gui"))
        >>> env.load_robot("panda")
        >>> env.set_joint_positions([0.0]*7)
        >>> obs = env.get_robot_state()
        >>> for _ in range(1000): env.step()
        >>> env.close()
    """

    def __init__(self, config: Optional[SimConfig] = None):
        self.cfg = config or SimConfig()
        self._cid: Optional[int] = None            # PyBullet client id
        self._plane_id: Optional[int] = None       # 地面id
        self._robot_id: Optional[int] = None       # 机器人id
        self._objects: Dict[str, int] = {}         # 场景对象
        self._num_joints: int = 0                  # 机器人关节数
        self._ee_index: int = -1                   # 末端执行器关节索引
        self._timestep_count: int = 0              # 步数计数
        self._start_time_s: float = 0.0            # 启动仿真时间

        if not HAS_PYBULLET:
            raise ImportError(
                "PyBullet未安装，请先运行：pip install pybullet numpy\n"
                "或使用项目根目录：pip install -r requirements.txt"
            )

        if self.cfg.auto_start:
            self.connect()

    # ============== 生命周期 ==============
    def connect(self) -> int:
        """连接PyBullet仿真服务"""
        mode_map = {
            "gui": p.GUI,
            "direct": p.DIRECT,
            "share_memory": p.SHARED_MEMORY,
        }
        if self.cfg.mode not in mode_map:
            raise ValueError(f"未知mode: {self.cfg.mode}")

        self._cid = p.connect(mode_map[self.cfg.mode])
        p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=self._cid)
        p.setGravity(0, 0, self.cfg.gravity, physicsClientId=self._cid)
        p.setPhysicsEngineParameter(
            fixedTimeStep=self.cfg.time_step,
            numSolverIterations=100,
            physicsClientId=self._cid,
        )
        p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0, physicsClientId=self._cid)
        p.configureDebugVisualizer(p.COV_ENABLE_MOUSE_PICKING, 1, physicsClientId=self._cid)
        p.resetDebugVisualizerCamera(
            cameraDistance=1.8,
            cameraYaw=45,
            cameraPitch=-30,
            cameraTargetPosition=[0.3, 0.0, 0.4],
            physicsClientId=self._cid,
        )
        # 加载地面
        self._plane_id = p.loadURDF("plane.urdf", physicsClientId=self._cid)
        self._start_time_s = time.time()
        if self.cfg.verbose:
            print(f"[SimEnv] PyBullet已连接 | mode={self.cfg.mode} | client_id={self._cid}")
        return self._cid

    def reset(self) -> RobotState:
        """重置仿真环境（回到初始位姿）"""
        if self._robot_id is None:
            raise RuntimeError("请先调用 load_robot() 加载机器人")
        p.resetSimulation(physicsClientId=self._cid)
        self._plane_id = p.loadURDF("plane.urdf", physicsClientId=self._cid)
        # 重新加载机器人
        robot = self._robot_info if hasattr(self, '_robot_info') else {}
        if robot:
            self.load_robot(robot.get("type", "panda"), robot.get("ee_index", 11))
        self._timestep_count = 0
        return self.get_robot_state()

    def step(self, n_steps: int = 1) -> None:
        """推进仿真 n_steps 步"""
        for _ in range(n_steps):
            p.stepSimulation(physicsClientId=self._cid)
            self._timestep_count += 1
        # GUI模式下轻度sleep防止画面过快
        if self.cfg.mode == "gui":
            time.sleep(0.001)

    def close(self) -> None:
        """关闭仿真"""
        if self._cid is not None and p.getConnectionInfo(self._cid)["isConnected"]:
            p.disconnect(physicsClientId=self._cid)
            self._cid = None
            if self.cfg.verbose:
                print(f"[SimEnv] 仿真已关闭 | 总步数={self._timestep_count}")

    # ============== 机器人管理 ==============
    def load_robot(
        self,
        robot_type: str = "panda",
        ee_index: int = 11,
        start_pos: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        start_orn: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
    ) -> int:
        """
        加载机器人模型
        :param robot_type: 机器人类型（示例：panda / kuka_iiwa）
        :param ee_index:   末端执行器关节索引
        :return: 机器人body unique id
        """
        if robot_type == "panda":
            urdf_path = "franka_panda/panda.urdf"
            use_fixed = True
        elif robot_type == "kuka_iiwa":
            urdf_path = "kuka_iiwa/model.urdf"
            use_fixed = True
        else:
            # 自定义URDF路径支持
            urdf_path = robot_type
            use_fixed = True

        self._robot_id = p.loadURDF(
            urdf_path,
            basePosition=start_pos,
            baseOrientation=start_orn,
            useFixedBase=use_fixed,
            physicsClientId=self._cid,
        )
        self._num_joints = p.getNumJoints(self._robot_id, physicsClientId=self._cid)
        self._ee_index = ee_index if 0 <= ee_index < self._num_joints else self._num_joints - 1
        self._robot_info = {"type": robot_type, "ee_index": self._ee_index}

        if self.cfg.verbose:
            print(
                f"[SimEnv] 机器人已加载 | type={robot_type} | "
                f"joints={self._num_joints} | ee_index={self._ee_index}"
            )
        return self._robot_id

    # ============== 控制接口 ==============
    def set_joint_positions(self, positions: List[float], max_force: Optional[List[float]] = None) -> None:
        """设置关节目标位置（position control）"""
        if self._robot_id is None:
            return
        controlled = [i for i in range(self._num_joints)
                      if p.getJointInfo(self._robot_id, i, self._cid)[2] == p.JOINT_REVOLUTE]
        pos_list = list(positions)[: len(controlled)]
        if len(pos_list) < len(controlled):
            pos_list += [0.0] * (len(controlled) - len(pos_list))
        force_list = list(max_force)[: len(controlled)] if max_force else [300.0] * len(controlled)
        p.setJointMotorControlArray(
            bodyUniqueId=self._robot_id,
            jointIndices=controlled,
            controlMode=p.POSITION_CONTROL,
            targetPositions=pos_list,
            forces=force_list,
            physicsClientId=self._cid,
        )

    def set_end_effector_pose(self, target_pos: Tuple[float, float, float],
                              target_orn: Optional[Tuple[float, float, float, float]] = None) -> None:
        """逆运动学设置末端位姿（调用PyBullet内置IK，纯应用层接口）"""
        if self._robot_id is None or self._ee_index < 0:
            return
        if target_orn is None:
            target_orn = p.getQuaternionFromEuler([0.0, math.pi, 0.0])
        controlled = [i for i in range(self._num_joints)
                      if p.getJointInfo(self._robot_id, i, self._cid)[2] == p.JOINT_REVOLUTE]
        joint_poses = p.calculateInverseKinematics(
            bodyUniqueId=self._robot_id,
            endEffectorLinkIndex=self._ee_index,
            targetPosition=target_pos,
            targetOrientation=target_orn,
            physicsClientId=self._cid,
        )
        self.set_joint_positions(list(joint_poses)[: len(controlled)])

    # ============== 状态获取 ==============
    def get_robot_state(self) -> RobotState:
        """获取机器人当前状态快照"""
        state = RobotState()
        if self._robot_id is None:
            return state
        controlled = [i for i in range(self._num_joints)
                      if p.getJointInfo(self._robot_id, i, self._cid)[2] == p.JOINT_REVOLUTE]
        js = p.getJointStates(self._robot_id, controlled, physicsClientId=self._cid)
        state.joint_positions = [j[0] for j in js]
        state.joint_velocities = [j[1] for j in js]
        state.joint_torques = [j[3] for j in js] if len(js) and len(js[0]) >= 4 else []
        if self._ee_index >= 0:
            ls = p.getLinkState(self._robot_id, self._ee_index, computeForwardKinematics=True, physicsClientId=self._cid)
            state.end_effector_pos = tuple(ls[4])
            state.end_effector_orn = tuple(ls[5])
        state.timestamp_s = time.time() - self._start_time_s
        return state

    # ============== 场景物体 ==============
    def add_box(self, name: str, half_extents: Tuple[float, float, float],
                pos: Tuple[float, float, float], mass: float = 1.0,
                color: Tuple[float, float, float, float] = (0.8, 0.2, 0.2, 1.0)) -> int:
        """在场景中添加一个立方体（常用于仿真演示）"""
        col_id = p.createCollisionShape(p.GEOM_BOX, halfExtents=half_extents, physicsClientId=self._cid)
        vis_id = p.createVisualShape(p.GEOM_BOX, halfExtents=half_extents, rgbaColor=color, physicsClientId=self._cid)
        obj_id = p.createMultiBody(baseMass=mass, baseCollisionShapeIndex=col_id,
                                   baseVisualShapeIndex=vis_id, basePosition=pos, physicsClientId=self._cid)
        self._objects[name] = obj_id
        return obj_id

    def add_worktable(self, pos: Tuple[float, float, float] = (0.5, 0.0, 0.2)) -> int:
        """添加一张简易工作台（通用场景组件）"""
        return self.add_box("worktable", half_extents=(0.6, 0.6, 0.2),
                            pos=pos, mass=0.0, color=(0.6, 0.5, 0.4, 1.0))

    def list_objects(self) -> Dict[str, int]:
        """列出所有场景物体"""
        return dict(self._objects)

    # ============== 渲染 / 相机 ==============
    def render_camera_image(self, target_pos: Tuple[float, float, float] = (0.5, 0.0, 0.4),
                            distance: float = 1.2, yaw: float = 45.0, pitch: float = -20.0
                            ) -> Tuple[Any, Any, Any]:
        """渲染RGB/深度/分割图像（不涉及算法，仅展示渲染能力）"""
        view_matrix = p.computeViewMatrixFromYawPitchRoll(
            cameraTargetPosition=target_pos, distance=distance, yaw=yaw, pitch=pitch,
            roll=0.0, upAxisIndex=2, physicsClientId=self._cid,
        )
        proj_matrix = p.computeProjectionMatrixFOV(
            fov=60.0, aspect=float(self.cfg.render_width) / self.cfg.render_height,
            nearVal=0.1, farVal=10.0, physicsClientId=self._cid,
        )
        w, h, rgb, depth, seg = p.getCameraImage(
            width=self.cfg.render_width, height=self.cfg.render_height,
            viewMatrix=view_matrix, projectionMatrix=proj_matrix,
            renderer=p.ER_BULLET_HARDWARE_OPENGL, physicsClientId=self._cid,
        )
        return rgb, depth, seg

    # ============== 上下文管理器（推荐用法） ==============
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # ============== 信息查询 ==============
    @property
    def is_connected(self) -> bool:
        return self._cid is not None

    @property
    def elapsed_sim_time_s(self) -> float:
        return self._timestep_count * self.cfg.time_step

    def __repr__(self) -> str:
        status = "CONNECTED" if self.is_connected else "CLOSED"
        return (f"<PyBulletSimulationEnv status={status} mode={self.cfg.mode} "
                f"steps={self._timestep_count} robot={self._robot_id or 'None'}>")
