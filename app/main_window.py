"""主窗口：提醒模板 / 历史记录 / 设置 三个 Tab，并统筹计时与弹窗。"""

import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import APP_EDITION, APP_NAME, APP_VERSION, COPYRIGHT
from .exporter import export_to_excel
from .reminder_dialog import ReminderDialog
from .settings import APPDATA_DIR, is_autostart_enabled, set_autostart


class TemplateEditDialog(QDialog):
    """新增/编辑模板的弹窗。"""

    def __init__(self, default_interval=30, template=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑提醒模板" if template else "新增提醒模板")
        self.setMinimumWidth(460)
        form = QFormLayout(self)

        self.name_edit = QLineEdit(template["template_name"] if template else "")
        form.addRow("模板名称：", self.name_edit)

        self.content_edit = QPlainTextEdit(template["content"] if template else "")
        self.content_edit.setPlaceholderText("例如：请及时处理待审核的退款工单")
        self.content_edit.setFixedHeight(110)
        form.addRow("提醒内容：", self.content_edit)

        hint = QLabel("提示：提醒弹出时会自动显示当前时间，这里只写要做的事就行。")
        hint.setStyleSheet("color:#8a94a6; font-size:12px;")
        hint.setWordWrap(True)
        form.addRow("", hint)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 1440)
        self.interval_spin.setSuffix(" 分钟")
        self.interval_spin.setValue(
            template["interval_minutes"] if template else default_interval
        )
        form.addRow("提醒间隔：", self.interval_spin)

        self.active_check = QCheckBox("启用该模板")
        self.active_check.setChecked(bool(template["is_active"]) if template else True)
        form.addRow("", self.active_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_ok(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "提示", "模板名称不能为空。")
            return
        if not self.content_edit.toPlainText().strip():
            QMessageBox.warning(self, "提示", "提醒内容不能为空。")
            return
        self.accept()

    def values(self):
        return {
            "name": self.name_edit.text().strip(),
            "content": self.content_edit.toPlainText().strip(),
            "interval": self.interval_spin.value(),
            "active": 1 if self.active_check.isChecked() else 0,
        }


class MainWindow(QMainWindow):
    def __init__(self, db, config, engine):
        super().__init__()
        self.db = db
        self.config = config
        self.engine = engine
        self._force_quit = False  # True 时关闭窗口=真正退出

        self.setWindowTitle(f"{APP_NAME}  v{APP_VERSION} {APP_EDITION}")
        self.resize(900, 660)
        self.setMinimumSize(760, 560)
        self._build_ui()
        self._reload_templates()
        self._reload_history()

        # 引擎到点 -> 弹窗
        self.engine.reminder_due.connect(self._show_reminder)

    # ---------- UI 构建 ----------

    def _shadow(self, blur=24, dy=4, alpha=40):
        """生成一个柔和投影效果（用于卡片/横幅的悬浮感）。"""
        eff = QGraphicsDropShadowEffect(self)
        eff.setBlurRadius(blur)
        eff.setXOffset(0)
        eff.setYOffset(dy)
        eff.setColor(QColor(26, 60, 110, alpha))
        return eff

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 18, 20, 14)
        root.setSpacing(16)

        root.addWidget(self._build_banner())

        # 内容卡片：承载三个 Tab
        card = QFrame()
        card.setObjectName("ContentCard")
        card.setGraphicsEffect(self._shadow(blur=28, dy=6, alpha=30))
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(18, 14, 18, 16)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_template_tab(), "提醒模板")
        self.tabs.addTab(self._build_history_tab(), "历史记录")
        self.tabs.addTab(self._build_settings_tab(), "设置")
        card_lay.addWidget(self.tabs)
        root.addWidget(card, 1)

        footer = QLabel(f"{COPYRIGHT}　·　v{APP_VERSION} {APP_EDITION}")
        footer.setObjectName("Footer")
        footer.setAlignment(Qt.AlignCenter)
        root.addWidget(footer)

    def _build_banner(self) -> QFrame:
        banner = QFrame()
        banner.setObjectName("Banner")
        banner.setFixedHeight(88)
        banner.setGraphicsEffect(self._shadow(blur=26, dy=6, alpha=70))
        lay = QHBoxLayout(banner)
        lay.setContentsMargins(22, 0, 22, 0)
        lay.setSpacing(16)

        logo = QLabel("🐚")
        logo.setObjectName("BannerLogo")
        logo.setFixedSize(52, 52)
        logo.setAlignment(Qt.AlignCenter)
        lay.addWidget(logo)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        title = QLabel(APP_NAME)
        title.setObjectName("BannerTitle")
        slogan = QLabel("按时提醒 · 全程留痕 · 让每一单售后都不遗漏")
        slogan.setObjectName("BannerSlogan")
        text_box.addWidget(title)
        text_box.addWidget(slogan)
        lay.addLayout(text_box)

        lay.addStretch(1)

        badge = QLabel(f"v{APP_VERSION} {APP_EDITION}")
        badge.setObjectName("VersionBadge")
        badge.setAlignment(Qt.AlignCenter)
        lay.addWidget(badge, 0, Qt.AlignVCenter)
        return banner

    def _style_table(self, table: QTableWidget):
        """统一表格观感：行高、斑马纹、整行选择、隐藏行号。"""
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(38)
        table.setShowGrid(False)

    def _build_template_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 10, 4, 4)
        v.setSpacing(12)

        tip = QLabel("管理周期性提醒任务。启用的模板会各自独立计时，到点强制提醒。")
        tip.setObjectName("FieldHint")
        v.addWidget(tip)

        self.tpl_table = QTableWidget(0, 4)
        self.tpl_table.setHorizontalHeaderLabels(["模板名称", "间隔(分钟)", "状态", "内容预览"])
        self.tpl_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.Stretch
        )
        self._style_table(self.tpl_table)
        self.tpl_table.doubleClicked.connect(lambda *_: self._edit_template())
        v.addWidget(self.tpl_table, 1)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        add_btn = QPushButton("＋ 新增模板")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.clicked.connect(self._add_template)
        edit_btn = QPushButton("编辑")
        edit_btn.clicked.connect(self._edit_template)
        toggle_btn = QPushButton("启用 / 停用")
        toggle_btn.clicked.connect(self._toggle_template)
        del_btn = QPushButton("删除")
        del_btn.clicked.connect(self._delete_template)
        btns.addWidget(add_btn)
        btns.addStretch(1)
        for b in (edit_btn, toggle_btn, del_btn):
            btns.addWidget(b)
        v.addLayout(btns)
        return w

    def _build_history_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 10, 4, 4)
        v.setSpacing(12)

        filt = QHBoxLayout()
        filt.setSpacing(8)
        filt.addWidget(QLabel("姓名筛选："))
        self.op_filter = QComboBox()
        self.op_filter.setMinimumWidth(150)
        self.op_filter.currentIndexChanged.connect(self._reload_history)
        filt.addWidget(self.op_filter)
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._reload_history)
        filt.addWidget(refresh_btn)
        filt.addStretch(1)
        export_btn = QPushButton("⬇ 导出 Excel")
        export_btn.setObjectName("PrimaryBtn")
        export_btn.clicked.connect(self._export_history)
        filt.addWidget(export_btn)
        v.addLayout(filt)

        self.hist_table = QTableWidget(0, 6)
        self.hist_table.setHorizontalHeaderLabels(
            ["完成时间", "任务模板", "内容", "操作人", "延迟次数", "响应时长"]
        )
        self.hist_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch
        )
        self._style_table(self.hist_table)
        v.addWidget(self.hist_table, 1)
        return w

    def _build_settings_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(8, 14, 8, 8)
        outer.setSpacing(10)

        # —— 基本设置 ——
        outer.addWidget(self._section_title("基本设置"))
        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        self.name_setting = QLineEdit(self.db.get_setting("operator_name", ""))
        self.name_setting.setMaximumWidth(260)
        self.name_setting.editingFinished.connect(
            lambda: self.db.set_setting("operator_name", self.name_setting.text().strip())
        )
        form.addRow("默认姓名：", self.name_setting)

        self.interval_setting = QSpinBox()
        self.interval_setting.setRange(1, 1440)
        self.interval_setting.setSuffix(" 分钟")
        self.interval_setting.setMaximumWidth(160)
        self.interval_setting.setValue(int(self.config.get("default_interval", 30)))
        form.addRow("默认提醒间隔：", self.interval_setting)

        self.autostart_check = QCheckBox("开机时自动启动本软件")
        self.autostart_check.setChecked(is_autostart_enabled())
        self.autostart_check.toggled.connect(self._on_autostart_toggled)
        form.addRow("开机自启：", self.autostart_check)
        outer.addLayout(form)

        # —— 数据管理 ——
        outer.addWidget(self._section_title("数据管理"))
        data_row = QHBoxLayout()
        data_row.setSpacing(10)
        exp_btn = QPushButton("⬇ 导出全部记录")
        exp_btn.clicked.connect(lambda: self._export_history(all_records=True))
        clear_btn = QPushButton("清空历史记录")
        clear_btn.setObjectName("DangerBtn")
        clear_btn.clicked.connect(self._clear_history)
        data_row.addWidget(exp_btn)
        data_row.addWidget(clear_btn)
        data_row.addStretch(1)
        outer.addLayout(data_row)

        # —— 关于 ——
        outer.addWidget(self._section_title("关于"))
        about = QLabel(
            f"{APP_NAME}  v{APP_VERSION} {APP_EDITION}\n"
            f"{COPYRIGHT}\n"
            "技术支持：培训发展中心"
        )
        about.setObjectName("FieldHint")
        outer.addWidget(about)

        outer.addStretch(1)
        return w

    def _section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("SectionTitle")
        return lbl

    # ---------- 模板 Tab 逻辑 ----------

    def _reload_templates(self):
        rows = self.db.list_templates()
        self.tpl_table.setRowCount(len(rows))
        for i, t in enumerate(rows):
            preview = (t["content"] or "").replace("\n", " ")
            if len(preview) > 30:
                preview = preview[:30] + "…"
            cells = [
                t["template_name"],
                str(t["interval_minutes"]),
                "启用" if t["is_active"] else "停用",
                preview,
            ]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setData(Qt.UserRole, t["id"])
                self.tpl_table.setItem(i, c, item)

    def _selected_template_id(self):
        row = self.tpl_table.currentRow()
        if row < 0:
            return None
        return self.tpl_table.item(row, 0).data(Qt.UserRole)

    def _add_template(self):
        dlg = TemplateEditDialog(
            default_interval=int(self.config.get("default_interval", 30)), parent=self
        )
        if dlg.exec() == QDialog.Accepted:
            v = dlg.values()
            new_id = self.db.add_template(v["name"], v["content"], v["interval"], v["active"])
            if v["active"]:
                self.db.schedule_from_now(new_id, v["interval"])
            self._reload_templates()

    def _edit_template(self):
        tid = self._selected_template_id()
        if tid is None:
            QMessageBox.information(self, "提示", "请先选中一个模板。")
            return
        tpl = self.db.get_template(tid)
        dlg = TemplateEditDialog(template=tpl, parent=self)
        if dlg.exec() == QDialog.Accepted:
            v = dlg.values()
            self.db.update_template(tid, v["name"], v["content"], v["interval"], v["active"])
            # 启用状态下，间隔可能变化，按新间隔重排下次到期
            if v["active"]:
                self.db.schedule_from_now(tid, v["interval"])
            self._reload_templates()

    def _toggle_template(self):
        tid = self._selected_template_id()
        if tid is None:
            QMessageBox.information(self, "提示", "请先选中一个模板。")
            return
        tpl = self.db.get_template(tid)
        new_active = 0 if tpl["is_active"] else 1
        self.db.set_template_active(tid, new_active)
        if new_active:
            self.db.schedule_from_now(tid, tpl["interval_minutes"])
        self._reload_templates()

    def _delete_template(self):
        tid = self._selected_template_id()
        if tid is None:
            QMessageBox.information(self, "提示", "请先选中一个模板。")
            return
        if QMessageBox.question(self, "确认", "确定删除该模板？历史记录会保留。") \
                == QMessageBox.Yes:
            self.db.delete_template(tid)
            self._reload_templates()

    # ---------- 历史 Tab 逻辑 ----------

    def _reload_history(self):
        # 刷新姓名下拉（保留当前选择）
        current = self.op_filter.currentText()
        self.op_filter.blockSignals(True)
        self.op_filter.clear()
        self.op_filter.addItem("全部")
        for name in self.db.distinct_operators():
            self.op_filter.addItem(name)
        idx = self.op_filter.findText(current)
        self.op_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.op_filter.blockSignals(False)

        op = None if self.op_filter.currentText() in ("全部", "") else self.op_filter.currentText()
        records = self.db.list_completions(operator_name=op)
        from .exporter import _response_duration
        self.hist_table.setRowCount(len(records))
        for i, r in enumerate(records):
            dur = _response_duration(r.get("reminded_at"), r.get("completed_at"))
            cells = [
                r.get("completed_at", ""),
                r.get("template_name", ""),
                r.get("reminder_content", ""),
                r.get("operator_name", ""),
                str(r.get("delay_count", 0)),
                dur,
            ]
            for c, text in enumerate(cells):
                self.hist_table.setItem(i, c, QTableWidgetItem(text))

    def _export_history(self, all_records=False):
        op = None
        if not all_records and self.op_filter.currentText() not in ("全部", ""):
            op = self.op_filter.currentText()
        records = self.db.list_completions(operator_name=op)
        if not records:
            QMessageBox.information(self, "提示", "没有可导出的记录。")
            return
        target_dir = QFileDialog.getExistingDirectory(
            self, "选择导出目录", os.path.expanduser("~")
        )
        if not target_dir:
            return
        try:
            path = export_to_excel(records, target_dir, op or "")
            QMessageBox.information(self, "导出成功", f"已导出到：\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _clear_history(self):
        if QMessageBox.warning(
            self, "二次确认",
            "确定清空全部历史记录？此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) == QMessageBox.Yes:
            self.db.clear_completions()
            self._reload_history()

    # ---------- 设置逻辑 ----------

    def _on_autostart_toggled(self, checked: bool):
        ok = set_autostart(checked)
        if not ok:
            QMessageBox.warning(self, "提示", "设置开机自启动失败，请检查权限。")
            self.autostart_check.blockSignals(True)
            self.autostart_check.setChecked(is_autostart_enabled())
            self.autostart_check.blockSignals(False)

    def _save_default_interval(self):
        self.config["default_interval"] = self.interval_setting.value()

    # ---------- 弹窗编排 ----------

    def _show_reminder(self, template: dict):
        """引擎到点回调：弹出强制提醒窗，并按用户选择回写引擎。"""
        op_name = self.db.get_setting("operator_name", "")
        tid = template["id"]
        delay = int(self.db.get_setting(f"delay_count_{tid}", "0") or "0")

        dlg = ReminderDialog(template, operator_name=op_name, delay_count=delay, parent=self)
        dlg.exec()

        if dlg.result_action == "completed":
            # 保存姓名 + 写完成记录 + 重置该模板延迟计数
            self.db.set_setting("operator_name", dlg.operator_name)
            self.name_setting.setText(dlg.operator_name)
            rendered = (template.get("content") or "").replace(
                "{time}", template.get("_reminded_at", "")
            )
            self.db.add_completion(
                operator_name=dlg.operator_name,
                template_id=tid,
                template_name=template.get("template_name", ""),
                reminder_content=rendered,
                reminded_at=template.get("_reminded_at", ""),
                delay_count=delay,
            )
            self.db.set_setting(f"delay_count_{tid}", "0")
            self.engine.on_completed(tid)
            self._reload_history()
        else:
            # 稍后提醒：延迟计数 +1
            if dlg.operator_name:
                self.db.set_setting("operator_name", dlg.operator_name)
            self.db.set_setting(f"delay_count_{tid}", str(delay + 1))
            self.engine.on_snoozed(tid)

    # ---------- 关闭=最小化到托盘 ----------

    def closeEvent(self, event):
        if self._force_quit:
            self.config["default_interval"] = self.interval_setting.value()
            event.accept()
            return
        # 普通关闭 -> 隐藏到托盘
        event.ignore()
        self.hide()

    def request_quit(self):
        self._force_quit = True
        self.close()
