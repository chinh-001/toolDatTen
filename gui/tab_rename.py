"""
RenameTab - Giao diện và logic của tab Đổi Tên Video.
Được tách từ app.py để đảm bảo code modular và dễ bảo trì.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading

from core.scanner import scan_video_folder
from core.matcher import match_all_titles
from core.renamer import build_rename_plan, execute_renames
from core.video_name_extractor import quick_export_folder_to_txt
from gui.widgets import ResultTable
from gui.dialog_extract_names import ExtractVideoNamesDialog
from utils.constants import (
    DEFAULT_MATCH_THRESHOLD, DEFAULT_START_NUMBER,
    DEFAULT_SEPARATOR, DEFAULT_CODE_PREFIX,
)


class RenameTab(ttk.Frame):
    """Tab Đổi Tên Video Theo Danh Sách."""

    def __init__(self, parent, log_panel, **kwargs):
        super().__init__(parent, **kwargs)
        self.log_panel = log_panel

        # State
        self._folder_path = tk.StringVar(value="")
        self._code_prefix = tk.StringVar(value=DEFAULT_CODE_PREFIX)
        self._separator = tk.StringVar(value=DEFAULT_SEPARATOR)
        self._start_number = tk.IntVar(value=DEFAULT_START_NUMBER)
        self._threshold = tk.IntVar(value=DEFAULT_MATCH_THRESHOLD)
        self._match_results = []
        self._rename_plan = []

        self._build_ui()

    def _build_ui(self):
        """Xây dựng giao diện Tab 1."""
        # Top section: Inputs and settings
        top_frame = ttk.Frame(self)
        top_frame.pack(fill='x', pady=(0, 8))

        # Left side: Title input
        self._build_title_input(top_frame)

        # Right side: Settings
        self._build_settings(top_frame)

        # Middle: Action Buttons
        self._build_buttons(self)

        # Bottom section: Results Table
        self._build_result_section(self)

    def _build_title_input(self, parent):
        """Xây dựng phần nhập danh sách tiêu đề."""
        frame = ttk.LabelFrame(parent, text="📋 Danh sách tiêu đề (mỗi dòng 1 tiêu đề)",
                               style='Section.TLabelframe', padding=8)
        frame.pack(side='left', fill='both', expand=True, padx=(0, 8))

        self.title_text = tk.Text(
            frame,
            height=8,
            wrap='word',
            font=('Segoe UI', 10),
            bg='#ffffff',
            fg='#2c3e50',
            relief='flat',
            borderwidth=1,
            padx=8,
            pady=6,
            insertbackground='#3498db',
            selectbackground='#3498db',
            selectforeground='white',
        )

        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.title_text.yview)
        self.title_text.configure(yscrollcommand=scrollbar.set)

        self.title_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    def _build_settings(self, parent):
        """Xây dựng phần cài đặt."""
        frame = ttk.LabelFrame(parent, text="⚙️ Cài đặt",
                               style='Section.TLabelframe', padding=8)
        frame.pack(side='right', fill='y', ipadx=8)

        # Folder picker
        ttk.Label(frame, text="📂 Thư mục video:").grid(
            row=0, column=0, sticky='w', padx=(0, 4), pady=2)

        folder_frame = ttk.Frame(frame)
        folder_frame.grid(row=1, column=0, sticky='ew', pady=(0, 8))

        folder_entry = ttk.Entry(folder_frame, textvariable=self._folder_path, width=30)
        folder_entry.pack(side='left', fill='x', expand=True)

        ttk.Button(folder_frame, text="Chọn...", command=self._pick_folder).pack(
            side='right', padx=(4, 0))

        # Quick Export TXT button
        ttk.Button(
            frame,
            text="📄 Trích & Xuất file .TXT tên video",
            command=self._on_quick_export_txt
        ).grid(row=2, column=0, sticky='ew', pady=(0, 6))

        # Separator line
        ttk.Separator(frame, orient='horizontal').grid(
            row=3, column=0, sticky='ew', pady=4)

        # Preview format
        ttk.Label(frame, text="📝 Format: {mã}{số}{dấu phân cách}{tên gốc}",
                  font=('Segoe UI', 8, 'italic')).grid(
            row=4, column=0, sticky='w', pady=(0, 4))

        # Code prefix
        ttk.Label(frame, text="Mã (prefix):").grid(
            row=5, column=0, sticky='w', pady=2)
        ttk.Entry(frame, textvariable=self._code_prefix, width=15).grid(
            row=6, column=0, sticky='ew', pady=(0, 4))

        # Separator
        ttk.Label(frame, text="Dấu phân cách:").grid(
            row=7, column=0, sticky='w', pady=2)
        ttk.Entry(frame, textvariable=self._separator, width=15).grid(
            row=8, column=0, sticky='ew', pady=(0, 4))

        # Start number
        ttk.Label(frame, text="Bắt đầu từ số:").grid(
            row=9, column=0, sticky='w', pady=2)
        ttk.Spinbox(frame, from_=0, to=9999, textvariable=self._start_number,
                    width=10).grid(
            row=10, column=0, sticky='w', pady=(0, 4))

        # Threshold
        ttk.Label(frame, text="Ngưỡng khớp (%):").grid(
            row=11, column=0, sticky='w', pady=2)

        threshold_frame = ttk.Frame(frame)
        threshold_frame.grid(row=12, column=0, sticky='ew', pady=(0, 4))

        self._threshold_label = ttk.Label(threshold_frame,
                                          text=f"{self._threshold.get()}%",
                                          width=5)
        self._threshold_label.pack(side='right')

        threshold_scale = ttk.Scale(
            threshold_frame,
            from_=10, to=100,
            orient='horizontal',
            variable=self._threshold,
            command=self._on_threshold_change,
        )
        threshold_scale.pack(side='left', fill='x', expand=True)

        # Live preview of format
        ttk.Separator(frame, orient='horizontal').grid(
            row=13, column=0, sticky='ew', pady=4)

        ttk.Label(frame, text="Xem trước tên:", font=('Segoe UI', 8)).grid(
            row=14, column=0, sticky='w', pady=2)

        self._preview_label = ttk.Label(
            frame, text="", font=('Segoe UI', 9, 'italic'),
            foreground='#3498db')
        self._preview_label.grid(row=15, column=0, sticky='w')

        # Bind changes to update preview
        self._code_prefix.trace_add('write', self._update_format_preview)
        self._separator.trace_add('write', self._update_format_preview)
        self._start_number.trace_add('write', self._update_format_preview)

        # Initial preview
        self._update_format_preview()

    def _build_buttons(self, parent):
        """Xây dựng các nút hành động."""
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill='x', pady=4)

        self.btn_preview = ttk.Button(
            btn_frame, text="🔍 Xem trước",
            style='Action.TButton',
            command=self._on_preview,
        )
        self.btn_preview.pack(side='left', padx=(0, 8))

        self.btn_rename = ttk.Button(
            btn_frame, text="✅ Đổi tên",
            style='Action.TButton',
            command=self._on_rename,
            state='disabled',
        )
        self.btn_rename.pack(side='left', padx=(0, 8))

        self.btn_extract = ttk.Button(
            btn_frame, text="📋 Xem trước & Xuất .TXT Tên Video",
            command=self._on_extract_video_names,
        )
        self.btn_extract.pack(side='left', padx=(0, 8))

        self.btn_clear = ttk.Button(
            btn_frame, text="🗑 Xóa tất cả",
            command=self._on_clear,
        )
        self.btn_clear.pack(side='right')

        # Stats label
        self._stats_label = ttk.Label(btn_frame, text="",
                                      font=('Segoe UI', 9))
        self._stats_label.pack(side='right', padx=16)

    def _build_result_section(self, parent):
        """Xây dựng bảng kết quả."""
        frame = ttk.LabelFrame(parent, text="📊 Kết quả đối chiếu",
                               style='Section.TLabelframe', padding=4)
        frame.pack(fill='both', expand=True, pady=(0, 4))

        self.result_table = ResultTable(frame)
        self.result_table.pack(fill='both', expand=True)

    # ==========================================
    # Event handlers
    # ==========================================

    def _pick_folder(self):
        """Mở dialog chọn thư mục."""
        folder = filedialog.askdirectory(title="Chọn thư mục chứa video")
        if folder:
            self._folder_path.set(folder)
            self.log_panel.log(f"Đã chọn thư mục: {folder}")

    def _on_quick_export_txt(self):
        """Mở dialog xem trước và trích xuất danh sách tên video từ thư mục."""
        folder = self._folder_path.get().strip()
        if not folder:
            folder = filedialog.askdirectory(title="Chọn thư mục chứa video để trích tên", parent=self)
            if not folder:
                return
            self._folder_path.set(folder)

        ExtractVideoNamesDialog(
            self,
            initial_folder=folder,
            on_apply_titles=self._set_titles_text,
            log_panel=self.log_panel
        )

    def _on_extract_video_names(self):
        """Mở dialog trích xuất danh sách tên video từ thư mục."""
        folder = self._folder_path.get()
        ExtractVideoNamesDialog(
            self,
            initial_folder=folder,
            on_apply_titles=self._set_titles_text,
            log_panel=self.log_panel
        )

    def _set_titles_text(self, text):
        """Nạp danh sách tiêu đề vào khung Text."""
        self.title_text.delete('1.0', 'end')
        self.title_text.insert('1.0', text)
        self.log_panel.log("Đã cập nhật danh sách tiêu đề.", 'info')

    def _on_threshold_change(self, value):
        """Cập nhật label khi thay đổi ngưỡng."""
        self._threshold_label.configure(text=f"{int(float(value))}%")

    def _update_format_preview(self, *args):
        """Cập nhật preview tên file khi thay đổi cài đặt."""
        try:
            code = self._code_prefix.get()
            sep = self._separator.get()
            num = self._start_number.get()
            preview = f"{code}{num}{sep}tên_video.mp4"
            self._preview_label.configure(text=preview)
        except (tk.TclError, ValueError):
            self._preview_label.configure(text="...")

    def _get_titles(self):
        """Lấy danh sách tiêu đề từ textarea."""
        raw = self.title_text.get('1.0', 'end').strip()
        if not raw:
            return []
        lines = [line.strip() for line in raw.split('\n')]
        return [line for line in lines if line]  # Bỏ dòng trống

    def _validate_inputs(self):
        """Kiểm tra input hợp lệ."""
        titles = self._get_titles()
        if not titles:
            messagebox.showwarning("Thiếu dữ liệu",
                                   "Vui lòng nhập danh sách tiêu đề!")
            return False

        folder = self._folder_path.get()
        if not folder:
            messagebox.showwarning("Thiếu dữ liệu",
                                   "Vui lòng chọn thư mục video!")
            return False

        return True

    def _on_preview(self):
        """Xử lý khi nhấn nút Xem trước."""
        if not self._validate_inputs():
            return

        self.log_panel.clear()
        self.result_table.clear()
        self.btn_rename.configure(state='disabled')
        self._stats_label.configure(text="Đang xử lý...")

        titles = self._get_titles()
        folder = self._folder_path.get()
        threshold = self._threshold.get()

        self.log_panel.log(f"Bắt đầu quét thư mục: {folder}")
        self.log_panel.log(f"Số tiêu đề: {len(titles)} | Ngưỡng: {threshold}%")

        # Run heavy logic in thread to avoid freezing GUI
        def worker():
            try:
                # Scan thư mục
                video_files = scan_video_folder(folder)
                self.log_panel.log(f"Tìm thấy {len(video_files)} file video trong thư mục", 'success')

                if not video_files:
                    self.log_panel.log("Không tìm thấy file video nào!", 'warning')
                    self.after(0, lambda: self._stats_label.configure(text="Không có video"))
                    return

                # Matching
                self.log_panel.log("Đang đối chiếu tiêu đề với file video...")
                self._match_results = match_all_titles(titles, video_files, threshold)

                # Build rename plan
                self._rename_plan = build_rename_plan(
                    self._match_results,
                    code_prefix=self._code_prefix.get(),
                    separator=self._separator.get(),
                    start_number=self._start_number.get(),
                )

                # Hiển thị kết quả trong main thread
                self.after(0, self._show_preview_results)
            except Exception as e:
                self.after(0, lambda: self._handle_error(e))

        threading.Thread(target=worker, daemon=True).start()

    def _show_preview_results(self):
        """Hiển thị kết quả preview lên giao diện."""
        self.result_table.load_preview_results(self._match_results, self._rename_plan)

        # Thống kê
        matched_count = sum(1 for r in self._match_results if r['status'] == 'matched')
        total = len(self._match_results)
        self._stats_label.configure(text=f"Khớp: {matched_count}/{total} tiêu đề")

        self.log_panel.log(
            f"Hoàn tất: {matched_count}/{total} tiêu đề khớp với file video",
            'success' if matched_count > 0 else 'warning'
        )

        if matched_count > 0:
            self.btn_rename.configure(state='normal')
            self.log_panel.log("Nhấn 'Đổi tên' để thực hiện đổi tên.", 'info')

    def _on_rename(self):
        """Xử lý khi nhấn nút Đổi tên."""
        if not self._rename_plan:
            messagebox.showinfo("Thông báo", "Không có file nào để đổi tên.")
            return

        count = len(self._rename_plan)
        confirm = messagebox.askyesno(
            "Xác nhận đổi tên",
            f"Bạn có chắc muốn đổi tên {count} file video?\n\n"
            "Hành động này không thể hoàn tác!",
            icon='warning'
        )

        if not confirm:
            return

        self.log_panel.log(f"Bắt đầu đổi tên {count} file...")
        self.btn_rename.configure(state='disabled')
        self.btn_preview.configure(state='disabled')

        def worker():
            try:
                results = execute_renames(self._rename_plan)
                self.after(0, lambda: self._show_rename_results(results, count))
            except Exception as e:
                self.after(0, lambda: self._handle_error(e))

        threading.Thread(target=worker, daemon=True).start()

    def _show_rename_results(self, results, count):
        """Hiển thị kết quả đổi tên và bật lại các nút."""
        self.result_table.load_rename_results(results)

        success_count = sum(1 for r in results if r['success'])
        fail_count = count - success_count

        for r in results:
            if r['success']:
                self.log_panel.log(f"✅ {r['old_name']} → {r['new_name']}", 'success')
            else:
                self.log_panel.log(f"❌ {r['old_name']}: {r['error']}", 'error')

        self.log_panel.log(
            f"Hoàn tất: {success_count} thành công, {fail_count} lỗi",
            'success' if fail_count == 0 else 'warning'
        )

        self._stats_label.configure(text=f"Đổi tên: {success_count}/{count} thành công")
        self.btn_preview.configure(state='normal')
        self._rename_plan = []

        if fail_count == 0:
            messagebox.showinfo("Thành công", f"Đã đổi tên thành công {success_count} file!")
        else:
            messagebox.showwarning("Hoàn tất", f"Thành công: {success_count}\nLỗi: {fail_count}")

    def _handle_error(self, e):
        """Xử lý và hiển thị lỗi."""
        self.btn_preview.configure(state='normal')
        self._stats_label.configure(text="Lỗi xảy ra")
        self.log_panel.log(f"Lỗi: {e}", 'error')
        messagebox.showerror("Lỗi", str(e))

    def _on_clear(self):
        """Xóa tất cả dữ liệu trên tab Đổi tên."""
        self.title_text.delete('1.0', 'end')
        self._folder_path.set("")
        self._code_prefix.set(DEFAULT_CODE_PREFIX)
        self._separator.set(DEFAULT_SEPARATOR)
        self._start_number.set(DEFAULT_START_NUMBER)
        self._threshold.set(DEFAULT_MATCH_THRESHOLD)
        self.result_table.clear()
        self.btn_rename.configure(state='disabled')
        self._stats_label.configure(text="")
        self._match_results = []
        self._rename_plan = []
        self.log_panel.log("Đã xóa tất cả dữ liệu Tab Đổi tên.", 'info')
