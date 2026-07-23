"""
DurationCheckerTab - Giao diện và logic của tab Check Thời Lượng Video & Xóa Video Ngắn.
Được thiết kế modular, chuyên nghiệp và dễ bảo trì.
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading

from core.video_checker import (
    scan_and_check_durations,
    delete_video_file,
    batch_delete_videos,
    format_file_size,
)
from utils.constants import DEFAULT_DURATION_THRESHOLD_SEC


class DurationCheckerTab(ttk.Frame):
    """Tab Check Thời Lượng Video và Xóa Video Ngắn."""

    def __init__(self, parent, log_panel, **kwargs):
        super().__init__(parent, **kwargs)
        self.log_panel = log_panel

        # State variables
        self._folder_path = tk.StringVar(value="")
        self._threshold_sec = tk.IntVar(value=DEFAULT_DURATION_THRESHOLD_SEC)
        
        self._short_videos = []
        self._long_videos = []
        
        self._is_scanning = False
        self._cancel_event = threading.Event()

        self._build_ui()

    def _build_ui(self):
        """Xây dựng toàn bộ giao diện cho Tab."""
        # Top section: Input Controls & Settings
        top_frame = ttk.LabelFrame(self, text="⚙️ Cài đặt & Điều khiển", style='Section.TLabelframe', padding=8)
        top_frame.pack(fill='x', pady=(0, 6))

        self._build_header_controls(top_frame)

        # Progress bar section
        self._progress_frame = ttk.Frame(self)
        self._progress_frame.pack(fill='x', pady=(0, 6))

        self.progress_bar = ttk.Progressbar(self._progress_frame, mode='determinate')
        self.progress_bar.pack(fill='x', side='top', pady=(0, 2))

        self.lbl_progress_status = ttk.Label(self._progress_frame, text="Sẵn sàng quét thư mục video.", font=('Segoe UI', 9, 'italic'))
        self.lbl_progress_status.pack(anchor='w')

        # Main Split View (PanedWindow) for Short & Long videos
        paned = ttk.PanedWindow(self, orient='vertical')
        paned.pack(fill='both', expand=True, pady=(0, 4))

        # --- Section 1: Video Dưới Ngưỡng (< 1 phút) ---
        short_frame = ttk.LabelFrame(paned, text="🔴 Danh Sách Video Dưới Ngưỡng (< 1 phút)", style='Section.TLabelframe', padding=6)
        paned.add(short_frame, weight=1)

        self._build_short_videos_section(short_frame)

        # --- Section 2: Video Đạt Ngưỡng (>= 1 phút) ---
        long_frame = ttk.LabelFrame(paned, text="🟢 Danh Sách Video Đạt Ngưỡng (>= 1 phút)", style='Section.TLabelframe', padding=6)
        paned.add(long_frame, weight=1)

        self._build_long_videos_section(long_frame)

    def _build_header_controls(self, parent):
        """Xây dựng phần nhập đường dẫn thư mục và cấu hình ngưỡng lọc."""
        # Grid layout inside top_frame
        parent.columnconfigure(1, weight=1)

        # Row 0: Folder picker
        ttk.Label(parent, text="📂 Thư mục video:").grid(row=0, column=0, sticky='w', padx=(0, 6), pady=4)

        folder_subframe = ttk.Frame(parent)
        folder_subframe.grid(row=0, column=1, columnspan=2, sticky='ew', pady=4)

        entry_folder = ttk.Entry(folder_subframe, textvariable=self._folder_path)
        entry_folder.pack(side='left', fill='x', expand=True, padx=(0, 6))

        ttk.Button(folder_subframe, text="Chọn...", command=self._pick_folder).pack(side='right')

        # Row 1: Threshold setting & Presets
        ttk.Label(parent, text="⏱️ Ngưỡng lọc (giây):").grid(row=1, column=0, sticky='w', padx=(0, 6), pady=4)

        thresh_subframe = ttk.Frame(parent)
        thresh_subframe.grid(row=1, column=1, sticky='w', pady=4)

        spin_thresh = ttk.Spinbox(thresh_subframe, from_=1, to=3600, textvariable=self._threshold_sec, width=8)
        spin_thresh.pack(side='left', padx=(0, 8))

        ttk.Label(thresh_subframe, text="Nhanh:").pack(side='left', padx=(4, 4))
        
        ttk.Button(thresh_subframe, text="30s", width=5, command=lambda: self._set_threshold(30)).pack(side='left', padx=2)
        ttk.Button(thresh_subframe, text="60s (1p)", width=8, command=lambda: self._set_threshold(60)).pack(side='left', padx=2)
        ttk.Button(thresh_subframe, text="120s (2p)", width=9, command=lambda: self._set_threshold(120)).pack(side='left', padx=2)
        ttk.Button(thresh_subframe, text="180s (3p)", width=9, command=lambda: self._set_threshold(180)).pack(side='left', padx=2)

        # Row 1 Right side: Action Buttons
        btn_action_subframe = ttk.Frame(parent)
        btn_action_subframe.grid(row=1, column=2, sticky='e', pady=4)

        self.btn_scan = ttk.Button(
            btn_action_subframe, text="🔍 Quét & Check thời lượng",
            style='Action.TButton', command=self._on_scan
        )
        self.btn_scan.pack(side='left', padx=(0, 6))

        self.btn_stop = ttk.Button(
            btn_action_subframe, text="⛔ Dừng",
            command=self._on_stop, state='disabled'
        )
        self.btn_stop.pack(side='left')

    def _build_short_videos_section(self, parent):
        """Xây dựng phần danh sách video dưới ngưỡng và các nút xóa."""
        # Top toolbar of short videos section
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill='x', pady=(0, 4))

        self.lbl_short_stats = ttk.Label(
            toolbar, text="Số lượng: 0 video | Dung lượng: 0 B",
            font=('Segoe UI', 9, 'bold'), foreground='#e74c3c'
        )
        self.lbl_short_stats.pack(side='left', anchor='w')

        # Delete action buttons
        self.btn_delete_all_short = ttk.Button(
            toolbar, text="🗑️ Xóa TẤT CẢ video dưới 1 phút trong danh sách",
            command=self._on_delete_all_short, state='disabled'
        )
        self.btn_delete_all_short.pack(side='right', padx=(6, 0))

        self.btn_delete_selected_short = ttk.Button(
            toolbar, text="❌ Xóa video đã chọn",
            command=self._on_delete_selected_short, state='disabled'
        )
        self.btn_delete_selected_short.pack(side='right')

        # Treeview Table for Short Videos
        cols = ('stt', 'name', 'duration', 'size', 'path')
        self.tree_short = ttk.Treeview(
            parent, columns=cols, show='headings', selectmode='extended', height=6
        )

        self.tree_short.heading('stt', text='#')
        self.tree_short.heading('name', text='Tên File Video')
        self.tree_short.heading('duration', text='Thời lượng')
        self.tree_short.heading('size', text='Kích thước')
        self.tree_short.heading('path', text='Đường dẫn tuyệt đối')

        self.tree_short.column('stt', width=40, minwidth=40, anchor='center')
        self.tree_short.column('name', width=220, minwidth=140)
        self.tree_short.column('duration', width=90, minwidth=70, anchor='center')
        self.tree_short.column('size', width=100, minwidth=80, anchor='center')
        self.tree_short.column('path', width=350, minwidth=150)

        # Scrollbars
        sc_y = ttk.Scrollbar(parent, orient='vertical', command=self.tree_short.yview)
        sc_x = ttk.Scrollbar(parent, orient='horizontal', command=self.tree_short.xview)
        self.tree_short.configure(yscrollcommand=sc_y.set, xscrollcommand=sc_x.set)

        self.tree_short.pack(side='top', fill='both', expand=True)

        # Tags cho dòng
        self.tree_short.tag_configure('short_row', background='#fadbd8')

        # Bind select event to enable/disable selected delete button
        self.tree_short.bind('<<TreeviewSelect>>', self._on_short_tree_select)

    def _build_long_videos_section(self, parent):
        """Xây dựng phần danh sách video đạt ngưỡng."""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill='x', pady=(0, 4))

        self.lbl_long_stats = ttk.Label(
            toolbar, text="Số lượng: 0 video | Dung lượng: 0 B",
            font=('Segoe UI', 9, 'bold'), foreground='#27ae60'
        )
        self.lbl_long_stats.pack(side='left', anchor='w')

        cols = ('stt', 'name', 'duration', 'size', 'path')
        self.tree_long = ttk.Treeview(
            parent, columns=cols, show='headings', selectmode='browse', height=6
        )

        self.tree_long.heading('stt', text='#')
        self.tree_long.heading('name', text='Tên File Video')
        self.tree_long.heading('duration', text='Thời lượng')
        self.tree_long.heading('size', text='Kích thước')
        self.tree_long.heading('path', text='Đường dẫn tuyệt đối')

        self.tree_long.column('stt', width=40, minwidth=40, anchor='center')
        self.tree_long.column('name', width=220, minwidth=140)
        self.tree_long.column('duration', width=90, minwidth=70, anchor='center')
        self.tree_long.column('size', width=100, minwidth=80, anchor='center')
        self.tree_long.column('path', width=350, minwidth=150)

        sc_y = ttk.Scrollbar(parent, orient='vertical', command=self.tree_long.yview)
        self.tree_long.configure(yscrollcommand=sc_y.set)

        self.tree_long.pack(side='top', fill='both', expand=True)

        # Tag màu sắc cho video đạt ngưỡng
        self.tree_long.tag_configure('long_row', background='#d5f5e3')

    # ==========================================
    # Event Handlers & Helper Methods
    # ==========================================

    def _pick_folder(self):
        """Mở dialog chọn thư mục chứa video."""
        folder = filedialog.askdirectory(title="Chọn thư mục chứa video cần check thời lượng")
        if folder:
            self._folder_path.set(folder)
            self.log_panel.log(f"Đã chọn thư mục check thời lượng: {folder}")

    def _set_threshold(self, val):
        """Đặt giá trị ngưỡng thời lượng nhanh."""
        self._threshold_sec.set(val)

    def _on_short_tree_select(self, event):
        """Kích hoạt/vô hiệu nút xóa video đã chọn khi người dùng chọn dòng."""
        selected = self.tree_short.selection()
        if selected and not self._is_scanning:
            self.btn_delete_selected_short.configure(state='normal')
        else:
            self.btn_delete_selected_short.configure(state='disabled')

    def _on_stop(self):
        """Xử lý khi nhấn nút Dừng quét."""
        if self._is_scanning:
            self._cancel_event.set()
            self.log_panel.log("Đã phát lệnh dừng quét video...", 'warning')
            self.lbl_progress_status.configure(text="Đang dừng quét...")

    def _on_scan(self):
        """Bắt đầu quét thư mục và check thời lượng trên Thread ngầm."""
        folder = self._folder_path.get().strip()
        if not folder:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng chọn thư mục chứa video!")
            return

        if not os.path.exists(folder):
            messagebox.showerror("Lỗi thư mục", "Thư mục đã chọn không tồn tại trên hệ thống!")
            return

        threshold = self._threshold_sec.get()
        if threshold <= 0:
            messagebox.showwarning("Cài đặt không hợp lệ", "Ngưỡng thời lượng phải lớn hơn 0 giây!")
            return

        # Prepare UI state for scanning
        self._is_scanning = True
        self._cancel_event.clear()
        self.btn_scan.configure(state='disabled')
        self.btn_stop.configure(state='normal')
        self.btn_delete_all_short.configure(state='disabled')
        self.btn_delete_selected_short.configure(state='disabled')

        # Clear existing tables
        self._clear_tables()

        self.log_panel.log(f"Bắt đầu quét thời lượng video tại: {folder} (Ngưỡng: < {threshold}s)", 'info')

        # Worker thread
        def worker():
            def progress_cb(current, total, filename, status_info):
                percent = int((current / total) * 100) if total > 0 else 0
                self.after(0, lambda: self._update_progress_ui(current, total, percent, filename))

            try:
                res = scan_and_check_durations(
                    folder_path=folder,
                    threshold_sec=threshold,
                    progress_callback=progress_cb,
                    cancel_event=self._cancel_event
                )
                self.after(0, lambda: self._on_scan_completed(res))
            except Exception as e:
                self.after(0, lambda: self._handle_error(e))

        threading.Thread(target=worker, daemon=True).start()

    def _update_progress_ui(self, current, total, percent, filename):
        """Cập nhật thanh tiến trình và thông báo trong main thread."""
        self.progress_bar['value'] = percent
        self.lbl_progress_status.configure(
            text=f"Đang check [{current}/{total}] ({percent}%): {filename}"
        )

    def _on_scan_completed(self, result):
        """Hiển thị kết quả sau khi quét hoàn tất."""
        self._is_scanning = False
        self.btn_scan.configure(state='normal')
        self.btn_stop.configure(state='disabled')

        self._short_videos = result.get('short_videos', [])
        self._long_videos = result.get('long_videos', [])
        total_count = result.get('total_count', 0)
        was_cancelled = result.get('cancelled', False)

        # Populate tables
        self._render_short_videos_table()
        self._render_long_videos_table()

        if was_cancelled:
            self.lbl_progress_status.configure(text=f"Đã dừng quét. Đã xử lý {len(self._short_videos) + len(self._long_videos)}/{total_count} video.")
            self.log_panel.log(f"Quét bị hủy bởi người dùng.", 'warning')
        else:
            self.progress_bar['value'] = 100
            self.lbl_progress_status.configure(text=f"Hoàn tất quét {total_count} video.")
            self.log_panel.log(
                f"Quét hoàn tất {total_count} video: {len(self._short_videos)} video dưới {self._threshold_sec.get()}s, {len(self._long_videos)} video đạt ngưỡng.",
                'success'
            )

        if self._short_videos:
            self.btn_delete_all_short.configure(state='normal')

    def _render_short_videos_table(self):
        """Nạp dữ liệu vào bảng video dưới ngưỡng và tính tổng dung lượng."""
        for item in self.tree_short.get_children():
            self.tree_short.delete(item)

        total_bytes = 0
        for idx, video in enumerate(self._short_videos):
            total_bytes += video['size']
            self.tree_short.insert(
                '', 'end', iid=video['path'],
                values=(
                    idx + 1,
                    video['name'],
                    video['duration_str'],
                    video['size_str'],
                    video['path']
                ),
                tags=('short_row',)
            )

        thresh_label = f"{self._threshold_sec.get()}s"
        self.lbl_short_stats.configure(
            text=f"Số lượng: {len(self._short_videos)} video (< {thresh_label}) | Dung lượng: {format_file_size(total_bytes)}"
        )

        if self._short_videos and not self._is_scanning:
            self.btn_delete_all_short.configure(state='normal')
        else:
            self.btn_delete_all_short.configure(state='disabled')

        self.btn_delete_selected_short.configure(state='disabled')

    def _render_long_videos_table(self):
        """Nạp dữ liệu vào bảng video đạt ngưỡng và tính tổng dung lượng."""
        for item in self.tree_long.get_children():
            self.tree_long.delete(item)

        total_bytes = 0
        for idx, video in enumerate(self._long_videos):
            total_bytes += video['size']
            self.tree_long.insert(
                '', 'end', iid=video['path'],
                values=(
                    idx + 1,
                    video['name'],
                    video['duration_str'],
                    video['size_str'],
                    video['path']
                ),
                tags=('long_row',)
            )

        thresh_label = f"{self._threshold_sec.get()}s"
        self.lbl_long_stats.configure(
            text=f"Số lượng: {len(self._long_videos)} video (>= {thresh_label}) | Dung lượng: {format_file_size(total_bytes)}"
        )

    def _on_delete_all_short(self):
        """Xử lý khi người dùng nhấn nút xóa tất cả video dưới ngưỡng."""
        if not self._short_videos:
            messagebox.showinfo("Thông báo", "Không có video nào trong danh sách dưới ngưỡng!")
            return

        thresh_name = f"{self._threshold_sec.get()} giây"
        count = len(self._short_videos)

        confirm = messagebox.askyesno(
            "Xác nhận xóa tất cả video ngắn",
            f"⚠️ BẠN CÓ CHẮC CHẮN MỐN XÓA TẤT CẢ {count} VIDEO DƯỚI {thresh_name.upper()} KHỎI ĐĨA CỨNG?\n\n"
            "Các tệp tin sẽ bị xóa vĩnh viễn và không thể khôi phục!",
            icon='warning'
        )

        if not confirm:
            return

        paths_to_delete = [v['path'] for v in self._short_videos]
        self._execute_batch_delete(paths_to_delete)

    def _on_delete_selected_short(self):
        """Xử lý khi người dùng chọn 1 hoặc nhiều dòng video ngắn và bấm xóa."""
        selected_iids = self.tree_short.selection()
        if not selected_iids:
            messagebox.showinfo("Thông báo", "Vui lòng chọn ít nhất một video trong bảng để xóa.")
            return

        count = len(selected_iids)
        confirm = messagebox.askyesno(
            "Xác nhận xóa video đã chọn",
            f"Bạn có chắc muốn xóa {count} video đã chọn khỏi đĩa cứng?\n\n"
            "Hành động này không thể hoàn tác!",
            icon='warning'
        )

        if not confirm:
            return

        self._execute_batch_delete(list(selected_iids))

    def _execute_batch_delete(self, filepath_list):
        """Thực hiện xóa danh sách tệp trên đĩa và cập nhật giao diện ngay lập tức."""
        self.btn_delete_all_short.configure(state='disabled')
        self.btn_delete_selected_short.configure(state='disabled')

        self.log_panel.log(f"Đang thực hiện xóa {len(filepath_list)} tệp video...", 'info')

        def worker():
            res = batch_delete_videos(filepath_list)
            self.after(0, lambda: self._on_delete_completed(res))

        threading.Thread(target=worker, daemon=True).start()

    def _on_delete_completed(self, delete_res):
        """Cập nhật lại danh sách dữ liệu và giao diện sau khi xóa tệp."""
        success_count = delete_res['success_count']
        fail_count = delete_res['fail_count']
        results = delete_res['results']

        deleted_paths = set()
        for r in results:
            if r['success']:
                deleted_paths.add(r['path'])
                self.log_panel.log(f"🗑️ Đã xóa file: {r['name']}", 'success')
            else:
                self.log_panel.log(f"❌ Không thể xóa {r['name']}: {r['error']}", 'error')

        # Cập nhật lại mảng dữ liệu local
        self._short_videos = [v for v in self._short_videos if v['path'] not in deleted_paths]

        # Vẽ lại bảng video ngắn
        self._render_short_videos_table()

        self.log_panel.log(
            f"Hoàn tất xóa: {success_count} tệp đã xóa thành công, {fail_count} lỗi.",
            'success' if fail_count == 0 else 'warning'
        )

        if fail_count == 0:
            messagebox.showinfo("Thành công", f"Đã xóa thành công {success_count} tệp video!")
        else:
            messagebox.showwarning("Hoàn tất", f"Thành công: {success_count}\nLỗi: {fail_count}")

    def _clear_tables(self):
        """Xóa trắng các bảng hiển thị."""
        self._short_videos = []
        self._long_videos = []
        for item in self.tree_short.get_children():
            self.tree_short.delete(item)
        for item in self.tree_long.get_children():
            self.tree_long.delete(item)
        self.lbl_short_stats.configure(text="Số lượng: 0 video | Dung lượng: 0 B")
        self.lbl_long_stats.configure(text="Số lượng: 0 video | Dung lượng: 0 B")

    def _handle_error(self, e):
        """Xử lý ngoại lệ."""
        self._is_scanning = False
        self.btn_scan.configure(state='normal')
        self.btn_stop.configure(state='disabled')
        self.lbl_progress_status.configure(text="Xảy ra lỗi trong quá trình xử lý.")
        self.log_panel.log(f"Lỗi: {e}", 'error')
        messagebox.showerror("Lỗi hệ thống", str(e))
