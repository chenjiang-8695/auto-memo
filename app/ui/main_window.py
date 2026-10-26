"""主窗口：备忘录列表（搜索/筛选）、新建/编辑/删除/完成切换。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database import SOURCE_LABELS


class MainWindow(QMainWindow):
    new_memo_requested = Signal()
    edit_memo_requested = Signal(int)      # memo_id
    delete_memo_requested = Signal(int)
    toggle_done_requested = Signal(int, bool)
    voice_requested = Signal()
    ocr_requested = Signal()
    settings_requested = Signal()
    toggle_float_requested = Signal()

    STATUS_FILTERS = [("all", "全部"), ("pending", "待办"),
                      ("reminded", "待提醒"), ("done", "已完成")]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("自动备忘录")
        self.resize(760, 520)
        self._memos = []  # 当前列表缓存，行号 -> memo

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 顶部工具行
        top = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索内容…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self.refresh)
        self._filter = QComboBox()
        for key, label in self.STATUS_FILTERS:
            self._filter.addItem(label, key)
        self._filter.currentIndexChanged.connect(self.refresh)
        btn_new = QPushButton("＋ 新建")
        btn_voice = QPushButton("🎤 语音")
        btn_ocr = QPushButton("📷 OCR")
        btn_settings = QPushButton("⚙ 设置")
        btn_float = QPushButton("🗔 悬浮窗")
        top.addWidget(self._search, 1)
        top.addWidget(self._filter)
        top.addWidget(btn_new)
        top.addWidget(btn_voice)
        top.addWidget(btn_ocr)
        top.addWidget(btn_settings)
        top.addWidget(btn_float)
        layout.addLayout(top)

        # 列表
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["内容", "来源", "提醒时间", "状态"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._context_menu)
        self._table.doubleClicked.connect(self._edit_current)
        layout.addWidget(self._table)

        self.setStatusBar(QStatusBar())

        btn_new.clicked.connect(self.new_memo_requested)
        btn_voice.clicked.connect(self.voice_requested)
        btn_ocr.clicked.connect(self.ocr_requested)
        btn_settings.clicked.connect(self.settings_requested)
        btn_float.clicked.connect(self.toggle_float_requested)

    # ---------- 数据刷新 ----------
    def refresh(self):
        """由控制器注入 db 后调用（set_db 只调用一次）。"""
        if not hasattr(self, "_db"):
            return
        search = self._search.text().strip()
        status = self._filter.currentData()
        self._memos = self._db.list_memos(search, status)
        self._table.setRowCount(len(self._memos))
        for row, memo in enumerate(self._memos):
            content = memo["content"].replace("\n", " ")
            if len(content) > 60:
                content = content[:60] + "…"
            self._table.setItem(row, 0, QTableWidgetItem(content))
            self._table.setItem(row, 1, QTableWidgetItem(
                SOURCE_LABELS.get(memo["source"], memo["source"])))
            self._table.setItem(row, 2, QTableWidgetItem(memo["remind_at"] or "-"))
            self._table.setItem(row, 3, QTableWidgetItem(self._status_text(memo)))
            if memo["done"]:
                for col in range(4):
                    item = self._table.item(row, col)
                    item.setForeground(Qt.GlobalColor.gray)

    @staticmethod
    def _status_text(memo):
        if memo["done"]:
            return "已完成"
        if memo["remind_at"]:
            return "已提醒" if memo["notified"] else "待提醒"
        return "备忘"

    def set_db(self, db):
        self._db = db
        self.refresh()

    def closeEvent(self, event):
        # 关闭按钮 = 最小化到托盘（程序由托盘菜单退出）
        event.ignore()
        self.hide()

    def show_status(self, text, timeout=4000):
        self.statusBar().showMessage(text, timeout)

    # ---------- 交互 ----------
    def _current_memo(self):
        row = self._table.currentRow()
        if 0 <= row < len(self._memos):
            return self._memos[row]
        return None

    def _edit_current(self):
        memo = self._current_memo()
        if memo:
            self.edit_memo_requested.emit(memo["id"])

    def _context_menu(self, pos):
        memo = self._current_memo()
        if not memo:
            return
        menu = QMenu(self)
        act_edit = menu.addAction("编辑")
        act_done = menu.addAction("标记完成" if not memo["done"] else "取消完成")
        menu.addSeparator()
        act_delete = menu.addAction("删除")
        chosen = menu.exec(self._table.viewport().mapToGlobal(pos))
        if chosen is act_edit:
            self.edit_memo_requested.emit(memo["id"])
        elif chosen is act_done:
            self.toggle_done_requested.emit(memo["id"], not memo["done"])
        elif chosen is act_delete:
            self.delete_memo_requested.emit(memo["id"])
