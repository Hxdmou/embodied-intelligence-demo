"""
感知-决策-执行 三层解耦接口定义
================================================
本文件定义具身智能系统的三层标准接口，
展示系统架构设计与模块化解耦能力：
  1) Perception（感知层）   —— 输入：传感器原始数据 → 输出：语义理解结果
  2) Decision（决策层）     —— 输入：语义+状态 → 输出：动作指令
  3) Execution（执行层）    —— 输入：动作指令 → 输出：执行结果

说明：三层都提供「抽象基类 + 基础实现」，
      不含任何复杂算法，仅展示架构设计模式。
"""

from __future__ import annotations

import abc
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable


# ============================================================
# 通用消息信封（三层之间通信的标准格式）
# ============================================================
@dataclass
class Message:
    """系统内部统一消息格式（架构级规范）"""
    msg_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    source: str = "unknown"          # 来源模块名
    target: str = "unknown"          # 目标模块名
    msg_type: str = "data"           # data / command / event / error
    timestamp_s: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_log_line(self) -> str:
        return (f"[{self.msg_type.upper()}] {self.source} -> {self.target} | "
                f"ts={self.timestamp_s:.3f} | keys={list(self.payload.keys())}")


# ============================================================
# 1. 感知层 接口
# ============================================================
class PerceptionModule(abc.ABC):
    """
    感知层抽象基类
    ------------------------------------------------
    职责：从各类传感器获取原始数据，转化为「可供决策层理解的语义化结果」
    """

    def __init__(self, name: str = "perception"):
        self.name = name
        self._subscribers: List[Callable[[Message], None]] = []
        self._sensor_status: Dict[str, bool] = {}

    # ---- 订阅机制（松耦合：感知→决策通信） ----
    def subscribe(self, callback: Callable[[Message], None]) -> None:
        self._subscribers.append(callback)

    def _publish(self, msg: Message) -> None:
        for cb in list(self._subscribers):
            try:
                cb(msg)
            except Exception as e:  # 订阅者异常不影响感知层主流程
                self._on_publish_error(e, msg)

    def _on_publish_error(self, err: Exception, msg: Message) -> None:
        """默认实现：打印错误日志（可被子类重写）"""
        print(f"[Perception] 订阅者处理异常: {err} | msg={msg.to_log_line()}")

    # ---- 传感器管理 ----
    def register_sensor(self, sensor_id: str, available: bool = True) -> None:
        self._sensor_status[sensor_id] = available

    def get_sensor_health(self) -> Dict[str, bool]:
        return dict(self._sensor_status)

    def all_sensors_ready(self) -> bool:
        return bool(self._sensor_status) and all(self._sensor_status.values())

    # ---- 核心抽象方法（子类实现具体算法/驱动） ----
    @abc.abstractmethod
    def sense(self) -> Message:
        """
        执行一次感知：读取传感器→处理→返回语义化结果
        返回 Message.payload 标准字段（建议包含）：
          - detected_objects: List[{label, bbox, confidence, pose_3d}]
          - scene_state:    {workspace_free_ratio, lighting_ok, ...}
          - system_state:   {battery_level, temperature, ...}
        """
        raise NotImplementedError

    def tick(self) -> Message:
        """对外调度入口：健康检查→感知→发布"""
        if not self.all_sensors_ready():
            return Message(source=self.name, msg_type="error",
                           payload={"reason": "部分传感器离线",
                                    "details": self._sensor_status})
        result = self.sense()
        result.source = self.name
        self._publish(result)
        return result


class MockPerception(PerceptionModule):
    """
    感知层参考实现：Mock版（用于无硬件时的系统联调）
    ------------------------------------------------
    作用：模拟相机/激光雷达/关节传感器返回数据，
         确保整个系统架构在无硬件情况下也能全链路跑通。
    """

    def __init__(self, name: str = "mock_perception"):
        super().__init__(name)
        self.register_sensor("camera_rgb", available=True)
        self.register_sensor("joint_encoder", available=True)
        self.register_sensor("wrist_force_torque", available=True)
        self._frame_counter = 0

    def sense(self) -> Message:
        self._frame_counter += 1
        mock_payload = {
            "detected_objects": [
                {"label": "workpiece_peg", "confidence": 0.94,
                 "pose_3d": {"xyz": (0.5,  0.05, 0.42), "rpy": (0.0, 0.0, 0.15)}},
                {"label": "base_hole",      "confidence": 0.88,
                 "pose_3d": {"xyz": (0.5, -0.05, 0.40), "rpy": (0.0, 0.0, 0.0)}},
            ],
            "scene_state": {
                "workspace_free_ratio": 0.82,
                "lighting_ok": True,
                "safety_zone_violation": False,
            },
            "system_state": {
                "temperature_c": 28.6,
                "mock_frame_seq": self._frame_counter,
            },
        }
        return Message(target="decision", msg_type="data", payload=mock_payload)


