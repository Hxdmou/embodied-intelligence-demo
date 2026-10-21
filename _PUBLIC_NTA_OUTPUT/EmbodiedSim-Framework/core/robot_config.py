"""
机器人配置（通用示例版）
================================================
仅保留行业通用的代表性型号：
  - Franka Emika Panda 协作臂（学术与工业通用）
  - KUKA LBR iiwa 协作臂（工业级高精度代表）

说明：本文件为公共展示版本，仅保留通用示例配置，
      不包含任何企业私有参数与品牌全量数据库。
"""

from typing import Dict, Any, List

# ============================================================
# 机器人类型定义
# ============================================================
ROBOT_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "collaborative_arm": {
        "name": "协作机械臂",
        "description": "6/7轴人机协作机械臂，通用工业与科研场景",
        "default_dofs": 7,
        "default_payload_kg": 5.0,
        "default_reach_m": 0.85,
    },
    "industrial_arm": {
        "name": "工业机械臂",
        "description": "传统6轴工业机器人，焊接/搬运/喷涂通用",
        "default_dofs": 6,
        "default_payload_kg": 20.0,
        "default_reach_m": 1.5,
    },
    "humanoid": {
        "name": "人形机器人",
        "description": "双足人形机器人通用定义（抽象接口）",
        "default_dofs": 32,
        "default_height_m": 1.70,
    },
}


# ============================================================
# 通用示例机器人（公共展示版）
# ============================================================
ROBOT_BRANDS: Dict[str, Dict[str, Any]] = {
    # ========== 示例 1: Franka Emika Panda（学术通用标杆） ==========
    "panda": {
        "name": "Franka Emika Panda",
        "category": "collaborative_arm",
        "origin": "德国（通用学术研究型号）",
        "dofs": 7,
        "payload_kg": 3.0,
        "reach_m": 0.855,
        "repeatability_mm": 0.1,
        "features": [
            "7自由度冗余设计",
            "关节力矩传感（可做力控）",
            "碰撞检测与人机协作安全",
            "学术与科研通用参考型号",
        ],
        "scenes": ["industrial_assembly", "research_education", "manipulation"],
        "status": "reference_implementation",
        "controller": "Franka Control Interface (FCI)",
        "battery_hours": None,  # 工业供电型无电池
        "protocol": ["TCP/IP (FCI)", "ROS", "EtherCAT"],
        "simulation": ["PyBullet", "MuJoCo", "Isaac Sim"],
        "urdf_model": "panda/panda.urdf",  # 仿真URDF模型路径（通用示例）
        "default_joint_limits": {
            "lower": [-2.8973, -1.7628, -2.8973, -3.0718, -2.8973, -0.0175, -2.8973],
            "upper": [ 2.8973,  1.7628,  2.8973, -0.0698,  2.8973,  3.7525,  2.8973],
            "max_velocity": [2.1750, 2.1750, 2.1750, 2.1750, 2.6100, 2.6100, 2.6100],
            "max_torque":  [87, 87, 87, 87, 12, 12, 12],
        },
    },

    # ========== 示例 2: KUKA LBR iiwa（工业级高精度代表） ==========
    "kuka_iiwa": {
        "name": "KUKA LBR iiwa 7 R800",
        "category": "collaborative_arm",
        "origin": "德国（工业级量产型号）",
        "dofs": 7,
        "payload_kg": 7.0,
        "reach_m": 0.800,
        "repeatability_mm": 0.15,
        "features": [
            "7轴敏感型协作臂",
            "关节级扭矩传感，力控装配应用广泛",
            "Sunrise.OS 工业级控制软件栈",
            "汽车制造与3C电子通用型号",
        ],
        "scenes": ["industrial_assembly", "automotive", "electronics_manufacturing"],
        "status": "industrial_reference",
        "controller": "KUKA Sunrise.OS + FRI",
        "battery_hours": None,
        "protocol": ["FRI (Fast Robot Interface)", "EtherCAT", "PROFINET", "ROS"],
        "simulation": ["PyBullet", "KUKA.Sim", "ISG-virtuos"],
        "urdf_model": "kuka_iiwa/lbr_iiwa_7_r800.urdf",
        "default_joint_limits": {
            "lower": [-2.9671, -2.0944, -2.9671, -2.0944, -2.9671, -2.0944, -3.0543],
            "upper": [ 2.9671,  2.0944,  2.9671,  2.0944,  2.9671,  2.0944,  3.0543],
            "max_velocity": [1.7104, 1.7104, 1.7453, 2.2689, 2.4435, 3.1416, 3.1416],
            "max_torque":  [320, 320, 320, 176, 176, 110, 40],
        },
    },
}


# ============================================================
# 查询辅助函数（框架层）
# ============================================================
def get_robot_config(robot_type: str) -> Dict[str, Any]:
    """获取指定机器人的配置（公共示例版）"""
    if robot_type not in ROBOT_BRANDS:
        raise ValueError(
            f"未知机器人类型: {robot_type}. "
            f"可用示例: {list(ROBOT_BRANDS.keys())}"
        )
    return ROBOT_BRANDS[robot_type]


def list_available_robots() -> List[str]:
    """列出所有可用的机器人类型"""
    return sorted(ROBOT_BRANDS.keys())


def get_category_info(category_key: str) -> Dict[str, Any]:
    """获取机器人类别信息"""
    if category_key not in ROBOT_CATEGORIES:
        raise ValueError(
            f"未知类别: {category_key}. 可用: {list(ROBOT_CATEGORIES.keys())}"
        )
    return ROBOT_CATEGORIES[category_key]
