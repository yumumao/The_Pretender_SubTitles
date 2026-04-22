import re
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

FPS_OPTIONS = ["23.976", "24", "25", "29.97", "30", "48", "50", "59.94", "60"]

ENCODING_CANDIDATES = [
    'utf-8-sig',
    'utf-8',
    'gb18030',
    'cp936',
    'gbk',
    'gb2312',
    'big5',
    'cp1252',
    'cp1250',
    'cp1251',
    'iso-8859-1',
]


def detect_encoding(path):
    try:
        import chardet
        with open(path, 'rb') as f:
            raw = f.read()
        guess = chardet.detect(raw)
        enc  = guess.get('encoding') or ''
        conf = guess.get('confidence', 0)
        if enc and conf >= 0.5:
            try:
                with open(path, 'r', encoding=enc, errors='strict') as f:
                    f.read()
                return enc, f'chardet {conf:.0%}'
            except (UnicodeDecodeError, LookupError):
                pass
    except ImportError:
        pass

    for enc in ENCODING_CANDIDATES:
        try:
            with open(path, 'r', encoding=enc, errors='strict') as f:
                f.read()
            return enc, 'auto-detect'
        except (UnicodeDecodeError, LookupError):
            continue

    return 'iso-8859-1', 'fallback'


def parse_ms(time_str):
    h, m, s_ms = time_str.split(':')
    s, ms = s_ms.split(',')
    return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)


