"""自动备忘录入口：组装配置、数据库、快捷键、语音、OCR、提醒、托盘与各窗口。

运行方式：
    .venv\\Scripts\\pythonw.exe main.py        # 无控制台后台运行
    .venv\\Scripts\\python.exe main.py         # 带控制台（调试用）
"""
import sys
from datetime import datetime, timedelta

from PySide6.QtCore import QObject, QSharedMemory, QTimer
from PySide6.QtWidgets import QApplication

from app import autostart
from app.config import Config
from app.database import (
    SOURCE_LABELS,
    SOURCE_OCR,
    SOURCE_TEXT,
    SOURCE_VOICE,
    TIME_FMT,
    Database,
)
from app.hotkeys import HotkeyManager
from app.ocr import OcrEngine
from app.reminder import ReminderScheduler
from app.tray import TrayIcon, make_app_icon
from app.ui.floating_bar import FloatingBar
from app.ui.main_window import MainWindow
from app.ui.memo_editor import MemoEditor
from app.ui.reminder_dialog import ReminderDialog
from app.ui.settings import SettingsDialog
from app.ui.snip_overlay import SnipManager
from app.voice import Transcriber, VoiceRecorder


class MainApp(QObject):
    def __init__(self, qt_app):
        super().__init__()
        self.qt_app = qt_app
        self.config = Config()
        self.db = Database()

        # ---- UI ----
        self.window = MainWindow()
        self.window.set_db(self.db)
        self.window.setWindowIcon(make_app_icon())
        self.floating = FloatingBar(self.config)
        self.tray = TrayIcon()

        # ---- 功能模块 ----
        self.hotkeys = HotkeyManager()
        self.recorder = VoiceRecorder()
        self.transcriber = Transcriber(
            self.config.get("whisper_model", default="base"))
        self.ocr = OcrEngine()
        self.scheduler = ReminderScheduler(self.db)

        self._editor_source = SOURCE_TEXT  # 当前编辑器对应的新建来源
        self._reminder_queue = []
        self._reminder_dialog = None
        self._snip = None

        self._wire()

    # ---------------- 信号接线 ----------------
    def _wire(self):
        hk = self.hotkeys
        hk.triggered.connect(self._on_hotkey)
        hk.voice_pressed.connect(self._voice_start)
        hk.voice_released.connect(self._voice_stop)

        self.recorder.stopped.connect(self._voice_transcribe)
        self.recorder.error.connect(self._notify_error)
        self.transcriber.finished.connect(self._voice_done)
        self.transcriber.failed.connect(self._voice_failed)
        self.transcriber.progress.connect(
            lambda msg: self.floating.set_status(msg, 0))

        self.ocr.finished.connect(self._ocr_done)
        self.ocr.failed.connect(self._ocr_failed)

        self.scheduler.triggered.connect(self._on_reminder)

        w = self.window
        w.new_memo_requested.connect(self.new_memo)
        w.edit_memo_requested.connect(self.edit_memo)
        w.delete_memo_requested.connect(self.delete_memo)
        w.toggle_done_requested.connect(self.toggle_done)
        w.voice_requested.connect(self.voice_toggle)
        w.ocr_requested.connect(self.start_ocr)
        w.settings_requested.connect(self.open_settings)
        w.toggle_float_requested.connect(self.toggle_float)

        f = self.floating
        f.voice_requested.connect(self.voice_toggle)
        f.ocr_requested.connect(self.start_ocr)
        f.new_requested.connect(self.new_memo)
        f.open_main_requested.connect(self.show_main)
        f.hidden_manually.connect(
            lambda: self.config.set("floating_bar", "visible", value=False))

        t = self.tray
        t.show_main.connect(self.show_main)
        t.new_memo.connect(self.new_memo)
        t.toggle_float.connect(self.toggle_float)
        t.open_settings.connect(self.open_settings)
        t.quit_app.connect(self.quit)

    # ---------------- 启动 ----------------
    def run(self):
        autostart.apply(self.config.get("autostart", default=True))
        self.tray.show()
        if self.config.get("floating_bar", "visible", default=True):
            self.floating.show()
        self.hotkeys.start(self.config.get("hotkeys", default={}))
        self.scheduler.start()
        self.transcriber.preload()  # 后台预加载语音模型（首次自动下载）
        self._refresh_views()
        self.window.show()

    def quit(self):
        self.hotkeys.stop()
        self.scheduler.stop()
        self.db.close()
        self.qt_app.quit()

    # ---------------- 视图刷新 ----------------
    def _refresh_views(self):
        self.window.refresh()
        self.floating.update_memo(self.db.latest_pending())

    def show_main(self):
        self.floating.stop_flash()
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    # ---------------- 快捷键动作 ----------------
    def _on_hotkey(self, action):
        if action == "new_memo":
            self.new_memo()
        elif action == "ocr_snip":
            self.start_ocr()
        elif action == "toggle_float":
            self.toggle_float()

    def toggle_float(self):
        visible = not self.floating.isVisible()
        self.floating.setVisible(visible)
        self.config.set("floating_bar", "visible", value=visible)

    # ---------------- 语音流程 ----------------
    def voice_toggle(self):
        """悬浮窗/主窗口按钮：在 录音中/停止 之间切换。"""
        if self.recorder.is_recording:
            self.recorder.stop()
        else:
            self._voice_start()

    def _voice_start(self):
        self.recorder.start()
        if self.recorder.is_recording:
            self.floating.set_status("🎤 录音中…（松开快捷键结束）", 0)

    def _voice_stop(self):
        if self.recorder.is_recording:
            self.recorder.stop()

    def _voice_transcribe(self, wav_path):
        self.floating.set_status("识别中…", 0)
        self.transcriber.transcribe_async(wav_path)

    def _voice_done(self, text):
        self.floating.clear_status()
        self.open_editor(content=text, source=SOURCE_VOICE)

    def _voice_failed(self, msg):
        self.floating.clear_status()
        self.floating.set_status("语音识别失败", 3000)
        self.tray.notify("语音识别失败", msg)

    # ---------------- OCR 流程 ----------------
    def start_ocr(self):
        # 先隐藏本程序窗口，避免把自己截进图里
        self._win_visible = self.window.isVisible()
        self._float_visible = self.floating.isVisible()
        self.window.hide()
        self.floating.hide()
        QTimer.singleShot(200, self._snip_begin)

    def _snip_begin(self):
        self._snip = SnipManager(self._snip_result, self._snip_cancel)
        self._snip.start()

    def _restore_windows(self):
        if self._win_visible:
            self.window.show()
        if self._float_visible:
            self.floating.show()

    def _snip_result(self, image):
        self._restore_windows()
        self.floating.set_status("OCR 识别中…", 0)
        self.ocr.recognize_async(image)

    def _snip_cancel(self):
        self._restore_windows()

    def _ocr_done(self, text):
        self.floating.clear_status()
        self.open_editor(content=text, source=SOURCE_OCR)

    def _ocr_failed(self, msg):
        self.floating.clear_status()
        self.floating.set_status("OCR 识别失败", 3000)
        self.tray.notify("OCR 识别失败", msg)

    # ---------------- 备忘录增删改 ----------------
    def new_memo(self):
        self.open_editor(source=SOURCE_TEXT)

    def open_editor(self, content="", source=SOURCE_TEXT):
        self._editor_source = source
        editor = MemoEditor(self.window, content=content,
                            source_label=SOURCE_LABELS[source])
        editor.saved.connect(self._save_memo)
        editor.exec()

    def edit_memo(self, memo_id):
        memo = self.db.get_memo(memo_id)
        if not memo:
            return
        editor = MemoEditor(
            self.window, memo_id=memo_id, content=memo["content"],
            remind_at=memo["remind_at"],
            source_label=SOURCE_LABELS.get(memo["source"], memo["source"]))
        editor.saved.connect(self._save_memo)
        editor.exec()

    def _save_memo(self, memo_id, content, remind_at):
        if memo_id is None:
            self.db.add_memo(content, source=self._editor_source,
                             remind_at=remind_at)
            self.window.show_status("备忘录已保存")
        else:
            self.db.update_memo(memo_id, content=content, remind_at=remind_at)
            self.window.show_status("备忘录已更新")
        self._refresh_views()

    def delete_memo(self, memo_id):
        self.db.delete_memo(memo_id)
        self._refresh_views()

    def toggle_done(self, memo_id, done):
        self.db.update_memo(memo_id, done=done)
        self._refresh_views()

    # ---------------- 提醒 ----------------
    def _on_reminder(self, memo):
        self._reminder_queue.append(memo)
        self._pump_reminders()

    def _pump_reminders(self):
        if self._reminder_dialog is not None:
            return
        if not self._reminder_queue:
            return
        memo = self._reminder_queue.pop(0)
        if self.config.get("reminder", "system_notify", default=True):
            self.tray.notify("备忘录提醒", memo["content"][:120])
        if self.config.get("reminder", "float_flash", default=True):
            self.floating.start_flash()
        if self.config.get("reminder", "popup", default=True):
            dialog = ReminderDialog(
                memo, self.config.get("reminder", "snooze_minutes", default=5),
                self.window)
            dialog.snooze_requested.connect(self._snooze_memo)
            dialog.done_requested.connect(self._done_memo)
            dialog.finished.connect(self._reminder_closed)
            self._reminder_dialog = dialog
            dialog.show()
            self.qt_app.alert(dialog, 0)
        else:
            QTimer.singleShot(50, self._pump_reminders)

    def _reminder_closed(self, _result):
        self._reminder_dialog = None
        if self._reminder_queue:
            QTimer.singleShot(50, self._pump_reminders)
        else:
            self.floating.stop_flash()

    def _snooze_memo(self, memo_id):
        minutes = self.config.get("reminder", "snooze_minutes", default=5)
        remind_at = (datetime.now() + timedelta(minutes=minutes)).strftime(TIME_FMT)
        self.db.update_memo(memo_id, remind_at=remind_at)
        self._refresh_views()

    def _done_memo(self, memo_id):
        self.db.update_memo(memo_id, done=True)
        self._refresh_views()

    # ---------------- 设置 ----------------
    def open_settings(self):
        dialog = SettingsDialog(self.config, autostart.is_enabled(), self.window)
        dialog.settings_changed.connect(self._apply_settings)
        dialog.exec()

    def _apply_settings(self):
        self.hotkeys.start(self.config.get("hotkeys", default={}))
        autostart.apply(self.config.get("autostart", default=True))
        self.transcriber.set_model(self.config.get("whisper_model", default="base"))
        self.window.show_status("设置已保存")

    # ---------------- 错误提示 ----------------
    def _notify_error(self, msg):
        self.tray.notify("自动备忘录", msg)
        self.window.show_status(msg)


def main():
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("自动备忘录")
    qt_app.setQuitOnLastWindowClosed(False)  # 托盘常驻

    # 单实例：避免开机自启 + 手动启动造成快捷键重复注册
    shared = QSharedMemory("AutoMemoSingleInstance")
    if not shared.create(1):
        print("自动备忘录已在运行中。")
        sys.exit(0)

    app = MainApp(qt_app)
    app.run()
    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
