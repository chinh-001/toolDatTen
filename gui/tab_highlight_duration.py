"""
HighlightDurationTab - Giao diện và logic cho Tab Tính Toán & Kiểm Tra Thời Lượng Highlight Video.
Hỗ trợ dán dữ liệu 3 cột (Tiêu đề, Link, Highlight), phân tách tự động và lọc theo ngưỡng thời lượng.

Quy định màu sắc theo yêu cầu:
- Dưới ngưỡng (< threshold): MÀU XANH (🟢 Green)
- Trên ngưỡng (>= threshold): MÀU ĐỎ (🔴 Red)
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
    """Tab Tính toán thời lượng Highlight & Kiểm tra lọc theo ngưỡng."""

    def __init__(self, parent, log_panel, **kwargs):
        super().__init__(parent, **kwargs)
        self.log_panel = log_panel

        # State variables
        self._threshold_sec = tk.IntVar(value=90)  # Mặc định 90 giây = 1 phút 30 giây
        self._entries = []
        self._short_entries = []  # Dưới ngưỡng (MÀU XANH)
        self._long_entries = []   # Trên ngưỡng (MÀU ĐỎ)

        self._build_ui()

    def _build_ui(self):
        """Xây dựng toàn bộ giao diện cho Tab."""
        # Top section: Input Controls & Settings
        top_frame = ttk.LabelFrame(
            self,
            text="📥 Nhập dữ liệu 3 cột & ⚙️ Cài đặt ngưỡng lọc",
            style='Section.TLabelframe',
            padding=8
        )
        top_frame.pack(fill='x', pady=(0, 6))

        self._build_input_and_settings(top_frame)

        # Main Split View (PanedWindow) cho 2 bảng: Dưới ngưỡng (Xanh) và Trên ngưỡng (Đỏ)
        paned = ttk.PanedWindow(self, orient='vertical')
        paned.pack(fill='both', expand=True, pady=(0, 4))

        # --- Section 1: Video DƯỚI NGƯỜNG (🟢 < Ngưỡng lọc - MÀU XANH) ---
        short_frame = ttk.LabelFrame(
            paned,
            text="🟢 Danh Sách Highlight DƯỚI NGƯỜNG (< Ngưỡng lọc)",
            style='Section.TLabelframe',
            padding=6
        )
        paned.add(short_frame, weight=1)
        self._build_short_videos_section(short_frame)

        # --- Section 2: Video TRÊN NGƯỜNG (🔴 >= Ngưỡng lọc - MÀU ĐỎ) ---
        long_frame = ttk.LabelFrame(
            paned,
            text="🔴 Danh Sách Highlight TRÊN NGƯỜNG (>= Ngưỡng lọc)",
            style='Section.TLabelframe',
            padding=6
        )
        paned.add(long_frame, weight=1)
        self._build_long_videos_section(long_frame)

        # Context Menu setup
        self._build_context_menus()

    def _build_input_and_settings(self, parent):
        """Xây dựng phần nhập dữ liệu và chỉnh ngưỡng."""
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

        # Sub-frame 2: Controls & Threshold setting row
        ctrl_row = ttk.Frame(parent)
        ctrl_row.pack(fill='x')

        # Left side: Action Buttons
        btn_paste = ttk.Button(ctrl_row, text="📋 Dán từ Clipboard", command=self._on_paste_clipboard)
        btn_paste.pack(side='left', padx=(0, 6))

        btn_parse = ttk.Button(ctrl_row, text="⚡ Phân Tách & Tính Thời Lượng", style='Action.TButton', command=self._on_calculate)
        btn_parse.pack(side='left', padx=(0, 6))

        btn_split_top = ttk.Button(ctrl_row, text="✂️ Cắt Highlight > 1p30s", command=self._on_open_split_dialog)
        btn_split_top.pack(side='left', padx=(0, 6))

        btn_clear = ttk.Button(ctrl_row, text="🧹 Xóa dữ liệu", command=self._on_clear)
        btn_clear.pack(side='left', padx=(0, 16))

        # Right side: Threshold Spinbox & Preset Buttons
        thresh_frame = ttk.Frame(ctrl_row)
        thresh_frame.pack(side='right')

        ttk.Label(thresh_frame, text="⏱️ Ngưỡng lọc (giây):", font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(0, 4))

        spin_thresh = ttk.Spinbox(thresh_frame, from_=1, to=7200, textvariable=self._threshold_sec, width=6)
        spin_thresh.pack(side='left', padx=(0, 6))

        # Preset buttons
        ttk.Button(thresh_frame, text="30s", width=4, command=lambda: self._set_threshold(30)).pack(side='left', padx=1)
        ttk.Button(thresh_frame, text="60s (1p)", width=7, command=lambda: self._set_threshold(60)).pack(side='left', padx=1)
        ttk.Button(thresh_frame, text="90s (1p30)", width=9, command=lambda: self._set_threshold(90)).pack(side='left', padx=1)
        ttk.Button(thresh_frame, text="120s (2p)", width=8, command=lambda: self._set_threshold(120)).pack(side='left', padx=1)
        ttk.Button(thresh_frame, text="180s (3p)", width=8, command=lambda: self._set_threshold(180)).pack(side='left', padx=1)

    def _build_short_videos_section(self, parent):
        """Xây dựng phần danh sách video DƯỚI NGƯỜNG (< threshold) - MÀU XANH."""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill='x', pady=(0, 4))

        self.lbl_short_stats = ttk.Label(
            toolbar,
            text="Số lượng: 0 video | Tổng thời lượng highlight: 00m 00s",
            font=('Segoe UI', 9, 'bold'),
            foreground='#27ae60'  # MÀU XANH
        )
        self.lbl_short_stats.pack(side='left', anchor='w')

        # Action Buttons cho video dưới ngưỡng
        btn_copy_short = ttk.Button(
            toolbar,
            text="📋 Copy Bảng Dưới Ngưỡng (Form Excel)",
            command=lambda: self._copy_table_tsv(self._short_entries, "Dưới ngưỡng (< threshold)")
        )
        btn_copy_short.pack(side='right', padx=(6, 0))

        btn_export_short = ttk.Button(
            toolbar,
            text="📥 Xuất File Excel / CSV...",
            command=lambda: self._export_to_file(self._short_entries, "duoi_nguong")
        )
        btn_export_short.pack(side='right')

        # Treeview Table cho Video Dưới Ngưỡng
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

        # TAG MÀU XANH cho dòng dưới ngưỡng
        self.tree_short.tag_configure('short_row', background='#d5f5e3')

    def _build_long_videos_section(self, parent):
        """Xây dựng phần danh sách video TRÊN NGƯỜNG (>= threshold) - MÀU ĐỎ."""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill='x', pady=(0, 4))

        self.lbl_long_stats = ttk.Label(
            toolbar,
            text="Số lượng: 0 video | Tổng thời lượng highlight: 00m 00s",
            font=('Segoe UI', 9, 'bold'),
            foreground='#e74c3c'  # MÀU ĐỎ
        )
        self.lbl_long_stats.pack(side='left', anchor='w')

        # Action Buttons cho video trên ngưỡng
        btn_copy_long = ttk.Button(
            toolbar,
            text="📋 Copy Bảng Trên Ngưỡng (Form Excel)",
            command=lambda: self._copy_table_tsv(self._long_entries, "Trên ngưỡng (>= threshold)")
        )
        btn_copy_long.pack(side='right', padx=(6, 0))

        btn_export_long = ttk.Button(
            toolbar,
            text="📥 Xuất File Excel / CSV...",
            command=lambda: self._export_to_file(self._long_entries, "tren_nguong")
        )
        btn_export_long.pack(side='right', padx=(6, 0))

        # Nút Phân Tách Highlight Quá Dài (>1p30s)
        btn_split_long = ttk.Button(
            toolbar,
            text="✂️ Cắt Highlight Quá Dài (>1p30s)...",
            style='Action.TButton',
            command=self._on_open_split_dialog
        )
        btn_split_long.pack(side='right')

        # Treeview Table cho Video Trên Ngưỡng
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

        # TAG MÀU ĐỎ cho dòng trên ngưỡng
        self.tree_long.tag_configure('long_row', background='#fadbd8')

    def _build_context_menus(self):
        """Tạo menu chuột phải cho 2 bảng."""
        self.menu_context = tk.Menu(self, tearoff=0)
        self.menu_context.add_command(label="📋 Copy Tiêu Đề", command=self._copy_selected_title)
        self.menu_context.add_command(label="🔗 Copy Link Video", command=self._copy_selected_url)
        self.menu_context.add_command(label="🎬 Copy Chuỗi Highlight", command=self._copy_selected_highlight)
        self.menu_context.add_separator()
        self.menu_context.add_command(label="✂️ Tách Highlight video này (1p - 1p30s)...", command=self._split_selected_entry)
        self.menu_context.add_separator()
        self.menu_context.add_command(label="📄 Copy Cả Dòng (Form Excel)", command=self._copy_selected_row)

        self.tree_short.bind("<Button-3>", lambda e: self._show_context_menu(e, self.tree_short))
        self.tree_long.bind("<Button-3>", lambda e: self._show_context_menu(e, self.tree_long))
        
        self._active_tree = None

    # ==========================================
    # Event Handlers & Core Logic Interfacing
    # ==========================================

    def _set_threshold(self, val):
        """Đặt ngưỡng thời lượng và cập nhật lại bộ lọc."""
        self._threshold_sec.set(val)
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
        self._short_entries = []
        self._long_entries = []
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

        thresh = self._threshold_sec.get()
        self.log_panel.log(f"Đã phân tách {len(self._entries)} dòng dữ liệu. Đang phân loại theo ngưỡng {thresh}s ({format_duration_str(thresh)})...", 'info')

        self._update_filtered_views()

    def _update_filtered_views(self):
        """Cập nhật phân loại dữ liệu theo ngưỡng và vẽ lại bảng."""
        thresh = self._threshold_sec.get()
        # short_entries (< threshold - MÀU XANH), long_entries (>= threshold - MÀU ĐỎ)
        self._short_entries, self._long_entries = filter_entries_by_duration(self._entries, thresh)
        self._render_tables()

        thresh_label = f"{thresh}s ({format_duration_str(thresh)})"
        self.log_panel.log(
            f"Tính toán hoàn tất ({len(self._entries)} video): {len(self._short_entries)} video DƯỚI ngưỡng (MÀU XANH < {thresh_label}), {len(self._long_entries)} video TRÊN ngưỡng (MÀU ĐỎ >= {thresh_label}).",
            'success'
        )

    def _render_tables(self):
        """Nạp dữ liệu vào 2 bảng Treeview."""
        # Clear tables
        for item in self.tree_short.get_children():
            self.tree_short.delete(item)
        for item in self.tree_long.get_children():
            self.tree_long.delete(item)

        thresh_val = self._threshold_sec.get()
        thresh_str = f"{thresh_val}s ({format_duration_str(thresh_val)})"

        # 1. Render Short entries (🟢 MÀU XANH - DƯỚI NGƯỜNG < threshold)
        total_short_sec = sum(item['total_seconds'] for item in self._short_entries)
        for idx, item in enumerate(self._short_entries, 1):
            self.tree_short.insert(
                '', 'end', iid=f"short_{idx}",
                values=(
                    idx,
                    item['title'],
                    item['url'],
                    item['highlight_clean'] if item['highlight_clean'] else item['highlight_raw'],
                    item['segment_count'],
                    item['duration_formatted'],
                    item['total_seconds']
                ),
                tags=('short_row',)
            )

        self.lbl_short_stats.configure(
            text=f"🟢 Số lượng: {len(self._short_entries)} video (< {thresh_str}) | Tổng thời lượng: {format_duration_str(total_short_sec)}"
        )

        # 2. Render Long entries (🔴 MÀU ĐỎ - TRÊN NGƯỜNG >= threshold)
        total_long_sec = sum(item['total_seconds'] for item in self._long_entries)
        for idx, item in enumerate(self._long_entries, 1):
            self.tree_long.insert(
                '', 'end', iid=f"long_{idx}",
                values=(
                    idx,
                    item['title'],
                    item['url'],
                    item['highlight_clean'] if item['highlight_clean'] else item['highlight_raw'],
                    item['segment_count'],
                    item['duration_formatted'],
                    item['total_seconds']
                ),
                tags=('long_row',)
            )

        self.lbl_long_stats.configure(
            text=f"🔴 Số lượng: {len(self._long_entries)} video (>= {thresh_str}) | Tổng thời lượng: {format_duration_str(total_long_sec)}"
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

    def _on_open_split_dialog(self):
        """Mở cửa sổ dialog phân tách các đoạn highlight quá dài (>1p30s)."""
        # Lấy các video có thời lượng > 90s (hoặc tất cả các video trên ngưỡng)
        target_entries = [e for e in self._entries if e.get('total_seconds', 0) > 90]
        if not target_entries:
            if self._long_entries:
                target_entries = self._long_entries
            elif self._entries:
                target_entries = self._entries

        if not target_entries:
            messagebox.showinfo(
                "Thông báo",
                "Chưa có dữ liệu video nào!\nVui lòng dán dữ liệu 3 cột và bấm nút '⚡ Phân Tách & Tính Thời Lượng' trước khi cắt."
            )
            return

        HighlightSplitDialog(
            parent=self,
            entries=target_entries,
            log_panel=self.log_panel,
            min_target_sec=60,
            max_target_sec=90
        )

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
            # Fallback nếu không tìm thấy title khớp chính xác
            selected_entry = {
                'row_index': 1,
                'title': vals[1],
                'url': vals[2],
                'highlight_raw': vals[3],
                'total_seconds': float(vals[6]) if str(vals[6]).replace('.', '', 1).isdigit() else 0.0
            }

        HighlightSplitDialog(
            parent=self,
            entries=[selected_entry],
            log_panel=self.log_panel,
            min_target_sec=60,
            max_target_sec=90
        )

