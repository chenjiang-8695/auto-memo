"""配置管理：读写 data/config.json，合并未知/缺失字段，提供默认值。"""
import copy
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")

DEFAULT_CONFIG = {
    "hotkeys": {
        "new_memo": "ctrl+alt+n",       # 新建备忘录
        "voice_input": "ctrl+alt+v",    # 按住说话，松开识别
        "ocr_snip": "ctrl+alt+o",       # 截图 OCR
        "toggle_float": "ctrl+alt+h",   # 显示/隐藏悬浮窗
    },
    "whisper_model": "base",            # tiny(39MB) / base(150MB) / small(460MB)
    "autostart": True,                  # 开机自启
    "reminder": {
        "popup": True,                  # 置顶弹窗 + 提示音
        "system_notify": True,          # Windows 系统通知
        "float_flash": True,            # 悬浮窗闪烁
        "snooze_minutes": 5,            # “稍后提醒”默认分钟数
    },
    "floating_bar": {
        "visible": True,
        "x": -1,                        # -1 表示使用默认位置（屏幕右上角）
        "y": -1,
    },
}


class Config:
    """简单的 JSON 配置封装：get/set 后即落盘。"""

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self._cfg = copy.deepcopy(DEFAULT_CONFIG)
        self._load()

    def _load(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            self._merge(self._cfg, saved)
        except (OSError, json.JSONDecodeError):
            pass  # 配置文件损坏时使用默认值

    @staticmethod
    def _merge(base, override):
        """把用户已保存的字段合并进默认配置（保留新增字段的默认值）。"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                Config._merge(base[key], value)
            else:
                base[key] = value

    def save(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self._cfg, f, ensure_ascii=False, indent=2)

    def get(self, *keys, default=None):
        node = self._cfg
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def set(self, *keys, value):
        node = self._cfg
        for key in keys[:-1]:
            node = node.setdefault(key, {})
        node[keys[-1]] = value
        self.save()

    @property
    def data(self):
        return self._cfg
