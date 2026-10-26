# 自动备忘录

[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey)](#)
[![storage](https://img.shields.io/badge/storage-SQLite%20local-informational)](#)
[![network](https://img.shields.io/badge/network-none-success)](#)

Windows 桌面备忘录 / 提醒小工具：常驻悬浮条、托盘、全局热键、截图圈选 OCR 识别、
语音输入、本地 SQLite 存储。界面用 PySide6。

> 这是个人/课程项目，代码按"能跑、能读"的标准写；没有服务器、没有账号体系，数据只在本机。

## 功能

| 功能 | 说明 |
|---|---|
| 悬浮条 | 桌面常驻的小条，点开就是备忘录列表，可拖动、可贴边 |
| 快速记录 | 无标题直接写，回车即存；支持 Markdown 风格的简单排版 |
| 提醒 | 给备忘录挂时间提醒，到点系统通知 |
| 截图圈选 OCR | 全局热键圈选屏幕区域，识别文字后直接存成备忘录 |
| 语音输入 | 用系统语音识别把说的话转成文字（依赖系统能力） |
| 托盘常驻 | 关闭窗口不退出，托盘菜单里退出；可选开机自启 |

## 运行

```bash
python -m pip install -r requirements.txt
python main.py
```

数据位置：`data/`（SQLite `memos.db` + `config.json`）。删掉这个目录等于清空所有备忘录。

## 目录

```
main.py                 入口：单实例锁、托盘、热键注册、窗口装配
app/config.py           配置读写（data/config.json）
app/database.py         SQLite 存储（备忘录 / 提醒）
app/reminder.py         提醒调度（到点通知）
app/hotkeys.py          全局热键
app/ocr.py              截图圈选 + OCR
app/voice.py            语音输入
app/tray.py             托盘图标与菜单
app/autostart.py        开机自启（注册表 Run 键）
app/ui/                 悬浮条 / 主窗口 / 编辑器 / 提醒对话框 / 设置 / 圈选层
```

## 说明

- 不联网：没有上传、没有云同步、没有账号
- 语音与 OCR 优先用 Windows 自带能力，缺依赖时会在界面上说明而不是静默失败
- 本项目为个人学习用途，未做代码签名，分发给他人时 Windows 可能提示未知发布者

## 许可

[MIT](LICENSE)。
