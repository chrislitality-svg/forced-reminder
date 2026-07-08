"""强提醒助手 —— 程序入口。"""

import os
import sys

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QInputDialog, QMessageBox

from app import APP_NAME, ORG_NAME
from app.database import Database
from app.main_window import MainWindow
from app.settings import load_config, save_config
from app.timer_engine import TimerEngine
from app.tray_icon import TrayIcon, make_brand_icon


def _load_stylesheet() -> str:
    """加载 QSS 全局样式（缺失则返回空串，不影响运行）。"""
    qss_path = os.path.join(os.path.dirname(__file__), "ui", "styles.qss")
    try:
        with open(qss_path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _seed_default_templates(db: Database):
    """首次运行无任何模板时，写入一条示例模板。"""
    if not db.list_templates():
        db.add_template(
            "处理退款工单",
            "请及时处理待审核的退款申请。",
            interval_minutes=30,
            is_active=1,
        )


def ensure_operator_name(db) -> bool:
    """首次启动引导填写姓名。已填过则跳过。

    返回 False 表示用户取消（此时不进入主程序）。
    """
    name = (db.get_setting("operator_name", "") or "").strip()
    if name:
        return True
    while True:
        text, ok = QInputDialog.getText(
            None, "请填写姓名",
            "欢迎使用强提醒助手\n首次使用请填写您的姓名：",
        )
        if not ok:
            return False  # 用户点了取消
        text = text.strip()
        if text:
            db.set_setting("operator_name", text)
            return True
        QMessageBox.warning(None, "提示", "姓名不能为空，请填写。")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setFont(QFont("微软雅黑", 10))
    # 关闭最后一个窗口时不退出（要常驻托盘）
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(_load_stylesheet())

    config = load_config()

    try:
        db = Database(config["db_path"])
    except Exception as e:
        QMessageBox.critical(None, "启动失败", f"数据库初始化失败：\n{e}")
        return 1

    _seed_default_templates(db)

    # 首次启动先引导填写姓名；用户取消则不进入
    if not ensure_operator_name(db):
        return 0

    engine = TimerEngine(db, config)
    window = MainWindow(db, config, engine)
    icon = make_brand_icon()
    window.setWindowIcon(icon)

    def on_quit():
        engine.stop()
        save_config(config)
        window.request_quit()
        app.quit()

    tray = TrayIcon(
        icon,
        on_show=lambda: (window.showNormal(), window.activateWindow()),
        on_toggle_pause=engine.set_paused,
        on_quit=on_quit,
        parent=window,
    )
    tray.show()

    engine.start()
    window.show()

    exit_code = app.exec()
    save_config(config)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
