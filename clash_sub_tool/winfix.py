# -*- coding: utf-8 -*-
"""Windows 层修复 tkinter 窗口最大化/拉伸时的黑闪。

根因：Windows 在 WM_SIZE 调整期间会先擦除客户区（用系统默认/黑色），
Tk 要等拿到新尺寸后才重绘，这段时间窗口就是黑的。

方案：用 ctypes 子类化顶层窗口过程（WndProc），接管 WM_ERASEBKGND，
用应用背景色画刷填充客户区再返回「已擦除」，从而避免黑色闪现。
其余消息全部转发给原窗口过程，对 Tk 行为零侵入。

非 Windows 平台调用 fix() 为 no-op。
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

    # 保留回调引用，防止被 GC 回收导致崩溃
    _KEEP = []

    WNDPROC_T = ctypes.WINFUNCTYPE(
        ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
        wintypes.WPARAM, wintypes.LPARAM,
    )

    GWL_WNDPROC = -4
    WM_ERASEBKGND = 0x0014

    def _parse_color(hexstr: str) -> int:
        h = hexstr.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return (b << 16) | (g << 8) | r  # COLORREF = 0x00BBGGRR

    def fix(root, bg_color="#f4f6f9"):
        """子类化 root 顶层窗口，接管背景擦除以消除黑闪。返回是否成功。"""
        try:
            hwnd = int(root.winfo_id())
            color = _parse_color(bg_color)
            brush = gdi32.CreateSolidBrush(color)

            # 设置 API 参数类型，避免 64 位下指针截断
            user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            user32.FillRect.argtypes = [
                wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.HGDIOBJ,
            ]
            user32.CallWindowProcW.argtypes = [
                ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                wintypes.WPARAM, wintypes.LPARAM,
            ]
            user32.CallWindowProcW.restype = ctypes.c_ssize_t
            user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
            user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
            user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t

            prev = user32.GetWindowLongPtrW(hwnd, GWL_WNDPROC)

            def _wndproc(hWnd, msg, wParam, lParam):
                if msg == WM_ERASEBKGND:
                    hdc = wintypes.HDC(wParam)
                    rect = wintypes.RECT()
                    user32.GetClientRect(hWnd, ctypes.byref(rect))
                    user32.FillRect(hdc, ctypes.byref(rect), brush)
                    return 1  # 已擦除，跳过系统黑色填充
                return user32.CallWindowProcW(prev, hWnd, msg, wParam, lParam)

            cb = WNDPROC_T(_wndproc)
            result = user32.SetWindowLongPtrW(hwnd, GWL_WNDPROC, cb)
            if result == 0:
                err = ctypes.GetLastError()
                if err != 0:
                    return False
            _KEEP.append((cb, brush, hwnd, prev))
            return True
        except Exception:
            return False
