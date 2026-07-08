"""系统托盘图标与菜单。"""

from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAction, QMenu, QSystemTrayIcon


def make_brand_icon() -> QIcon:
    """无外部图标资源时，用品牌色绘制一个简易贝壳风格图标。"""
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    # 海洋蓝圆底 + 碧波绿弧
    p.setBrush(QColor("#1A8CFF"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(6, 6, 52, 52)
    p.setBrush(QColor("#00D4AA"))
    p.drawChord(16, 20, 32, 40, 30 * 16, 120 * 16)
    p.end()
    return QIcon(pix)


class TrayIcon(QSystemTrayIcon):
    """托盘图标。

    回调由主窗口注入：on_show / on_toggle_pause / on_quit。
    """

    def __init__(self, icon: QIcon, on_show, on_toggle_pause, on_quit, parent=None):
        super().__init__(icon, parent)
        self.on_show = on_show
        self.on_toggle_pause = on_toggle_pause
        self.on_quit = on_quit
        self._paused = False

        self.setToolTip("强提醒助手")
        self._build_menu()
        self.activated.connect(self._on_activated)

    def _build_menu(self):
        menu = QMenu()
        self.act_show = QAction("显示主窗口", menu)
        self.act_show.triggered.connect(lambda: self.on_show())

        self.act_pause = QAction("暂停提醒", menu)
        self.act_pause.triggered.connect(self._toggle_pause)

        act_quit = QAction("退出", menu)
        act_quit.triggered.connect(lambda: self.on_quit())

        menu.addAction(self.act_show)
        menu.addAction(self.act_pause)
        menu.addSeparator()
        menu.addAction(act_quit)
        self.setContextMenu(menu)

    def _toggle_pause(self):
        self._paused = not self._paused
        self.act_pause.setText("恢复提醒" if self._paused else "暂停提醒")
        self.on_toggle_pause(self._paused)
        self.showMessage(
            "强提醒",
            "提醒已暂停" if self._paused else "提醒已恢复",
            QSystemTrayIcon.Information, 2000,
        )

    def _on_activated(self, reason):
        # 左键单击切换主窗口显示
        if reason == QSystemTrayIcon.Trigger:
            self.on_show()
