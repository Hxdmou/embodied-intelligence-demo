#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
真机部署调用接口（便携版）v1.0
================================================================
U盘根目录【真机部署.bat】是唯一调用接口，本文件为接口实现；
真机底层驱动包（deploy_main / real_robot_adapter / deploy_adapters 等）
全部保留在 embodied-intelligence\ 内部，不暴露到U盘根目录。

流程（对齐交付规范）：
  1. 点击运行后先进行环境自检；
  2. 提示符由甲方自行输入真机 IP 或接口参数；
  3. 输入错误/缺省/不可达 => 优雅退出，仅提示
     “真机环境未就绪，请检查硬件连接”，不抛任何 traceback；
  4. 输入 SIM 可走仿真部署排练（不连真机，全流程演练并生成部署报告）。
"""

import os
import re
import sys
import time
import socket
import threading
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

NOT_READY = "真机环境未就绪，请检查硬件连接。"
SIM_REHEARSAL_SECONDS = 45.0
DEFAULT_PORT = 8080
PROBE_TIMEOUT = 2.5
FOUND_MODEL = None


def _setup_console():
    """控制台切UTF-8(65001)；调用方bat在退出后会重新锚定936。"""
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.SetConsoleOutputCP(65001)
        k32.SetConsoleCP(65001)
    except Exception:
        pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _ok(msg):
    print("  [通过] %s" % msg)


def _warn(msg):
    print("  [警告] %s" % msg)


def _fail(msg):
    print("  [失败] %s" % msg)


def banner():
    print("=" * 66)
    print("              真机部署系统（便携版） v1.0")
    print("     具身智能工程化部署 · Sim2Real · 六协议通信适配")
    print("     TCP / UDP / CAN / EtherCAT / ROS / Modbus")
    print("=" * 66)
    print()


def self_check():
    """第1步：环境自检。返回True=通过。"""
    global FOUND_MODEL
    print("[1/3] 环境自检")
    hard_ok = True

    ver = sys.version_info
    portable = "python" in os.path.basename(sys.executable).lower()
    _ok("Python 运行环境 %d.%d.%d（%s）" % (
        ver.major, ver.minor, ver.micro,
        "便携解释器" if portable else "外部解释器"))

    missing = [m for m in ("pybullet", "stable_baselines3", "numpy")
               if importlib.util.find_spec(m) is None]
    if missing:
        _fail("核心依赖缺失: %s" % ", ".join(missing))
        hard_ok = False
    else:
        _ok("核心依赖 pybullet / stable_baselines3 / numpy")

    if os.path.exists(os.path.join(HERE, "robot_config.py")):
        _ok("机器人配置 robot_config.py（关节限位/速度限位/软限位）")
    else:
        _fail("机器人配置 robot_config.py 缺失")
        hard_ok = False

    if os.path.exists(os.path.join(HERE, "deploy_main.py")):
        _ok("部署主流程 deploy_main.py（标定→部署循环→报告归档）")
    else:
        _fail("部署主流程 deploy_main.py 缺失")
        hard_ok = False

    model = None
    for name in ("ppo_robot_reach_final_5m_enhanced.zip",
                 "ppo_robot_reach_curriculum.zip",
                 "ppo_kuka_reach_finetuned_best.zip"):
        if os.path.exists(os.path.join(HERE, name)):
            model = name
            break
    if model:
        FOUND_MODEL = model
        _ok("策略模型归档 %s（真机模式启用模型推理）" % model)
    else:
        _warn("未找到策略模型，部署时将自动降级为轨迹模式")

    try:
        from deploy_tools import SafetyParameterValidator
        safety_ok, issues = SafetyParameterValidator().validate_all()
        if safety_ok:
            _ok("安全参数完整性校验（急停/限位/熔断 5 层防护）")
        else:
            _fail("安全参数校验发现 %d 个问题" % len(issues))
            hard_ok = False
    except Exception as e:
        _warn("安全参数校验跳过: %s" % e.__class__.__name__)

    print()
    return hard_ok


def _parse_ip(raw):
    m = re.match(r"^(\d{1,3}(?:\.\d{1,3}){3})(?::(\d{1,5}))?$", raw)
    if not m:
        return None
    host, port = m.group(1), m.group(2)
    for part in host.split("."):
        if int(part) > 255:
            return None
    if port is not None and int(port) > 65535:
        return None
    return host, (int(port) if port else DEFAULT_PORT)


def _probe_tcp(host, port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(PROBE_TIMEOUT)
        rc = s.connect_ex((host, port))
        s.close()
        return rc == 0
    except Exception:
        return False


def _com_exists(name):
    try:
        import ctypes
        from ctypes import wintypes
        handle = ctypes.windll.kernel32.CreateFileW(
            "\\\\.\\" + name, 0x80000000 | 0x40000000, 0, None, 3, 0, None)
        invalid = wintypes.HANDLE(-1).value
        ok = handle not in (invalid, -1, 0)
        if ok:
            ctypes.windll.kernel32.CloseHandle(handle)
        return ok
    except Exception:
        return False


def prompt_target():
    """第2步：提示甲方输入真机IP或接口参数。

    返回: ("real_ip", host, port) / ("real_com", com) / ("sim",) / ("quit",)
    输入错误/缺省时直接打印优雅退出提示并返回 ("notready", 原因)
    """
    print("[2/3] 真机连接参数")
    print("  请甲方输入真机的 IP 或接口参数：")
    print("    - IP 方式    : 如 192.168.1.100 或 192.168.1.100:8080（默认端口%d）" % DEFAULT_PORT)
    print("    - 串口方式   : 如 COM3")
    print("    - 仿真排练   : 输入 SIM（不连真机，全流程演练部署管线）")
    print("    - 退出       : 输入 Q 或直接回车")
    try:
        raw = input("  > ").strip()
    except EOFError:
        raw = ""
    print()

    if raw == "":
        print("  输入缺省。")
        return ("notready",)
    up = raw.upper()
    if up in ("Q", "QUIT", "EXIT", "退出"):
        return ("quit",)
    if up in ("SIM", "S", "仿真"):
        return ("sim",)

    parsed = _parse_ip(raw)
    if parsed:
        host, port = parsed
        sys.stdout.write("  连接测试 %s:%d ..." % (host, port))
        sys.stdout.flush()
        if _probe_tcp(host, port):
            print(" 可达")
            return ("real_ip", host, port)
        print(" 无响应（超时%.1fs）" % PROBE_TIMEOUT)
        return ("notready",)

    m = re.match(r"^COM\d{1,3}$", up)
    if m:
        if _com_exists(up):
            _ok("串口 %s 存在且空闲" % up)
            return ("real_com", up)
        print("  串口 %s 不存在或已被占用。" % up)
        return ("notready",)

    print("  输入格式无法识别: %s" % raw)
    print("  （支持: IP 如 192.168.1.100:8080 / 串口 如 COM3 / SIM / Q）")
    return ("notready",)


def run_pipeline(mode, host=None, port=None, com=None):
    """第3步：执行部署管线（真机或仿真排练）。"""
    if mode == "sim":
        print("[3/3] 执行仿真部署排练（执行: 轨迹插值，不连真机，约%d秒后自动收口并生成部署报告）"
              % int(SIM_REHEARSAL_SECONDS))
        execution = "trajectory"
    else:
        target = ("%s:%s" % (host, port)) if host else com
        print("[3/3] 执行真机部署管线（目标: %s，执行: PPO模型推理+连续失败自动降级）" % target)
        execution = "model"
    print("  安全策略: 默认低速(速度系数0.2) / 关节双重限位裁剪 / 急停最高优先级")
    print("  真机模式可随时按 Ctrl+C 安全退出并生成部署报告。")
    print()

    import robot_config
    robot_config.ROBOT_MODE = mode
    if host:
        robot_config.REAL_ROBOT_CONFIG["host"] = host
        robot_config.REAL_ROBOT_CONFIG["port"] = port
    if com:
        robot_config.REAL_ROBOT_CONFIG["protocol"] = "custom"
        robot_config.REAL_ROBOT_CONFIG["host"] = com
    os.environ["DEPLOY_MODE"] = mode

    import deploy_main
    if FOUND_MODEL:
        deploy_main.MODEL_PATH = os.path.join(HERE, FOUND_MODEL)
    timer = None
    if mode == "sim":
        timer = threading.Timer(SIM_REHEARSAL_SECONDS,
                                lambda: setattr(deploy_main, "running", False))
        timer.daemon = True
        timer.start()
    try:
        config = deploy_main.init_environment(execution_mode=execution)
        if config is None:
            raise RuntimeError("部署环境初始化失败")
        deploy_main.run_calibration(config)
        deploy_main.deploy_loop(config)
    finally:
        if timer is not None:
            timer.cancel()
        try:
            deploy_main.cleanup()
        except Exception:
            pass
    print()
    print("  部署报告与归档数据: embodied-intelligence\\deploy_reports\\ 、deploy_archives\\")


def main():
    _setup_console()
    banner()

    if not self_check():
        print()
        print(NOT_READY)
        return 0

    target = prompt_target()
    if target[0] == "notready":
        print()
        print(NOT_READY)
        return 0
    if target[0] == "quit":
        print("  已退出，未执行真机部署流程。")
        return 0
    if target[0] == "sim":
        run_pipeline("sim")
        return 0
    if target[0] == "real_ip":
        run_pipeline("real", host=target[1], port=target[2])
        return 0
    run_pipeline("real", com=target[1])
    return 0


if __name__ == "__main__":
    _exit_code = 0
    try:
        _exit_code = main()
    except KeyboardInterrupt:
        print()
        print("  已退出。")
    except Exception:
        try:
            import traceback
            log_dir = os.path.join(HERE, "deploy_reports")
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, "_real_deploy_error.log"), "a",
                      encoding="utf-8") as fh:
                fh.write(time.strftime("%Y-%m-%d %H:%M:%S\n"))
                traceback.print_exc(file=fh)
        except Exception:
            pass
        print()
        print(NOT_READY)
    sys.exit(_exit_code)
