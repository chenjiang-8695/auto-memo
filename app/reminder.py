"""定时提醒调度：QTimer 周期轮询 SQLite，到期备忘通过 triggered 信号发出。

- 程序启动时立即检查一次，可补发关机/未运行期间错过的提醒。
- 备忘发出前先标记 notified，避免同一提醒重复弹出。
"""
from PySide6.QtCore import QObject, QTimer, Signal


class ReminderScheduler(QObject):
    triggered = Signal(dict)  # 到期的备忘录记录

    def __init__(self, db, interval_ms=15000, parent=None):
        super().__init__(parent)
        self._db = db
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._check)

    def start(self):
        self._timer.start()
        self._check()

    def stop(self):
        self._timer.stop()

    def _check(self):
        for memo in self._db.due_memos():
            self._db.mark_notified(memo["id"])
            self.triggered.emit(memo)
