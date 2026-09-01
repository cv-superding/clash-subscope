# -*- coding: utf-8 -*-
"""Windows 层修复 tkinter 窗口最大化/拉伸时的黑闪。

## 真正的根因（v1.2.8 实测定位，推翻 v1.2.3 的错误诊断）

**v1.2.3 的修复完全打错了对象。** 实测 (`_scratch/diag_top.py`)：

    winfo_id()          -> class=TkChild      (Tk 的内部子窗口)
    GetAncestor(GA_ROOT)-> class=TkTopLevel   (真正的顶层窗口)

`root.winfo_id()` 返回的**不是**顶层 HWND，而是 Tk 用来承载控件的内部子窗口
`TkChild`。所以 v1.2.3 那三件套（类画刷 / WM_ERASEBKGND / DWM 关动画）
全都作用在了 TkChild 上，真正的顶层窗口 TkTopLevel **从未被修复**——
它一直是 brush=0x0（无画刷，系统默认黑）+ CS_HREDRAW|CS_VREDRAW。

## 本版方案（四管齐下，任一失败不影响其余）

对 **TkTopLevel（顶层）和 TkChild（子窗口）两者**都应用：

  1) **清除窗口类的 CS_HREDRAW | CS_VREDRAW**
     这两个标志会让 Windows 在尺寸变化时**强制擦除并重绘整个客户区**，
     是 Win32 闪烁最经典的根因。清掉后 resize 不再触发全区域擦除。
  2) **SetClassLongPtrW(GCLP_HBRBACKGROUND) 换成应用背景色画刷**
     让必须擦除时用浅色而非系统默认黑。
  3) **子类化 WndProc 接管 WM_ERASEBKGND**，用同色画刷填客户区后返回「已擦除」。
  4) **DwmSetWindowAttribute(DWMWA_TRANSITIONS_FORCEDISABLED)** 关闭最大化缩放动画，
     消除动画期间的合成黑帧（作用在当前真实顶层 HWND 上）。

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
    GCLP_HBRBACKGROUND = -10
    GCL_STYLE = -26
    WM_ERASEBKGND = 0x0014
    DWMWA_TRANSITIONS_FORCEDISABLED = 3

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
        """对单个 HWND 应用「清重绘标志 + 换画刷 + 接管擦除」。成功任一层即 True。"""
        ok = False

        # ---- 1) 清除 CS_HREDRAW | CS_VREDRAW（resize 不再强制全擦除）----
        try:
            user32.GetClassLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.GetClassLongPtrW.restype = ctypes.c_ssize_t
            user32.SetClassLongPtrW.argtypes = [
                wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t,
            ]
            user32.SetClassLongPtrW.restype = ctypes.c_ssize_t

            cur = user32.GetClassLongPtrW(wintypes.HWND(hwnd), GCL_STYLE)
            if cur and (cur & (CS_HREDRAW | CS_VREDRAW)):
                kernel32.SetLastError(0)
                user32.SetClassLongPtrW(
                    wintypes.HWND(hwnd), GCL_STYLE,
                    ctypes.c_ssize_t(cur & ~(CS_HREDRAW | CS_VREDRAW)),
                )
                if kernel32.GetLastError() == 0:
                    ok = True
        except Exception:
            pass

        # ---- 2) 窗口类背景画刷换成应用色 ----
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

        # ---- 3) 子类化 WndProc 接管 WM_ERASEBKGND ----
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
        """消除黑闪。返回是否至少成功应用了一层修复。"""
        try:
            child = int(root.winfo_id())
        except Exception:
            return False

        color = _parse_color(bg_color)
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
