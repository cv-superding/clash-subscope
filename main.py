# -*- coding: utf-8 -*-
"""Clash 订阅链接提取工具 —— 入口。

本工具只读取本机已有的客户端配置文件，并可选通过本机回环地址 /
本地命名管道查询正在运行的核心状态。不会对订阅链接发起任何网络请求，
不会向任何服务器上传数据。
"""

import os
import sys

# Windows 高分屏下让字体清晰
if sys.platform == "win32":
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            from ctypes import windll

            windll.user32.SetProcessDPIAware()
        except Exception:
            pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    try:
        import ttkbootstrap  # 现代化 UI 主题（cosmo）
    except ImportError:
        sys.stderr.write("依赖缺失：缺少 ttkbootstrap，请执行 pip install ttkbootstrap\n")
        return 1

    try:
        from clash_sub_tool.ui import App
    except ImportError as e:
        sys.stderr.write("依赖缺失或模块导入失败：%s\n若缺少 PyYAML 请执行 pip install pyyaml\n" % e)
        return 1

    root = ttkbootstrap.Window(themename="cosmo")
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
