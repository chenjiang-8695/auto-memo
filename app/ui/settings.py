"""设置对话框：快捷键自定义、语音模型、提醒方式、开机自启。

快捷键使用 QKeySequenceEdit 录入，保存时转换为 keyboard 库格式
（如 "Ctrl+Alt+V" -> "ctrl+alt+v"，Windows 键 Meta -> win）。
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

HOTKEY_ITEMS = [
    ("new_memo", "新建备忘录"),
    ("voice_input", "语音输入（按住说话）"),
    ("ocr_snip", "截图 OCR"),
    ("toggle_float", "显示/隐藏悬浮窗"),
]

WHISPER_MODELS = [("tiny", "tiny（39MB，最快）"),
                  ("base", "base（150MB，推荐）"),
                  ("small", "small（460MB，更准）")]


def qt_seq_to_keyboard(seq_text):
    """QKeySequence 文本 -> keyboard 库热键格式。"""
    text = seq_text.strip().lower()
    if not text:
        return ""
    text = text.replace("meta", "win")
    return text


class SettingsDialog(QDialog):
    settings_changed = Signal()

    def __init__(self, config, autostart_enabled, parent=None):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("设置")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)

        # ---- 快捷键 ----
        group_key = QGroupBox("全局快捷键")
        form = QFormLayout(group_key)
        self._key_edits = {}
        for action, label in HOTKEY_ITEMS:
            edit = QKeySequenceEdit()
            current = config.get("hotkeys", action, default="")
            if current:
                edit.setKeySequence(QKeySequence(current))
            edit.setClearButtonEnabled(True)
            form.addRow(label + "：", edit)
            self._key_edits[action] = edit
        layout.addWidget(group_key)

        # ---- 语音模型 ----
        group_voice = QGroupBox("语音识别")
        form_voice = QFormLayout(group_voice)
        self._model_combo = QComboBox()
        for key, label in WHISPER_MODELS:
            self._model_combo.addItem(label, key)
        current_model = config.get("whisper_model", default="base")
        idx = next((i for i, (k, _) in enumerate(WHISPER_MODELS)
                    if k == current_model), 1)
        self._model_combo.setCurrentIndex(idx)
        form_voice.addRow("离线模型：", self._model_combo)
        note = QLabel("切换模型后，下次识别时自动下载新模型")
        note.setStyleSheet("color:#888;")
        form_voice.addRow(note)
        layout.addWidget(group_voice)

        # ---- 提醒方式 ----
        group_remind = QGroupBox("提醒方式")
        form_remind = QFormLayout(group_remind)
        self._ck_popup = QCheckBox("置顶弹窗 + 提示音")
        self._ck_notify = QCheckBox("Windows 系统通知")
        self._ck_flash = QCheckBox("悬浮窗闪烁")
        self._ck_popup.setChecked(config.get("reminder", "popup", default=True))
        self._ck_notify.setChecked(
            config.get("reminder", "system_notify", default=True))
        self._ck_flash.setChecked(
            config.get("reminder", "float_flash", default=True))
        self._snooze = QSpinBox()
        self._snooze.setRange(1, 120)
        self._snooze.setSuffix(" 分钟")
        self._snooze.setValue(config.get("reminder", "snooze_minutes", default=5))
        form_remind.addRow(self._ck_popup)
        form_remind.addRow(self._ck_notify)
        form_remind.addRow(self._ck_flash)
        form_remind.addRow("稍后提醒时长：", self._snooze)
        layout.addWidget(group_remind)

        # ---- 系统 ----
        self._ck_autostart = QCheckBox("开机自动启动")
        self._ck_autostart.setChecked(autostart_enabled)
        layout.addWidget(self._ck_autostart)

        # ---- 按钮 ----
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

    def _on_save(self):
        # 校验快捷键：非空且不重复
        combos = {}
        for action, edit in self._key_edits.items():
            combo = qt_seq_to_keyboard(edit.keySequence().toString())
            if not combo:
                label = dict(HOTKEY_ITEMS)[action]
                QMessageBox.warning(self, "设置", f"请为「{label}」设置快捷键")
                return
            if combo in combos.values():
                QMessageBox.warning(self, "设置", f"快捷键 {combo} 重复，请修改")
                return
            combos[action] = combo

        cfg = self._config
        for action, combo in combos.items():
            cfg.set("hotkeys", action, value=combo)
        cfg.set("whisper_model", value=self._model_combo.currentData())
        cfg.set("reminder", "popup", value=self._ck_popup.isChecked())
        cfg.set("reminder", "system_notify", value=self._ck_notify.isChecked())
        cfg.set("reminder", "float_flash", value=self._ck_flash.isChecked())
        cfg.set("reminder", "snooze_minutes", value=self._snooze.value())
        cfg.set("autostart", value=self._ck_autostart.isChecked())

        self.settings_changed.emit()
        self.accept()
