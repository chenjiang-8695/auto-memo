"""开机自启：写入/删除 HKCU\\...\\CurrentVersion\\Run 注册表项。

指向当前虚拟环境的 pythonw.exe + main.py，避免开机弹出控制台窗口。
"""
import os
import sys
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "AutoMemo"


def _command():
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        candidate = exe[:-10] + "pythonw.exe"
        if os.path.exists(candidate):
            exe = candidate
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
    return f'"{exe}" "{script}"'


def is_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except OSError:
        return False


def enable():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                        winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _command())


def disable():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
    except OSError:
        pass


def apply(enabled):
    if enabled:
        enable()
    else:
        disable()
