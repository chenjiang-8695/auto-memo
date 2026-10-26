"""提醒弹窗：置顶显示备忘内容 + 循环提示音，直到用户操作为止。

按钮：稍后提醒（按配置分钟数）/ 已完成 / 关闭（仅关闭本次提醒）。
"""
import winsound

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class ReminderDialog(QDialog):
    snooze_requested = Signal(int)  # memo_id
    done_requested = Signal(int)    # memo_id

    def __init__(self, memo: dict, snooze_minutes: int, parent=None):
        super().__init__(parent)
        self._memo_id = memo["id"]
        self._snooze_minutes = snooze_minutes
        self._sound_on = False

        self.setWindowTitle("备忘录提醒")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setMinimumWidth(360)
        self.setStyleSheet(
            "QDialog { background: #FFF8E7; }"
            "QLabel#title { font-size: 16px; font-weight: bold; color: #D97706; }"
            "QLabel#content { font-size: 14px; color: #333; padding: 8px 0; }"
            "QLabel#time { color: #888; font-size: 12px; }"
        )

        layout = QVBoxLayout(self)
        title = QLabel("⏰ 你有新的备忘提醒")
        title.setObjectName("title")
        layout.addWidget(title)

        content = QLabel(memo["content"])
        content.setObjectName("content")
        content.setWordWrap(True)
        layout.addWidget(content)

        time_label = QLabel(f"计划提醒时间：{memo.get('remind_at') or '-'}")
        time_label.setObjectName("time")
        layout.addWidget(time_label)

        btns = QHBoxLayout()
        btn_snooze = QPushButton(f"稍后 {snooze_minutes} 分钟")
        btn_done = QPushButton("已完成")
        btn_close = QPushButton("关闭")
        btns.addWidget(btn_snooze)
        btns.addWidget(btn_done)
        btns.addStretch()
        btns.addWidget(btn_close)
        layout.addLayout(btns)

        btn_snooze.clicked.connect(self._on_snooze)
        btn_done.clicked.connect(self._on_done)
        btn_close.clicked.connect(self.reject)

    # ---------- 提示音 ----------
    def showEvent(self, event):
        super().showEvent(event)
        self._start_sound()

    def _start_sound(self):
        try:
            winsound.PlaySound(
                "SystemExclamation",
                winsound.SND_ALIAS | winsound.SND_LOOP | winsound.SND_ASYNC,
            )
            self._sound_on = True
        except RuntimeError:
            pass

    def _stop_sound(self):
        if self._sound_on:
            winsound.PlaySound(None, winsound.SND_PURGE)
            self._sound_on = False

    # ---------- 操作 ----------
    def _on_snooze(self):
        self._stop_sound()
        self.snooze_requested.emit(self._memo_id)
        self.accept()

    def _on_done(self):
        self._stop_sound()
        self.done_requested.emit(self._memo_id)
        self.accept()

    def reject(self):
        self._stop_sound()
        super().reject()
