#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
网络与产业适配层 - V1.0
================================================================
新增内容：
  1. NetworkGeneration（网络制式枚举）
  2. NetworkStatus（网络状态枚举）
  3. NetworkProfile（网络配置数据类）
  4. NetworkHealth（网络健康数据类）
  5. NETWORK_PROFILES（网络制式档案表）
  6. NetworkAdapter（网络适配器类）
  7. IndustrialRobotBrand（工业机器人品牌枚举）
  8. IndustrialRobotProfile（机器人品牌数据类）
  9. INDUSTRIAL_ROBOT_PROFILES（品牌档案表）
  10. IndustrialRobotAdapter（工业机器人适配器类）
  15. NetworkIndustryAdapter（统一适配层类）

网络制式名称列表：
  ETHERNET / WIFI_6 / WIFI_7 / FIVEG / FIVEG_A / SIXG / LOCAL_ONLY

工业机器人品牌名称列表：
  ESTUN / INOVANCE / HIKROBOT / SIASUN / AUBO / DOOSAN /
  FANUC / ABB / KUKA / YASKAWA / UNIVERSAL / GUOAO / XUNJI

北京产业类别名称列表：
  SENSOR / MEMS_FOUNDRY / BRAIN_COMPUTER / AI_COMPUTING /
  SMART_COMMUNITY / INDUSTRIAL_AI / ROBOTICS
