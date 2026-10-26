"""全屏截图框选层：每个屏幕一个半透明覆盖窗口，拖动框选区域。

- 抓屏在显示覆盖层之前完成（可先隐藏本程序窗口，避免把自己截进去）。
- 正确处理多显示器与高 DPI（按 screen.devicePixelRatio 换算裁剪像素坐标）。
- ESC 或右键取消，松开左键完成。
"""
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget


class _SnipOverlay(QWidget):
    finished = Signal(QRect, object)  # (本 widget 内选区, screen)
    cancelled = Signal()

    def __init__(self, screen, pixmap):
        super().__init__()
        self._screen = screen
        self._pixmap = pixmap  # 该屏幕的完整截图
        self._origin = QPoint()
        self._current = QRect()
        self._dragging = False

        geo = screen.geometry()
        self.setGeometry(geo)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.showFullScreen()
        self.setGeometry(geo)  # showFullScreen 后再次确保覆盖整个屏幕
        self.activateWindow()
        self.raise_()

    # ---------- 绘制 ----------
    def paintEvent(self, _event):
        painter = QPainter(self)
        # 背景：完整截图 + 暗色遮罩
        painter.drawPixmap(self.rect(), self._pixmap, self._pixmap.rect())
        painter.fillRect(self.rect(), QColor(0, 0, 0, 110))

        if not self._current.isNull():
            dpr = self._pixmap.devicePixelRatio()
            src = QRect(
                int(self._current.x() * dpr),
                int(self._current.y() * dpr),
                int(self._current.width() * dpr),
                int(self._current.height() * dpr),
            )
            # 选区显示原始亮度截图
            painter.drawPixmap(self._current, self._pixmap, src)
            painter.setPen(QPen(QColor(0, 150, 255), 2))
            painter.drawRect(self._current)
            # 尺寸提示
            tip = f"{self._current.width()} × {self._current.height()}"
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(
                self._current.left(), max(16, self._current.top() - 6), tip
            )
        painter.end()

    # ---------- 鼠标 ----------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.position().toPoint()
            self._current = QRect(self._origin, self._origin)
            self._dragging = True
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self.cancelled.emit()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._current = QRect(self._origin, event.position().toPoint()).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            if self._current.width() > 4 and self._current.height() > 4:
                self.finished.emit(self._current, self._screen)
            else:
                self.cancelled.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()


class SnipManager:
    """协调多屏覆盖窗口；result/cancel 回调只触发一次。"""

    def __init__(self, on_result, on_cancel):
        self._overlays = []
        self._on_result = on_result
        self._on_cancel = on_cancel
        self._done = False

    def start(self):
        app = QGuiApplication.instance()
        app.processEvents()
        for screen in QGuiApplication.screens():
            pixmap = screen.grabWindow(0)
            overlay = _SnipOverlay(screen, pixmap)
            overlay.finished.connect(self._finish)
            overlay.cancelled.connect(self._cancel)
            self._overlays.append(overlay)
        if not self._overlays:
            self._cancel()

    def _finish(self, rect, screen):
        if self._done:
            return
        self._done = True
        dpr = screen.devicePixelRatio()
        image = None
        for ov in self._overlays:
            if ov._screen is screen:
                src = QRect(
                    int(rect.x() * dpr),
                    int(rect.y() * dpr),
                    int(rect.width() * dpr),
                    int(rect.height() * dpr),
                )
                image = ov._pixmap.copy(src).toImage()
                break
        self._close_all()
        if image is not None and not image.isNull():
            self._on_result(image)
        else:
            self._on_cancel()

    def _cancel(self):
        if self._done:
            return
        self._done = True
        self._close_all()
        self._on_cancel()

    def _close_all(self):
        for ov in self._overlays:
            ov.close()
        self._overlays.clear()
