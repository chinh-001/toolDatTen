"""
HighlightDurationTab - Giao diện và logic cho Tab Tính Toán & Kiểm Tra Thời Lượng Highlight Video.
Hỗ trợ dán dữ liệu 3 cột (Tiêu đề, Link, Highlight), phân tách tự động và lọc theo khoảng thời lượng [Min A - Max B].

Quy định màu sắc:
- TRONG KHOẢNG (Min A <= Thời lượng <= Max B): MÀU XANH (🟢 Green)
- NGOÀI KHOẢNG (< Min A hoặc > Max B): MÀU ĐỎ (🔴 Red)
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core.highlight_duration_calculator import (
    parse_3column_input,
    filter_entries_by_duration,
    export_entries_to_tsv,
    export_entries_to_csv,
    format_duration_str,
)
from gui.dialog_highlight_split import HighlightSplitDialog



class HighlightDurationTab(ttk.Frame):
    """Tab Tính toán thời lượng Highlight & Lọc theo khoảng [Min A - Max B]."""

    def __init__(self, parent, log_panel, **kwargs):
        super().__init__(parent, **kwargs)
        self.log_panel = log_panel

        # State variables
        self._min_sec = tk.IntVar(value=60)  # Mặc định 60 giây
        self._max_sec = tk.IntVar(value=90)  # Mặc định 90 giây
        self._entries = []
        self._in_range_entries = []   # Trong khoảng (MÀU XANH)
        self._out_range_entries = []  # Ngoài khoảng (MÀU ĐỎ)

        self._build_ui()

    def _build_ui(self):
        """Xây dựng toàn bộ giao diện cho Tab."""
        # Top section: Input Controls & Settings
        top_frame = ttk.LabelFrame(
            self,
            text="📥 Nhập dữ liệu 3 cột & ⚙️ Cài đặt khoảng lọc thời lượng [Min A - Max B]",
            style='Section.TLabelframe',
            padding=8
        )
        top_frame.pack(fill='x', pady=(0, 6))

        self._build_input_and_settings(top_frame)

        # Main Split View (PanedWindow) cho 2 bảng: Trong khoảng (Xanh) và Ngoài khoảng (Đỏ)
        paned = ttk.PanedWindow(self, orient='vertical')
        paned.pack(fill='both', expand=True, pady=(0, 4))

        # --- Section 1: Video TRONG KHOẢNG (🟢 Min <= Dur <= Max - MÀU XANH) ---
        in_range_frame = ttk.LabelFrame(
            paned,
            text="🟢 Danh Sách Highlight TRONG KHOẢNG (Min A <= Thời lượng <= Max B)",
            style='Section.TLabelframe',
            padding=6
        )
        paned.add(in_range_frame, weight=1)
        self._build_in_range_section(in_range_frame)

        # --- Section 2: Video NGOÀI KHOẢNG (🔴 < Min A hoặc > Max B - MÀU ĐỎ) ---
        out_range_frame = ttk.LabelFrame(
            paned,
            text="🔴 Danh Sách Highlight NGOÀI KHOẢNG (< Min A hoặc > Max B)",
            style='Section.TLabelframe',
            padding=6
        )
        paned.add(out_range_frame, weight=1)
        self._build_out_range_section(out_range_frame)

        # Context Menu setup
        self._build_context_menus()

    def _build_input_and_settings(self, parent):
        """Xây dựng phần nhập dữ liệu và chỉnh khoảng lọc Min/Max."""
        parent.columnconfigure(0, weight=1)

        # Sub-frame 1: Input Text Area
        lbl_info = ttk.Label(
            parent,
            text="Dán dữ liệu dạng bảng (Cột 1: Tiêu đề | Cột 2: Link Video | Cột 3: Highlight):",
            font=('Segoe UI', 9, 'bold')
        )
        lbl_info.pack(anchor='w', pady=(0, 2))

        input_container = ttk.Frame(parent)
        input_container.pack(fill='x', pady=(0, 6))

        self.txt_input = tk.Text(
            input_container,
            height=4,
            font=('Segoe UI', 9),
            wrap='none',
            bg='#ffffff',
            relief='solid',
            bd=1
        )
        sc_input_y = ttk.Scrollbar(input_container, orient='vertical', command=self.txt_input.yview)
        sc_input_x = ttk.Scrollbar(input_container, orient='horizontal', command=self.txt_input.xview)
        self.txt_input.configure(yscrollcommand=sc_input_y.set, xscrollcommand=sc_input_x.set)

        sc_input_y.pack(side='right', fill='y')
        sc_input_x.pack(side='bottom', fill='x')
        self.txt_input.pack(side='left', fill='both', expand=True)

        # Sub-frame 2: Controls & Range setting row
        ctrl_row = ttk.Frame(parent)
        ctrl_row.pack(fill='x')

        # Left side: Action Buttons
        btn_paste = ttk.Button(ctrl_row, text="📋 Dán từ Clipboard", command=self._on_paste_clipboard)
        btn_paste.pack(side='left', padx=(0, 6))

        btn_parse = ttk.Button(ctrl_row, text="⚡ Phân Tách & Tính Thời Lượng", style='Action.TButton', command=self._on_calculate)
        btn_parse.pack(side='left', padx=(0, 6))

        btn_split_top = ttk.Button(ctrl_row, text="✂️ Cắt Highlight Theo Thời Lượng...", command=self._on_open_split_all_dialog)
        btn_split_top.pack(side='left', padx=(0, 6))

        btn_clear = ttk.Button(ctrl_row, text="🧹 Xóa dữ liệu", command=self._on_clear)
        btn_clear.pack(side='left', padx=(0, 16))

        # Right side: Range Spinboxes & Preset Buttons
        range_frame = ttk.Frame(ctrl_row)
        range_frame.pack(side='right')

        ttk.Label(range_frame, text="⏱️ Khoảng lọc (Min - Max):", font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(0, 4))

        self.spin_min = ttk.Spinbox(range_frame, from_=1, to=7200, textvariable=self._min_sec, width=5)
        self.spin_min.pack(side='left', padx=1)

        ttk.Label(range_frame, text="-", font=('Segoe UI', 9, 'bold')).pack(side='left', padx=2)

        self.spin_max = ttk.Spinbox(range_frame, from_=1, to=7200, textvariable=self._max_sec, width=5)
        self.spin_max.pack(side='left', padx=1)

        ttk.Label(range_frame, text="giây", font=('Segoe UI', 9)).pack(side='left', padx=(2, 6))

        # Preset buttons
        ttk.Button(range_frame, text="30s-45s", command=lambda: self._set_range(30, 45)).pack(side='left', padx=1)
        ttk.Button(range_frame, text="45s-60s", command=lambda: self._set_range(45, 60)).pack(side='left', padx=1)
        ttk.Button(range_frame, text="60s-90s (1p-1p30)", command=lambda: self._set_range(60, 90)).pack(side='left', padx=1)
        ttk.Button(range_frame, text="90s-120s (1p30-2p)", command=lambda: self._set_range(90, 120)).pack(side='left', padx=1)
        ttk.Button(range_frame, text="120s-180s (2p-3p)", command=lambda: self._set_range(120, 180)).pack(side='left', padx=1)

    def _build_in_range_section(self, parent):
        """Xây dựng phần danh sách video TRONG KHOẢNG (A <= dur <= B) - MÀU XANH."""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill='x', pady=(0, 4))

        self.lbl_in_range_stats = ttk.Label(
            toolbar,
            text="Số lượng: 0 video | Tổng thời lượng highlight: 00m 00s",
            font=('Segoe UI', 9, 'bold'),
            foreground='#27ae60'  # MÀU XANH
        )
        self.lbl_in_range_stats.pack(side='left', anchor='w')

        # Action Buttons cho video trong khoảng
        btn_copy = ttk.Button(
            toolbar,
            text="📋 Copy Bảng Trong Khoảng (Form Excel)",
            command=lambda: self._copy_table_tsv(self._in_range_entries, "Trong khoảng (MÀU XANH)")
        )
        btn_copy.pack(side='right', padx=(6, 0))

        btn_export = ttk.Button(
            toolbar,
            text="📥 Xuất File Excel / CSV...",
            command=lambda: self._export_to_file(self._in_range_entries, "trong_khoang")
        )
        btn_export.pack(side='right', padx=(6, 0))

        btn_split = ttk.Button(
            toolbar,
            text="✂️ Cắt Các Hàng TRONG KHOẢNG...",
            style='Action.TButton',
            command=self._on_open_split_in_range_dialog
        )
        btn_split.pack(side='right')

        # Treeview Table cho Video Trong Khoảng
        cols = ('stt', 'title', 'url', 'highlight', 'segments', 'duration', 'seconds')
        self.tree_short = ttk.Treeview(parent, columns=cols, show='headings', selectmode='extended', height=5)

        self.tree_short.heading('stt', text='#')
        self.tree_short.heading('title', text='Tiêu Đề Video')
        self.tree_short.heading('url', text='Link Video')
        self.tree_short.heading('highlight', text='Chuỗi Highlight')
        self.tree_short.heading('segments', text='Số đoạn')
        self.tree_short.heading('duration', text='Thời lượng')
        self.tree_short.heading('seconds', text='Số giây')

        self.tree_short.column('stt', width=40, minwidth=40, anchor='center')
        self.tree_short.column('title', width=220, minwidth=140)
        self.tree_short.column('url', width=220, minwidth=140)
        self.tree_short.column('highlight', width=220, minwidth=140)
        self.tree_short.column('segments', width=65, minwidth=50, anchor='center')
        self.tree_short.column('duration', width=95, minwidth=80, anchor='center')
        self.tree_short.column('seconds', width=75, minwidth=60, anchor='center')

        sc_y = ttk.Scrollbar(parent, orient='vertical', command=self.tree_short.yview)
        sc_x = ttk.Scrollbar(parent, orient='horizontal', command=self.tree_short.xview)
        self.tree_short.configure(yscrollcommand=sc_y.set, xscrollcommand=sc_x.set)

        sc_y.pack(side='right', fill='y')
        sc_x.pack(side='bottom', fill='x')
        self.tree_short.pack(side='top', fill='both', expand=True)

        # TAG MÀU XANH cho dòng trong khoảng
        self.tree_short.tag_configure('in_range_row', background='#d5f5e3')

    def _build_out_range_section(self, parent):
        """Xây dựng phần danh sách video NGOÀI KHOẢNG (< Min hoặc > Max) - MÀU ĐỎ."""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill='x', pady=(0, 4))

        self.lbl_out_range_stats = ttk.Label(
            toolbar,
            text="Số lượng: 0 video | Tổng thời lượng highlight: 00m 00s",
            font=('Segoe UI', 9, 'bold'),
            foreground='#e74c3c'  # MÀU ĐỎ
        )
        self.lbl_out_range_stats.pack(side='left', anchor='w')

        # Action Buttons cho video ngoài khoảng
        btn_copy = ttk.Button(
            toolbar,
            text="📋 Copy Bảng Ngoài Khoảng (Form Excel)",
            command=lambda: self._copy_table_tsv(self._out_range_entries, "Ngoài khoảng (MÀU ĐỎ)")
        )
        btn_copy.pack(side='right', padx=(6, 0))

        btn_export = ttk.Button(
            toolbar,
            text="📥 Xuất File Excel / CSV...",
            command=lambda: self._export_to_file(self._out_range_entries, "ngoai_khoang")
        )
        btn_export.pack(side='right', padx=(6, 0))

        btn_split = ttk.Button(
            toolbar,
            text="✂️ Cắt Các Hàng NGOÀI KHOẢNG...",
            style='Action.TButton',
            command=self._on_open_split_out_range_dialog
        )
        btn_split.pack(side='right')

        # Treeview Table cho Video Ngoài Khoảng
        cols = ('stt', 'title', 'url', 'highlight', 'segments', 'duration', 'seconds')
        self.tree_long = ttk.Treeview(parent, columns=cols, show='headings', selectmode='extended', height=5)

        self.tree_long.heading('stt', text='#')
        self.tree_long.heading('title', text='Tiêu Đề Video')
        self.tree_long.heading('url', text='Link Video')
        self.tree_long.heading('highlight', text='Chuỗi Highlight')
        self.tree_long.heading('segments', text='Số đoạn')
        self.tree_long.heading('duration', text='Thời lượng')
        self.tree_long.heading('seconds', text='Số giây')

        self.tree_long.column('stt', width=40, minwidth=40, anchor='center')
        self.tree_long.column('title', width=220, minwidth=140)
        self.tree_long.column('url', width=220, minwidth=140)
        self.tree_long.column('highlight', width=220, minwidth=140)
        self.tree_long.column('segments', width=65, minwidth=50, anchor='center')
        self.tree_long.column('duration', width=95, minwidth=80, anchor='center')
        self.tree_long.column('seconds', width=75, minwidth=60, anchor='center')

        sc_y = ttk.Scrollbar(parent, orient='vertical', command=self.tree_long.yview)
        sc_x = ttk.Scrollbar(parent, orient='horizontal', command=self.tree_long.xview)
        self.tree_long.configure(yscrollcommand=sc_y.set, xscrollcommand=sc_x.set)

        sc_y.pack(side='right', fill='y')
        sc_x.pack(side='bottom', fill='x')
        self.tree_long.pack(side='top', fill='both', expand=True)

        # TAG MÀU ĐỎ cho dòng ngoài khoảng
        self.tree_long.tag_configure('out_range_row', background='#fadbd8')

    def _build_context_menus(self):
        """Tạo menu chuột phải cho 2 bảng."""
        self.menu_context = tk.Menu(self, tearoff=0)
        self.menu_context.add_command(label="📋 Copy Tiêu Đề", command=self._copy_selected_title)
        self.menu_context.add_command(label="🔗 Copy Link Video", command=self._copy_selected_url)
        self.menu_context.add_command(label="🎬 Copy Chuỗi Highlight", command=self._copy_selected_highlight)
        self.menu_context.add_separator()
        self.menu_context.add_command(label="✂️ Cắt Highlight video này...", command=self._split_selected_entry)
        self.menu_context.add_separator()
        self.menu_context.add_command(label="📄 Copy Cả Dòng (Form Excel)", command=self._copy_selected_row)

        self.tree_short.bind("<Button-3>", lambda e: self._show_context_menu(e, self.tree_short))
        self.tree_long.bind("<Button-3>", lambda e: self._show_context_menu(e, self.tree_long))
        
        self._active_tree = None

    # ==========================================
    # Event Handlers & Core Logic Interfacing
    # ==========================================

    def _set_range(self, min_val, max_val):
        """Đặt khoảng thời lượng lọc Min - Max."""
        self._min_sec.set(min_val)
        self._max_sec.set(max_val)
        if hasattr(self, 'spin_min'):
            self.spin_min.delete(0, 'end')
            self.spin_min.insert(0, str(min_val))
        if hasattr(self, 'spin_max'):
            self.spin_max.delete(0, 'end')
            self.spin_max.insert(0, str(max_val))
        if self._entries:
            self._update_filtered_views()

    def _on_paste_clipboard(self):
        """Lấy dữ liệu từ Clipboard và tính toán ngay."""
        try:
            clip_text = self.clipboard_get()
            if not clip_text or not clip_text.strip():
                messagebox.showwarning("Clipboard rỗng", "Bộ nhớ tạm không chứa văn bản nào!")
                return
            
            self.txt_input.delete('1.0', tk.END)
            self.txt_input.insert('1.0', clip_text)
            self._on_calculate()
        except tk.TclError:
            messagebox.showwarning("Clipboard rỗng", "Không lấy được dữ liệu từ bộ nhớ tạm!")

    def _on_clear(self):
        """Xóa sạch dữ liệu ô nhập liệu và 2 bảng."""
        self.txt_input.delete('1.0', tk.END)
        self._entries = []
        self._in_range_entries = []
        self._out_range_entries = []
        self._render_tables()
        self.log_panel.log("Đã xóa toàn bộ dữ liệu nhập và bảng kết quả.", 'info')

    def _on_calculate(self):
        """Phân tách văn bản thô và tính toán thời lượng highlight."""
        raw_text = self.txt_input.get('1.0', tk.END).strip()
        if not raw_text:
            messagebox.showwarning("Thiếu dữ liệu", "Vui lòng nhập hoặc dán dữ liệu 3 cột vào ô văn bản!")
            return

        self._entries = parse_3column_input(raw_text)
        if not self._entries:
            messagebox.showwarning("Dữ liệu rỗng", "Không phân tách được dòng hợp lệ nào từ văn bản đã nhập!")
            return

        min_val = self._min_sec.get()
        max_val = self._max_sec.get()
        self.log_panel.log(f"Đã phân tách {len(self._entries)} dòng dữ liệu. Đang phân loại theo khoảng [{min_val}s - {max_val}s]...", 'info')

        self._update_filtered_views()

    def _update_filtered_views(self):
        """Cập nhật phân loại dữ liệu theo khoảng [Min A - Max B] và vẽ lại bảng."""
        min_val = self._min_sec.get()
        max_val = self._max_sec.get()
        if min_val >= max_val:
            min_val, max_val = 60, 90

        # in_range_entries (MÀU XANH), out_range_entries (MÀU ĐỎ)
        self._in_range_entries, self._out_range_entries = filter_entries_by_duration(self._entries, min_val, max_val)
        self._render_tables()

        range_label = f"{min_val}s - {max_val}s ({format_duration_str(min_val)} - {format_duration_str(max_val)})"
        self.log_panel.log(
            f"Tính toán hoàn tất ({len(self._entries)} video): {len(self._in_range_entries)} video TRONG khoảng (MÀU XANH [{range_label}]), {len(self._out_range_entries)} video NGOÀI khoảng (MÀU ĐỎ).",
            'success'
        )

    def _render_tables(self):
        """Nạp dữ liệu vào 2 bảng Treeview."""
        # Clear tables
        for item in self.tree_short.get_children():
            self.tree_short.delete(item)
        for item in self.tree_long.get_children():
            self.tree_long.delete(item)

        min_val = self._min_sec.get()
        max_val = self._max_sec.get()
        range_str = f"{min_val}s - {max_val}s ({format_duration_str(min_val)} - {format_duration_str(max_val)})"

        # 1. Render In-range entries (🟢 MÀU XANH - TRONG KHOẢNG [Min, Max])
        total_in_sec = sum(item['total_seconds'] for item in self._in_range_entries)
        for idx, item in enumerate(self._in_range_entries, 1):
            self.tree_short.insert(
                '', 'end', iid=f"in_{idx}",
                values=(
                    idx,
                    item['title'],
                    item['url'],
                    item['highlight_clean'] if item['highlight_clean'] else item['highlight_raw'],
                    item['segment_count'],
                    item['duration_formatted'],
                    item['total_seconds']
                ),
                tags=('in_range_row',)
            )

        self.lbl_in_range_stats.configure(
            text=f"🟢 Số lượng: {len(self._in_range_entries)} video TRONG khoảng [{range_str}] | Tổng thời lượng: {format_duration_str(total_in_sec)}"
        )

        # 2. Render Out-of-range entries (🔴 MÀU ĐỎ - NGOÀI KHOẢNG < Min hoặc > Max)
        total_out_sec = sum(item['total_seconds'] for item in self._out_range_entries)
        for idx, item in enumerate(self._out_range_entries, 1):
            self.tree_long.insert(
                '', 'end', iid=f"out_{idx}",
                values=(
                    idx,
                    item['title'],
                    item['url'],
                    item['highlight_clean'] if item['highlight_clean'] else item['highlight_raw'],
                    item['segment_count'],
                    item['duration_formatted'],
                    item['total_seconds']
                ),
                tags=('out_range_row',)
            )

        self.lbl_out_range_stats.configure(
            text=f"🔴 Số lượng: {len(self._out_range_entries)} video NGOÀI khoảng [< {min_val}s hoặc > {max_val}s] | Tổng thời lượng: {format_duration_str(total_out_sec)}"
        )

    def _copy_table_tsv(self, entries, label_name):
        """Sao chép toàn bộ bảng dữ liệu dạng TSV chuẩn cho Excel vào Clipboard."""
        if not entries:
            messagebox.showinfo("Thông báo", f"Bảng {label_name} hiện không có dữ liệu nào!")
            return

        tsv_data = export_entries_to_tsv(entries)
        self.clipboard_clear()
        self.clipboard_append(tsv_data)
        self.update()
        
        self.log_panel.log(f"📋 Đã copy {len(entries)} dòng của bảng [{label_name}] vào Clipboard (chuẩn Excel).", 'success')
        messagebox.showinfo("Thành công", f"Đã sao chép {len(entries)} dòng dữ liệu từ bảng [{label_name}]!\nBạn có thể Ctrl+V dán trực tiếp vào Excel hoặc Google Sheets.")

    def _export_to_file(self, entries, file_suffix):
        """Xuất danh sách dữ liệu ra file CSV/TSV."""
        if not entries:
            messagebox.showinfo("Thông báo", "Không có dữ liệu để xuất file!")
            return

        file_path = filedialog.asksaveasfilename(
            title="Chọn vị trí lưu file",
            defaultextension=".csv",
            filetypes=[("File CSV", "*.csv"), ("File Text TSV", "*.txt"), ("Tất cả tệp", "*.*")],
            initialfile=f"highlight_duration_{file_suffix}.csv"
        )
        if not file_path:
            return

        try:
            if file_path.endswith('.txt') or file_path.endswith('.tsv'):
                content = export_entries_to_tsv(entries)
            else:
                content = export_entries_to_csv(entries)

            with open(file_path, 'w', encoding='utf-8-sig') as f:
                f.write(content)

            self.log_panel.log(f"💾 Đã xuất {len(entries)} dòng dữ liệu thành công ra: {file_path}", 'success')
            messagebox.showinfo("Xuất file thành công", f"Đã lưu thành công tại:\n{file_path}")
        except Exception as e:
            self.log_panel.log(f"❌ Lỗi khi lưu file: {e}", 'error')
            messagebox.showerror("Lỗi lưu file", str(e))

    # ==========================================
    # Context Menu Actions
    # ==========================================

    def _show_context_menu(self, event, tree):
        """Hiển thị menu chuột phải tại vị trí con trỏ."""
        item = tree.identify_row(event.y)
        if item:
            tree.selection_set(item)
            self._active_tree = tree
            self.menu_context.post(event.x_root, event.y_root)

    def _get_selected_row_values(self):
        """Lấy giá trị của dòng đang chọn."""
        if not self._active_tree:
            return None
        selected = self._active_tree.selection()
        if not selected:
            return None
        return self._active_tree.item(selected[0], 'values')

    def _copy_selected_title(self):
        vals = self._get_selected_row_values()
        if vals:
            title = vals[1]
            self.clipboard_clear()
            self.clipboard_append(title)
            self.update()
            self.log_panel.log(f"📋 Copied title: {title}", 'info')

    def _copy_selected_url(self):
        vals = self._get_selected_row_values()
        if vals:
            url = vals[2]
            self.clipboard_clear()
            self.clipboard_append(url)
            self.update()
            self.log_panel.log(f"📋 Copied URL: {url}", 'info')

    def _copy_selected_highlight(self):
        vals = self._get_selected_row_values()
        if vals:
            hl = vals[3]
            self.clipboard_clear()
            self.clipboard_append(hl)
            self.update()
            self.log_panel.log(f"📋 Copied highlight: {hl}", 'info')

    def _copy_selected_row(self):
        vals = self._get_selected_row_values()
        if vals:
            row_tsv = f"{vals[1]}\t{vals[2]}\t{vals[3]}\t{vals[5]}\t{vals[6]}"
            self.clipboard_clear()
            self.clipboard_append(row_tsv)
            self.update()
            self.log_panel.log(f"📋 Copied full row: {vals[1]}", 'info')

    # ==========================================
    # Highlight Splitter Action Handlers
    # ==========================================

    def _apply_split_results(self, updated_split_entries):
        """Áp dụng các entry đã cắt từ HighlightSplitDialog trở lại danh sách chính và cập nhật giao diện."""
        if not updated_split_entries:
            return

        updated_map = {}
        for entry in updated_split_entries:
            orig_id = entry.get('_orig_id')
            orig_title = entry.get('original_title', entry.get('title'))
            key = orig_id if orig_id is not None else orig_title
            if key not in updated_map:
                updated_map[key] = []
            updated_map[key].append(entry)

        new_all_entries = []
        processed_keys = set()

        for old_entry in self._entries:
            orig_id = old_entry.get('_orig_id', old_entry.get('row_index'))
            orig_title = old_entry.get('title')
            key = orig_id if orig_id in updated_map else orig_title

            if key in updated_map:
                if key not in processed_keys:
                    processed_keys.add(key)
                    for new_item in updated_map[key]:
                        merged = dict(old_entry)
                        merged['title'] = new_item['title']
                        merged['highlight_clean'] = new_item['highlight_clean']
                        merged['total_seconds'] = new_item['total_seconds']
                        merged['duration_formatted'] = new_item['duration_formatted']
                        merged['segment_count'] = new_item.get('segment_count', 1)
                        new_all_entries.append(merged)
            else:
                new_all_entries.append(old_entry)

        for key, items in updated_map.items():
            if key not in processed_keys:
                for new_item in items:
                    new_all_entries.append({
                        '_orig_id': new_item.get('_orig_id', 0),
                        'row_index': new_item.get('row_index', 0),
                        'title': new_item['title'],
                        'url': new_item.get('url', ''),
                        'highlight_raw': new_item.get('highlight_raw', ''),
                        'highlight_clean': new_item['highlight_clean'],
                        'total_seconds': new_item['total_seconds'],
                        'duration_formatted': new_item['duration_formatted'],
                        'segment_count': new_item.get('segment_count', 1),
                    })

        self._entries = new_all_entries
        self._update_filtered_views()
        self.log_panel.log(f"✅ Đã áp dụng {len(updated_split_entries)} dòng dữ liệu highlight đã cắt vào bảng chính.", 'success')

    def _on_open_split_in_range_dialog(self):
        """Mở dialog cắt highlight dành riêng cho danh sách TRONG KHOẢNG (MÀU XANH)."""
        if not self._in_range_entries:
            messagebox.showinfo("Thông báo", "Danh sách video TRONG KHOẢNG hiện tại đang rỗng!")
            return

        min_val = self._min_sec.get()
        max_val = self._max_sec.get()

        HighlightSplitDialog(
            parent=self,
            entries=self._in_range_entries,
            log_panel=self.log_panel,
            min_target_sec=min_val,
            max_target_sec=max_val,
            on_apply_callback=self._apply_split_results
        )

    def _on_open_split_out_range_dialog(self):
        """Mở dialog cắt highlight dành riêng cho danh sách NGOÀI KHOẢNG (MÀU ĐỎ)."""
        if not self._out_range_entries:
            messagebox.showinfo("Thông báo", "Danh sách video NGOÀI KHOẢNG hiện tại đang rỗng!")
            return

        min_val = self._min_sec.get()
        max_val = self._max_sec.get()

        HighlightSplitDialog(
            parent=self,
            entries=self._out_range_entries,
            log_panel=self.log_panel,
            min_target_sec=min_val,
            max_target_sec=max_val,
            on_apply_callback=self._apply_split_results
        )

    def _on_open_split_all_dialog(self):
        """Mở dialog cắt highlight cho TẤT CẢ video."""
        if not self._entries:
            messagebox.showinfo(
                "Thông báo",
                "Chưa có dữ liệu video nào!\nVui lòng dán dữ liệu 3 cột và bấm nút '⚡ Phân Tách & Tính Thời Lượng' trước khi cắt."
            )
            return

        min_val = self._min_sec.get()
        max_val = self._max_sec.get()

        HighlightSplitDialog(
            parent=self,
            entries=self._entries,
            log_panel=self.log_panel,
            min_target_sec=min_val,
            max_target_sec=max_val,
            on_apply_callback=self._apply_split_results
        )

    def _on_open_split_dialog(self):
        """Giữ tương thích alias."""
        self._on_open_split_all_dialog()

    def _split_selected_entry(self):
        """Mở dialog cắt highlight cho 1 video duy nhất được chọn trong bảng."""
        vals = self._get_selected_row_values()
        if not vals:
            messagebox.showinfo("Thông báo", "Vui lòng chọn 1 dòng video trong bảng trước!")
            return

        selected_title = vals[1]
        selected_entry = None
        for item in self._entries:
            if item.get('title') == selected_title:
                selected_entry = item
                break

        if not selected_entry:
            selected_entry = {
                'row_index': 1,
                'title': vals[1],
                'original_title': vals[1],
                'url': vals[2],
                'highlight_raw': vals[3],
                'total_seconds': float(vals[6]) if str(vals[6]).replace('.', '', 1).isdigit() else 0.0
            }

        min_val = self._min_sec.get()
        max_val = self._max_sec.get()

        HighlightSplitDialog(
            parent=self,
            entries=[selected_entry],
            log_panel=self.log_panel,
            min_target_sec=min_val,
            max_target_sec=max_val,
            on_apply_callback=self._apply_split_results
        )

