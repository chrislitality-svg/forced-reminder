"""并行多模板计时引擎。

模型：
- 每条**启用**模板各自持有一个绝对到期时间 next_due_at（存于数据库）。
- 一个 1 秒心跳 QTimer 周期性检查所有启用模板，凡 now >= next_due_at 的，
  推入「待弹窗队列」，并立即把该模板标记为「弹窗中」以避免重复入队。
- 弹窗**串行**展示：同一时刻只显示一个提醒窗，其余在队列等待，
  避免多个模态窗互相遮挡。
- 用户在弹窗中：
    * 点「已完成」  -> 记录完成，按 interval 重排该模板下次到期；
    * 点「稍后提醒」-> 按 snooze_minutes 重排，delay_count + 1。
- 暂停：心跳停止；恢复后按绝对时间判断，错过的会立即补弹。
"""

from datetime import datetime

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from .database import parse_dt


class TimerEngine(QObject):
    """负责调度，但不负责 UI。需要弹窗时发出 reminder_due 信号。"""

    # 参数为模板字典（含 id/template_name/content/interval_minutes 等）
    reminder_due = pyqtSignal(dict)

    def __init__(self, db, config: dict, parent=None):
        super().__init__(parent)
        self.db = db
        self.config = config
        self.paused = False

        # 正在等待用户处理（已入队或正在弹）的模板 id，防止重复入队
        self._pending_ids = set()
        # 待展示队列（模板 id 列表，保持先到先弹）
        self._queue = []
        # 当前是否有弹窗正在显示
        self._showing = False

        self._heartbeat = QTimer(self)
        self._heartbeat.setInterval(1000)  # 1 秒
        self._heartbeat.timeout.connect(self._tick)

    # ---------- 生命周期 ----------

    def start(self):
        """启动引擎：补排程未排程的启用模板，然后开始心跳。"""
        self.db.ensure_scheduled()
        self._heartbeat.start()

    def stop(self):
        self._heartbeat.stop()

    def set_paused(self, paused: bool):
        self.paused = paused

    # ---------- 心跳 ----------

    def _tick(self):
        """每秒检查到期模板。"""
        if self.paused:
            return
        now = datetime.now()
        for tpl in self.db.list_templates(only_active=True):
            tid = tpl["id"]
            if tid in self._pending_ids:
                continue
            due_s = tpl["next_due_at"]
            if not due_s:
                # 理论上 ensure_scheduled 已处理，这里兜底
                self.db.schedule_from_now(tid, tpl["interval_minutes"])
                continue
            try:
                if now >= parse_dt(due_s):
                    self._enqueue(tid)
            except ValueError:
                # 时间字段损坏：重排，避免卡死
                self.db.schedule_from_now(tid, tpl["interval_minutes"])
        self._pump()

    def _enqueue(self, template_id: int):
        self._pending_ids.add(template_id)
        self._queue.append(template_id)

    def _pump(self):
        """若当前无弹窗且队列非空，弹出下一个。"""
        if self._showing or not self._queue:
            return
        tid = self._queue.pop(0)
        tpl = self.db.get_template(tid)
        if not tpl or not tpl["is_active"]:
            # 模板在等待期间被删除/停用，丢弃
            self._pending_ids.discard(tid)
            self._pump()
            return
        self._showing = True
        # 附带提醒弹出时间，供完成记录使用
        tpl = dict(tpl)
        tpl["_reminded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.reminder_due.emit(tpl)

    # ---------- 弹窗回调（由主窗口在用户操作后调用） ----------

    def on_completed(self, template_id: int):
        """用户点了「已完成」：按 interval 重排，释放队列。"""
        tpl = self.db.get_template(template_id)
        if tpl:
            self.db.schedule_from_now(template_id, tpl["interval_minutes"])
        self._release(template_id)

    def on_snoozed(self, template_id: int):
        """用户点了「稍后提醒」：按 snooze 间隔重排。"""
        snooze = int(self.config.get("snooze_minutes", 1))
        self.db.schedule_from_now(template_id, snooze)
        self._release(template_id)

    def _release(self, template_id: int):
        self._pending_ids.discard(template_id)
        self._showing = False
        # 立即尝试弹出队列中下一个
        self._pump()
