"""
GeminiWebTab - Giao diện và logic của Tab 3 (Trích Highlight Video qua Gemini Web Automation).
Tự động hóa trình duyệt web Gemini để trích xuất timestamps mà không cần API key.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading

from core.parser import parse_raw_input
from core.gemini_web_automation import open_interactive_browser, get_default_user_data_dir
from core.gemini_web_handler import GeminiWebBatchWorker
from core.profile_manager import get_all_profiles, resolve_profile_dir, create_new_app_profile
from gui.widgets import HighlightResultTable, ErrorLogPanel
from utils.config import load_setting, save_setting
from utils.constants import DEFAULT_HIGHLIGHT_PROMPT
from utils.clipboard_formatter import (
    format_for_spreadsheet, format_single_for_spreadsheet
)


class GeminiWebTab(ttk.Frame):
    """Tab 3: Trích Highlight Video qua Gemini Web Automation."""

    def __init__(self, parent, log_panel, **kwargs):
        super().__init__(parent, **kwargs)
        self.log_panel = log_panel
        self.parsed_entries = []
        self.reprocess_entries = []
        self._is_processing = False
        self._current_worker = None
        self._profiles_map = {}

        self._build_ui()
        self._load_saved_config()

    def _build_ui(self):
        """Xây dựng toàn bộ giao diện Tab 3."""
        self.paned = ttk.PanedWindow(self, orient='horizontal')
        self.paned.pack(fill='both', expand=True)

        # Left panel: Input & settings
        left_frame = ttk.Frame(self.paned, padding=4)
        self.paned.add(left_frame, weight=1)

        # Right panel: Table & Results
        right_frame = ttk.Frame(self.paned, padding=4)
        self.paned.add(right_frame, weight=1)

        # --- LEFT PANEL CONTENT ---
        # 1. Raw Input
        input_frame = ttk.LabelFrame(left_frame, text="📋 Nhập tiêu đề & Link video (trộn lẫn)",
                                     style='Section.TLabelframe', padding=8)
        input_frame.pack(fill='both', expand=True, pady=(0, 6))

        self.raw_text = tk.Text(
            input_frame,
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
        scrollbar = ttk.Scrollbar(input_frame, orient='vertical', command=self.raw_text.yview)
        self.raw_text.configure(yscrollcommand=scrollbar.set)
        
        self.raw_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Action button for parsing
        parse_btn_frame = ttk.Frame(left_frame)
        parse_btn_frame.pack(fill='x', pady=(0, 6))
        
        self.btn_parse = ttk.Button(
            parse_btn_frame,
            text="🔄 Phân tách dữ liệu",
            style='Action.TButton',
            command=self._on_parse_and_sort
        )
        self.btn_parse.pack(side='left', fill='x', expand=True)

        # 2. Gemini Web Settings
        web_frame = ttk.LabelFrame(left_frame, text="🌐 Cài đặt Gemini Web Automation",
                                   style='Section.TLabelframe', padding=8)
        web_frame.pack(fill='x', pady=(0, 4))

        # Profile Selector Frame
        profile_frame = ttk.Frame(web_frame)
        profile_frame.pack(fill='x', pady=(0, 6))

        ttk.Label(profile_frame, text="Profile trình duyệt:").pack(side='left', padx=(0, 4))
        self.cb_profile = ttk.Combobox(profile_frame, state='readonly', width=26)
        self.cb_profile.pack(side='left', fill='x', expand=True, padx=(0, 4))

        self.btn_refresh_profiles = ttk.Button(
            profile_frame,
            text="🔄",
            width=3,
            command=self._reload_profiles
        )
        self.btn_refresh_profiles.pack(side='left', padx=(0, 4))

        self.btn_new_profile = ttk.Button(
            profile_frame,
            text="➕ Tạo Profile",
            command=self._on_create_new_profile
        )
        self.btn_new_profile.pack(side='left')

        # Checkbox Headless & Login Button
        browser_opt_frame = ttk.Frame(web_frame)
        browser_opt_frame.pack(fill='x', pady=(0, 6))

        self.headless_var = tk.BooleanVar(value=True)
        self.chk_headless = ttk.Checkbutton(
            browser_opt_frame,
            text="Chạy ẩn trình duyệt (Headless)",
            variable=self.headless_var
        )
        self.chk_headless.pack(side='left', padx=(0, 10))

        self.btn_open_web = ttk.Button(
            browser_opt_frame,
            text="🌐 Mở Gemini Web",
            command=self._on_open_web_login
        )
        self.btn_open_web.pack(side='right')

        # Timeout Option
        timeout_frame = ttk.Frame(web_frame)
        timeout_frame.pack(fill='x', pady=(0, 6))

        ttk.Label(timeout_frame, text="Thời gian chờ tối đa mỗi video:").pack(side='left', padx=(0, 4))
        self.timeout_var = tk.StringVar(value="60")
        self.entry_timeout = ttk.Entry(timeout_frame, textvariable=self.timeout_var, width=6)
        self.entry_timeout.pack(side='left')
        ttk.Label(timeout_frame, text="giây").pack(side='left', padx=(4, 0))

        # Limit Check Settings
        self.enable_limit_var = tk.BooleanVar(value=True)
        self.chk_limit = ttk.Checkbutton(
            web_frame,
            text="Kiểm tra giới hạn thời lượng highlight",
            variable=self.enable_limit_var,
            command=self._on_toggle_limit_widgets
        )
        self.chk_limit.pack(anchor='w', pady=2)

        limit_widgets_frame = ttk.Frame(web_frame)
        limit_widgets_frame.pack(anchor='w', pady=(0, 6))
        
        self.lbl_max_minutes = ttk.Label(limit_widgets_frame, text="Số phút tối đa:")
        self.lbl_max_minutes.pack(side='left', padx=(0, 4))
        
        self.max_minutes_var = tk.StringVar(value="2.0")
        self.entry_max_minutes = ttk.Entry(limit_widgets_frame, textvariable=self.max_minutes_var, width=8)
        self.entry_max_minutes.pack(side='left')
        
        self.lbl_minutes_unit = ttk.Label(limit_widgets_frame, text="phút")
        self.lbl_minutes_unit.pack(side='left', padx=(4, 0))

        # Prompt template
        prompt_label = ttk.Label(web_frame, text="Prompt gửi cho AI:")
        prompt_label.pack(anchor='w', pady=(4, 2))

        self.prompt_text = tk.Text(
            web_frame,
            height=6,
            wrap='word',
            font=('Segoe UI', 9),
            bg='#fbfcfc',
            fg='#2c3e50',
            borderwidth=1,
            padx=6,
            pady=4
        )
        self.prompt_text.insert('1.0', DEFAULT_HIGHLIGHT_PROMPT)
        self.prompt_text.pack(fill='x', pady=(0, 4))

        # Reset prompt button
        btn_reset_prompt = ttk.Button(
            web_frame,
            text="Khôi phục Prompt mặc định",
            command=self._on_reset_prompt
        )
        btn_reset_prompt.pack(anchor='w', pady=2)

        # --- RIGHT PANEL CONTENT ---
        # 1. Main Table
        table_frame = ttk.LabelFrame(right_frame, text="📊 Danh sách video chính",
                                     style='Section.TLabelframe', padding=4)
        table_frame.pack(fill='both', expand=True, pady=(0, 4))

        self.result_table = HighlightResultTable(table_frame)
        self.result_table.pack(fill='both', expand=True)

        # 2. Control buttons
        control_frame = ttk.Frame(right_frame)
        control_frame.pack(fill='x', pady=2)

        self.btn_extract = ttk.Button(
            control_frame,
            text="🌐 Trích Highlight Gemini Web",
            style='Action.TButton',
            command=self._on_start_extraction
        )
        self.btn_extract.pack(side='left', padx=(0, 6))

        self.btn_stop = ttk.Button(
            control_frame,
            text="🛑 Dừng lại",
            state='disabled',
            command=self._on_stop_extraction
        )
        self.btn_stop.pack(side='left', padx=(0, 6))

        self.btn_copy_selected = ttk.Button(
            control_frame,
            text="📋 Copy dòng chọn",
            command=self._on_copy_selected
        )
        self.btn_copy_selected.pack(side='right', padx=2)

        self.btn_copy_all = ttk.Button(
            control_frame,
            text="📋 Copy Tất cả",
            command=self._on_copy_all
        )
        self.btn_copy_all.pack(side='right', padx=2)

        self.btn_copy_success = ttk.Button(
            control_frame,
            text="✅ Copy thành công",
            command=self._on_copy_success_only
        )
        self.btn_copy_success.pack(side='right', padx=2)

        # Progress bar + info label
        progress_frame = ttk.Frame(right_frame)
        progress_frame.pack(fill='x', pady=4)

        self.lbl_progress = ttk.Label(progress_frame, text="", font=('Segoe UI', 9))
        self.lbl_progress.pack(side='left', padx=(0, 8))

        self.progress_bar = ttk.Progressbar(
            progress_frame,
            orient='horizontal',
            mode='determinate',
            length=300
        )
        self.progress_bar.pack(side='left', fill='x', expand=True)

        # 3. Sub-notebook: Reprocess + Error Log
        self.sub_notebook = ttk.Notebook(right_frame)
        self.sub_notebook.pack(fill='both', expand=True, pady=(4, 0))

        # --- Tab phụ 1: Bảng xử lý lại ---
        reprocess_container = ttk.Frame(self.sub_notebook, padding=4)
        self.sub_notebook.add(reprocess_container, text="🔄 Cần xử lý lại")

        self.reprocess_table = HighlightResultTable(reprocess_container)
        self.reprocess_table.pack(fill='both', expand=True)

        reprocess_control = ttk.Frame(reprocess_container)
        reprocess_control.pack(fill='x', pady=2)

        self.btn_reprocess = ttk.Button(
            reprocess_control,
            text="🔄 Chạy lại danh sách này",
            command=self._on_start_reprocess
        )
        self.btn_reprocess.pack(side='left', padx=2)

        self.btn_clear_reprocess = ttk.Button(
            reprocess_control,
            text="🗑 Xóa danh sách này",
            command=self._on_clear_reprocess
        )
        self.btn_clear_reprocess.pack(side='left', padx=2)

        # --- Tab phụ 2: Log Lỗi ---
        error_log_container = ttk.Frame(self.sub_notebook, padding=4)
        self.sub_notebook.add(error_log_container, text="❌ Log Lỗi")

        self.error_log_panel = ErrorLogPanel(
            error_log_container,
            tab_label_callback=self._update_error_tab_label
        )
        self.error_log_panel.pack(fill='both', expand=True)

    def _update_error_tab_label(self, error_count):
        """Cập nhật badge số lỗi trên tab Log Lỗi."""
        if error_count > 0:
            self.sub_notebook.tab(1, text=f"❌ Log Lỗi ({error_count})")
        else:
            self.sub_notebook.tab(1, text="❌ Log Lỗi")

    def _load_saved_config(self):
        """Đọc các setting đã lưu cho Gemini Web."""
        saved_prompt = load_setting('gemini_web_prompt')
        if saved_prompt:
            # Nếu prompt cũ chứa từ ngữ yêu cầu AI bịa hoặc giả lập, tự động nâng cấp lên prompt mới
            if any(k in saved_prompt for k in ["KHÔNG THỂ xem", "BỊA", "giả lập", "Dựa vào tiêu đề"]):
                saved_prompt = DEFAULT_HIGHLIGHT_PROMPT
                save_setting('gemini_web_prompt', DEFAULT_HIGHLIGHT_PROMPT)
            self.prompt_text.delete('1.0', 'end')
            self.prompt_text.insert('1.0', saved_prompt)

        saved_max_min = load_setting('gemini_web_max_minutes')
        if saved_max_min:
            self.max_minutes_var.set(str(saved_max_min))

        saved_enable_limit = load_setting('gemini_web_enable_limit', True)
        self.enable_limit_var.set(saved_enable_limit)

        saved_headless = load_setting('gemini_web_headless', True)
        self.headless_var.set(saved_headless)

        saved_timeout = load_setting('gemini_web_timeout', 60)
        self.timeout_var.set(str(saved_timeout))

        self._on_toggle_limit_widgets()
        self._reload_profiles()

    def _reload_profiles(self):
        """Tải lại danh sách profile có sẵn (Chrome hệ thống, Edge, và App Profiles)."""
        profiles = get_all_profiles()
        self._profiles_map = {p["label"]: p for p in profiles}

        labels = [p["label"] for p in profiles]
        self.cb_profile['values'] = labels

        saved_profile = load_setting('gemini_web_profile')
        if saved_profile and saved_profile in labels:
            self.cb_profile.set(saved_profile)
        elif labels:
            self.cb_profile.current(0)

    def _on_create_new_profile(self):
        """Tạo một App Profile riêng biệt mới."""
        name = simpledialog.askstring("Tạo Profile mới", "Nhập tên Profile mới (VD: Tài khoản Gemini 2):", parent=self)
        if name and name.strip():
            new_prof = create_new_app_profile(name.strip())
            self._reload_profiles()
            if new_prof["label"] in self.cb_profile['values']:
                self.cb_profile.set(new_prof["label"])
                save_setting('gemini_web_profile', new_prof["label"])
            self.log_panel.log(f"Đã tạo Profile mới: {new_prof['label']}", 'success')

    def _get_selected_profile_info(self):
        """
        Lấy thông tin profile đang chọn.

        Returns:
            tuple: (profile_id, profile_label, user_data_dir)
        """
        selected_label = self.cb_profile.get()
        prof_dict = self._profiles_map.get(selected_label)

        if prof_dict:
            prof_id = prof_dict["id"]
            user_data_dir = resolve_profile_dir(prof_id)
            return prof_id, selected_label, user_data_dir
        else:
            default_dir = get_default_user_data_dir()
            return "default", "Default", default_dir

    def _on_toggle_limit_widgets(self):
        """Ẩn/hiện entry thời lượng tối đa."""
        state = 'normal' if self.enable_limit_var.get() else 'disabled'
        self.entry_max_minutes.configure(state=state)

    def _on_reset_prompt(self):
        """Khôi phục prompt mặc định."""
        self.prompt_text.delete('1.0', 'end')
        self.prompt_text.insert('1.0', DEFAULT_HIGHLIGHT_PROMPT)
        self.log_panel.log("Đã khôi phục prompt mặc định.", 'info')

    def _on_open_web_login(self):
        """Mở trình duyệt thực để người dùng xem/mở Gemini Web với Profile chọn."""
        prof_id, prof_label, user_data_dir = self._get_selected_profile_info()
        save_setting('gemini_web_profile', prof_label)
        self.log_panel.log(f"🌐 Đang mở trang Gemini Web cho [{prof_label}]...", 'info')
        self.log_panel.log(f"💡 Hướng dẫn: Nếu cửa sổ trình duyệt hiện ra chưa đăng nhập, bạn chỉ cần bấm 'Đăng nhập' (Sign In) tài khoản Google tương ứng ONCE. Trạng thái đăng nhập sẽ được lưu VĨNH VIỄN cho Profile này!", 'warning')
        open_interactive_browser(user_data_dir=user_data_dir, headless=False)

    def _on_parse_and_sort(self):
        """Phân tách dữ liệu video thô."""
        raw = self.raw_text.get('1.0', 'end').strip()
        if not raw:
            messagebox.showwarning("Cảnh báo", "Vui lòng paste dữ liệu video (tiêu đề + link) vào ô nhập.")
            return

        self.log_panel.log("Đang phân tách dữ liệu thô...")
        entries = parse_raw_input(raw)
        
        if not entries:
            self.log_panel.log("Không tìm thấy thông tin video hoặc URL nào hợp lệ.", 'warning')
            messagebox.showwarning("Thông báo", "Không trích xuất được thông tin video nào. Vui lòng kiểm tra lại định dạng.")
            return

        self.parsed_entries = entries
        self.result_table.load_entries(self.parsed_entries)
        
        self.log_panel.log(f"Đã phân tách xong {len(self.parsed_entries)} video.", 'success')
        self.lbl_progress.configure(text=f"Đã nạp {len(self.parsed_entries)} video. Sẵn sàng trích highlight qua Gemini Web.")

    def _update_progress(self, progress_text, pct):
        """Cập nhật tiến trình từ background thread."""
        self.after(0, lambda: self.lbl_progress.configure(text=progress_text))
        self.after(0, lambda: self.progress_bar.configure(value=pct))

    def _on_start_extraction(self):
        """Bắt đầu trích highlight bằng Gemini Web cho danh sách chính."""
        if self._is_processing:
            return

        if not self.parsed_entries:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập và phân tách dữ liệu video trước.")
            return

        prompt_tpl = self.prompt_text.get('1.0', 'end').strip()
        if not prompt_tpl:
            messagebox.showwarning("Thiếu thông tin", "Prompt gửi cho AI không được để trống.")
            return

        try:
            timeout_val = int(self.timeout_var.get())
        except ValueError:
            timeout_val = 60

        try:
            max_min_val = float(self.max_minutes_var.get())
        except ValueError:
            max_min_val = 2.0

        prof_id, prof_label, user_data_dir = self._get_selected_profile_info()

        # Lưu config
        save_setting('gemini_web_prompt', prompt_tpl)
        save_setting('gemini_web_headless', self.headless_var.get())
        save_setting('gemini_web_timeout', timeout_val)
        save_setting('gemini_web_max_minutes', max_min_val)
        save_setting('gemini_web_enable_limit', self.enable_limit_var.get())
        save_setting('gemini_web_profile', prof_label)

        options = {
            'headless': self.headless_var.get(),
            'timeout': timeout_val,
            'enable_limit': self.enable_limit_var.get(),
            'max_minutes': max_min_val,
            'user_data_dir': user_data_dir,
            'profile_label': prof_label
        }

        callbacks = {
            'log': lambda msg, cat='info': self.after(0, lambda: self.log_panel.log(msg, cat)),
            'error_log': lambda t, dl, cat='error': self.after(0, lambda: self.error_log_panel.log_error(t, dl, cat)),
            'progress': self._update_progress,
            'finish': lambda: self.after(0, self._on_worker_finished)
        }

        self._is_processing = True
        self.btn_extract.configure(state='disabled')
        self.btn_reprocess.configure(state='disabled')
        self.btn_stop.configure(state='normal')
        self.btn_parse.configure(state='disabled')
        self.progress_bar.configure(value=0)
        self.lbl_progress.configure(text=f"Đang khởi chạy Gemini Web [{prof_label}]...")

        self._current_worker = GeminiWebBatchWorker(
            self.parsed_entries, self.result_table, prompt_tpl, options, callbacks
        )

        threading.Thread(target=self._current_worker.run, daemon=True).start()

    def _on_start_reprocess(self):
        """Chạy lại AI cho danh sách cần xử lý lại."""
        if self._is_processing:
            return

        if not self.reprocess_entries:
            messagebox.showwarning("Cảnh báo", "Danh sách cần xử lý lại hiện tại đang rỗng.")
            return

        prompt_tpl = self.prompt_text.get('1.0', 'end').strip()
        if not prompt_tpl:
            messagebox.showwarning("Thiếu thông tin", "Prompt gửi cho AI không được để trống.")
            return

        try:
            timeout_val = int(self.timeout_var.get())
            max_min_val = float(self.max_minutes_var.get())
        except ValueError:
            timeout_val = 60
            max_min_val = 2.0

        prof_id, prof_label, user_data_dir = self._get_selected_profile_info()
        save_setting('gemini_web_profile', prof_label)

        options = {
            'headless': self.headless_var.get(),
            'timeout': timeout_val,
            'enable_limit': self.enable_limit_var.get(),
            'max_minutes': max_min_val,
            'user_data_dir': user_data_dir,
            'profile_label': prof_label
        }

        callbacks = {
            'log': lambda msg, cat='info': self.after(0, lambda: self.log_panel.log(msg, cat)),
            'error_log': lambda t, dl, cat='error': self.after(0, lambda: self.error_log_panel.log_error(t, dl, cat)),
            'progress': self._update_progress,
            'finish': lambda: self.after(0, self._on_worker_finished)
        }

        self._is_processing = True
        self.btn_extract.configure(state='disabled')
        self.btn_reprocess.configure(state='disabled')
        self.btn_stop.configure(state='normal')
        self.btn_parse.configure(state='disabled')
        self.progress_bar.configure(value=0)

        self._current_worker = GeminiWebBatchWorker(
            self.reprocess_entries, self.reprocess_table, prompt_tpl, options, callbacks
        )

        threading.Thread(target=self._current_worker.run, daemon=True).start()

    def _on_stop_extraction(self):
        """Bấm nút dừng tiến trình."""
        if self._current_worker:
            self._current_worker.stop()
        self.log_panel.log("Đã phát lệnh dừng tiến trình Gemini Web...", 'warning')
        self.btn_stop.configure(state='disabled')

    def _on_worker_finished(self):
        """Khôi phục trạng thái nút bấm khi worker hoàn thành hoặc bị dừng."""
        self._is_processing = False
        self._current_worker = None
        self.btn_extract.configure(state='normal')
        self.btn_reprocess.configure(state='normal')
        self.btn_stop.configure(state='disabled')
        self.btn_parse.configure(state='normal')

    def _on_clear_reprocess(self):
        """Xóa danh sách cần xử lý lại."""
        self.reprocess_entries = []
        self.reprocess_table.clear()
        self.log_panel.log("Đã xóa danh sách cần xử lý lại.", 'info')

    def _on_copy_selected(self):
        """Copy dòng đang được chọn vào clipboard dạng 3 cột (Tiêu đề | Link | Highlight)."""
        data = self.result_table.get_selected_highlights()
        if not data:
            data = self.reprocess_table.get_selected_highlights()
            
        if not data:
            messagebox.showinfo("Thông báo", "Vui lòng chọn ít nhất 1 dòng trong bảng kết quả chính hoặc phụ.")
            return

        text = format_single_for_spreadsheet(data)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        self.log_panel.log(f"Đã copy dòng chọn vào clipboard (dạng 3 cột: Tiêu đề | Link | Highlight).", 'success')

    def _on_copy_all(self):
        """Copy toàn bộ danh sách kết quả dạng 3 cột (Tiêu đề | Link | Highlight)."""
        all_rows = self.result_table.get_all_rows()
        if not all_rows:
            messagebox.showinfo("Thông báo", "Bảng kết quả hiện đang rỗng.")
            return

        text, count = format_for_spreadsheet(all_rows, include_empty=True)
        if count == 0:
            messagebox.showinfo("Thông báo", "Không có dữ liệu để copy.")
            return

        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        self.log_panel.log(f"Đã copy toàn bộ {count} dòng vào clipboard (dạng 3 cột: Tiêu đề | Link | Highlight).", 'success')

    def _on_copy_success_only(self):
        """Copy các dòng đã trích thành công dạng 3 cột (Tiêu đề | Link | Highlight)."""
        rows = self.result_table.get_successful_rows()
        if not rows:
            messagebox.showinfo("Thông báo", "Chưa có dòng nào hoàn thành thành công.")
            return

        text, count = format_for_spreadsheet(rows, include_empty=False)
        if count == 0:
            messagebox.showinfo("Thông báo", "Không có dòng thành công nào để copy.")
            return

        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        self.log_panel.log(f"Đã copy {count} dòng thành công vào clipboard (dạng 3 cột: Tiêu đề | Link | Highlight).", 'success')

