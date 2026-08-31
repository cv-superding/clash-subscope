# -*- coding: utf-8 -*-
"""Windows 层修复 tkinter 窗口最大化/拉伸时的黑闪。

根因（更完整）：
  Windows 在窗口尺寸变化（尤其最大化）期间，会用「窗口类背景画刷」先擦除客户区；
  Tk 自带的顶层窗口类背景多半是黑色/未定义，于是出现「黑一下再恢复」。
  更麻烦的是 DWM 的最大化缩放动画会把这份未上色的背景合成进动画帧，
  单靠应用层 WM_ERASEBKGND 兜底盖不住 —— 这正是 v1.2.1/1.2.2 修不掉的原因。

方案（三管齐下，任一失败不影响其余）：
  1) SetClassLongPtrW(GCLP_HBRBACKGROUND) 把窗口类背景画刷换成应用背景色，
     让 Windows / DWM 自己擦底色时就是浅色，从源头消除黑；
  2) 子类化 WndProc 接管 WM_ERASEBKGND，用同色画刷填客户区再返回「已擦除」；
  3) DwmSetWindowAttribute(DWMWA_TRANSITIONS_FORCEDISABLED) 关闭最大化缩放动画，
     进一步消除动画期间的合成黑帧。
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
    WM_ERASEBKGND = 0x0014
    DWMWA_TRANSITIONS_FORCEDISABLED = 3

    def _parse_color(hexstr: str) -> int:
        h = hexstr.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return (b << 16) | (g << 8) | r  # COLORREF = 0x00BBGGRR

    def fix(root, bg_color="#f4f6f9"):
        """消除黑闪。返回是否至少成功应用了一层修复。"""
        try:
            hwnd = int(root.winfo_id())
        except Exception:
            return False

        color = _parse_color(bg_color)
        brush = gdi32.CreateSolidBrush(color)
        _KEEP.append(brush)  # 保活画刷

        ok = False

        # ---- 1) 窗口类背景画刷换成应用色（覆盖 DWM 合成层）----
        try:
            kernel32.SetLastError(0)
            user32.SetClassLongPtrW.argtypes = [
                wintypes.HWND, ctypes.c_int, ctypes.c_void_p,
            ]
            user32.SetClassLongPtrW.restype = ctypes.c_ssize_t
            user32.SetClassLongPtrW(hwnd, GCLP_HBRBACKGROUND, brush)
            if kernel32.GetLastError() == 0:
                ok = True
        except Exception:
            pass

        # ---- 2) 子类化 WndProc 接管 WM_ERASEBKGND（应用层兜底）----
        try:
            kernel32.SetLastError(0)
            user32.GetClientRect.argtypes = [
                wintypes.HWND, ctypes.POINTER(wintypes.RECT),
            ]
            user32.FillRect.argtypes = [
                wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.HGDIOBJ,
            ]
            user32.CallWindowProcW.argtypes = [
                ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                wintypes.WPARAM, wintypes.LPARAM,
            ]
            user32.CallWindowProcW.restype = ctypes.c_ssize_t
            user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
            user32.SetWindowLongPtrW.argtypes = [
                wintypes.HWND, ctypes.c_int, ctypes.c_void_p,
            ]
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
            user32.SetWindowLongPtrW(hwnd, GWL_WNDPROC, cb)
            if kernel32.GetLastError() == 0:
                ok = True
            _KEEP.append((cb, hwnd, prev))
        except Exception:
            pass

        # ---- 3) 关闭 DWM 最大化/最小化缩放动画（消除动画黑帧）----
        try:
            dwmapi = ctypes.windll.dwmapi
            kernel32.SetLastError(0)
            attr = ctypes.c_int(1)  # TRUE：强制禁用过渡动画
            dwmapi.DwmSetWindowAttribute.argtypes = [
                wintypes.HWND, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint,
            ]
            dwmapi.DwmSetWindowAttribute.restype = ctypes.c_int
            dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_TRANSITIONS_FORCEDISABLED,
                ctypes.byref(attr), ctypes.sizeof(attr),
            )
            if kernel32.GetLastError() == 0:
                ok = True
        except Exception:
            pass

        return ok
