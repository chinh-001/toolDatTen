"""
HighlightTab - Giao diện và logic của tab Trích Highlight AI.
Sử dụng Gemini API để trích xuất timestamps từ tiêu đề và link.
Hỗ trợ kiểm tra giới hạn thời lượng tối đa và tự động chạy lại (retry) hoặc gom danh sách xử lý lại.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading

from core.parser import parse_raw_input, sort_entries
from core.highlight_api import (
    extract_highlights, validate_api_key, calculate_total_highlight_duration
)
from gui.widgets import HighlightResultTable, ErrorLogPanel
from utils.config import load_api_key, save_api_key, load_setting, save_setting
from utils.constants import (
    DEFAULT_HIGHLIGHT_PROMPT, GEMINI_MODELS, DEFAULT_MODEL_NAME, GEMINI_MODEL_RPM
)
from utils.clipboard_formatter import (
    format_for_spreadsheet, format_single_for_spreadsheet
)
from utils.key_rotator import KeyRotator, RateLimiter


class HighlightTab(ttk.Frame):
    """Tab Trích Highlight AI."""

    def __init__(self, parent, log_panel, **kwargs):
        super().__init__(parent, **kwargs)
        self.log_panel = log_panel
        self.parsed_entries = []
        self.reprocess_entries = []
        self._is_processing = False

        self._build_ui()
        self._load_saved_config()

    def _build_ui(self):
        """Xây dựng giao diện Tab 2."""
        # Main vertical splitter
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

        # 2. AI Settings
        ai_frame = ttk.LabelFrame(left_frame, text="🤖 Cài đặt AI & Giới hạn",
                                  style='Section.TLabelframe', padding=8)
        ai_frame.pack(fill='x', pady=(0, 4))

        # API Keys (hỗ trợ nhiều key, mỗi key 1 dòng)
        key_label = ttk.Label(ai_frame, text="Gemini API Keys (mỗi dòng 1 key, càng nhiều càng nhanh):")
        key_label.grid(row=0, column=0, columnspan=2, sticky='w', pady=2)

        key_input_frame = ttk.Frame(ai_frame)
        key_input_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(0, 6))

        self.api_keys_text = tk.Text(
            key_input_frame,
            height=3,
            wrap='none',
            font=('Consolas', 9),
            bg='#ffffff',
            fg='#2c3e50',
            relief='flat',
            borderwidth=1,
            padx=6,
            pady=4,
        )
        keys_scrollbar = ttk.Scrollbar(key_input_frame, orient='vertical', command=self.api_keys_text.yview)
        self.api_keys_text.configure(yscrollcommand=keys_scrollbar.set)
        self.api_keys_text.pack(side='left', fill='both', expand=True)
        keys_scrollbar.pack(side='left', fill='y')

        key_btn_frame = ttk.Frame(key_input_frame)
        key_btn_frame.pack(side='right', fill='y', padx=(4, 0))

        self.btn_check_key = ttk.Button(
            key_btn_frame,
            text="Kiểm tra",
            command=self._on_check_api_key
        )
        self.btn_check_key.pack(fill='x', pady=(0, 2))

        # Model selector
        model_frame = ttk.Frame(ai_frame)
        model_frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(0, 6))

        model_label = ttk.Label(model_frame, text="Model:")
        model_label.pack(side='left', padx=(0, 4))

        self.model_var = tk.StringVar(value=DEFAULT_MODEL_NAME)
        model_names = list(GEMINI_MODELS.keys())
        self.model_combo = ttk.Combobox(
            model_frame,
            textvariable=self.model_var,
            values=model_names,
            state='readonly',
            width=35
        )
        self.model_combo.pack(side='left', fill='x', expand=True)

        # Limit Check Settings
        self.enable_limit_var = tk.BooleanVar(value=True)
        self.chk_limit = ttk.Checkbutton(
            ai_frame,
            text="Kiểm tra giới hạn thời lượng highlight",
            variable=self.enable_limit_var,
            command=self._on_toggle_limit_widgets
        )
        self.chk_limit.grid(row=3, column=0, columnspan=2, sticky='w', pady=2)

        limit_widgets_frame = ttk.Frame(ai_frame)
        limit_widgets_frame.grid(row=4, column=0, columnspan=2, sticky='w', pady=(0, 6))
        
        self.lbl_max_minutes = ttk.Label(limit_widgets_frame, text="Số phút tối đa:")
        self.lbl_max_minutes.pack(side='left', padx=(0, 4))
        
        self.max_minutes_var = tk.StringVar(value="2.0")
        self.entry_max_minutes = ttk.Entry(limit_widgets_frame, textvariable=self.max_minutes_var, width=8)
        self.entry_max_minutes.pack(side='left')
        
        self.lbl_minutes_unit = ttk.Label(limit_widgets_frame, text="phút")
        self.lbl_minutes_unit.pack(side='left', padx=(4, 0))

        # Info label về Rate Limiter tự động
        rate_info_frame = ttk.Frame(ai_frame)
        rate_info_frame.grid(row=5, column=0, columnspan=2, sticky='w', pady=(0, 6))

        self.lbl_rate_info = ttk.Label(
            rate_info_frame,
            text="⚡ Delay tự động theo RPM model (không cần chỉnh thủ công)",
            font=('Segoe UI', 8, 'italic'),
            foreground='#7f8c8d'
        )
        self.lbl_rate_info.pack(side='left')

        # Prompt template
        prompt_label = ttk.Label(ai_frame, text="Prompt gửi cho AI:")
        prompt_label.grid(row=6, column=0, sticky='w', pady=(4, 2))

        self.prompt_text = tk.Text(
            ai_frame,
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
        self.prompt_text.grid(row=7, column=0, columnspan=2, sticky='ew', pady=(0, 4))

        # Reset prompt button
        btn_reset_prompt = ttk.Button(
            ai_frame,
            text="Khôi phục Prompt mặc định",
            command=self._on_reset_prompt
        )
        btn_reset_prompt.grid(row=8, column=0, sticky='w', pady=2)

        # --- RIGHT PANEL CONTENT ---
        # 1. Bảng dữ liệu chính
        table_frame = ttk.LabelFrame(right_frame, text="📊 Danh sách video chính",
                                     style='Section.TLabelframe', padding=4)
        table_frame.pack(fill='both', expand=True, pady=(0, 4))

        self.result_table = HighlightResultTable(table_frame)
        self.result_table.pack(fill='both', expand=True)

        # 2. Control buttons for main table
        control_frame = ttk.Frame(right_frame)
        control_frame.pack(fill='x', pady=2)

        self.btn_extract = ttk.Button(
            control_frame,
            text="🤖 Trích Highlight AI",
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

        # --- Tab phụ 2: Log Lỗi (tự xóa sau 5 phút) ---
        error_log_container = ttk.Frame(self.sub_notebook, padding=4)
        self.sub_notebook.add(error_log_container, text="❌ Log Lỗi")

        self.error_log_panel = ErrorLogPanel(
            error_log_container,
            tab_label_callback=self._update_error_tab_label
        )
        self.error_log_panel.pack(fill='both', expand=True)

    def _update_error_tab_label(self, error_count):
        """Cập nhật label của tab phụ Log Lỗi với badge số lỗi.
        
        Args:
            error_count (int): Số lỗi hiện tại.
        """
        if error_count > 0:
            self.sub_notebook.tab(1, text=f"❌ Log Lỗi ({error_count})")
        else:
            self.sub_notebook.tab(1, text="❌ Log Lỗi")

    def _load_saved_config(self):
        """Đọc key và settings đã lưu."""
        saved_key = load_api_key()
        if saved_key:
            self.api_keys_text.delete('1.0', 'end')
            # Hiển thị mỗi key trên 1 dòng
            keys_display = saved_key.replace(',', '\n')
            self.api_keys_text.insert('1.0', keys_display)

        saved_prompt = load_setting('highlight_prompt')
        if saved_prompt:
            # Nếu prompt cũ chứa từ ngữ yêu cầu AI bịa hoặc giả lập, tự động nâng cấp lên prompt mới
            if any(k in saved_prompt for k in ["KHÔNG THỂ xem", "BỊA", "giả lập", "Dựa vào tiêu đề"]):
                saved_prompt = DEFAULT_HIGHLIGHT_PROMPT
                save_setting('highlight_prompt', DEFAULT_HIGHLIGHT_PROMPT)
            self.prompt_text.delete('1.0', 'end')
            self.prompt_text.insert('1.0', saved_prompt)
            
        saved_max_min = load_setting('max_minutes')
        if saved_max_min:
            self.max_minutes_var.set(str(saved_max_min))
            
        saved_enable_limit = load_setting('enable_limit', True)
        self.enable_limit_var.set(saved_enable_limit)

        saved_model = load_setting('gemini_model')
        if saved_model and saved_model in list(GEMINI_MODELS.keys()):
            self.model_var.set(saved_model)
            
        self._on_toggle_limit_widgets()

    def _on_toggle_limit_widgets(self):
        """Ẩn/hiện hoặc disable các widget giới hạn khi toggle checkbox."""
        state = 'normal' if self.enable_limit_var.get() else 'disabled'
        self.entry_max_minutes.configure(state=state)

    def _toggle_api_key_visibility(self):
        """Phương thức giữ tương thích (không còn dùng)."""
        pass

    def _on_reset_prompt(self):
        """Khôi phục prompt mặc định."""
        self.prompt_text.delete('1.0', 'end')
        self.prompt_text.insert('1.0', DEFAULT_HIGHLIGHT_PROMPT)
        self.log_panel.log("Đã khôi phục prompt mặc định.", 'info')

    def _on_check_api_key(self):
        """Kiểm tra API Key đầu tiên có hoạt động không."""
        keys_raw = self.api_keys_text.get('1.0', 'end').strip()
        if not keys_raw:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập ít nhất 1 API Key trước khi kiểm tra.")
            return

        rotator = KeyRotator(keys_raw)
        if rotator.count == 0:
            messagebox.showwarning("Cảnh báo", "Không tìm thấy API Key hợp lệ nào.")
            return

        key = rotator.first_key
        model_name = self.model_var.get()
        model_id = GEMINI_MODELS.get(model_name, 'gemini-2.0-flash')

        self.btn_check_key.configure(state='disabled')
        self.log_panel.log(f"Đang kiểm tra kết nối với Gemini API ({rotator.count} key, model: {model_id})...")

        def worker():
            ok, msg, error_meta = validate_api_key(key, model_id)
            if ok:
                save_api_key(rotator.get_all_keys_text())
                self.after(0, lambda: self.log_panel.log(f"API Key hợp lệ và hoạt động tốt! ({rotator.count} key đã lưu)", 'success'))
                self.after(0, lambda: messagebox.showinfo("Thành công", f"Kết nối tới Gemini API thành công!\n{rotator.count} API Key đã được lưu."))
            else:
                self.after(0, lambda: self.log_panel.log(f"API Key không hoạt động: {msg}", 'error'))
                dev_log = error_meta.get("dev_log", msg)
                self.after(0, lambda dl=dev_log: self.error_log_panel.log_error("[Kiểm tra Key]", dl, 'error'))
                self.after(0, lambda: messagebox.showerror("Lỗi kết nối", f"Kiểm tra thất bại:\n{msg}"))
            self.after(0, lambda: self.btn_check_key.configure(state='normal'))

        threading.Thread(target=worker, daemon=True).start()

    def _on_parse_and_sort(self):
        """Phân tách dữ liệu video thô và sắp xếp theo bảng chữ cái A-Z."""
        raw = self.raw_text.get('1.0', 'end').strip()
        if not raw:
            messagebox.showwarning("Cảnh báo", "Vui lòng paste dữ liệu video (tiêu đề + link) vào ô nhập.")
            return

        # Thực hiện parse
        self.log_panel.log("Đang phân tách dữ liệu thô...")
        entries = parse_raw_input(raw)
        
        if not entries:
            self.log_panel.log("Không tìm thấy thông tin video hoặc URL nào hợp lệ.", 'warning')
            messagebox.showwarning("Thông báo", "Không trích xuất được thông tin video nào. Vui lòng kiểm tra lại định dạng.")
            return

        # Giữ nguyên thứ tự danh sách được gửi
        self.parsed_entries = entries
        
        # Load vào bảng
        self.result_table.load_entries(self.parsed_entries)
        
        self.log_panel.log(f"Đã phân tách xong {len(self.parsed_entries)} video.", 'success')
        self.lbl_progress.configure(text=f"Đã nạp {len(self.parsed_entries)} video. Sẵn sàng trích highlight.")

    def _update_progress(self, progress_text, pct):
        """Cập nhật giao diện tiến độ từ background thread."""
        self.lbl_progress.configure(text=progress_text)
        self.progress_bar.configure(value=pct)

    def _on_start_extraction(self):
        """Bắt đầu chạy AI trích xuất highlight cho danh sách chính."""
        if self._is_processing:
            return

        if not self.parsed_entries:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập và phân tách dữ liệu video trước.")
            return

        keys_raw = self.api_keys_text.get('1.0', 'end').strip()
        if not keys_raw:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập ít nhất 1 Gemini API Key.")
            return

        rotator = KeyRotator(keys_raw)
        if rotator.count == 0:
            messagebox.showwarning("Thiếu thông tin", "Không tìm thấy API Key hợp lệ nào.")
            return

        prompt_tpl = self.prompt_text.get('1.0', 'end').strip()
        if not prompt_tpl:
            messagebox.showwarning("Thiếu thông tin", "Prompt gửi cho AI không được để trống.")
            return

        # Lấy model ID
        model_name = self.model_var.get()
        model_id = GEMINI_MODELS.get(model_name, 'gemini-2.0-flash')

        # Lưu config
        save_api_key(rotator.get_all_keys_text())
        save_setting('highlight_prompt', prompt_tpl)
        save_setting('gemini_model', model_name)
        try:
            max_min = float(self.max_minutes_var.get())
            save_setting('max_minutes', max_min)
        except ValueError:
            pass
        save_setting('enable_limit', self.enable_limit_var.get())

        # Set status
        self._is_processing = True
        self.btn_extract.configure(state='disabled')
        self.btn_reprocess.configure(state='disabled')
        self.btn_stop.configure(state='normal')
        self.btn_parse.configure(state='disabled')
        self.progress_bar.configure(value=0)
        self.lbl_progress.configure(text="Đang khởi chạy...")
        # Tạo rate limiter dựa trên RPM của model và số key
        rpm = GEMINI_MODEL_RPM.get(model_id, 15)
        rate_limiter = RateLimiter(rpm, rotator.count)
        self.log_panel.log(
            f"Bắt đầu trích xuất highlight ({rotator.count} key, model: {model_id}, "
            f"RPM tổng: {rate_limiter.effective_rpm}, delay tối thiểu: {rate_limiter.min_delay_seconds:.1f}s)..."
        )

        # Chạy thread worker
        threading.Thread(
            target=self._extraction_worker,
            args=(self.parsed_entries, self.result_table, rotator, prompt_tpl, model_id, False, rate_limiter),
            daemon=True
        ).start()

    def _on_start_reprocess(self):
        """Bắt đầu chạy lại AI cho danh sách cần xử lý lại."""
        if self._is_processing:
            return

        if not self.reprocess_entries:
            messagebox.showwarning("Cảnh báo", "Danh sách cần xử lý lại hiện tại đang rỗng.")
            return

        keys_raw = self.api_keys_text.get('1.0', 'end').strip()
        if not keys_raw:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập ít nhất 1 Gemini API Key.")
            return

        rotator = KeyRotator(keys_raw)
        if rotator.count == 0:
            messagebox.showwarning("Thiếu thông tin", "Không tìm thấy API Key hợp lệ nào.")
            return

        prompt_tpl = self.prompt_text.get('1.0', 'end').strip()
        if not prompt_tpl:
            messagebox.showwarning("Thiếu thông tin", "Prompt gửi cho AI không được để trống.")
            return

        model_name = self.model_var.get()
        model_id = GEMINI_MODELS.get(model_name, 'gemini-2.0-flash')

        # Set status
        self._is_processing = True
        self.btn_extract.configure(state='disabled')
        self.btn_reprocess.configure(state='disabled')
        self.btn_stop.configure(state='normal')
        self.btn_parse.configure(state='disabled')
        self.progress_bar.configure(value=0)
        self.lbl_progress.configure(text="Đang khởi chạy chạy lại...")
        # Tạo rate limiter cho reprocess
        rpm = GEMINI_MODEL_RPM.get(model_id, 15)
        rate_limiter = RateLimiter(rpm, rotator.count)
        self.log_panel.log(
            f"Bắt đầu tiến trình xử lý lại (RPM tổng: {rate_limiter.effective_rpm})..."
        )

        # Chạy thread worker
        threading.Thread(
            target=self._extraction_worker,
            args=(self.reprocess_entries, self.reprocess_table, rotator, prompt_tpl, model_id, True, rate_limiter),
            daemon=True
        ).start()

    def _safe_extract_highlights(self, title, url, prompt, rotator, model_id, target_table, entry_index, rate_limiter):
        """
        Gọi API an toàn với xoay vòng nhiều key + rate limiter chủ động.
        Khi 1 key bị lỗi (429 hoặc lỗi khác), chuyển sang key tiếp theo.
        Nếu tất cả API key đều bị block ở model hiện tại, tự động chuyển sang model khác và thử lại.
        Phân biệt giữa daily quota (chuyển model ngay) vs per-minute rate limit (chờ hoặc xoay key).
        
        Returns:
            tuple: (res_text, ok, final_model_id)
        """
        import time
        
        # Danh sách các model để fallback, đưa model được chọn lên đầu
        fallback_models = list(dict.fromkeys([model_id] + list(GEMINI_MODELS.values())))
        model_idx = 0
        current_model = fallback_models[model_idx]
        
        # Số lần thử lại tối đa (mỗi key 3 lần) cho toàn bộ tiến trình
        max_total_attempts = rotator.count * 3 * len(fallback_models)
        attempt = 0
        
        while attempt < max_total_attempts:
            if not self._is_processing:
                return "Đã dừng tiến trình", False, current_model
            
            # Cập nhật cấu hình rate limiter cho model hiện tại
            current_model = fallback_models[model_idx]
            rpm = GEMINI_MODEL_RPM.get(current_model, 15)
            rate_limiter.update_config(rpm, rotator.count)
            
            # Lấy key sẵn sàng (có kiểm tra cả daily quota cho model hiện tại)
            key = rotator.get_current_key(model_id=current_model)
            
            if key is None:
                # Tất cả key đều bị block cho model hiện tại
                # Thử chuyển sang model khác
                next_model_found = False
                for idx, m in enumerate(fallback_models):
                    if idx == model_idx:
                        continue
                    # Kiểm tra xem model này có còn key nào dùng được không
                    test_key = rotator.get_current_key(model_id=m)
                    if test_key is not None:
                        old_model = current_model
                        model_idx = idx
                        current_model = m
                        next_model_found = True
                        self.after(0, lambda old_m=old_model, new_m=current_model: self.log_panel.log(
                            f"⚠️ Tất cả key đều bị block ở model {old_m}. Tự động chuyển sang model {new_m}...", 'warning'
                        ))
                        break
                
                if next_model_found:
                    continue
                else:
                    # Tất cả model đều bị block cho tất cả key
                    # Tính thời gian chờ tối thiểu (chỉ tính rate-limit, không tính daily quota)
                    min_wait = rotator.get_min_wait_time(model_id=current_model)
                    
                    # Nếu thời gian chờ >= 30 phút, chứng tỏ là lỗi daily quota hoặc lỗi cấu hình
                    if min_wait >= 1800:
                        return ("Tất cả API Key đã hết quota ngày cho tất cả model. "
                                "Vui lòng thêm key mới hoặc chờ đến ngày mai."), False, current_model
                        
                    wait_sec = int(min_wait) + 1
                    
                    self.after(0, lambda w=wait_sec, models=fallback_models: self.log_panel.log(
                        f"⚠️ Tất cả model ({', '.join(models)}) đều bị rate limit. Chờ {w}s...", 'warning'
                    ))
                    
                    for remaining in range(wait_sec, 0, -1):
                        if not self._is_processing:
                            return "Đã dừng tiến trình", False, current_model
                        self.after(0, lambda id_=entry_index, rem=remaining: target_table.update_status(id_, f"Chờ key ({rem}s)...", 'warning'))
                        time.sleep(1)
                    
                    self.after(0, lambda id_=entry_index: target_table.update_status(id_, "Đang xử lý...", 'running'))
                    # Sau khi chờ xong, reset block rate-limit chung và thử lại
                    rotator.reset_blocks()
                    model_idx = 0
                    current_model = fallback_models[model_idx]
                    continue
            
            # Chủ động chờ theo rate limiter TRƯỚC khi gửi request
            wait_time = rate_limiter.get_wait_time()
            if wait_time > 0:
                wait_int = int(wait_time) + 1
                self.after(0, lambda w=wait_int: self.log_panel.log(
                    f"⏳ Rate limiter: chờ {w}s trước khi gửi request tiếp...", 'info'
                ))
                for remaining in range(wait_int, 0, -1):
                    if not self._is_processing:
                        return "Đã dừng tiến trình", False, current_model
                    self.after(0, lambda id_=entry_index, rem=remaining: target_table.update_status(id_, f"Chờ RPM ({rem}s)...", 'info'))
                    time.sleep(1)
                self.after(0, lambda id_=entry_index: target_table.update_status(id_, "Đang xử lý...", 'running'))
            
            # Ghi nhận request và gọi API
            rate_limiter.record_request()
            
            masked_key = key[:6] + "..." + key[-4:] if len(key) > 10 else key
            self.after(0, lambda m=current_model, k=masked_key: self.log_panel.log(
                f"🔑 Gọi API bằng key {k} trên model {m}...", 'info'
            ))
            
            res_text, ok, error_meta = extract_highlights(title, url, prompt, key, current_model)
            
            if ok:
                rotator.rotate()  # Xoay key cho request tiếp theo
                return res_text, True, current_model
            
            # Tăng attempt lên khi có lỗi xảy ra
            attempt += 1
            
            # Kiểm tra lỗi rate limit (dùng structured metadata)
            if error_meta.get("is_rate_limit", False):
                is_daily = error_meta.get("is_daily_quota", False)
                retry_sec = error_meta.get("retry_after_seconds", 60)
                
                if is_daily:
                    # Daily quota exhausted: block key cho model này vĩnh viễn (24h)
                    # và chuyển ngay sang model khác, KHÔNG chờ
                    rotator.mark_model_exhausted(key, current_model)
                    
                    self.after(0, lambda t=title, k=masked_key, m=current_model: self.log_panel.log(
                        f"🚫 Key {k} đã hết quota NGÀY cho model {m}. Chuyển key/model khác ngay...", 'warning'
                    ))
                    dev_log = error_meta.get("dev_log", res_text)
                    self.after(0, lambda t=title, dl=dev_log: self.error_log_panel.log_error(t, dl, 'warning'))
                    
                    # Kiểm tra xem tất cả key đã hết quota ngày cho model này chưa
                    if rotator.is_all_keys_model_exhausted(current_model):
                        # Chuyển sang model khác ngay
                        self.after(0, lambda m=current_model: self.log_panel.log(
                            f"🚫 Tất cả key đã hết quota ngày cho model {m}. Tìm model khác...", 'warning'
                        ))
                        # Tìm model tiếp theo chưa bị hết quota
                        found_next = False
                        for idx, m in enumerate(fallback_models):
                            if idx == model_idx:
                                continue
                            if not rotator.is_all_keys_model_exhausted(m):
                                model_idx = idx
                                current_model = m
                                found_next = True
                                self.after(0, lambda new_m=m: self.log_panel.log(
                                    f"➔ Chuyển sang model {new_m}.", 'info'
                                ))
                                break
                        
                        if not found_next:
                            return ("Tất cả API Key đã hết quota ngày cho tất cả model. "
                                    "Vui lòng thêm key mới hoặc chờ đến ngày mai."), False, current_model
                    continue
                else:
                    # Per-minute rate limit: block key tạm thời và xoay key
                    rotator.mark_rate_limited(key, retry_sec + 2)
                    
                    self.after(0, lambda t=title, k=masked_key, s=retry_sec: self.log_panel.log(
                        f"⚠️ Key {k} bị rate limit per-minute (chờ {s}s). Thử key tiếp theo.", 'warning'
                    ))
                    dev_log = error_meta.get("dev_log", res_text)
                    self.after(0, lambda t=title, dl=dev_log: self.error_log_panel.log_error(t, dl, 'warning'))
                    continue
            else:
                # Lỗi khác (ví dụ: API key invalid, model unavailable, 403, etc.)
                if error_meta.get("is_model_unavailable", False):
                    # Model không khả dụng. Block model này cho TẤT CẢ keys để không dùng nữa.
                    for k in rotator._keys:
                        rotator.mark_model_exhausted(k, current_model)
                    
                    self.after(0, lambda m=current_model: self.log_panel.log(
                        f"❌ Model {m} không khả dụng hoặc đã bị Google gỡ bỏ. Tự động chuyển sang model khác...", 'error'
                    ))
                    
                    # Chuyển sang model tiếp theo ngay lập tức
                    found_next = False
                    for idx, m in enumerate(fallback_models):
                        if idx == model_idx:
                            continue
                        if not rotator.is_all_keys_model_exhausted(m):
                            model_idx = idx
                            current_model = m
                            found_next = True
                            self.after(0, lambda new_m=m: self.log_panel.log(
                                f"➔ Chuyển sang model {new_m}.", 'info'
                            ))
                            break
                    
                    if not found_next:
                        return f"Không có model khả dụng (Model {current_model} không khả dụng)", False, current_model
                    continue
                else:
                    # Lỗi cấu hình key hoặc lỗi khác: Đánh dấu key này bị block lâu (1 giờ) để không thử lại trong phiên này
                    rotator.mark_rate_limited(key, 3600)
                    
                    self.after(0, lambda t=title, k=masked_key, err=res_text: self.log_panel.log(
                        f"❌ Key {k} bị lỗi ({err}) cho: {t[:30]}... Tự động đổi sang key khác.", 'error'
                    ))
                    dev_log = error_meta.get("dev_log", res_text)
                    self.after(0, lambda t=title, dl=dev_log: self.error_log_panel.log_error(t, dl, 'error'))
                    continue
                
        return f"Vượt quá số lần thử lại ({max_total_attempts} lần)", False, current_model

    def _extraction_worker(self, entries, target_table, rotator, prompt_tpl, model_id, is_reprocess_run=False, rate_limiter=None):
        """Hàm chạy ngầm xử lý API request tuần tự cho danh sách chính hoặc phụ."""
        try:
            total = len(entries)
            success_count = 0

            # Cấu hình thời lượng
            enable_limit = self.enable_limit_var.get()
            try:
                max_min = float(self.max_minutes_var.get())
            except ValueError:
                max_min = 2.0

            for i, entry in enumerate(entries):
                if not self._is_processing:
                    self.after(0, lambda: self.log_panel.log("Đã dừng tiến trình theo yêu cầu.", 'warning'))
                    break


                idx = entry['index']
                title = entry['title']
                url = entry['url']

                # Cập nhật GUI: Đang xử lý
                self.after(0, lambda id_=idx: target_table.update_status(id_, "Đang xử lý...", 'running'))
                self.after(0, lambda i_=i, t=title: self.log_panel.log(f"[{i_+1}/{total}] Đang trích highlight cho: {t[:40]}..."))

                # Gọi API lần 1 (qua safe_extract với xoay vòng key + rate limiter)
                res_text, ok, model_id = self._safe_extract_highlights(title, url, prompt_tpl, rotator, model_id, target_table, idx, rate_limiter)

                if not self._is_processing:
                    break

                if ok:
                    # Kiểm tra giới hạn thời lượng nếu bật cấu hình
                    if enable_limit:
                        total_dur = calculate_total_highlight_duration(res_text)
                        if total_dur > max_min * 60:
                            # Vượt quá số phút mong muốn -> TỰ ĐỘNG CHẠY LẠI lần 2
                            dur_text = self._format_duration(total_dur)
                            self.after(0, lambda t=title, d=dur_text: self.log_panel.log(
                                f"⚠️ Thời lượng highlight ({d}) vượt giới hạn ({max_min} phút). Đang tự động chạy lại với yêu cầu ngắn hơn...", 'warning'
                            ))
                            self.after(0, lambda id_=idx: target_table.update_status(id_, "Chạy lại lần 2...", 'running'))

                            # Thêm nhắc nhở siết chặt thời lượng vào cuối prompt
                            retry_prompt = (
                                f"{prompt_tpl}\n\n"
                                f"[QUAN TRỌNG] Kết quả trích xuất trước đó bị quá dài ({dur_text}).\n"
                                f"Hãy rút ngắn các mốc thời gian lại và giảm bớt số lượng đoạn highlight để tổng thời lượng dưới {max_min} phút."
                            )
                            
                            # Gọi API lần 2 (cũng qua safe_extract với xoay vòng key + rate limiter)
                            res_text, ok, model_id = self._safe_extract_highlights(title, url, retry_prompt, rotator, model_id, target_table, idx, rate_limiter)
                            
                            if ok:
                                total_dur = calculate_total_highlight_duration(res_text)
                                if total_dur > max_min * 60:
                                    # Vẫn vượt quá sau lần 2 -> Đẩy sang Reprocess
                                    dur_text = self._format_duration(total_dur)
                                    status_msg = f"Vượt giới hạn ({dur_text})"
                                    self.after(0, lambda id_=idx, val=res_text, st=status_msg: target_table.update_status(id_, st, 'warning', val))
                                    self.after(0, lambda t=title, d=dur_text: self.log_panel.log(f"➔ Thử lại lần 2 vẫn vượt giới hạn ({d}): Đẩy sang danh sách xử lý lại.", 'warning'))
                                    self.after(0, lambda t=title, d=dur_text: self.error_log_panel.log_error(t, f"Vượt giới hạn sau 2 lần thử ({d})", 'warning'))
                                    if not is_reprocess_run:
                                        self.after(0, lambda ent=entry, val=res_text, st=status_msg: self._push_to_reprocess(ent, val, st))
                                else:
                                    # Lần 2 thành công dưới giới hạn
                                    success_count += 1
                                    self.after(0, lambda id_=idx, val=res_text: target_table.update_status(id_, "Thành công", 'success', val))
                                    self.after(0, lambda t=title, val=res_text: self.log_panel.log(f"➔ Chạy lại lần 2 thành công: {val}", 'success'))
                                    # Đồng bộ bảng chính nếu đây là Reprocess run
                                    if is_reprocess_run:
                                        self.after(0, lambda u=url, val=res_text: self._sync_to_main_table(u, "Thành công", 'success', val))
                            else:
                                # Lần 2 bị lỗi
                                self.after(0, lambda id_=idx, val=res_text: target_table.update_status(id_, f"Lỗi thử lại: {val}", 'error', ""))
                                self.after(0, lambda t=title, val=res_text: self.log_panel.log(f"➔ Chạy lại lần 2 thất bại: {val}", 'error'))
                                if not is_reprocess_run:
                                    self.after(0, lambda ent=entry, st=f"Lỗi thử lại: {res_text}": self._push_to_reprocess(ent, "", st))
                        else:
                            # Lần 1 thành công dưới giới hạn
                            success_count += 1
                            self.after(0, lambda id_=idx, val=res_text: target_table.update_status(id_, "Thành công", 'success', val))
                            self.after(0, lambda t=title, val=res_text: self.log_panel.log(f"➔ Thành công: {val}", 'success'))
                            # Đồng bộ bảng chính nếu đây là Reprocess run
                            if is_reprocess_run:
                                self.after(0, lambda u=url, val=res_text: self._sync_to_main_table(u, "Thành công", 'success', val))
                    else:
                        # Lần 1 thành công dưới giới hạn
                        success_count += 1
                        self.after(0, lambda id_=idx, val=res_text: target_table.update_status(id_, "Thành công", 'success', val))
                        self.after(0, lambda t=title, val=res_text: self.log_panel.log(f"➔ Thành công: {val}", 'success'))
                        # Đồng bộ bảng chính nếu đây là Reprocess run
                        if is_reprocess_run:
                            self.after(0, lambda u=url, val=res_text: self._sync_to_main_table(u, "Thành công", 'success', val))
                else:
                    # Gọi API thất bại lần 1
                    self.after(0, lambda id_=idx, val=res_text: target_table.update_status(id_, f"Lỗi: {val}", 'error', ""))
                    self.after(0, lambda t=title, val=res_text: self.log_panel.log(f"➔ Thất bại: {val}", 'error'))
                    if not is_reprocess_run:
                        self.after(0, lambda ent=entry, st=f"Lỗi: {res_text}": self._push_to_reprocess(ent, "", st))

                # Cập nhật label progress + progress bar
                pct = int(((i + 1) / total) * 100)
                progress_msg = f"Tiến độ: {i+1}/{total} | Thành công: {success_count}"
                self.after(0, lambda msg=progress_msg, p=pct: self._update_progress(msg, p))

                # Rate limiting được xử lý tự động bởi RateLimiter trong _safe_extract_highlights
                # Không cần delay cố định nữa

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.after(0, lambda msg=f"Lỗi hệ thống chạy ngầm: {e}": self.log_panel.log(msg, 'error'))
            # In chi tiết lỗi (traceback) ra log panel để user xem
            self.after(0, lambda msg=f"Chi tiết lỗi:\n{tb}": self.log_panel.log(msg, 'error'))
            self.after(0, lambda msg=str(e): self.error_log_panel.log_error("[Hệ thống]", f"Lỗi nghiêm trọng: {msg}", 'error'))
        finally:
            self.after(0, self._on_finish_extraction)

    def _push_to_reprocess(self, entry, highlight, status_text):
        """Đưa video bị lỗi hoặc vượt giới hạn xuống bảng phụ."""
        # Kiểm tra xem link này đã có trong danh sách reprocess chưa
        for item in self.reprocess_entries:
            if item['url'] == entry['url']:
                item['highlight'] = highlight
                item['status'] = status_text
                # Cập nhật dòng trên table phụ
                tag = 'warning' if "Vượt giới hạn" in status_text else 'error'
                self.reprocess_table.update_status(item['index'], status_text, tag, highlight)
                return

        new_idx = len(self.reprocess_entries)
        new_entry = {
            'index': new_idx,
            'title': entry['title'],
            'url': entry['url'],
            'highlight': highlight,
            'status': status_text
        }
        self.reprocess_entries.append(new_entry)

        # Thêm dòng mới vào table phụ
        tag = 'warning' if "Vượt giới hạn" in status_text else 'error'
        self.reprocess_table.tree.insert(
            '',
            'end',
            iid=str(new_idx),
            values=(
                new_idx + 1,
                new_entry['title'],
                new_entry['url'],
                highlight,
                status_text
            ),
            tags=(tag,)
        )

    def _sync_to_main_table(self, url, status_text, tag, highlight):
        """Đồng bộ trạng thái từ bảng xử lý lại lên bảng chính."""
        for entry in self.parsed_entries:
            if entry['url'] == url:
                self.result_table.update_status(entry['index'], status_text, tag, highlight)
                break

    def _format_duration(self, seconds):
        """Format thời lượng giây sang định dạng thân thiện."""
        m = int(seconds // 60)
        s = int(seconds % 60)
        if m > 0:
            return f"{m}m {s}s"
        return f"{s}s"

    def _on_stop_extraction(self):
        """Yêu cầu dừng tiến trình."""
        self._is_processing = False
        self.btn_stop.configure(state='disabled')
        self.log_panel.log("Đang gửi yêu cầu dừng...")

    def _on_finish_extraction(self):
        """Khôi phục trạng thái GUI sau khi hoàn tất hoặc dừng."""
        self._is_processing = False
        self.btn_extract.configure(state='normal')
        self.btn_reprocess.configure(state='normal')
        self.btn_stop.configure(state='disabled')
        self.btn_parse.configure(state='normal')
        self.progress_bar.configure(value=100)
        self.log_panel.log("Tiến trình hoàn tất.", 'info')

    def _on_clear_reprocess(self):
        """Xóa danh sách cần xử lý lại."""
        self.reprocess_entries = []
        self.reprocess_table.clear()
        self.log_panel.log("Đã xóa sạch danh sách cần xử lý lại.", 'info')

    def _on_copy_selected(self):
        """Copy dòng đang chọn vào clipboard dạng 3 cột (Tiêu đề | Link | Highlight)."""
        item = self.result_table.get_selected_item()
        if not item:
            item = self.reprocess_table.get_selected_item()

        if not item:
            messagebox.showinfo("Thông báo", "Vui lòng chọn một dòng trong bảng kết quả chính hoặc phụ để copy.")
            return

        clipboard_text = format_single_for_spreadsheet(item)
        self.clipboard_clear()
        self.clipboard_append(clipboard_text)
        self.update()  # Đồng bộ clipboard trên Windows
        self.log_panel.log(f"Đã copy video '{item['title'][:30]}...' vào clipboard (dạng 3 cột: Tiêu đề | Link | Highlight).", 'success')

    def _on_copy_all(self):
        """Copy toàn bộ danh sách vào clipboard dạng 3 cột (Tiêu đề | Link | Highlight)."""
        items = self.result_table.get_all_rows()
        if not items:
            messagebox.showinfo("Thông báo", "Bảng kết quả rỗng.")
            return

        clipboard_text, count = format_for_spreadsheet(items, include_empty=True)

        if count == 0:
            messagebox.showwarning("Thông báo", "Chưa có kết quả nào để copy.")
            return

        self.clipboard_clear()
        self.clipboard_append(clipboard_text)
        self.update()
        self.log_panel.log(f"Đã copy {count} video vào clipboard (dạng 3 cột: Tiêu đề | Link | Highlight).", 'success')

    def _on_copy_success_only(self):
        """Chỉ copy các dòng thành công vào clipboard dạng 3 cột (Tiêu đề | Link | Highlight)."""
        items = self.result_table.get_successful_rows()
        if not items:
            messagebox.showinfo("Thông báo", "Chưa có dòng nào thành công để copy.")
            return

        clipboard_text, count = format_for_spreadsheet(items, include_empty=False)

        if count == 0:
            messagebox.showwarning("Thông báo", "Chưa có dòng nào thành công để copy.")
            return

        self.clipboard_clear()
        self.clipboard_append(clipboard_text)
        self.update()
        self.log_panel.log(f"Đã copy {count} dòng thành công vào clipboard (dạng 3 cột: Tiêu đề | Link | Highlight).", 'success')
        messagebox.showinfo("Thành công", f"Đã copy highlight của {count} video thành công!")

