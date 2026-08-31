# -*- coding: utf-8 -*-
"""桌面 GUI（tkinter，简体中文，浅色主题）。"""

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional

from . import __version__
from .formatting import (build_export_text, default_export_path, fmt_expire,
                         fmt_time, fmt_traffic, mask_url)
from .models import LV_ERROR, LV_WARN, ScanResult, SubscriptionItem

# ---------------- 配色（浅色主题） ----------------
C_BG = "#f4f6f9"
C_CARD = "#ffffff"
C_BORDER = "#dde2e8"
C_TEXT = "#1f2328"
C_MUTED = "#6b7280"
C_ACCENT = "#2563eb"
C_ACCENT_D = "#1d4ed8"
C_CUR_BG = "#e6f0ff"
C_WARN = "#b45309"
C_ERROR = "#b91c1c"
C_OK = "#15803d"

FONT = "Microsoft YaHei UI"
FONT_MONO = "Consolas"


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.result: Optional[ScanResult] = None
        self.reveal = tk.BooleanVar(value=False)
        self.q: "queue.Queue" = queue.Queue()
        self.scanning = False
        self._name_count = {}

        root.title("Clash SubScope · 订阅透镜  v%s" % __version__)
        root.geometry("1140x760")
        root.minsize(980, 640)
        root.configure(bg=C_BG)

        self._build_style()
        self._build_header()
        self._build_status()
        self._build_table()
        self._build_actions()
        self._build_bottom()

        root.after(120, self._poll)
        root.after(200, self.start_scan)

    # ------------------------------------------------------------------
    # 构建界面
    # ------------------------------------------------------------------
    def _build_style(self) -> None:
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass

        st.configure(".", background=C_BG, foreground=C_TEXT, font=(FONT, 10))
        st.configure("TFrame", background=C_BG)
        st.configure("Card.TFrame", background=C_CARD, relief="flat")
        st.configure("TLabel", background=C_BG, foreground=C_TEXT, font=(FONT, 10))
        st.configure("Card.TLabel", background=C_CARD, foreground=C_TEXT)
        st.configure("Muted.TLabel", background=C_CARD, foreground=C_MUTED, font=(FONT, 9))
        st.configure("Head.TLabel", background=C_BG, foreground=C_TEXT,
                     font=(FONT, 16, "bold"))
        st.configure("Sub.TLabel", background=C_BG, foreground=C_MUTED, font=(FONT, 9))
        st.configure("Badge.TLabel", background="#e8f5e9", foreground=C_OK,
                     font=(FONT, 9, "bold"), padding=(8, 2))

        st.configure("Accent.TButton", font=(FONT, 10, "bold"), padding=(18, 8),
                     background=C_ACCENT, foreground="#ffffff", borderwidth=0,
                     focuscolor=C_ACCENT)
        st.map("Accent.TButton",
               background=[("active", C_ACCENT_D), ("disabled", "#9db4e0")],
               foreground=[("disabled", "#ffffff")])
        st.configure("TButton", font=(FONT, 10), padding=(12, 6),
                     background="#ffffff", foreground=C_TEXT,
                     bordercolor=C_BORDER, focuscolor=C_ACCENT)
        st.map("TButton", background=[("active", "#eef2f7")])
        st.configure("TCheckbutton", background=C_CARD, foreground=C_TEXT, font=(FONT, 10))
        st.map("TCheckbutton", background=[("active", C_CARD)])

        st.configure("Treeview", background="#ffffff", fieldbackground="#ffffff",
                     foreground=C_TEXT, font=(FONT, 10), rowheight=28, borderwidth=0)
        st.configure("Treeview.Heading", background="#eef2f7", foreground=C_TEXT,
                     font=(FONT, 10, "bold"), borderwidth=0, relief="flat")
        st.map("Treeview", background=[("selected", "#cfe0ff")],
               foreground=[("selected", C_TEXT)])
        st.configure("TNotebook", background=C_BG, borderwidth=0)
        st.configure("TNotebook.Tab", font=(FONT, 10), padding=(14, 6))
        # ttk clam 主题下，选中态默认比未选中态多几像素 padding，标签会忽大忽小。
        # 把选中态的 padding 强制成相同值，同时去掉未选中标签的焦点框。
        st.map("TNotebook.Tab",
               padding=[("selected", (14, 6))],
               focuscolor=[("!selected", "")])

    def _build_header(self) -> None:
        bar = ttk.Frame(self.root, padding=(20, 14, 20, 8))
        bar.pack(fill="x")
        left = ttk.Frame(bar)
        left.pack(side="left")
        ttk.Label(left, text="Clash 订阅链接提取工具", style="Head.TLabel").pack(anchor="w")
        ttk.Label(left, text="仅读取本机已有配置，不联网、不上传、不抓取订阅内容",
                  style="Sub.TLabel").pack(anchor="w", pady=(3, 0))

        right = ttk.Frame(bar)
        right.pack(side="right")
        ttk.Label(right, text="本地只读 · 零上传", style="Badge.TLabel").pack(side="left", padx=(0, 12))
        self.btn_scan = ttk.Button(right, text="一键扫描", style="Accent.TButton",
                                   command=self.start_scan)
        self.btn_scan.pack(side="left")

    def _build_status(self) -> None:
        card = ttk.Frame(self.root, style="Card.TFrame", padding=14)
        card.pack(fill="x", padx=20, pady=(4, 10))

        self.var_client = tk.StringVar(value="客户端：正在检测…")
        self.var_core = tk.StringVar(value="核心：—")
        self.var_channel = tk.StringVar(value="接口：—")
        self.var_summary = tk.StringVar(value="订阅：—")

        row1 = ttk.Frame(card, style="Card.TFrame")
        row1.pack(fill="x")
        ttk.Label(row1, textvariable=self.var_client, style="Card.TLabel",
                  font=(FONT, 11, "bold")).pack(side="left")
        self.dot = tk.Label(row1, text="●", fg=C_MUTED, bg=C_CARD, font=(FONT, 11))
        self.dot.pack(side="left", padx=(10, 0))
        self.var_state = tk.StringVar(value="—")
        ttk.Label(row1, textvariable=self.var_state, style="Muted.TLabel").pack(side="left")

        row2 = ttk.Frame(card, style="Card.TFrame")
        row2.pack(fill="x", pady=(6, 0))
        for var, width in ((self.var_core, 260), (self.var_channel, 300)):
            ttk.Label(row2, textvariable=var, style="Muted.TLabel",
                      width=width // 8).pack(side="left")
        ttk.Label(row2, textvariable=self.var_summary, style="Muted.TLabel").pack(side="left")

    def _build_table(self) -> None:
        wrap = ttk.Frame(self.root, style="Card.TFrame")
        wrap.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        cols = (
            ("cur", "状态", 130, "center"),
            ("name", "配置名称", 196, "w"),
            ("url", "订阅链接", 360, "w"),
            ("source", "来源", 148, "w"),
            ("updated", "更新时间", 116, "center"),
            ("traffic", "流量（已用 / 总量）", 186, "w"),
            ("expire", "到期", 148, "w"),
        )
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings",
                                 selectmode="browse")
        for key, title, width, anchor in cols:
            self.tree.heading(key, text=title, anchor=anchor)
            self.tree.column(key, width=width, minwidth=60, anchor=anchor,
                             stretch=(key in ("url", "name")))
        self.tree.tag_configure("current", background=C_CUR_BG)
        self.tree.tag_configure("odd", background="#fafbfc")

        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        hs = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", lambda e: self._show_detail())
        self.tree.bind("<Double-1>", lambda e: self._copy_selected())

        self.empty_hint = ttk.Label(wrap, text="点击下方「一键扫描」开始，首次打开会自动扫描一次。",
                                    style="Card.TLabel", foreground=C_MUTED)
        self.empty_hint.place(relx=0.5, rely=0.5, anchor="center")

    def _build_actions(self) -> None:
        bar = ttk.Frame(self.root, padding=(20, 0, 20, 6))
        bar.pack(fill="x")

        self.btn_copy_one = ttk.Button(bar, text="复制选中链接", command=self._copy_selected)
        self.btn_copy_one.pack(side="left")
        self.btn_copy_all = ttk.Button(bar, text="复制全部链接", command=self._copy_all)
        self.btn_copy_all.pack(side="left", padx=8)
        self.btn_export = ttk.Button(bar, text="导出为 TXT", command=self._export)
        self.btn_export.pack(side="left")

        ttk.Checkbutton(bar, text="显示完整链接（关闭脱敏）",
                        variable=self.reveal, command=self._render_table).pack(side="left", padx=(18, 0))

        self.var_toast = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.var_toast, style="Sub.TLabel").pack(side="right")

    def _build_bottom(self) -> None:
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=False, padx=20, pady=(0, 16), ipady=2)
        nb.configure(height=190)

        f1 = ttk.Frame(nb, style="Card.TFrame")
        nb.add(f1, text="诊断与排查建议")
        self.txt_diag = tk.Text(f1, height=8, wrap="word", relief="flat",
                                bg=C_CARD, fg=C_TEXT, font=(FONT, 10),
                                padx=12, pady=10, spacing1=2, spacing3=4,
                                insertbackground=C_TEXT)
        self.txt_diag.pack(fill="both", expand=True, side="left")
        sb1 = ttk.Scrollbar(f1, command=self.txt_diag.yview)
        sb1.pack(fill="y", side="right")
        self.txt_diag.configure(yscrollcommand=sb1.set, state="disabled")

        f2 = ttk.Frame(nb, style="Card.TFrame")
        nb.add(f2, text="选中项详情")
        self.txt_detail = tk.Text(f2, height=8, wrap="word", relief="flat",
                                  bg=C_CARD, fg=C_TEXT, font=(FONT_MONO, 10),
                                  padx=12, pady=10, spacing1=2,
                                  insertbackground=C_TEXT)
        self.txt_detail.pack(fill="both", expand=True, side="left")
        sb2 = ttk.Scrollbar(f2, command=self.txt_detail.yview)
        sb2.pack(fill="y", side="right")
        self.txt_detail.configure(yscrollcommand=sb2.set, state="disabled")

        for txt in (self.txt_diag, self.txt_detail):
            txt.tag_configure("warn", foreground=C_WARN)
            txt.tag_configure("error", foreground=C_ERROR)
            txt.tag_configure("muted", foreground=C_MUTED)
            txt.tag_configure("ok", foreground=C_OK)

    # ------------------------------------------------------------------
    # 扫描
    # ------------------------------------------------------------------
    def start_scan(self) -> None:
        if self.scanning:
            return
        self.scanning = True
        self.btn_scan.configure(state="disabled", text="扫描中…")
        self._toast("正在扫描本机配置…")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self) -> None:
        try:
            from . import scanner

            def progress(msg):
                self.q.put(("progress", msg))

            result = scanner.scan(progress=progress)
            self.q.put(("done", result))
        except Exception as e:
            import traceback
            self.q.put(("fail", "%s\n%s" % (e, traceback.format_exc())))

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "progress":
                    self._toast(payload)
                elif kind == "done":
                    self._on_scanned(payload)
                elif kind == "fail":
                    self._on_failed(payload)
        except queue.Empty:
            pass
        self.root.after(120, self._poll)

    def _on_failed(self, payload: str) -> None:
        self.scanning = False
        self.btn_scan.configure(state="normal", text="一键扫描")
        self._set_text(self.txt_diag, "扫描过程中出现未捕获的异常：\n\n" + payload, "error")
        self._toast("扫描失败")
        messagebox.showerror("扫描失败",
                             "扫描过程中出现错误，详情见「诊断与排查建议」页。\n\n工具未做任何写入操作。")

    def _on_scanned(self, result: ScanResult) -> None:
        self.scanning = False
        self.btn_scan.configure(state="normal", text="一键扫描")
        self.result = result
        self._render_status()
        self._render_table()
        self._render_diag()
        self._show_detail()
        n = len(result.items)
        self._toast("扫描完成，共 %d 个订阅配置" % n)

    # ------------------------------------------------------------------
    # 渲染
    # ------------------------------------------------------------------
    def _render_status(self) -> None:
        r = self.result
        if not r:
            return
        running = [c for c in r.clients if c.running]
        if running:
            names = "、".join(c.name for c in running)
            self.var_client.set("客户端：%s" % names)
            self.dot.configure(fg=C_OK)
            self.var_state.set("运行中")
        elif r.clients:
            self.var_client.set("客户端：%s" % "、".join(c.name for c in r.clients))
            self.dot.configure(fg=C_WARN)
            self.var_state.set("未运行（仅读取本地配置）")
        else:
            self.var_client.set("客户端：未发现")
            self.dot.configure(fg=C_ERROR)
            self.var_state.set("—")

        rt = r.runtime
        if rt and rt.connected:
            self.var_core.set("核心：%s" % (rt.core_name or "未知"))
            self.var_channel.set("接口：%s" % rt.channel)
        else:
            self.var_core.set("核心：—")
            self.var_channel.set("接口：未连接（本地配置仍可用）")

        cur = sum(1 for i in r.items if i.is_current)
        self.var_summary.set("订阅：%d 个（当前使用 %d 个）" % (len(r.items), cur))

    def _display_name(self, item: SubscriptionItem) -> str:
        base = item.name or "未命名配置"
        if self._name_count.get(base, 0) > 1 and item.uid:
            return "%s（%s）" % (base, item.uid[:8])
        return base

    def _render_table(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self.empty_hint.place_forget()
        r = self.result
        if not r or not r.items:
            self.empty_hint.configure(
                text="未找到订阅配置。请查看下方「诊断与排查建议」了解原因。")
            self.empty_hint.place(relx=0.5, rely=0.5, anchor="center")
            return

        self._name_count = {}
        for it in r.items:
            self._name_count[it.name] = self._name_count.get(it.name, 0) + 1

        show_url = (lambda u: u) if self.reveal.get() else mask_url
        for idx, it in enumerate(r.items):
            tags = ("current",) if it.is_current else (("odd",) if idx % 2 else ())
            state_bits = []
            if it.is_current:
                state_bits.append("使用中")
            if it.shared_count > 1:
                state_bits.append("共用×%d" % it.shared_count)
            self.tree.insert(
                "", "end", iid=str(idx), tags=tags,
                values=(
                    "  ·  ".join(state_bits),
                    self._display_name(it),
                    show_url(it.url),
                    it.source,
                    fmt_time(it.updated),
                    fmt_traffic(it),
                    fmt_expire(it.expire),
                ),
            )
        if r.items:
            first = next((i for i, x in enumerate(r.items) if x.is_current), 0)
            self.tree.selection_set(str(first))
            self.tree.see(str(first))

    def _render_diag(self) -> None:
        r = self.result
        if not r:
            return
        self.txt_diag.configure(state="normal")
        self.txt_diag.delete("1.0", "end")
        for issue in r.issues:
            tag = issue.level if issue.level in ("warn", "error") else ""
            self.txt_diag.insert("end", issue.as_text() + "\n\n", (tag,) if tag else ())
        if not r.issues:
            self.txt_diag.insert("end", "未发现异常，一切正常。\n", ("ok",))
        self.txt_diag.configure(state="disabled")

    def _show_detail(self) -> None:
        self.txt_detail.configure(state="normal")
        self.txt_detail.delete("1.0", "end")
        item = self._selected_item()
        if item is None:
            self.txt_detail.insert("end", "在上方表格中选择一行即可查看完整信息。\n", ("muted",))
        else:
            url = item.url if self.reveal.get() else mask_url(item.url)
            lines = [
                "配置名称：%s" % item.name,
                "客户端    ：%s" % item.client_name,
                "配置 ID   ：%s" % (item.uid or "—"),
                "是否在用  ：%s" % ("是（当前生效）" if item.is_current else "否"),
                "订阅链接  ：%s" % url,
                "来源      ：%s" % item.source,
                "来源位置  ：%s" % (item.source_detail or "—"),
                "更新时间  ：%s" % fmt_time(item.updated),
                "已用流量  ：%s" % fmt_traffic(item),
                "到期时间  ：%s" % fmt_expire(item.expire),
            ]
            if item.shared_count > 1:
                lines.append("注意      ：该链接被 %d 个配置共用" % item.shared_count)
            if item.runtime_nodes is not None:
                lines.append("运行时节点数：%d" % item.runtime_nodes)
            self.txt_detail.insert("end", "\n".join(lines))
        self.txt_detail.configure(state="disabled")

    # ------------------------------------------------------------------
    # 操作
    # ------------------------------------------------------------------
    def _selected_item(self) -> Optional[SubscriptionItem]:
        if not self.result:
            return None
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return self.result.items[int(sel[0])]
        except (ValueError, IndexError):
            return None

    def _toast(self, msg: str) -> None:
        self.var_toast.set(msg)
        self.root.after(4000, lambda: self.var_toast.set("")
                        if self.var_toast.get() == msg else None)

    def _copy(self, text: str, tip: str) -> None:
        if not text:
            self._toast("没有可复制的内容")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update_idletasks()
        self._toast(tip)

    def _copy_selected(self) -> None:
        item = self._selected_item()
        if not item:
            self._toast("请先在表格中选择一行")
            return
        self._copy(item.url, "已复制 1 条订阅链接到剪贴板")

    def _copy_all(self) -> None:
        if not self.result or not self.result.items:
            self._toast("列表为空，请先扫描")
            return
        urls = [it.url for it in self.result.items if it.url]
        if not urls:
            self._toast("没有可复制的链接")
            return
        self._copy("\n".join(urls), "已复制 %d 条订阅链接到剪贴板" % len(urls))

    def _export(self) -> None:
        if not self.result or not self.result.items:
            messagebox.showinfo("无法导出", "当前没有可导出的订阅配置，请先执行扫描。")
            return
        reveal = self.reveal.get()
        if not reveal:
            ok = messagebox.askyesno(
                "导出确认",
                "当前为脱敏显示，导出的文件中订阅链接也会被打码。\n\n"
                "是否仍要导出脱敏版本？\n（选「否」可先勾选「显示完整链接」再导出）",
            )
            if not ok:
                return
        path = filedialog.asksaveasfilename(
            title="导出订阅链接",
            defaultextension=".txt",
            initialfile=os.path.basename(default_export_path()),
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            content = build_export_text(self.result, reveal=reveal)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            messagebox.showerror("导出失败", "写入文件时出错：\n%s" % e)
            return
        self._toast("已导出到 %s" % path)
        messagebox.showinfo("导出完成", "已导出到：\n%s" % path)

    @staticmethod
    def _set_text(widget: tk.Text, text: str, tag: str = "") -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", text, (tag,) if tag else ())
        widget.configure(state="disabled")


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
