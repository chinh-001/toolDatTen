"""
HighlightSplitDialog Module - Giao diện cửa sổ phân tách & cắt nhỏ các đoạn Highlight theo thời lượng tùy chọn.

Cho phép người dùng:
1. Thiết lập thời lượng thành phẩm mong muốn trước khi cắt (ví dụ: 30s-45s, 45s-60s, 60s-90s, 90s-120s...).
2. Trích xuất đúng 1 Dòng Highlight / Video hoặc chia nhiều Phần (Part).
3. Tùy chỉnh Giới hạn độ dài MỖI ĐOẠN (mặc định tối đa 8 giây) để người xem không bị ngán.
4. Chỉnh sửa khoảng thời lượng mục tiêu (Min target - Max target) và bấm "⚡ Cắt Lại Highlight".
5. Sao chép kết quả dạng bảng Excel (TSV) hoặc xuất ra file CSV / TSV.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core.highlight_splitter import (
    split_long_entries,
    split_long_entry,
    export_split_entries_to_tsv,
    export_split_entries_to_csv,
)
from core.highlight_duration_calculator import format_duration_str


class HighlightSplitDialog(tk.Toplevel):
    """Cửa sổ Modal Phân Tách & Cắt Highlight quá dài."""

    def __init__(self, parent, entries, log_panel=None, min_target_sec=60, max_target_sec=90, mode='single', max_segment_sec=8, **kwargs):
        super().__init__(parent, **kwargs)
        min_str = format_duration_str(min_target_sec)
        max_str = format_duration_str(max_target_sec)
        self.title(f"✂️ Cắt Gọt Highlight Video (Thời lượng thành phẩm: {min_str} - {max_str})")
        self.geometry("980x700")
        self.minsize(840, 540)

        self.parent = parent
        self.log_panel = log_panel
        self._original_entries = list(entries)

        # Target range, Max segment & Mode variables
        self._min_var = tk.IntVar(value=min_target_sec)
        self._max_var = tk.IntVar(value=max_target_sec)
        self._max_seg_var = tk.IntVar(value=max_segment_sec)  # Mặc định mỗi mốc tối đa 8 giây
        self._mode_var = tk.StringVar(value=mode)  # 'single' (Mặc định 1 dòng/video) hoặc 'split' (Nhiều part)
        self._split_entries = []

        self._setup_ui()
        self._center_window()
        self._recalculate_split()

        # Grab focus as modal dialog
        self.transient(parent)
        self.grab_set()

    def _center_window(self):
        """Đặt cửa sổ ở vị trí trung tâm."""
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")

    def _setup_ui(self):
        """Xây dựng giao diện chính của Cửa sổ phân tách."""
        main_frame = ttk.Frame(self, padding=12)
        main_frame.pack(fill='both', expand=True)

        # 1. Top Header Banner
        hdr_frame = ttk.Frame(main_frame)
        hdr_frame.pack(fill='x', pady=(0, 8))

        min_str = format_duration_str(self._min_var.get())
        max_str = format_duration_str(self._max_var.get())
        max_seg = self._max_seg_var.get()
        seg_desc = f"tối đa {max_seg}s" if max_seg > 0 else "không giới hạn"

        self._lbl_header = ttk.Label(
            hdr_frame,
            text=f"✂️ Cắt Gọt Highlight Video (Mỗi mốc {seg_desc}, thành phẩm {min_str} - {max_str})",
            font=('Segoe UI', 12, 'bold'),
            foreground='#2c3e50'
        )
        self._lbl_header.pack(anchor='w')

        self._lbl_sub_header = ttk.Label(
            hdr_frame,
            text=f"Thiết lập thời lượng thành phẩm mong muốn bên dưới trước khi cắt. Hiện tại: {min_str} - {max_str}.",
            font=('Segoe UI', 9),
            foreground='#7f8c8d'
        )
        self._lbl_sub_header.pack(anchor='w', pady=(2, 0))

        # 2. Controls & Target Settings Frame
        ctrl_frame = ttk.LabelFrame(
            main_frame,
            text="⚙️ Cài đặt chế độ đầu ra, độ dài 1 mốc & thời lượng mục tiêu",
            style='Section.TLabelframe',
            padding=8
        )
        ctrl_frame.pack(fill='x', pady=(0, 8))

        # Row 1: Mode Selection (RadioButtons)
        mode_row = ttk.Frame(ctrl_frame)
        mode_row.pack(fill='x', pady=(0, 6))

        ttk.Label(mode_row, text="Chế độ đầu ra:", font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(0, 8))

        r_single = ttk.Radiobutton(
            mode_row,
            text="🟢 1 Dòng / Video (Cắt về thời lượng mục tiêu duy nhất)",
            value='single',
            variable=self._mode_var,
            command=self._recalculate_split
        )
        r_single.pack(side='left', padx=(0, 12))

        r_split = ttk.Radiobutton(
            mode_row,
            text="🔵 Chia nhiều Phần (Phần 1/X, Phần 2/X...)",
            value='split',
            variable=self._mode_var,
            command=self._recalculate_split
        )
        r_split.pack(side='left')

        ttk.Separator(ctrl_frame, orient='horizontal').pack(fill='x', pady=4)

        # Row 2: Max segment duration setting (mỗi đoạn tối đa 8 giây)
        seg_row = ttk.Frame(ctrl_frame)
        seg_row.pack(fill='x', pady=(0, 6))

        ttk.Label(seg_row, text="✂️ Giới hạn mỗi đoạn (Max mốc):", font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(0, 4))
        spin_seg = ttk.Spinbox(seg_row, from_=0, to=300, textvariable=self._max_seg_var, width=5)
        spin_seg.pack(side='left', padx=(0, 4))

        ttk.Label(seg_row, text="giây", font=('Segoe UI', 9)).pack(side='left', padx=(0, 16))

        # Quick Segment Presets
        ttk.Label(seg_row, text="Nhanh:").pack(side='left', padx=(0, 4))
        ttk.Button(seg_row, text="5s", width=4, command=lambda: self._set_max_seg(5)).pack(side='left', padx=1)
        ttk.Button(seg_row, text="8s (Chuẩn)", width=9, command=lambda: self._set_max_seg(8)).pack(side='left', padx=1)
        ttk.Button(seg_row, text="10s", width=5, command=lambda: self._set_max_seg(10)).pack(side='left', padx=1)
        ttk.Button(seg_row, text="15s", width=5, command=lambda: self._set_max_seg(15)).pack(side='left', padx=1)
        ttk.Button(seg_row, text="Không GH (0s)", width=12, command=lambda: self._set_max_seg(0)).pack(side='left', padx=1)

        ttk.Separator(ctrl_frame, orient='horizontal').pack(fill='x', pady=4)

        # Row 3: Min / Max total target Spinboxes & Action Row
        param_row = ttk.Frame(ctrl_frame)
        param_row.pack(fill='x')

        ttk.Label(param_row, text="⏱️ Tổng nhỏ nhất (Min):", font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(0, 4))
        spin_min = ttk.Spinbox(param_row, from_=10, to=3600, textvariable=self._min_var, width=6)
        spin_min.pack(side='left', padx=(0, 12))

        ttk.Label(param_row, text="⏱️ Tổng lớn nhất (Max):", font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(0, 4))
        spin_max = ttk.Spinbox(param_row, from_=10, to=3600, textvariable=self._max_var, width=6)
        spin_max.pack(side='left', padx=(0, 12))

        # Action Button: Recalculate All
        btn_recalc = ttk.Button(
            param_row,
            text="⚡ Cắt Lại Tất Cả",
            style='Action.TButton',
            command=self._recalculate_split
        )
        btn_recalc.pack(side='left', padx=(0, 6))

        # Action Button: Recalculate Selected Only
        btn_recalc_selected = ttk.Button(
            param_row,
            text="🎯 Cắt Lại Hàng Đã Chọn",
            command=self._recalculate_selected
        )
        btn_recalc_selected.pack(side='left', padx=(0, 16))

        # Quick Preset Buttons Frame
        preset_frame = ttk.Frame(param_row)
        preset_frame.pack(side='right')

        ttk.Label(preset_frame, text="Mẫu thành phẩm:").pack(side='left', padx=(0, 4))
        ttk.Button(preset_frame, text="30s-45s", command=lambda: self._set_preset(30, 45)).pack(side='left', padx=2)
        ttk.Button(preset_frame, text="45s-60s", command=lambda: self._set_preset(45, 60)).pack(side='left', padx=2)
        ttk.Button(preset_frame, text="60s-90s (1p-1p30)", command=lambda: self._set_preset(60, 90)).pack(side='left', padx=2)
        ttk.Button(preset_frame, text="90s-120s (1p30-2p)", command=lambda: self._set_preset(90, 120)).pack(side='left', padx=2)
        ttk.Button(preset_frame, text="120s-180s (2p-3p)", command=lambda: self._set_preset(120, 180)).pack(side='left', padx=2)

        # 3. Main Result Table (Treeview)
        tbl_frame = ttk.Frame(main_frame)
        tbl_frame.pack(fill='both', expand=True, pady=(0, 8))

        cols = ('stt', 'title', 'url', 'highlight', 'segments', 'duration', 'seconds', 'status')
        self.tree = ttk.Treeview(tbl_frame, columns=cols, show='headings', selectmode='extended')

        self.tree.heading('stt', text='#')
        self.tree.heading('title', text='Tiêu Đề Video')
        self.tree.heading('url', text='Link Video')
        self.tree.heading('highlight', text='Chuỗi Highlight Đã Cắt')
        self.tree.heading('segments', text='Số đoạn')
        self.tree.heading('duration', text='Thời lượng')
        self.tree.heading('seconds', text='Số giây')
        self.tree.heading('status', text='Trạng thái')

        self.tree.column('stt', width=40, minwidth=40, anchor='center')
        self.tree.column('title', width=220, minwidth=140)
        self.tree.column('url', width=200, minwidth=130)
        self.tree.column('highlight', width=260, minwidth=160)
        self.tree.column('segments', width=65, minwidth=50, anchor='center')
        self.tree.column('duration', width=95, minwidth=80, anchor='center')
        self.tree.column('seconds', width=75, minwidth=60, anchor='center')
        self.tree.column('status', width=90, minwidth=70, anchor='center')

        sc_y = ttk.Scrollbar(tbl_frame, orient='vertical', command=self.tree.yview)
        sc_x = ttk.Scrollbar(tbl_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=sc_y.set, xscrollcommand=sc_x.set)

        sc_y.pack(side='right', fill='y')
        sc_x.pack(side='bottom', fill='x')
        self.tree.pack(side='left', fill='both', expand=True)

        # Row styling tags
        self.tree.tag_configure('tag_good', background='#d5f5e3')   # Trong khoảng mục tiêu (Xanh lá)
        self.tree.tag_configure('tag_under', background='#fef9e7')  # Dưới min (Vàng nhạt)
        self.tree.tag_configure('tag_over', background='#fadbd8')   # Vượt max (Đỏ nhạt)

        # Context menu binding
        self._build_context_menu()

        # 4. Bottom Action Bar & Status
        bot_frame = ttk.Frame(main_frame)
        bot_frame.pack(fill='x')

        self.lbl_stats = ttk.Label(
            bot_frame,
            text="Số lượng: 0 dòng kết quả | Tổng thời lượng: 00m 00s",
            font=('Segoe UI', 9, 'bold'),
            foreground='#27ae60'
        )
        self.lbl_stats.pack(side='left', anchor='w')

        # Action Buttons
        btn_close = ttk.Button(bot_frame, text="❌ Đóng", command=self.destroy)
        btn_close.pack(side='right', padx=(6, 0))

        btn_export = ttk.Button(bot_frame, text="📥 Xuất File CSV...", command=self._export_split_file)
        btn_export.pack(side='right', padx=(6, 0))

        btn_copy = ttk.Button(
            bot_frame,
            text="📋 Copy Bảng Đã Cắt (Form Excel)",
            style='Action.TButton',
            command=self._copy_split_tsv
        )
        btn_copy.pack(side='right')

    def _build_context_menu(self):
        """Menu chuột phải cho bảng."""
        self.menu_context = tk.Menu(self, tearoff=0)
        self.menu_context.add_command(label="🎯 Cắt Lại Hàng Đã Chọn (theo Min/Max hiện tại)", command=self._recalculate_selected)
        self.menu_context.add_separator()
        self.menu_context.add_command(label="📋 Copy Tiêu Đề Video", command=self._copy_selected_title)
        self.menu_context.add_command(label="🔗 Copy Link Video", command=self._copy_selected_url)
        self.menu_context.add_command(label="🎬 Copy Chuỗi Highlight Cắt", command=self._copy_selected_highlight)
        self.menu_context.add_separator()
        self.menu_context.add_command(label="📄 Copy Cả Dòng (Form Excel)", command=self._copy_selected_row)

        self.tree.bind("<Button-3>", self._show_context_menu)

    def _set_preset(self, min_val, max_val):
        """Đặt mẫu nhanh cho khoảng thời gian và tính lại."""
        self._min_var.set(min_val)
        self._max_var.set(max_val)
        self._recalculate_split()

    def _set_max_seg(self, val):
        """Đặt mẫu nhanh độ dài tối đa 1 phân đoạn."""
        self._max_seg_var.set(val)
        self._recalculate_split()

    def _recalculate_split(self):
        """Thực hiện tính toán cắt lại toàn bộ dữ liệu theo thời lượng thành phẩm tùy chọn."""
        min_sec = self._min_var.get()
        max_sec = self._max_var.get()
        max_seg = self._max_seg_var.get()
        mode = self._mode_var.get()

        if min_sec >= max_sec:
            messagebox.showwarning("Cài đặt sai", "Min giây phải nhỏ hơn Max giây!")
            return

        # Cập nhật tiêu đề cửa sổ và banner header theo cài đặt mới
        min_str = format_duration_str(min_sec)
        max_str = format_duration_str(max_sec)
        seg_desc = f"tối đa {max_seg}s" if max_seg > 0 else "không giới hạn"

        self.title(f"✂️ Cắt Gọt Highlight Video (Thành phẩm: {min_str} - {max_str})")
        self._lbl_header.configure(
            text=f"✂️ Cắt Gọt Highlight Video (Mỗi mốc {seg_desc}, thành phẩm {min_str} - {max_str})"
        )
        self._lbl_sub_header.configure(
            text=f"Thiết lập thời lượng thành phẩm mong muốn bên dưới trước khi cắt. Hiện tại: {min_str} - {max_str}."
        )

        self._split_entries = split_long_entries(
            self._original_entries,
            min_target_sec=min_sec,
            max_target_sec=max_sec,
            mode=mode,
            max_segment_sec=max_seg
        )

        self._render_table(min_sec, max_sec)

        if self.log_panel:
            mode_desc = "1 dòng / video" if mode == 'single' else "chia nhiều parts"
            seg_desc = f"tối đa {max_seg}s/đoạn" if max_seg > 0 else "không giới hạn mốc"
            self.log_panel.log(
                f"✂️ Đã cắt phân tách {len(self._original_entries)} video thành {len(self._split_entries)} dòng kết quả [{mode_desc}, {seg_desc}] ({min_sec}s - {max_sec}s).",
                'success'
            )

    def _recalculate_selected(self):
        """Cắt lại chỉ những hàng đã chọn trong bảng theo cài đặt Min/Max hiện tại."""
        selected_iids = self.tree.selection()
        if not selected_iids:
            messagebox.showinfo("Thông báo", "Vui lòng chọn ít nhất 1 hàng trong bảng trước khi cắt lại!")
            return

        min_sec = self._min_var.get()
        max_sec = self._max_var.get()
        max_seg = self._max_seg_var.get()
        mode = self._mode_var.get()

        if min_sec >= max_sec:
            messagebox.showwarning("Cài đặt sai", "Min giây phải nhỏ hơn Max giây!")
            return

        # Chuyển iid (split_1, split_2, ...) thành chỉ mục 0-based trong _split_entries
        selected_indices = set()
        for iid in selected_iids:
            # iid có dạng "split_X" với X là 1-indexed
            try:
                idx = int(iid.replace("split_", "")) - 1
                if 0 <= idx < len(self._split_entries):
                    selected_indices.add(idx)
            except ValueError:
                continue

        if not selected_indices:
            messagebox.showinfo("Thông báo", "Không tìm thấy dữ liệu hàng đã chọn!")
            return

        # Thu thập các original entry tương ứng với hàng đã chọn (dùng row_index + original_title)
        # Mỗi split_entry có trường 'row_index' và 'original_title' liên kết về entry gốc
        recut_count = 0
        processed_originals = set()  # Tránh xử lý trùng 1 entry gốc nhiều lần

        new_split_entries = list(self._split_entries)  # Bản sao để thao tác

        for sel_idx in sorted(selected_indices):
            sel_entry = self._split_entries[sel_idx]
            row_idx = sel_entry.get('row_index', None)
            original_title = sel_entry.get('original_title', sel_entry.get('title', ''))

            # Key duy nhất cho 1 entry gốc
            origin_key = (row_idx, original_title)
            if origin_key in processed_originals:
                continue
            processed_originals.add(origin_key)

            # Tìm entry gốc tương ứng trong _original_entries
            orig_entry = None
            for oe in self._original_entries:
                if oe.get('row_index') == row_idx and oe.get('title', '') == original_title:
                    orig_entry = oe
                    break

            if orig_entry is None:
                # Fallback: dùng highlight_raw từ split_entry để tạo lại entry gốc
                orig_entry = {
                    'row_index': row_idx if row_idx is not None else 0,
                    'title': original_title,
                    'url': sel_entry.get('url', ''),
                    'highlight_raw': sel_entry.get('highlight_raw', ''),
                    'total_seconds': sel_entry.get('total_seconds', 0),
                }

            # Cắt lại entry gốc này với cài đặt mới
            new_sub_entries = split_long_entry(
                orig_entry,
                min_target_sec=min_sec,
                max_target_sec=max_sec,
                mode=mode,
                max_segment_sec=max_seg
            )

            # Tìm tất cả các vị trí trong new_split_entries thuộc về origin_key này
            indices_to_replace = []
            for i, entry in enumerate(new_split_entries):
                e_row = entry.get('row_index', None)
                e_title = entry.get('original_title', entry.get('title', ''))
                if (e_row, e_title) == origin_key:
                    indices_to_replace.append(i)

            if indices_to_replace:
                # Thay thế: xóa các entry cũ, chèn entry mới vào vị trí đầu tiên
                first_pos = indices_to_replace[0]
                for i in reversed(indices_to_replace):
                    new_split_entries.pop(i)
                for j, new_entry in enumerate(new_sub_entries):
                    new_split_entries.insert(first_pos + j, new_entry)
                recut_count += 1

        self._split_entries = new_split_entries

        # Cập nhật header
        min_str = format_duration_str(min_sec)
        max_str = format_duration_str(max_sec)
        seg_desc = f"tối đa {max_seg}s" if max_seg > 0 else "không giới hạn"
        self._lbl_header.configure(
            text=f"✂️ Cắt Gọt Highlight Video (Mỗi mốc {seg_desc}, thành phẩm {min_str} - {max_str})"
        )
        self._lbl_sub_header.configure(
            text=f"Đã cắt lại {recut_count} video được chọn. Thành phẩm: {min_str} - {max_str}."
        )

        self._render_table(min_sec, max_sec)

        if self.log_panel:
            self.log_panel.log(
                f"🎯 Đã cắt lại {recut_count} video được chọn theo thời lượng {min_sec}s - {max_sec}s.",
                'success'
            )

    def _render_table(self, min_sec, max_sec):
        """Nạp dữ liệu vào bảng Treeview."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        total_sec_all = sum(item['total_seconds'] for item in self._split_entries)

        for idx, item in enumerate(self._split_entries, 1):
            dur_sec = item['total_seconds']

            if min_sec <= dur_sec <= max_sec:
                tag = 'tag_good'
                status_str = "✅ Đúng chuẩn"
            elif dur_sec < min_sec:
                tag = 'tag_under'
                status_str = "⚠️ Dưới ngưỡng"
            else:
                tag = 'tag_over'
                status_str = "🔴 Trên ngưỡng"

            self.tree.insert(
                '', 'end', iid=f"split_{idx}",
                values=(
                    idx,
                    item['title'],
                    item['url'],
                    item['highlight_clean'],
                    item['segment_count'],
                    item['duration_formatted'],
                    item['total_seconds'],
                    status_str
                ),
                tags=(tag,)
            )

        min_str = format_duration_str(min_sec)
        max_str = format_duration_str(max_sec)
        mode_label = "Chế độ 1 dòng/video" if self._mode_var.get() == 'single' else "Chế độ chia nhiều phần"
        max_seg_val = self._max_seg_var.get()
        seg_str = f"Max {max_seg_val}s/đoạn" if max_seg_val > 0 else "Không GH mốc"

        self.lbl_stats.configure(
            text=f"🟢 {mode_label} ({seg_str}): {len(self._split_entries)} dòng từ {len(self._original_entries)} video | Mục tiêu: {min_str} - {max_str} | Tổng: {format_duration_str(total_sec_all)}"
        )

    def _copy_split_tsv(self):
        """Copy toàn bộ bảng đã cắt vào Clipboard dạng TSV chuẩn Excel."""
        if not self._split_entries:
            messagebox.showinfo("Thông báo", "Hiện không có dữ liệu để sao chép!")
            return

        tsv_data = export_split_entries_to_tsv(self._split_entries)
        self.clipboard_clear()
        self.clipboard_append(tsv_data)
        self.update()

        if self.log_panel:
            self.log_panel.log(f"📋 Đã copy {len(self._split_entries)} dòng highlight đã cắt vào Clipboard.", 'success')

        messagebox.showinfo(
            "Thành công",
            f"Đã sao chép {len(self._split_entries)} dòng dữ liệu highlight đã cắt!\nBạn có thể Ctrl+V dán trực tiếp vào Excel hoặc Google Sheets."
        )

    def _export_split_file(self):
        """Xuất danh sách highlight đã cắt ra file CSV/TSV."""
        if not self._split_entries:
            messagebox.showinfo("Thông báo", "Không có dữ liệu để xuất file!")
            return

        file_path = filedialog.asksaveasfilename(
            title="Chọn vị trí lưu file Highlight đã cắt",
            defaultextension=".csv",
            filetypes=[("File CSV", "*.csv"), ("File Text TSV", "*.txt"), ("Tất cả tệp", "*.*")],
            initialfile="highlight_split_result.csv"
        )
        if not file_path:
            return

        try:
            if file_path.endswith('.txt') or file_path.endswith('.tsv'):
                content = export_split_entries_to_tsv(self._split_entries)
            else:
                content = export_split_entries_to_csv(self._split_entries)

            with open(file_path, 'w', encoding='utf-8-sig') as f:
                f.write(content)

            if self.log_panel:
                self.log_panel.log(f"💾 Đã xuất file thành công ra: {file_path}", 'success')

            messagebox.showinfo("Thành công", f"Đã lưu thành công tại:\n{file_path}")
        except Exception as e:
            if self.log_panel:
                self.log_panel.log(f"❌ Lỗi khi lưu file: {e}", 'error')
            messagebox.showerror("Lỗi lưu file", str(e))

    # Context menu actions
    def _show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.menu_context.post(event.x_root, event.y_root)

    def _get_selected_row(self):
        selected = self.tree.selection()
        if not selected:
            return None
        return self.tree.item(selected[0], 'values')

    def _copy_selected_title(self):
        vals = self._get_selected_row()
        if vals:
            self.clipboard_clear()
            self.clipboard_append(vals[1])
            self.update()

    def _copy_selected_url(self):
        vals = self._get_selected_row()
        if vals:
            self.clipboard_clear()
            self.clipboard_append(vals[2])
            self.update()

    def _copy_selected_highlight(self):
        vals = self._get_selected_row()
        if vals:
            self.clipboard_clear()
            self.clipboard_append(vals[3])
            self.update()

    def _copy_selected_row(self):
        vals = self._get_selected_row()
        if vals:
            row_tsv = f"{vals[1]}\t{vals[2]}\t{vals[3]}\t{vals[5]}\t{vals[6]}"
            self.clipboard_clear()
            self.clipboard_append(row_tsv)
            self.update()