def format_ms(total_ms):
    total_ms = max(0, int(round(total_ms)))
    h = total_ms // 3600000
    total_ms %= 3600000
    m = total_ms // 60000
    total_ms %= 60000
    s = total_ms // 1000
    ms = total_ms % 1000
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def convert_file(input_path, src_fps_str, dst_fps_str, offset_ms):
    src_fps = float(src_fps_str)
    dst_fps = float(dst_fps_str)
    scale   = src_fps / dst_fps

    pattern = re.compile(
        r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})'
    )

    enc, method = detect_encoding(input_path)

    with open(input_path, 'r', encoding=enc, errors='replace') as f:
        content = f.read()

    def replace_timestamps(match):
        new_start = parse_ms(match.group(1)) * scale + offset_ms
        new_end   = parse_ms(match.group(2)) * scale + offset_ms
        return f"{format_ms(new_start)} --> {format_ms(new_end)}"

    result = pattern.sub(replace_timestamps, content)

    base, ext    = os.path.splitext(input_path)
    fps_str      = dst_fps_str.replace('.', '_')
    offset_str   = f"_offset{offset_ms:+d}ms" if offset_ms != 0 else ""
    output_path  = f"{base}_{fps_str}fps{offset_str}{ext}"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(result)

    return output_path, enc, method


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SRT 字幕转换工具")
        self.resizable(True, True)
        self.minsize(660, 600)
        self.configure(bg="#f5f5f5")
        self.file_list = []
        self._check_chardet()
        self._build_ui()

    def _check_chardet(self):
        try:
            import chardet
            self._chardet_available = True
        except ImportError:
            self._chardet_available = False

    def _build_ui(self):
        # ── 顶部说明条 ────────────────────────────────────────
        info_bg   = "#e8f0fe" if self._chardet_available else "#fff3cd"
        info_fg   = "#1a3a6b" if self._chardet_available else "#7a5500"
        info_text = (
            "帧率转换 + 时间轴整体偏移，输出文件名自动附加帧率和偏移信息，编码统一转为 UTF-8。"
            f"  {'✓ chardet 已安装，编码检测最准确。' if self._chardet_available else '⚠ 未检测到 chardet，建议运行：pip install chardet'}"
        )
        info_frame = tk.Frame(self, bg=info_bg)
        info_frame.pack(fill="x", padx=16, pady=(16, 0))
        tk.Label(
            info_frame, text=info_text,
            bg=info_bg, fg=info_fg,
            font=("Microsoft YaHei", 9),
            wraplength=600, justify="left", pady=8, padx=10
        ).pack(anchor="w")

        # ── 转换设置区 ────────────────────────────────────────
        settings_frame = tk.LabelFrame(
            self, text="  转换设置  ",
            bg="#f5f5f5", fg="#333",
            font=("Microsoft YaHei", 9, "bold"),
            bd=1, relief="groove", padx=14, pady=10
        )
        settings_frame.pack(fill="x", padx=16, pady=(12, 0))

        # —— 帧率选择行 ————————————————————————————————————————
        fps_row = tk.Frame(settings_frame, bg="#f5f5f5")
        fps_row.pack(fill="x", pady=(0, 10))

        tk.Label(fps_row, text="输入帧率：",
                 bg="#f5f5f5", fg="#444",
                 font=("Microsoft YaHei", 9)).pack(side="left")
        self.src_fps_var = tk.StringVar(value="25")
        src_combo = ttk.Combobox(
            fps_row, textvariable=self.src_fps_var,
            values=FPS_OPTIONS, width=8, state="readonly"
        )
        src_combo.pack(side="left", padx=(2, 22))

        tk.Label(fps_row, text="输出帧率：",
                 bg="#f5f5f5", fg="#444",
                 font=("Microsoft YaHei", 9)).pack(side="left")
        self.dst_fps_var = tk.StringVar(value="29.97")
        dst_combo = ttk.Combobox(
            fps_row, textvariable=self.dst_fps_var,
            values=FPS_OPTIONS, width=8, state="readonly"
        )
        dst_combo.pack(side="left", padx=(2, 22))

        self.scale_label = tk.Label(
            fps_row, text="",
            bg="#f5f5f5", fg="#888",
            font=("Microsoft YaHei", 9)
        )
        self.scale_label.pack(side="left")
        self._update_scale_label()
        src_combo.bind("<<ComboboxSelected>>", lambda e: self._update_scale_label())
        dst_combo.bind("<<ComboboxSelected>>", lambda e: self._update_scale_label())

        # —— 时间轴偏移行 ——————————————————————————————————————
        offset_row = tk.Frame(settings_frame, bg="#f5f5f5")
        offset_row.pack(fill="x")

        tk.Label(offset_row, text="时间轴偏移：",
                 bg="#f5f5f5", fg="#444",
                 font=("Microsoft YaHei", 9)).pack(side="left")

        tk.Button(
            offset_row, text=" − ",
            font=("Arial", 9, "bold"),
            bg="#ddd", fg="#333", activebackground="#bbb",
            bd=0, relief="flat", cursor="hand2",
            command=lambda: self._offset_step(-100)
        ).pack(side="left", padx=(2, 0))

        self.offset_var = tk.StringVar(value="0")
        tk.Entry(
            offset_row, textvariable=self.offset_var,
            width=10, font=("Consolas", 10),
            justify="center", bd=1, relief="solid"
        ).pack(side="left", padx=2)

        tk.Button(
            offset_row, text=" + ",
            font=("Arial", 9, "bold"),
            bg="#ddd", fg="#333", activebackground="#bbb",
            bd=0, relief="flat", cursor="hand2",
            command=lambda: self._offset_step(100)
        ).pack(side="left", padx=(0, 10))

        tk.Label(
            offset_row,
            text="毫秒　（正数 = 延迟字幕，负数 = 提前字幕；± 按钮每步 100 ms）",
            bg="#f5f5f5", fg="#888",
            font=("Microsoft YaHei", 9)
        ).pack(side="left")

        # ── 文件列表 ──────────────────────────────────────────
        list_frame = tk.Frame(self, bg="#f5f5f5")
        list_frame.pack(fill="both", expand=True, padx=16, pady=10)

        tk.Label(
            list_frame, text="待转换文件列表",
            bg="#f5f5f5", fg="#333",
            font=("Microsoft YaHei", 10, "bold")
        ).pack(anchor="w")

        box_frame = tk.Frame(list_frame, bg="#f5f5f5")
        box_frame.pack(fill="both", expand=True, pady=(4, 0))

        sb_y = tk.Scrollbar(box_frame, orient="vertical")
        sb_x = tk.Scrollbar(box_frame, orient="horizontal")

        self.listbox = tk.Listbox(
            box_frame,
            selectmode="extended",
            yscrollcommand=sb_y.set,
            xscrollcommand=sb_x.set,
            font=("Consolas", 9),
            bg="white", fg="#222",
            selectbackground="#4a90d9",
            activestyle="none",
            bd=1, relief="solid", height=9
        )
        sb_y.config(command=self.listbox.yview)
        sb_x.config(command=self.listbox.xview)
        sb_y.pack(side="right", fill="y")
        sb_x.pack(side="bottom", fill="x")
        self.listbox.pack(side="left", fill="both", expand=True)

        # ── 操作按钮 ──────────────────────────────────────────
        btn_frame = tk.Frame(self, bg="#f5f5f5")
        btn_frame.pack(fill="x", padx=16, pady=(0, 6))
        s = dict(font=("Microsoft YaHei", 9), bd=0, padx=14, pady=6, cursor="hand2")

        tk.Button(btn_frame, text="＋ 添加文件",
                  bg="#4a90d9", fg="white", activebackground="#357abd",
                  command=self.add_files, **s).pack(side="left", padx=(0, 6))
        tk.Button(btn_frame, text="－ 移除选中",
                  bg="#aaa", fg="white", activebackground="#888",
                  command=self.remove_selected, **s).pack(side="left", padx=(0, 6))
        tk.Button(btn_frame, text="清空列表",
                  bg="#aaa", fg="white", activebackground="#888",
                  command=self.clear_list, **s).pack(side="left")

        # ── 进度条 ────────────────────────────────────────────
        prog_frame = tk.Frame(self, bg="#f5f5f5")
        prog_frame.pack(fill="x", padx=16, pady=(0, 4))
        self.progress_var = tk.DoubleVar()
        ttk.Progressbar(prog_frame, variable=self.progress_var,
                        maximum=100).pack(fill="x")

        # ── 日志区 ────────────────────────────────────────────
        log_frame = tk.Frame(self, bg="#f5f5f5")
        log_frame.pack(fill="x", padx=16, pady=(0, 6))
        self.log_text = tk.Text(
            log_frame, height=6,
            font=("Consolas", 9),
            bg="#1e1e1e", fg="#d4d4d4",
            bd=1, relief="solid", state="disabled"
        )
        log_sb = tk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=log_sb.set)
        log_sb.pack(side="right", fill="y")
        self.log_text.pack(fill="x")

        # ── 底部主按钮 ────────────────────────────────────────
        bottom = tk.Frame(self, bg="#f5f5f5")
        bottom.pack(fill="x", padx=16, pady=(0, 16))

        self.convert_btn = tk.Button(
            bottom, text="▶  开始转换",
            bg="#27ae60", fg="white", activebackground="#1e8449",
            font=("Microsoft YaHei", 11, "bold"),
            bd=0, padx=20, pady=10, cursor="hand2",
            command=self.start_convert
        )
        self.convert_btn.pack(side="right")

        self.status_label = tk.Label(
            bottom, text="就绪",
            bg="#f5f5f5", fg="#666",
            font=("Microsoft YaHei", 9)
        )
        self.status_label.pack(side="left", pady=4)

    # ── 辅助方法 ──────────────────────────────────────────────

    def _update_scale_label(self):
        try:
            src = float(self.src_fps_var.get())
            dst = float(self.dst_fps_var.get())
            if dst == 0:
                raise ZeroDivisionError
            scale = src / dst
            self.scale_label.config(text=f"缩放比例：{scale:.6f}")
        except (ValueError, ZeroDivisionError):
            self.scale_label.config(text="⚠ 帧率无效")

    def _offset_step(self, delta):
        try:
            current = int(self.offset_var.get())
        except ValueError:
            current = 0
        self.offset_var.set(str(current + delta))

    # ── 文件列表操作 ──────────────────────────────────────────

    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="选择 SRT 字幕文件",
            filetypes=[("SRT 字幕", "*.srt"), ("所有文件", "*.*")]
        )
        added = 0
        for p in paths:
            if p not in self.file_list:
                self.file_list.append(p)
                self.listbox.insert("end", p)
                added += 1
        if added:
            self.log(f"已添加 {added} 个文件，共 {len(self.file_list)} 个待转换")
            self.status_label.config(text=f"共 {len(self.file_list)} 个文件")

    def remove_selected(self):
        for i in reversed(self.listbox.curselection()):
            self.listbox.delete(i)
            del self.file_list[i]
        self.status_label.config(text=f"共 {len(self.file_list)} 个文件")

    def clear_list(self):
        self.listbox.delete(0, "end")
        self.file_list.clear()
        self.progress_var.set(0)
        self.status_label.config(text="就绪")

    def log(self, msg, color=None):
        tag_map = {
            "green":  "#4ec94e",
            "red":    "#f47f7f",
            "yellow": "#f0c040",
        }
        self.log_text.config(state="normal")
        if color and color in tag_map:
            self.log_text.tag_config(color, foreground=tag_map[color])
        self.log_text.insert("end", msg + "\n", color or "")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    # ── 转换入口 ──────────────────────────────────────────────

    def start_convert(self):
        if not self.file_list:
            messagebox.showwarning("提示", "请先添加要转换的 SRT 文件")
            return

        # 验证帧率
        try:
            src_fps = float(self.src_fps_var.get())
            dst_fps = float(self.dst_fps_var.get())
            if src_fps <= 0 or dst_fps <= 0:
                raise ValueError("帧率必须大于 0")
        except ValueError as e:
            messagebox.showerror("参数错误", f"帧率设置有误：{e}")
            return

        # 验证偏移量
        try:
            offset_ms = int(self.offset_var.get())
        except ValueError:
            messagebox.showerror("参数错误", "时间轴偏移量请输入整数（单位：毫秒）")
            return

        src_fps_str = self.src_fps_var.get()
        dst_fps_str = self.dst_fps_var.get()
        scale       = src_fps / dst_fps

        self.convert_btn.config(state="disabled", text="转换中…")
        self.progress_var.set(0)
        total = len(self.file_list)
        success = fail = 0

        self.log(f"── 开始批量转换，共 {total} 个文件 ──")
        self.log(f"   帧率：{src_fps_str} fps → {dst_fps_str} fps　缩放比：{scale:.6f}")
        if offset_ms != 0:
            direction = "延迟" if offset_ms > 0 else "提前"
            self.log(
                f"   时间轴偏移：{offset_ms:+d} ms（{direction} {abs(offset_ms)} 毫秒）",
                color="yellow"
            )

        for idx, path in enumerate(self.file_list, 1):
            filename = os.path.basename(path)
            try:
                out_path, enc, method = convert_file(
                    path, src_fps_str, dst_fps_str, offset_ms
                )
                out_name = os.path.basename(out_path)
                self.log(
                    f"[{idx}/{total}] ✓ {filename}  →  {out_name}  [{enc} / {method}]",
                    color="green"
                )
                success += 1
            except Exception as e:
                self.log(f"[{idx}/{total}] ✗ {filename}  错误：{e}", color="red")
                fail += 1

            self.progress_var.set(idx / total * 100)
            self.update_idletasks()

        self.log(f"── 完成：成功 {success} 个，失败 {fail} 个 ──")
        self.status_label.config(text=f"完成：{success} 成功 / {fail} 失败")
        self.convert_btn.config(state="normal", text="▶  开始转换")

        if fail == 0:
            messagebox.showinfo("完成", f"全部 {success} 个文件转换成功！\n输出文件与原文件在同一目录。")
        else:
            messagebox.showwarning(
                "完成（有错误）",
                f"成功 {success} 个，失败 {fail} 个\n请查看日志了解详情。"
            )


if __name__ == '__main__':
    app = App()
    app.mainloop()