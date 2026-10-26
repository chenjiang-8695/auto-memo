"""全局快捷键：基于 keyboard 库。

- 普通动作（new_memo / ocr_snip / toggle_float）：按下即触发 triggered 信号。
- 语音输入（voice_input）：按住组合键开始录音（voice_pressed），
  松开组合键中任意键结束（voice_released）。

keyboard 库的回调运行在独立线程，Qt 信号会以队列方式投递到 GUI 线程，线程安全。
"""
from PySide6.QtCore import QObject, Signal


class HotkeyManager(QObject):
    triggered = Signal(str)   # 动作名：new_memo / ocr_snip / toggle_float
    voice_pressed = Signal()
    voice_released = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._keyboard = None
        self._voice_recording = False

    def start(self, hotkeys: dict):
        """按配置注册全部快捷键；重复调用会先清理旧注册。"""
        import keyboard  # 延迟导入，避免未安装时影响其它模块

        self.stop()
        self._keyboard = keyboard
        for action, combo in hotkeys.items():
            combo = (combo or "").strip().lower()
            if not combo:
                continue
            if action == "voice_input":
                keyboard.add_hotkey(combo, self._on_voice_down, suppress=False)
                # 组合键里任意一键松开都视为结束说话
                for key in combo.split("+"):
                    keyboard.on_release_key(key, self._on_voice_up, suppress=False)
            else:
                keyboard.add_hotkey(
                    combo,
                    lambda a=action: self.triggered.emit(a),
                    suppress=False,
                )

    def stop(self):
        if self._keyboard is not None:
            try:
                self._keyboard.unhook_all()
            except Exception:
                pass
            self._keyboard = None
        self._voice_recording = False

    # ---------- 语音按住说话 ----------
    def _on_voice_down(self):
        # 按住不放时系统会重复触发按下事件，需要去抖
        if not self._voice_recording:
            self._voice_recording = True
            self.voice_pressed.emit()

    def _on_voice_up(self, _event):
        if self._voice_recording:
            self._voice_recording = False
            self.voice_released.emit()
