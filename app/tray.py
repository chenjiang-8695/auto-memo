"""系统托盘图标与菜单；图标用 QPainter 运行时绘制，无需外部资源文件。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def make_app_icon(size=64):
    """绘制圆角橙底白字“备”图标。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#F59E0B"))
    painter.setPen(Qt.PenStyle.NoPen)
    margin = size // 16
    painter.drawRoundedRect(margin, margin, size - 2 * margin, size - 2 * margin,
                            size // 5, size // 5)
    painter.setPen(QColor("#FFFFFF"))
    font = QFont("Microsoft YaHei", int(size * 0.44), QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "备")
    painter.end()
    return QIcon(pixmap)


class TrayIcon(QSystemTrayIcon):
    show_main = Signal()
    new_memo = Signal()
    toggle_float = Signal()
    open_settings = Signal()
    quit_app = Signal()

    def __init__(self, parent=None):
        super().__init__(make_app_icon(), parent)
        self.setToolTip("自动备忘录")

        menu = QMenu()
        act_main = menu.addAction("打开主窗口")
        act_new = menu.addAction("新建备忘录")
        act_float = menu.addAction("显示/隐藏悬浮窗")
        act_settings = menu.addAction("设置")
        menu.addSeparator()
        act_quit = menu.addAction("退出")
        self.setContextMenu(menu)

        act_main.triggered.connect(self.show_main)
        act_new.triggered.connect(self.new_memo)
        act_float.triggered.connect(self.toggle_float)
        act_settings.triggered.connect(self.open_settings)
        act_quit.triggered.connect(self.quit_app)
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason):
        # 单击/双击托盘图标打开主窗口
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_main.emit()

    def notify(self, title, message):
        """Windows 系统通知。"""
        if QSystemTrayIcon.supportsMessages():
            self.showMessage(title, message, self.icon(), 5000)
