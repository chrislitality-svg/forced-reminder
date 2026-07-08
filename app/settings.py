"""配置管理：config.json（应用级配置）+ 开机自启动（启动文件夹方式）。

开机自启动采用「启动文件夹放快捷方式」而非注册表：
- 无需管理员权限；
- 用户在「启动」文件夹里能直接看到、可控；
- 杀软误报率低。
"""

import json
import os
import sys

APPDATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                           "ForcedReminder")
CONFIG_PATH = os.path.join(APPDATA_DIR, "config.json")

DEFAULT_CONFIG = {
    "db_path": os.path.join(APPDATA_DIR, "data", "reminder.db"),
    "log_level": "info",
    "theme": "light",
    "default_interval": 30,
    "snooze_minutes": 1,  # “稍后提醒”重弹间隔
}


def load_config() -> dict:
    """加载配置，缺失字段用默认值补全。"""
    os.makedirs(APPDATA_DIR, exist_ok=True)
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            # 配置损坏时回退到默认，不让程序起不来
            pass
    return cfg


def save_config(cfg: dict):
    os.makedirs(APPDATA_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ---------- 开机自启动 ----------

def _startup_dir() -> str:
    return os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
    )


def _shortcut_path() -> str:
    return os.path.join(_startup_dir(), "强提醒助手.lnk")


def _target_command():
    """返回启动目标 (target, args)。

    - 打包后的 exe：直接指向 exe；
    - 源码运行：指向 python 解释器 + main.py。
    """
    if getattr(sys, "frozen", False):
        return sys.executable, ""
    main_py = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py"
    )
    return sys.executable, f'"{main_py}"'


def is_autostart_enabled() -> bool:
    return os.path.exists(_shortcut_path())


def set_autostart(enabled: bool) -> bool:
    """开启/关闭开机自启动。成功返回 True。"""
    try:
        if enabled:
            _create_shortcut()
        else:
            lnk = _shortcut_path()
            if os.path.exists(lnk):
                os.remove(lnk)
        return True
    except Exception:
        return False


def _create_shortcut():
    """调用 PowerShell + WScript.Shell 创建 .lnk 快捷方式（无第三方依赖）。"""
    import subprocess

    os.makedirs(_startup_dir(), exist_ok=True)
    target, args = _target_command()
    workdir = os.path.dirname(
        target if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.abspath(__file__))
    )
    lnk = _shortcut_path()
    ps = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
        "$s.TargetPath='{target}';"
        "$s.Arguments='{args}';"
        "$s.WorkingDirectory='{workdir}';"
        "$s.Description='强提醒助手';"
        "$s.Save()"
    ).format(
        lnk=lnk.replace("'", "''"),
        target=target.replace("'", "''"),
        args=args.replace("'", "''"),
        workdir=workdir.replace("'", "''"),
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
