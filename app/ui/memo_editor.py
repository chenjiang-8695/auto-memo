"""新建/编辑备忘录对话框：内容 + 可选提醒时间（含常用快捷时间）。"""
from datetime import datetime, timedelta

from PySide6.QtCore import QDateTime, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDateTimeEdit,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from app.database import TIME_FMT


class MemoEditor(QDialog):
    # saved(memo_id, content, remind_at)；memo_id 为 None 表示新建
    saved = Signal(object, str, object)

    def __init__(self, parent=None, memo_id=None, content="", remind_at=None,
                 source_label="文字"):
        super().__init__(parent)
        self._memo_id = memo_id
        self.setWindowTitle(("编辑备忘录" if memo_id else "新建备忘录")
                            + f"（来源：{source_label}）")
        self.setMinimumSize(460, 300)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        layout = QVBoxLayout(self)
        self._edit = QPlainTextEdit(content)
        self._edit.setPlaceholderText("输入备忘内容…")
        layout.addWidget(self._edit)

        # 提醒时间
        time_row = QHBoxLayout()
        self._enable_time = QCheckBox("设置提醒时间")
        self._time_edit = QDateTimeEdit(QDateTime.currentDateTime().addSecs(600))
        self._time_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self._time_edit.setCalendarPopup(True)
        self._time_edit.setEnabled(False)
        self._enable_time.toggled.connect(self._time_edit.setEnabled)
        time_row.addWidget(self._enable_time)
        time_row.addWidget(self._time_edit)
        time_row.addStretch()
        layout.addLayout(time_row)

        # 常用快捷时间
        quick_row = QHBoxLayout()
        quick_row.addWidget(QLabel("快捷："))
        for text, func in [
            ("10分钟后", lambda: self._quick(minutes=10)),
            ("1小时后", lambda: self._quick(hours=1)),
            ("3小时后", lambda: self._quick(hours=3)),
            ("今晚20:00", self._tonight),
            ("明早9:00", self._tomorrow_9),
        ]:
            btn = QPushButton(text)
            btn.setStyleSheet("padding: 2px 8px;")
            btn.clicked.connect(func)
            quick_row.addWidget(btn)
        quick_row.addStretch()
        layout.addLayout(quick_row)

        # 保存/取消
        btn_row = QHBoxLayout()
        btn_save = QPushButton("保存")
        btn_save.setDefault(True)
        btn_cancel = QPushButton("取消")
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)
        btn_save.clicked.connect(self._on_save)
        btn_cancel.clicked.connect(self.reject)

        if remind_at:
            self._enable_time.setChecked(True)
            self._time_edit.setDateTime(
                QDateTime.fromString(remind_at, "yyyy-MM-dd HH:mm:ss")
            )

        self._edit.setFocus()
        self._edit.moveCursor(self._edit.textCursor().MoveOperation.End)

    # ---------- 快捷时间 ----------
    def _quick(self, **delta):
        self._enable_time.setChecked(True)
        self._time_edit.setDateTime(
            QDateTime.currentDateTime().addSecs(int(timedelta(**delta).total_seconds()))
        )

    def _tonight(self):
        self._enable_time.setChecked(True)
        dt = QDateTime.currentDateTime()
        dt.setTime(dt.time().fromString("20:00", "HH:mm"))
        if dt < QDateTime.currentDateTime():
            dt = dt.addDays(1)
        self._time_edit.setDateTime(dt)

    def _tomorrow_9(self):
        self._enable_time.setChecked(True)
        dt = QDateTime.currentDateTime().addDays(1)
        dt.setTime(dt.time().fromString("09:00", "HH:mm"))
        self._time_edit.setDateTime(dt)

    # ---------- 保存 ----------
    def _on_save(self):
        content = self._edit.toPlainText().strip()
        if not content:
            self._edit.setFocus()
            self._edit.setPlaceholderText("内容不能为空！")
            return
        remind_at = None
        if self._enable_time.isChecked():
            remind_at = self._time_edit.dateTime().toPython().strftime(TIME_FMT)
        self.saved.emit(self._memo_id, content, remind_at)
        self.accept()
