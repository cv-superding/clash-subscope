# -*- coding: utf-8 -*-
"""Windows 层修复 tkinter 窗口最大化/拉伸时的黑闪。

## 真因（v1.2.8 实测定位 + 撤回一项错误）

实测 (`_scratch/diag_top.py`) 发现 Tk 的窗口是双层结构：

    winfo_id()            -> class=TkChild     (Tk 的内部子窗口)
    GetAncestor(GA_ROOT)  -> class=TkTopLevel  (真正的顶层窗口)

`root.winfo_id()` **不是**顶层 HWND。v1.2.3 的"三件套"全都打在了 TkChild 上，
真正的 TkTopLevel 从未被修复——`brush=0x0`（无画刷）+ `CS_HREDRAW|CS_VREDRAW`
让它在 resize 时擦除出黑底。

## 修复三件套（**v1.2.8 撤回"清除重绘标志"那一项**）

对 TkTopLevel 与 TkChild 两层都应用：

  1) **`SetClassLongPtrW(GCLP_HBRBACKGROUND)` 换成应用浅色画刷**
     —— 关键：让 resize 时系统擦除用浅色而非默认黑。
  2) **子类化 WndProc 接管 `WM_ERASEBKGND`**：用同色画刷填客户区，return 1。
  3) **`DwmSetWindowAttribute(DWMWA_TRANSITIONS_FORCEDISABLED)` 关掉缩放动画**，
     作用于真实顶层 HWND —— 消除动画期间的合成黑帧。

## ⚠️ 关键陷阱：不要清除 CS_HREDRAW | CS_VREDRAW

v1.2.8 误以为"清掉这两个标志能避免 resize 时强制擦除导致的闪烁"，于是清掉了。
实测发现这是**反作用**：Tk 这种子窗口密布的布局，子窗口之间有大量客户区空隙，
这些空隙是顶层的责任，**顶层没有重绘标志后就不刷新**——结果"左侧一块黑"。
保留 `CS_HREDRAW|CS_VREDRAW`、让系统按需重绘全部客户区，靠类背景画刷保证
擦除时是浅色而非黑——这才是正确做法。

非 Windows 平台 fix() 为 no-op。
"""

import sys

if sys.platform != "win32":
    def fix(root, bg_color="#f4f6f9"):  # noqa: D401 - platform no-op
        return False

else:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    kernel32 = ctypes.windll.kernel32

    # 保留引用，防止画刷 / 回调被 GC 回收导致崩溃
    _KEEP = []

    WNDPROC_T = ctypes.WINFUNCTYPE(
        ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
        wintypes.WPARAM, wintypes.LPARAM,
    )

    GWL_WNDPROC = -4
    GWL_EXSTYLE = -20
    GCLP_HBRBACKGROUND = -10
    GCL_STYLE = -26
    WM_ERASEBKGND = 0x0014
    DWMWA_TRANSITIONS_FORCEDISABLED = 3

    # WS_EX_COMPOSITED：整个窗口树双缓冲，画到离屏缓冲后一次性贴上屏幕。
    # 这是 Win32 解决「擦除→重绘」不同步闪烁的标准手段，对本例（任何 resize 都黑）
    # 比单纯换画刷更对症。
    WS_EX_COMPOSITED = 0x02000000

    # SetWindowPos 标志：通知 Windows 样式已变更，使其立即生效
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOZORDER = 0x0004
    SWP_FRAMECHANGED = 0x0020

    # 窗口类样式：这两个标志会让 resize 时强制擦除整个客户区 → 闪烁
    CS_VREDRAW = 0x0001
    CS_HREDRAW = 0x0002

    GA_ROOT = 2  # GetAncestor：沿父链找到根（顶层）窗口

    def _parse_color(hexstr: str) -> int:
        try:
            h = (hexstr or "").lstrip("#")
            if len(h) == 3:
                h = "".join(c * 2 for c in h)
            r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
            return (b << 16) | (g << 8) | r  # COLORREF = 0x00BBGGRR
        except Exception:
            return 0x00F4F6F9  # 兜底浅色（解析失败时不崩）

    def _top_level_hwnd(hwnd: int) -> int:
        """拿到真正的顶层 HWND。

        root.winfo_id() 返回的是 Tk 内部子窗口 TkChild，
        真正的顶层窗口（TkTopLevel）是它的祖先。v1.2.3 正是漏了这一步。
        """
        try:
            user32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
            user32.GetAncestor.restype = wintypes.HWND
            top = user32.GetAncestor(wintypes.HWND(hwnd), GA_ROOT)
            if top:
                return int(top)
        except Exception:
            pass
        try:
            user32.GetParent.argtypes = [wintypes.HWND]
            user32.GetParent.restype = wintypes.HWND
            p = user32.GetParent(wintypes.HWND(hwnd))
            if p:
                return int(p)
        except Exception:
            pass
        return hwnd

    def _apply_to_hwnd(hwnd: int, brush) -> bool:
        """对单个 HWND 应用「换画刷 + 接管擦除」。成功任一层即 True。

        ⚠️ 不要清除 CS_HREDRAW|CS_VREDRAW：这两个标志本来就让 resize 时
        强制重绘整个客户区（包括子窗口之间的空隙），对 Tk 这种子窗口密布的
        布局是必需的。v1.2.8 一度清掉它们，结果子窗口之间的空隙不再刷新，
        用户实测发现「左侧一块黑」——正是这个反作用。背景画刷换浅色就够。
        """
        ok = False

        # ---- 1) 窗口类背景画刷换成应用色（关键：保证 resize 时擦除用浅色）----
        try:
            user32.SetClassLongPtrW.argtypes = [
                wintypes.HWND, ctypes.c_int, ctypes.c_void_p,
            ]
            kernel32.SetLastError(0)
            prev_brush = user32.SetClassLongPtrW(
                wintypes.HWND(hwnd), GCLP_HBRBACKGROUND, brush)
            # 释放被替换掉的旧类画刷，避免 GDI 句柄泄漏
            try:
                gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
                gdi32.DeleteObject(wintypes.HGDIOBJ(prev_brush))
            except Exception:
                pass
            if kernel32.GetLastError() == 0:
                ok = True
        except Exception:
            pass

        # ---- 2) 子类化 WndProc 接管 WM_ERASEBKGND（应用层兜底）----
        try:
            user32.GetClientRect.argtypes = [
                wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            user32.FillRect.argtypes = [
                wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.HGDIOBJ]
            user32.CallWindowProcW.argtypes = [
                ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                wintypes.WPARAM, wintypes.LPARAM]
            user32.CallWindowProcW.restype = ctypes.c_ssize_t
            user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
            user32.SetWindowLongPtrW.argtypes = [
                wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
            user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t

            prev = user32.GetWindowLongPtrW(wintypes.HWND(hwnd), GWL_WNDPROC)
            if prev:
                def _wndproc(hWnd, msg, wParam, lParam):
                    if msg == WM_ERASEBKGND:
                        hdc = wintypes.HDC(wParam)
                        rect = wintypes.RECT()
                        user32.GetClientRect(hWnd, ctypes.byref(rect))
                        user32.FillRect(hdc, ctypes.byref(rect), brush)
                        return 1  # 已擦除，跳过系统默认填充
                    return user32.CallWindowProcW(
                        prev, hWnd, msg, wParam, lParam)

                cb = WNDPROC_T(_wndproc)
                kernel32.SetLastError(0)
                user32.SetWindowLongPtrW(wintypes.HWND(hwnd), GWL_WNDPROC, cb)
                if kernel32.GetLastError() == 0:
                    ok = True
                _KEEP.append(cb)  # 回调必须保活，否则 GC 后崩溃
        except Exception:
            pass

        return ok

    def fix(root, bg_color="#f4f6f9"):
        """消除黑闪。返回是否至少成功应用了一层修复。

        诊断开关：设环境变量 SUBSCOPE_WIN_BG=<RRGGBB> 可强制指定擦除背景色。
        例如设为 FF0000（纯红）后 resize——若闪的是红色，说明本模块的擦除
        已生效、黑色来自 Tk/ttkbootstrap 自身绘制；若仍是黑色，说明擦除未生效。
        """
        try:
            child = int(root.winfo_id())
        except Exception:
            return False

        import os

        # 诊断用：允许用环境变量覆盖背景色（默认用应用浅色）
        eff = os.environ.get("SUBSCOPE_WIN_BG")
        color = _parse_color(("#" + eff) if eff else bg_color)
        brush = gdi32.CreateSolidBrush(color)
        _KEEP.append(brush)  # 画刷必须保活

        # 关键：winfo_id() 给的是 TkChild，必须另外拿到真正的顶层 TkTopLevel
        top = _top_level_hwnd(child)

        ok = False
        seen = []
        for hwnd in (top, child):
            if hwnd and hwnd not in seen:
                seen.append(hwnd)
                try:
                    if _apply_to_hwnd(hwnd, brush):
                        ok = True
                except Exception:
                    pass

        # ---- 3) WS_EX_COMPOSITED 双缓冲：**默认关闭**（仅环境变量可开）----
        # 它能消除黑闪，但对 Tk 是性能灾难：Tk 的每个 widget 都是独立 HWND 子窗口，
        # 本界面有几十个，双缓冲会让整个窗口树在每次 resize 时全量重绘到离屏缓冲，
        # 实测拖动窗口卡 ~10 秒 —— 远比黑闪严重，因此默认不启用。
        # 仅当 SUBSCOPE_COMPOSITED=1 时开启，用于验证「双缓冲确实能去黑闪」这一结论。
        if os.environ.get("SUBSCOPE_COMPOSITED") == "1":
            try:
                user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
                user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
                user32.SetWindowLongPtrW.argtypes = [
                    wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
                user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t

                cur = user32.GetWindowLongPtrW(wintypes.HWND(top), GWL_EXSTYLE)
                if not (cur & WS_EX_COMPOSITED):
                    user32.SetWindowLongPtrW(
                        wintypes.HWND(top), GWL_EXSTYLE,
                        ctypes.c_ssize_t(cur | WS_EX_COMPOSITED))
                    # 必须显式通知 Windows 样式已变更，否则不会立即生效
                    user32.SetWindowPos.argtypes = [
                        wintypes.HWND, wintypes.HWND, ctypes.c_int,
                        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
                    user32.SetWindowPos(
                        wintypes.HWND(top), wintypes.HWND(0), 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
            except Exception:
                pass

        # ---- 4) 关闭 DWM 最大化/最小化缩放动画（作用于真实顶层）----
        try:
            dwmapi = ctypes.windll.dwmapi
            attr = ctypes.c_int(1)  # TRUE：强制禁用过渡动画
            dwmapi.DwmSetWindowAttribute.argtypes = [
                wintypes.HWND, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
            dwmapi.DwmSetWindowAttribute.restype = ctypes.c_int
            dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(top), DWMWA_TRANSITIONS_FORCEDISABLED,
                ctypes.byref(attr), ctypes.sizeof(attr))
        except Exception:
            pass

        return ok