# ============================================================
# 2. 决策层 接口
# ============================================================
class DecisionModule(abc.ABC):
    """
    决策层抽象基类
    ------------------------------------------------
    职责：根据「感知语义结果 + 任务目标」产生「执行动作指令」
    注：本框架不包含RL算法训练逻辑，仅定义接口。
    """

    def __init__(self, name: str = "decision"):
        self.name = name
        self._task_goal: Dict[str, Any] = {"task": "idle"}
        self._step_count: int = 0

    # ---- 任务目标管理 ----
    def set_task_goal(self, task: str, **kwargs) -> None:
        self._task_goal = {"task": task, **kwargs}
        self._step_count = 0
        print(f"[Decision] 任务目标已设置: task={task} params={list(kwargs.keys())}")

    def get_task_goal(self) -> Dict[str, Any]:
        return dict(self._task_goal)

    # ---- 核心抽象方法 ----
    @abc.abstractmethod
    def decide(self, perception_msg: Message) -> Message:
        """
        根据感知结果产生动作指令
        返回 Message.payload 建议包含：
          - joint_positions / ee_pose / gripper_command
          - skill: {"name": "reach", "duration_s": 2.0, ...}
          - status:  running / done / failed
        """
        raise NotImplementedError

    def tick(self, perception_msg: Message) -> Message:
        """对外调度入口：决策→标记来源→返回"""
        self._step_count += 1
        decision = self.decide(perception_msg)
        decision.source = self.name
        decision.target = "execution"
        decision.meta["decision_step"] = self._step_count
        decision.meta["task_goal_snapshot"] = dict(self._task_goal)
        return decision


class SimpleSkillBasedDecision(DecisionModule):
    """
    决策层参考实现：基于原子技能库的简单状态机
    ------------------------------------------------
    演示架构：通过感知结果触发「reach → approach → insert → retract」等标准技能。
    （面试中可以清晰说明：感知输出目标位姿→决策选择合适技能→发送给执行层）
    """
    # 预定义技能库（工程应用视角，非算法视角）
    SKILL_LIBRARY: Dict[str, Dict[str, Any]] = {
        "reach":     {"name": "到达",  "default_duration_s": 2.0, "description": "移动到目标上方安全位置"},
        "approach":  {"name": "接近",  "default_duration_s": 1.5, "description": "沿Z轴缓慢接近工件"},
        "grip":      {"name": "抓取",  "default_duration_s": 0.8, "description": "闭合夹爪或磁吸"},
        "insert":    {"name": "插入",  "default_duration_s": 1.2, "description": "对齐后进行装配插入"},
        "retract":   {"name": "回撤",  "default_duration_s": 1.5, "description": "执行后回到安全位置"},
        "release":   {"name": "释放",  "default_duration_s": 0.5, "description": "松爪或释放磁吸"},
        "idle":      {"name": "待命",  "default_duration_s": 0.5, "description": "保持当前位姿"},
    }

    def __init__(self, name: str = "simple_skill_decision"):
        super().__init__(name)
        self._skill_sequence: List[str] = ["reach", "approach", "grip", "retract"]
        self._current_skill_idx: int = 0

    def decide(self, perception_msg: Message) -> Message:
        # 从感知中提取可用信息（容错：无则用默认）
        detected = perception_msg.payload.get("detected_objects", [])
        goal_task = self._task_goal.get("task", "idle")

        if goal_task == "idle" or not detected:
            skill = "idle"
        else:
            skill = self._skill_sequence[self._current_skill_idx % len(self._skill_sequence)]
            self._current_skill_idx += 1

        target_obj = detected[0] if detected else {"pose_3d": {"xyz": (0.5, 0.0, 0.6)}}
        default_dur = self.SKILL_LIBRARY[skill]["default_duration_s"]

        payload = {
            "skill": {
                "name": skill,
                "display_name": self.SKILL_LIBRARY[skill]["name"],
                "duration_s": default_dur,
                "description": self.SKILL_LIBRARY[skill]["description"],
            },
            "target_pose": target_obj["pose_3d"],
            "gripper_command": "close" if skill in ("grip", "insert") else "open",
            "status": "running" if skill != "idle" else "done",
        }
        return Message(msg_type="command", payload=payload)


