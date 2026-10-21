"""
场景配置（通用示例版）
================================================
仅保留三大通用行业场景框架：
  1. 工业制造（组装/搬运/检测通用接口）
  2. 物流仓储（拣选/存取/配送通用接口）
  3. 医疗健康（辅助/护理/康复通用接口）

说明：本文件为公共展示版本，仅保留通用场景框架定义，
      不包含任何企业私有商业场景参数。
"""

from typing import Dict, Any, List

# ============================================================
# 通用场景定义（框架示例版）
# ============================================================
SCENES: Dict[str, Dict[str, Any]] = {
    # ========== 1. 工业制造（通用框架） ==========
    "industrial": {
        "name": "工业制造",
        "description": "制造业通用自动化场景框架",
        "category_hint": "适用于汽车/3C/家电等离散制造业",
        "sub_scenes": {
            "assembly": {
                "name": "组装装配",
                "description": "零部件插拔、螺丝拧紧、卡扣装配等通用任务",
                "typical_robots": ["协作臂", "SCARA"],
                "difficulty": 5,          # 1-5通用难度参考
                "reward_scale": 1.0,      # 框架层奖励系数参考
                "task_template": {
                    "workpiece_types": ["peg_in_hole", "screw_driving", "clip_fitting"],
                    "tolerance_mm": [0.05, 0.10, 0.20],
                    "force_control_required": True,
                },
            },
            "handling": {
                "name": "搬运码垛",
                "description": "物料搬运、箱子堆叠、托盘码垛等通用任务",
                "typical_robots": ["协作臂", "码垛臂", "AGV/AMR"],
                "difficulty": 2,
                "reward_scale": 1.1,
                "task_template": {
                    "payload_range_kg": [1.0, 10.0, 50.0],
                    "cycle_time_s_target": [3.0, 5.0, 10.0],
                    "path_smoothing": True,
                },
            },
            "inspection": {
                "name": "质量检测",
                "description": "视觉尺寸测量、表面缺陷检测、功能测试等",
                "typical_robots": ["协作臂+2D/3D相机"],
                "difficulty": 4,
                "reward_scale": 1.0,
                "task_template": {
                    "sensors": ["2D_vision", "3D_structured_light", "laser_displacement"],
                    "accuracy_requirement": ["high", "medium", "low"],
                    "defect_types": ["scratch", "dent", "missing_part", "dimension_error"],
                },
            },
        },
    },

    # ========== 2. 物流仓储（通用框架） ==========
    "logistics": {
        "name": "物流仓储",
        "description": "仓储自动化与物流运输通用场景框架",
        "category_hint": "适用于电商/快递/零售等物流节点场景",
        "sub_scenes": {
            "picking": {
                "name": "拣选分拣",
                "description": "料箱拣选、单品分拣、订单播种等通用任务",
                "typical_robots": ["AMR/AGV", "Delta并联臂", "协作臂"],
                "difficulty": 4,
                "reward_scale": 1.0,
                "task_template": {
                    "item_types": ["box", "cylinder", "deformable_bag", "irregular"],
                    "pick_place_points_per_minute": [30, 60, 120],
                    "vision_required": True,
                },
            },
            "storage": {
                "name": "存储管理",
                "description": "货架存取、立体仓库、料箱上下架等",
                "typical_robots": ["堆垛机", "AMR货架到人", "提升机"],
                "difficulty": 3,
                "reward_scale": 1.2,
                "task_template": {
                    "storage_height_levels": [1, 5, 10],
                    "sku_count_range": [100, 1000, 10000],
                    "location_accuracy_cm": [1.0, 5.0, 10.0],
                },
            },
        },
    },

    # ========== 3. 医疗健康（通用框架） ==========
    "medical": {
        "name": "医疗健康",
        "description": "医疗辅助与健康服务通用场景框架",
        "category_hint": "适用于医院/康复中心/养老机构等场景",
        "sub_scenes": {
            "surgical_assist": {
                "name": "手术辅助",
                "description": "器械递送、视野调整、患者摆位等辅助任务",
                "typical_robots": ["协作臂+末端无菌适配器"],
                "difficulty": 5,
                "reward_scale": 1.5,
                "task_template": {
                    "safety_level": ["PL=d", "PL=e"],
                    "sterile_required": True,
                    "sub_mm_accuracy": True,
                },
            },
            "rehabilitation": {
                "name": "康复训练",
                "description": "上肢/下肢康复、步态训练、肌力训练等",
                "typical_robots": ["外骨骼", "末端牵引式康复臂"],
                "difficulty": 4,
                "reward_scale": 1.2,
                "task_template": {
                    "patient_groups": ["post_stroke", "spinal_cord_injury", "elder_frail"],
                    "force_assist_levels": ["passive", "semi_active", "active"],
                    "compliance_control_required": True,
                },
            },
        },
    },
}


# ============================================================
# 查询辅助函数（框架层）
# ============================================================
def list_all_scenes() -> List[str]:
    """列出所有一级场景名称"""
    return sorted(SCENES.keys())


def list_sub_scenes(scene_key: str) -> List[str]:
    """列出指定一级场景下的所有子场景"""
    if scene_key not in SCENES:
        raise ValueError(f"未知场景: {scene_key}. 可用: {list_all_scenes()}")
    return sorted(SCENES[scene_key]["sub_scenes"].keys())


def get_sub_scene_config(scene_key: str, sub_key: str) -> Dict[str, Any]:
    """获取子场景详细配置"""
    subs = SCENES[scene_key]["sub_scenes"]
    if sub_key not in subs:
        raise ValueError(
            f"场景[{scene_key}]下未找到子场景: {sub_key}. "
            f"可用: {list_sub_scenes(scene_key)}"
        )
    return subs[sub_key]


def get_scene_summary(scene_key: str) -> Dict[str, Any]:
    """获取场景摘要信息"""
    if scene_key not in SCENES:
        raise ValueError(f"未知场景: {scene_key}")
    s = SCENES[scene_key]
    return {
        "name": s["name"],
        "description": s["description"],
        "sub_scene_count": len(s["sub_scenes"]),
        "sub_scene_names": list(s["sub_scenes"].keys()),
    }
