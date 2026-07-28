"""
ExtractVideoNamesDialog - Giao diện trích xuất tên file video từ thư mục.
Cho phép xem trước, chỉnh sửa, sắp xếp theo số thứ tự (từ nhỏ -> lớn, video không số ở cuối),
định dạng cách dòng, copy vào Clipboard và xuất file .TXT.
Được thiết kế riêng theo quy chuẩn modular.
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core.video_name_extractor import (
    extract_video_names,
    format_video_names_spaced
)


class ExtractVideoNamesDialog(tk.Toplevel):
    """Cửa sổ Modal/Dialog Trích xuất, Xem Trước & Xuất tên file video."""

    def __init__(self, parent, initial_folder="", on_apply_titles=None, log_panel=None):
        super().__init__(parent)
        self.title("📋 Xem Trước & Trích Xuất Tên Video Từ Thư Mục")
        self.geometry("750x580")
        self.minsize(650, 480)

        self.on_apply_titles = on_apply_titles
        self.log_panel = log_panel

        # State
        self._folder_path = tk.StringVar(value=initial_folder)
        self._keep_ext = tk.BooleanVar(value=False)
        self._double_spacing = tk.BooleanVar(value=True)
        self._sort_by_number = tk.BooleanVar(value=True)
        self._video_names = []

        # Modal settings
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._center_window(parent)

        # Nếu đã có đường dẫn thư mục ban đầu, thực hiện trích xuất luôn
        if self._folder_path.get().strip():
            self._do_extract()

    def _center_window(self, parent):
        """Đặt cửa sổ ở giữa cửa sổ cha."""
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()

        dw = self.winfo_width()
        dh = self.winfo_height()

        x = px + max(0, (pw - dw) // 2)
        y = py + max(0, (ph - dh) // 2)
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        """Xây dựng giao diện Dialog."""
        main_frame = ttk.Frame(self, padding=12)
        main_frame.pack(fill='both', expand=True)

        # 1. Top Section: Thư mục & Tùy chọn
        top_frame = ttk.LabelFrame(main_frame, text="📂 Thư mục & Tùy chọn sắp xếp",
                                   style='Section.TLabelframe', padding=8)
        top_frame.pack(fill='x', pady=(0, 8))

        # Folder picker row
        f_row = ttk.Frame(top_frame)
        f_row.pack(fill='x', pady=(0, 6))

        ttk.Label(f_row, text="Thư mục video:").pack(side='left', padx=(0, 6))
        folder_entry = ttk.Entry(f_row, textvariable=self._folder_path)
        folder_entry.pack(side='left', fill='x', expand=True, padx=(0, 6))

        ttk.Button(f_row, text="Chọn...", command=self._pick_folder).pack(side='right')

        # Options row 1: Sorting & Ext
        opt_row1 = ttk.Frame(top_frame)
        opt_row1.pack(fill='x', pady=(0, 4))

        cb_sort = ttk.Checkbutton(
            opt_row1,
            text="🔢 Sắp xếp theo số thứ tự (1 -> 9 -> 10, video không số ở cuối)",
            variable=self._sort_by_number,
            command=self._do_extract
        )
        cb_sort.pack(side='left', padx=(0, 16))

        cb_ext = ttk.Checkbutton(
            opt_row1,
            text="🏷️ Giữ đuôi file (.mp4, .mkv...)",
            variable=self._keep_ext,
            command=self._do_extract
        )
        cb_ext.pack(side='left')

        ttk.Button(opt_row1, text="🔄 Quét lại", command=self._do_extract).pack(side='right')

        # Options row 2: Spacing
        opt_row2 = ttk.Frame(top_frame)
        opt_row2.pack(fill='x')

        cb_spacing = ttk.Checkbutton(
            opt_row2,
            text="✨ Trình bày cách dòng (dòng trống giữa các tên)",
            variable=self._double_spacing,
            command=self._update_preview
        )
        cb_spacing.pack(side='left')

        # 2. Bottom Action Buttons Section (Pack trước ở bottom để không bao giờ bị che)
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', side='bottom', pady=(8, 0))

        ttk.Button(
            btn_frame,
            text="💾 XUẤT FILE .TXT",
            style='Action.TButton',
            command=self._export_to_txt
        ).pack(side='left', padx=(0, 8))

        ttk.Button(
            btn_frame,
            text="📋 Copy vào Clipboard",
            style='Action.TButton',
            command=self._copy_to_clipboard
        ).pack(side='left', padx=(0, 8))

        if self.on_apply_titles:
            ttk.Button(
                btn_frame,
                text="📥 Nạp vào ô Tiêu đề",
                command=self._apply_to_title_box
            ).pack(side='left', padx=(0, 8))

        ttk.Button(
            btn_frame,
            text="Đóng",
            command=self.destroy
        ).pack(side='right')

        # Status label
        self.status_label = ttk.Label(main_frame, text="Chưa chọn thư mục", font=('Segoe UI', 9, 'bold'), foreground='#2980b9')
        self.status_label.pack(side='bottom', anchor='w', pady=(4, 0))

        # 3. Middle Section: Danh sách tên video (Preview Text Area - Fill phần còn lại)
        preview_frame = ttk.LabelFrame(
            main_frame,
            text="📋 Xem trước & Kiểm tra tên video (Có thể chỉnh sửa trực tiếp trước khi xuất)",
            style='Section.TLabelframe',
            padding=8
        )
        preview_frame.pack(fill='both', expand=True, pady=(0, 4))

        self.preview_text = tk.Text(
            preview_frame,
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
            selectforeground='white'
        )

        scrollbar = ttk.Scrollbar(preview_frame, orient='vertical', command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=scrollbar.set)

        self.preview_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    def _pick_folder(self):
        """Mở dialog chọn thư mục."""
        folder = filedialog.askdirectory(title="Chọn thư mục chứa video", parent=self)
        if folder:
            self._folder_path.set(folder)
            self._do_extract()

    def _do_extract(self):
        """Thực hiện quét thư mục và lấy danh sách tên video."""
        folder = self._folder_path.get().strip()
        if not folder:
            self.status_label.configure(text="⚠️ Vui lòng chọn thư mục video.")
            return

        if not os.path.exists(folder):
            self.status_label.configure(text="❌ Thư mục không tồn tại.")
            return

        try:
            self._video_names = extract_video_names(
                folder,
                keep_extension=self._keep_ext.get(),
                sort_by_number=self._sort_by_number.get()
            )
            count = len(self._video_names)
            ext_status = "có đuôi" if self._keep_ext.get() else "bỏ đuôi"
            sort_status = "đã xếp theo số (1->9->10, không số ở cuối)" if self._sort_by_number.get() else "mặc định"
            self.status_label.configure(
                text=f"✅ Tìm thấy {count} video ({ext_status} | {sort_status})"
            )
            if self.log_panel:
                self.log_panel.log(f"Đã trích {count} tên video ({sort_status}) từ {folder}")
            self._update_preview()
        except Exception as e:
            self.status_label.configure(text=f"❌ Lỗi: {e}")
            if self.log_panel:
                self.log_panel.log(f"Lỗi khi trích tên video: {e}", 'error')

    def _update_preview(self):
        """Cập nhật nội dung hiển thị trong Text widget."""
        formatted_text = format_video_names_spaced(
            self._video_names,
            double_spacing=self._double_spacing.get()
        )
        self.preview_text.delete('1.0', 'end')
        self.preview_text.insert('1.0', formatted_text)

    def _get_current_text(self):
        """Lấy văn bản hiện tại trong ô Text xem trước."""
        return self.preview_text.get('1.0', 'end-1c')

    def _copy_to_clipboard(self):
        """Sao chép danh sách tên video đã xem trước vào Clipboard."""
        text = self._get_current_text().strip()
        if not text:
            messagebox.showwarning("Thông báo", "Không có dữ liệu để copy!", parent=self)
            return

        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()

        messagebox.showinfo(
            "Thành công",
            "Đã copy danh sách tên video vào Clipboard!",
            parent=self
        )
        if self.log_panel:
            self.log_panel.log("Đã copy danh sách tên video xem trước vào Clipboard.", 'success')

    def _export_to_txt(self):
        """Xuất nội dung đang xem trước ra file .TXT."""
        text = self._get_current_text().strip()
        if not text:
            messagebox.showwarning("Thông báo", "Không có nội dung để xuất!", parent=self)
            return

        default_file = "danh_sach_ten_video.txt"
        file_path = filedialog.asksaveasfilename(
            parent=self,
            title="Lưu file danh sách tên video",
            initialfile=default_file,
            defaultextension=".txt",
            filetypes=[("Text files (*.txt)", "*.txt"), ("All files (*.*)", "*.*")]
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text)

            messagebox.showinfo(
                "Xuất file thành công",
                f"✅ Đã xuất thành công danh sách tên video ra file:\n{file_path}",
                parent=self
            )
            if self.log_panel:
                self.log_panel.log(f"Đã xuất file .txt thành công: {file_path}", 'success')
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể lưu file: {e}", parent=self)
            if self.log_panel:
                self.log_panel.log(f"Lỗi khi xuất file .txt: {e}", 'error')

    def _apply_to_title_box(self):
        """Đưa danh sách tên video vào khung nhập tiêu đề của tab cha."""
        text = self._get_current_text()
        if self.on_apply_titles and text:
            self.on_apply_titles(text)
            if self.log_panel:
                self.log_panel.log("Đã nạp danh sách tiêu đề vào khung nhập.", 'info')
            self.destroy()