# ============================================================
# 3. 执行层 接口
# ============================================================
class ExecutionModule(abc.ABC):
    """
    执行层抽象基类
    ------------------------------------------------
    职责：把动作指令安全下发到仿真/真机，确认执行结果
    """

    def __init__(self, name: str = "execution"):
        self.name = name
        self._last_result: Optional[Message] = None
        self._execution_log: List[Message] = []   # 最近N条执行记录（可用于审计）
        self._log_capacity: int = 200

    # ---- 日志管理 ----
    def _append_log(self, msg: Message) -> None:
        self._execution_log.append(msg)
        if len(self._execution_log) > self._log_capacity:
            self._execution_log = self._execution_log[-self._log_capacity:]

    def recent_logs(self, n: int = 10) -> List[Message]:
        return list(self._execution_log[-n:])

    # ---- 核心抽象方法 ----
    @abc.abstractmethod
    def execute(self, command_msg: Message) -> Message:
        """
        接收决策层的动作指令 → 下发给硬件/仿真 → 返回执行结果
        返回 Message.payload 建议包含：
          - success: bool
          - executed_skill: str
          - duration_actual_s: float
          - error_msg: str (if failed)
        """
        raise NotImplementedError

    def tick(self, command_msg: Message) -> Message:
        start_ts = time.time()
        result = self.execute(command_msg)
        result.source = self.name
        result.target = command_msg.source
        result.meta["execution_latency_ms"] = int((time.time() - start_ts) * 1000)
        result.meta["echo_command_id"] = command_msg.msg_id
        self._last_result = result
        self._append_log(result)
        return result


class MockExecution(ExecutionModule):
    """
    执行层参考实现：Mock版
    ------------------------------------------------
    无硬件情况下，以sleep模拟执行耗时，返回标准结果。
    作用：让整个三层架构在开发机上也能端到端闭环运行。
    """

    def __init__(self, name: str = "mock_execution"):
        super().__init__(name)
        self.failure_probability: float = 0.0   # 可设模拟故障概率（0.05=5%）

    def execute(self, command_msg: Message) -> Message:
        skill_info = command_msg.payload.get("skill", {})
        duration = skill_info.get("duration_s", 0.5)
        skill_name = skill_info.get("name", "unknown")

        # 模拟真实执行的耗时
        time.sleep(min(duration, 0.3))  # 为了演示，限制sleep上限，防止卡

        success = True
        error_msg = ""
        if self.failure_probability > 0:
            import random
            if random.random() < self.failure_probability:
                success = False
                error_msg = f"模拟执行故障: {skill_name} 执行中断（概率触发）"

        payload = {
            "success": success,
            "executed_skill": skill_name,
            "duration_actual_s": duration,
            "error_msg": error_msg,
            "target_pose_echo": command_msg.payload.get("target_pose"),
        }
        return Message(msg_type="event" if success else "error", payload=payload)


# ============================================================
# 三层编排器：把三层连起来跑（演示系统集成能力）
# ============================================================
class ThreeTierOrchestrator:
    """
    感知-决策-执行 三层编排器
    ------------------------------------------------
    作用：把三个模块按「感知→决策→执行」顺序串成闭环，
         同时支持日志回调、异常捕获、优雅停机。
    """

    def __init__(
        self,
        perception: PerceptionModule,
        decision: DecisionModule,
        execution: ExecutionModule,
    ):
        self.P = perception
        self.D = decision
        self.E = execution
        self._running = False
        self.on_tick_callback: Optional[Callable[[int, Message, Message, Message], None]] = None
        # 自动连接：感知发布→决策接收
        self.P.subscribe(lambda m: None)  # 预留，也可以在tick里显式串

    def run_cycle(self) -> Dict[str, Message]:
        """执行一次完整的感知→决策→执行闭环"""
        p_msg = self.P.tick()
        d_msg = self.D.tick(p_msg)
        e_msg = self.E.tick(d_msg)
        return {"perception": p_msg, "decision": d_msg, "execution": e_msg}

    def run_forever(self, max_cycles: int = 0,
                    period_s: float = 0.05,
                    break_on_error: bool = False) -> int:
        """持续运行直到Ctrl+C或达到max_cycles（0=无限）"""
        self._running = True
        cycle = 0
        try:
            while self._running:
                cycle += 1
                result = self.run_cycle()
                if self.on_tick_callback:
                    self.on_tick_callback(cycle, result["perception"],
                                          result["decision"], result["execution"])
                # 错误检查
                if break_on_error and result["execution"].payload.get("success") is False:
                    print(f"[Orchestrator] 执行失败，退出循环 cycle={cycle}")
                    break
                if max_cycles > 0 and cycle >= max_cycles:
                    break
                time.sleep(max(0.0, period_s))
        except KeyboardInterrupt:
            print("\n[Orchestrator] 用户终止")
        finally:
            self._running = False
        return cycle

    def stop(self) -> None:
        self._running = False
