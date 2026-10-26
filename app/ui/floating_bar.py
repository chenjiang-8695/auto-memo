"""悬浮窗迷你工具条：置顶、可拖动、显示最近备忘 + 三个快捷按钮。

- 提醒触发时红/白闪烁（start_flash），用户处理后 stop_flash。
- 位置自动记忆到配置文件，下次启动恢复。
- 右键菜单：打开主窗口 / 隐藏悬浮窗。
"""
from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QPushButton, QWidget


class FloatingBar(QWidget):
    voice_requested = Signal()
    ocr_requested = Signal()
    new_requested = Signal()
    open_main_requested = Signal()
    hidden_manually = Signal()

    NORMAL_STYLE = (
        "QWidget#bar { background: rgba(255,255,255,235); border: 1px solid #CCC;"
        " border-radius: 8px; }"
        "QLabel { color: #333; border: none; }"
        "QPushButton { border: none; font-size: 15px; padding: 2px 6px; }"
        "QPushButton:hover { background: #E8F0FE; border-radius: 4px; }"
    )
    FLASH_STYLE = (
        "QWidget#bar { background: rgba(255,80,80,235); border: 1px solid #C00;"
        " border-radius: 8px; }"
        "QLabel { color: #FFF; border: none; }"
        "QPushButton { border: none; font-size: 15px; padding: 2px 6px; }"
    )

    def __init__(self, config):
        super().__init__()
        self._config = config
        self._drag_pos = None
        self._flashing = False
        self._flash_on = False
        self._status_text = None  # 临时状态文本（录音中/识别中…）

        self.setObjectName("bar")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        # 不使用 WA_TranslucentBackground：在部分 Win10/11 + DPI 缩放下，
        # 顶层分层窗口会整窗透明不渲染。普通不透明窗口 + 样式表足够美观可靠。
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(self.NORMAL_STYLE)
        self.setFixedHeight(44)
        self.setMinimumWidth(300)
        self.setMaximumWidth(420)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 8, 4)
        self._label = QLabel("暂无备忘")
        self._label.setToolTip("点击查看主窗口")
        self._label.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self._label, 1)

        for text, tip, sig in [
            ("🎤", "语音输入（也可按住快捷键说话）", self.voice_requested),
            ("📷", "截图 OCR", self.ocr_requested),
            ("＋", "新建备忘录", self.new_requested),
        ]:
            btn = QPushButton(text)
            btn.setToolTip(tip)
            btn.clicked.connect(sig.emit)
            layout.addWidget(btn)

        self._flash_timer = QTimer(self)
        self._flash_timer.setInterval(450)
        self._flash_timer.timeout.connect(self._flash_tick)

        self._restore_pos()

    # ---------- 位置 ----------
    def _restore_pos(self):
        x = self._config.get("floating_bar", "x", default=-1)
        y = self._config.get("floating_bar", "y", default=-1)
        if x >= 0 and y >= 0:
            self.move(x, y)
        else:
            from PySide6.QtGui import QGuiApplication

            geo = QGuiApplication.primaryScreen().availableGeometry()
            self.move(geo.right() - self.width() - 30, geo.top() + 40)

    def _save_pos(self):
        self._config.set("floating_bar", "x", value=self.x())
        self._config.set("floating_bar", "y", value=self.y())

    # ---------- 内容 ----------
    def update_memo(self, memo):
        """更新展示的最近一条备忘。"""
        self._memo = memo
        if self._status_text:
            return  # 临时状态优先展示
        if memo:
            text = memo["content"].replace("\n", " ")
            if len(text) > 18:
                text = text[:18] + "…"
            if memo.get("remind_at") and not memo.get("done"):
                text = f"⏰ {text}（{memo['remind_at'][5:16]}）"
            self._label.setText(text)
            self._label.setToolTip(memo["content"])
        else:
            self._label.setText("暂无备忘，点 ＋ 或按住快捷键说话")

    def set_status(self, text, revert_ms=3000):
        """显示临时状态（如“录音中…”），超时后恢复最近备忘。"""
        self._status_text = text
        self._label.setText(text)
        if revert_ms:
            QTimer.singleShot(revert_ms, self.clear_status)

    def clear_status(self):
        """立即清除临时状态并恢复展示最近备忘。"""
        self._status_text = None
        self.update_memo(getattr(self, "_memo", None))

    # ---------- 闪烁 ----------
    def start_flash(self):
        if not self._flashing:
            self._flashing = True
            if not self.isVisible():
                self.show()
            self._flash_timer.start()

    def stop_flash(self):
        self._flashing = False
        self._flash_timer.stop()
        self._flash_on = False
        self.setStyleSheet(self.NORMAL_STYLE)

    def _flash_tick(self):
        self._flash_on = not self._flash_on
        self.setStyleSheet(self.FLASH_STYLE if self._flash_on else self.NORMAL_STYLE)

    # ---------- 拖动 / 事件 ----------
    def _label_clicked(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_main_requested.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, _event):
        if self._drag_pos is not None:
            self._drag_pos = None
            self._save_pos()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        act_main = menu.addAction("打开主窗口")
        act_hide = menu.addAction("隐藏悬浮窗")
        chosen = menu.exec(event.globalPos())
        if chosen is act_main:
            self.open_main_requested.emit()
        elif chosen is act_hide:
            self.hide()
            self.hidden_manually.emit()

    def closeEvent(self, event):
        self._save_pos()
        super().closeEvent(event)
