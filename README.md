<p align="center"><img src="docs/banner.svg" alt="forced-reminder banner" width="100%"></p>

# 强提醒助手 · Forced Reminder

> **一个「赖着不走」的桌面周期提醒工具 —— 到点强制弹窗，不点掉就不消失。**
> A stubborn desktop reminder: when it's due, it pops up on top, modal, and won't go away until you act.

[![Python](https://img.shields.io/badge/Python-3.8-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PyQt5](https://img.shields.io/badge/PyQt5-GUI-41CD52?logo=qt&logoColor=white)](https://riverbankcomputing.com/software/pyqt/)
[![Windows](https://img.shields.io/badge/Windows-7%20%7C%2010%20%7C%2011-0078D6?logo=windows&logoColor=white)](#)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

适合任何需要**周期性、强提醒、可追溯**的场景：定时喝水/久坐提醒、轮班盯任务、每 N 分钟处理一批工单、吃药提醒……多条任务各自独立计时，到点都会用一个**难以忽略**的置顶弹窗提醒你，并记录每次完成，可导出 Excel 复盘。

## ✨ 核心设计

- **多模板并行计时** — 每条启用的模板各自独立倒计时、各自到点弹窗；多个同时到点时串行排队展示，互不遮挡。
- **绝对时间戳计时** — 下次提醒以绝对时间戳存库（`next_due_at`），关机/重启后按真实时间判断，错过的会在恢复后立即补弹，不会出现"关机一晚倒计时还停在昨天"。
- **智能周期** — 点「已完成」才按间隔重排下一次；点「稍后提醒」按配置间隔重弹并累计延迟次数。
- **强制弹窗** — 置顶 + 模态 + 无关闭按钮 + 拦截 ESC/点 X，必须点按钮才能消除。
  > 说明：桌面程序无法真正阻止用户从任务管理器结束进程，故不承诺"绝对无法关闭"，而是确保正常操作下必须响应。
- **可追溯** — 完成记录保存提醒内容快照，模板被改/删不影响历史；一键导出 Excel。

## 🚀 运行

```bash
pip install -r requirements.txt
python main.py
```

首次运行会在 `%APPDATA%\ForcedReminder\` 下生成配置和数据库，并自带一条示例模板。

## 🧱 目录结构

```
forced-reminder/
├── main.py                 # 入口：装配 DB / 引擎 / 主窗口 / 托盘
├── app/
│   ├── database.py         # SQLite 数据层（绝对时间戳、上下文管理器）
│   ├── settings.py         # config.json + 开机自启动（启动文件夹快捷方式）
│   ├── timer_engine.py     # 并行多模板计时引擎 + 弹窗队列
│   ├── reminder_dialog.py  # 强制提醒弹窗
│   ├── main_window.py      # 三 Tab 主窗口 + 弹窗编排
│   ├── tray_icon.py        # 系统托盘
│   └── exporter.py         # 导出 Excel
├── ui/styles.qss           # 全局样式
└── requirements.txt
```

## 🛠️ 几个实现取舍

1. **计时存绝对时间戳**（而非剩余秒数）—— 解决关机/重启语义。
2. **多模板并行计时** —— 贴合"多类周期任务同时进行"的真实场景。
3. **不承诺"无法 Alt+F4 关闭"** —— 改为模态+置顶+必须点按钮，因为进程级强制不可实现且体验有害。

此外：开机自启动用**启动文件夹快捷方式**（PowerShell 创建，无 pywin32 依赖）而非注册表；导出**只做 Excel**（openpyxl）。

## 📦 打包（兼容 Windows 7 / 10 / 11）

> **重要**：如果你的目标机里还有 Windows 7，而 Python 3.9+ 与 PyQt6 均已放弃 Win7，
> 因此本项目锁定 **Python 3.8 + PyQt5 + PyInstaller 5.13.2** 这套向下兼容栈，
> 一个 exe 即可在 Win7/10/11 上运行。请务必用 Python 3.8 打包，不要用 3.9+。

```bash
# 用 Python 3.8 环境
py -3.8 -m pip install -r requirements.txt pyinstaller==5.13.2
py -3.8 -m PyInstaller --noconfirm --windowed --onefile ^
  --name "强提醒助手" ^
  --add-data "ui/styles.qss;ui" ^
  main.py
```

生成物：`dist\强提醒助手.exe`（单文件，约 35MB）。

### Windows 7 运行前置条件
若在 Win7 上仍提示缺少 DLL（如 VCRUNTIME140.dll 或 api-ms-win-crt-*）：
1. 确保系统是 **Windows 7 SP1**；
2. 安装 **KB2999226**（Universal C Runtime 更新）；
3. 安装 **VC++ 2015-2019 可再发行组件**。

## 许可

[MIT](LICENSE)