"""强制提醒弹窗。

约束（已与产品确认，去掉「绝对无法关闭」的不可实现承诺）：
- 置顶（WindowStaysOnTopHint）+ 模态（阻塞应用内其他交互）；
- 无系统关闭按钮，且拦截 ESC / 点 X，必须点按钮才能消除；
- 「已完成」需填写姓名；「稍后提醒」按配置间隔重弹。
"""

from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QVBoxLayout, QWidget,
)


class ReminderDialog(QDialog):
    """单个提醒的模态弹窗。

    返回值约定：
      - 用户点「已完成」 -> result_action == "completed"，operator_name / delay_count 可读；
      - 用户点「稍后提醒」-> result_action == "snoozed"。
    """

    def __init__(self, template: dict, operator_name: str = "",
                 delay_count: int = 0, parent=None):
        super().__init__(parent)
        self.template = template
        self.delay_count = delay_count
        self.result_action = None
        self.operator_name = operator_name

        self.setWindowTitle("强提醒")
        self.setObjectName("ReminderDialog")
        self.setModal(True)
        # 置顶 + 去掉关闭按钮（保留标题以便用户拖动）
        self.setWindowFlags(
            Qt.Dialog
            | Qt.WindowStaysOnTopHint
            | Qt.CustomizeWindowHint
            | Qt.WindowTitleHint
        )
        self.setFixedSize(600, 400)
        self._build_ui()

    def _render_content(self) -> str:
        """渲染提醒内容，把 {time} 替换为当前时间。"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return (self.template.get("content") or "").replace("{time}", now)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 顶部品牌强调色条
        accent = QWidget()
        accent.setObjectName("ReminderAccent")
        accent.setFixedHeight(6)
        root.addWidget(accent)

        body = QVBoxLayout()
        body.setContentsMargins(30, 22, 30, 24)
        body.setSpacing(14)
        root.addLayout(body, 1)

        # 标题行：圆形图标 + 标题/副标题
        head = QHBoxLayout()
        head.setSpacing(14)
        icon = QLabel("🔔")
        icon.setObjectName("ReminderIcon")
        icon.setFixedSize(48, 48)
        icon.setAlignment(Qt.AlignCenter)
        head.addWidget(icon)
        head_text = QVBoxLayout()
        head_text.setSpacing(2)
        title = QLabel("强提醒")
        title.setObjectName("ReminderTitle")
        subtitle = QLabel("您有一项任务待处理，请及时确认")
        subtitle.setObjectName("ReminderSubtitle")
        head_text.addWidget(title)
        head_text.addWidget(subtitle)
        head.addLayout(head_text)
        head.addStretch(1)
        body.addLayout(head)

        task = QLabel(f"当前任务：{self.template.get('template_name', '')}")
        task.setObjectName("ReminderTask")
        body.addWidget(task)

        ts = QLabel(f"提醒时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        ts.setObjectName("ReminderMeta")
        body.addWidget(ts)

        detail = QLabel(self._render_content())
        detail.setObjectName("ReminderDetail")
        detail.setWordWrap(True)
        detail.setMinimumHeight(90)
        detail.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        body.addWidget(detail, 1)

        # 姓名输入
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("姓名："))
        self.name_edit = QLineEdit(self.operator_name)
        self.name_edit.setPlaceholderText("首次填写后自动保存")
        name_row.addWidget(self.name_edit, 1)
        body.addLayout(name_row)

        self.delay_label = QLabel(f"📌 本次提醒已累计延迟 {self.delay_count} 次")
        self.delay_label.setObjectName("DelayLabel")
        body.addWidget(self.delay_label)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)
        self.done_btn = QPushButton("✅ 已完成")
        self.done_btn.setObjectName("DoneBtn")
        self.done_btn.setMinimumHeight(44)
        self.done_btn.clicked.connect(self._on_done)

        self.snooze_btn = QPushButton("⏰ 稍后提醒")
        self.snooze_btn.setObjectName("SnoozeBtn")
        self.snooze_btn.setMinimumHeight(44)
        self.snooze_btn.clicked.connect(self._on_snooze)

        btn_row.addWidget(self.done_btn)
        btn_row.addWidget(self.snooze_btn)
        body.addLayout(btn_row)

    # ---------- 按钮逻辑 ----------

    def _on_done(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请先填写姓名再标记完成。")
            self.name_edit.setFocus()
            return
        self.operator_name = name
        self.result_action = "completed"
        self.accept()

    def _on_snooze(self):
        # 稍后提醒也保留已输入的姓名
        self.operator_name = self.name_edit.text().strip()
        self.result_action = "snoozed"
        self.accept()

    # ---------- 拦截「绕过」操作 ----------

    def keyPressEvent(self, event):
        # 屏蔽 ESC 关闭
        if event.key() == Qt.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        # 没有通过按钮做出选择前，禁止直接关闭窗口
        if self.result_action is None:
            event.ignore()
        else:
            event.accept()