"""

import time
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


# ============================================================================
# 第一部分：6G/5G-A 网络适配
# ============================================================================

class NetworkGeneration(Enum):
    ETHERNET = "ethernet"
    WIFI_6 = "wifi_6"
    WIFI_7 = "wifi_7"
    FIVEG = "5g"
    FIVEG_A = "5g_a"
    SIXG = "6g"
    LOCAL_ONLY = "local_only"


class NetworkStatus(Enum):
    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"
    SWITCHING = "switching"


@dataclass
class NetworkProfile:
    generation: NetworkGeneration
    name: str
    typical_latency_ms: float
    min_latency_ms: float
    typical_bandwidth_mbps: float
    reliability_pct: float
    supports_urllc: bool = False
    supports_massive_iot: bool = False
    supports_sensing: bool = False
    supports_ai_native: bool = False
    available: bool = True
    notes: str = ""


@dataclass
class NetworkHealth:
    status: NetworkStatus = NetworkStatus.DISCONNECTED
    current_latency_ms: float = 999.0
    current_bandwidth_mbps: float = 0.0
    packet_loss_pct: float = 100.0
    jitter_ms: float = 999.0
    connected_since: float = 0.0
    active_profile: str = ""


NETWORK_PROFILES: Dict[str, NetworkProfile] = {
    "ethernet": NetworkProfile(
        generation=NetworkGeneration.ETHERNET, name="ethernet",
        typical_latency_ms=1.0, min_latency_ms=0.1,
        typical_bandwidth_mbps=1000.0, reliability_pct=99.999,
        supports_urllc=True, available=True,
    ),
    "wifi_6": NetworkProfile(
        generation=NetworkGeneration.WIFI_6, name="wifi_6",
        typical_latency_ms=10.0, min_latency_ms=2.0,
        typical_bandwidth_mbps=300.0, reliability_pct=99.5,
        available=True,
    ),
    "wifi_7": NetworkProfile(
        generation=NetworkGeneration.WIFI_7, name="wifi_7",
        typical_latency_ms=5.0, min_latency_ms=1.0,
        typical_bandwidth_mbps=1000.0, reliability_pct=99.7,
        supports_urllc=True, available=True,
    ),
    "5g": NetworkProfile(
        generation=NetworkGeneration.FIVEG, name="5g",
        typical_latency_ms=20.0, min_latency_ms=5.0,
        typical_bandwidth_mbps=500.0, reliability_pct=99.9,
        supports_urllc=True, supports_massive_iot=True, available=True,
    ),
    "5g_a": NetworkProfile(
        generation=NetworkGeneration.FIVEG_A, name="5g_a",
        typical_latency_ms=10.0, min_latency_ms=1.0,
        typical_bandwidth_mbps=1000.0, reliability_pct=99.99,
        supports_urllc=True, supports_massive_iot=True,
        supports_sensing=True, supports_ai_native=True, available=True,
    ),
    "6g": NetworkProfile(
        generation=NetworkGeneration.SIXG, name="6g",
        typical_latency_ms=1.0, min_latency_ms=0.001,
        typical_bandwidth_mbps=10000.0, reliability_pct=99.999,
        supports_urllc=True, supports_massive_iot=True,
        supports_sensing=True, supports_ai_native=True,
        available=False,
    ),
    "local_only": NetworkProfile(
        generation=NetworkGeneration.LOCAL_ONLY, name="local_only",
        typical_latency_ms=0.0, min_latency_ms=0.0,
        typical_bandwidth_mbps=0.0, reliability_pct=100.0,
        available=True,
    ),
}


class NetworkAdapter:
    FALLBACK_ORDER = ["ethernet", "wifi_7", "wifi_6", "5g_a", "5g", "local_only"]

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.preferred = self.config.get("preferred_network", "ethernet")
        self.health = NetworkHealth()
        self._active = "local_only"
        self._on_switch_callbacks = []

    def initialize(self) -> bool:
        try:
            self._active = self._select_best_available()
            self.health.status = NetworkStatus.CONNECTED
            self.health.active_profile = self._active
            self.health.connected_since = time.time()
            profile = NETWORK_PROFILES.get(self._active)
            if profile:
                self.health.current_latency_ms = profile.typical_latency_ms
                self.health.current_bandwidth_mbps = profile.typical_bandwidth_mbps
                self.health.packet_loss_pct = 0.0
            return True
        except Exception:
            self._active = "local_only"
            self.health.status = NetworkStatus.DISCONNECTED
            return True

    def _select_best_available(self) -> str:
        preferred = self.preferred
        if preferred in NETWORK_PROFILES and NETWORK_PROFILES[preferred].available:
            return preferred
        for net in self.FALLBACK_ORDER:
            if net in NETWORK_PROFILES and NETWORK_PROFILES[net].available:
                return net
        return "local_only"

    def check_health(self) -> NetworkHealth:
        try:
            profile = NETWORK_PROFILES.get(self._active)
            if profile is None:
                self.health.status = NetworkStatus.DISCONNECTED
                return self.health
            if self._active == "local_only":
                self.health.status = NetworkStatus.CONNECTED
                self.health.current_latency_ms = 0.0
            return self.health
        except Exception:
            self.health.status = NetworkStatus.DEGRADED
            return self.health

    def on_network_degraded(self) -> str:
        try:
            current_idx = (
                self.FALLBACK_ORDER.index(self._active)
                if self._active in self.FALLBACK_ORDER else 0
            )
            for net in self.FALLBACK_ORDER[current_idx + 1:]:
                profile = NETWORK_PROFILES.get(net)
                if profile and profile.available:
                    old = self._active
                    self._active = net
                    self.health.status = NetworkStatus.SWITCHING
                    self.health.active_profile = net
                    for cb in self._on_switch_callbacks:
                        try:
                            cb(old, net)
                        except Exception:
                            pass
                    self.health.status = NetworkStatus.CONNECTED
                    return net
            self._active = "local_only"
            return "local_only"
        except Exception:
            self._active = "local_only"
            return "local_only"

    def get_active_profile(self) -> NetworkProfile:
        return NETWORK_PROFILES.get(self._active, NETWORK_PROFILES["local_only"])

    def is_cloud_control_viable(self) -> bool:
        try:
            profile = self.get_active_profile()
            return (profile.typical_latency_ms < 50.0
                    and profile.reliability_pct >= 99.9
                    and self.health.status == NetworkStatus.CONNECTED)
        except Exception:
            return False

    def get_latency_budget_ms(self) -> float:
        try:
            return self.health.current_latency_ms * 1.5
        except Exception:
            return 100.0

    def register_switch_callback(self, callback) -> None:
        self._on_switch_callbacks.append(callback)

    def get_status(self) -> Dict[str, Any]:
        return {
            "active_network": self._active,
            "health": self.health.status.value,
            "latency_ms": self.health.current_latency_ms,
            "bandwidth_mbps": self.health.current_bandwidth_mbps,
            "cloud_viable": self.is_cloud_control_viable(),
        }


# ============================================================================
# 第二部分：工业机器人产业适配
# ============================================================================

class IndustrialRobotBrand(Enum):
    ESTUN = "estun"
    INOVANCE = "inovance"
    HIKROBOT = "hikrobot"
    SIASUN = "siasun"
    AUBO = "aubo"
    DOOSAN = "doosan"
    FANUC = "fanuc"
    ABB = "abb"
    KUKA = "kuka"
    YASKAWA = "yaskawa"
    UNIVERSAL = "universal"
    GUOAO = "guoao"
    XUNJI = "xunji"


@dataclass
class IndustrialRobotProfile:
    brand: IndustrialRobotBrand
    display_name: str
    country: str
    robot_types: List[str]
    controller_protocol: str
    payload_range_kg: Tuple[float, float]
    reach_range_mm: Tuple[float, float]
    repeatability_mm: float
    supports_ai_vision: bool = False
    supports_force_control: bool = False
    supports_collaborative: bool = False
    supports_mobile: bool = False
    sdk_available: bool = False
    local_support_china: bool = False
    notes: str = ""


INDUSTRIAL_ROBOT_PROFILES: Dict[str, IndustrialRobotProfile] = {
    "estun": IndustrialRobotProfile(
        brand=IndustrialRobotBrand.ESTUN, display_name="estun",
        country="CN", robot_types=["six_axis", "scara", "collaborative"],
        controller_protocol="native/modbus_tcp",
        payload_range_kg=(3, 700), reach_range_mm=(500, 3000),
        repeatability_mm=0.02, supports_ai_vision=True,
        supports_force_control=True, supports_collaborative=True,
        sdk_available=True, local_support_china=True,
    ),
    "fanuc": IndustrialRobotProfile(
        brand=IndustrialRobotBrand.FANUC, display_name="fanuc",
        country="JP", robot_types=["six_axis", "scara", "collaborative"],
        controller_protocol="native/tcp",
        payload_range_kg=(0.5, 2300), reach_range_mm=(300, 4000),
        repeatability_mm=0.01, supports_ai_vision=True,
        supports_force_control=True, supports_collaborative=True,
        sdk_available=True, local_support_china=True,
    ),
    "abb": IndustrialRobotProfile(
        brand=IndustrialRobotBrand.ABB, display_name="abb",
        country="CH", robot_types=["six_axis", "collaborative", "dual_arm"],
        controller_protocol="native/tcp",
        payload_range_kg=(0.5, 800), reach_range_mm=(300, 3500),
        repeatability_mm=0.01, supports_ai_vision=True,
        supports_force_control=True, supports_collaborative=True,
        sdk_available=True, local_support_china=True,
    ),
    "kuka": IndustrialRobotProfile(
        brand=IndustrialRobotBrand.KUKA, display_name="kuka",
        country="DE", robot_types=["six_axis", "collaborative", "mobile"],
        controller_protocol="native/tcp",
        payload_range_kg=(3, 1300), reach_range_mm=(500, 3500),
        repeatability_mm=0.02, supports_ai_vision=True,
        supports_force_control=True, supports_collaborative=True,
        supports_mobile=True, sdk_available=True, local_support_china=True,
    ),
    "universal": IndustrialRobotProfile(
        brand=IndustrialRobotBrand.UNIVERSAL, display_name="universal",
        country="DK", robot_types=["collaborative"],
        controller_protocol="rtde/tcp",
        payload_range_kg=(3, 30), reach_range_mm=(500, 1800),
        repeatability_mm=0.03, supports_force_control=True,
        supports_collaborative=True, sdk_available=True,
        local_support_china=True,
    ),
}


class IndustrialRobotAdapter:
    def __init__(self):
        self._profiles = INDUSTRIAL_ROBOT_PROFILES

    def get_supported_brands(self, china_only: bool = False) -> List[IndustrialRobotProfile]:
        try:
            results = list(self._profiles.values())
            if china_only:
                results = [r for r in results if r.country == "CN"]
            return results
        except Exception:
            return []

    def get_brand(self, brand_id: str) -> Optional[IndustrialRobotProfile]:
        return self._profiles.get(brand_id)

    def get_protocol(self, brand_id: str) -> str:
        try:
            profile = self._profiles.get(brand_id)
            return profile.controller_protocol if profile else "unknown"
        except Exception:
            return "unknown"

    def find_compatible(self, payload_kg: float, reach_mm: float,
                        collaborative: bool = False,
                        china_preferred: bool = False) -> List[IndustrialRobotProfile]:
        try:
            results = []
            for p in self._profiles.values():
                if not (p.payload_range_kg[0] <= payload_kg <= p.payload_range_kg[1]):
                    continue
                if p.reach_range_mm[1] > 0 and not (
                    p.reach_range_mm[0] <= reach_mm <= p.reach_range_mm[1]
                ):
                    continue
                if collaborative and not p.supports_collaborative:
                    continue
                results.append(p)
            if china_preferred:
                results.sort(key=lambda x: (x.country != "CN", x.repeatability_mm))
            return results
        except Exception:
            return []

    def get_supply_chain_summary(self) -> Dict[str, Any]:
        try:
            china = [p for p in self._profiles.values() if p.country == "CN"]
            foreign = [p for p in self._profiles.values() if p.country != "CN"]
            return {
                "total_brands": len(self._profiles),
                "china_brands": len(china),
                "foreign_brands": len(foreign),
                "all_sdk_available": all(
                    p.sdk_available for p in self._profiles.values()
                ),
            }
        except Exception:
            return {"total_brands": 0}


# ============================================================================
# 统一适配层
# ============================================================================

class NetworkIndustryAdapter:
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.network = NetworkAdapter(self.config.get("network", {}))
        self.industrial = IndustrialRobotAdapter()

    def initialize(self) -> bool:
        try:
            self.network.initialize()
            return True
        except Exception:
            return False

    def get_full_status(self) -> Dict[str, Any]:
        try:
            return {
                "network": self.network.get_status(),
                "industrial_supply_chain": self.industrial.get_supply_chain_summary(),
            }
        except Exception:
            return {"error": "status_failed"}

    def get_deployment_recommendations(self) -> Dict[str, Any]:
        try:
            cloud = self.network.is_cloud_control_viable()
            return {
                "control_mode": "cloud_edge_hybrid" if cloud else "edge_autonomous",
                "network_primary": self.network._active,
                "network_fallback": "local_only",
                "robot_brand_strategy": "multi_brand_supported",
                "sensor_supply": "local_sensor_valley",
                "compute_strategy": "cloud_plus_local" if cloud else "local_only",
            }
        except Exception:
            return {"control_mode": "edge_autonomous"}
