"""
Gemini Web Handler Module - Quản lý worker xử lý danh sách video thông qua Gemini Web Automation.
Đóng vai trò cầu nối giữa Giao diện Tkinter và Module Tự động hóa Trình duyệt Playwright.
"""

import time
import threading
from core.gemini_web_automation import GeminiWebController, get_default_user_data_dir
from core.highlight_api import _clean_timestamps, calculate_total_highlight_duration


REJECTION_PHRASES = [
    "không thể xem video",
    "không thể truy cập video",
    "không tìm thấy video",
    "không có video đính kèm",
    "không mở được link",
    "không thể xem nội dung",
    "không có khả năng truy cập video",
    "tôi là một mô hình ngôn ngữ",
    "tôi là mô hình trí tuệ nhân tạo",
    "không xem được video",
    "link video không hợp lệ",
    "video không tồn tại",
    "không thể mở video",
    "tự sáng tạo",
    "mốc thời gian giả lập",
    "không xem được tệp",
]


def check_response_validity(raw_text, has_video_attached=True):
    """
    Kiểm tra xem phản hồi từ Gemini có thực sự truy cập video hay từ chối / bịa kết quả.

    Returns:
        tuple: (bool, str) -> (Hợp lệ hay không, Lý do chi tiết)
    """
    if not raw_text or not raw_text.strip():
        return False, "Phản hồi rỗng"

    text_lower = raw_text.lower()
    for phrase in REJECTION_PHRASES:
        if phrase in text_lower:
            return False, f"Gemini thông báo không xem/truy cập được video ('{phrase}')"

    if not has_video_attached:
        return False, "Gemini không đính kèm hoặc nhận diện được thẻ video YouTube trong chat"

    return True, "Phản hồi hợp lệ và có video đi kèm."


class GeminiWebBatchWorker:
    """Worker chạy ngầm xử lý trích xuất highlight cho danh sách video sử dụng Gemini Web."""

    def __init__(self, entries, target_table, prompt_template, options, callbacks):
        """
        Khởi tạo worker.

        Args:
            entries (list): Danh sách các video dict {'index': int, 'title': str, 'url': str}.
            target_table: Bảng HighlightResultTable cần cập nhật dữ liệu.
            prompt_template (str): Prompt mẫu do người dùng cấu hình.
            options (dict): Các cấu hình thêm {'headless': bool, 'timeout': int, 'enable_limit': bool, 'max_minutes': float, 'user_data_dir': str}.
            callbacks (dict): Các callback giao diện {'log': func, 'error_log': func, 'progress': func, 'finish': func}.
        """
        self.entries = entries
        self.target_table = target_table
        self.prompt_template = prompt_template
        self.options = options
        self.callbacks = callbacks

        self._is_cancelled = False
        self.controller = None

    def stop(self):
        """Yêu cầu dừng tiến trình đang chạy."""
        self._is_cancelled = True
        if self.controller:
            self.controller.close()

    def is_stopped(self):
        """Kiểm tra xem người dùng đã nhấn dừng chưa."""
        return self._is_cancelled

    def _safe_log(self, text, category='info'):
        """Gửi log an toàn tới giao diện."""
        log_fn = self.callbacks.get('log')
        if log_fn:
            log_fn(text, category)

    def _safe_error_log(self, title, dev_log, category='error'):
        """Gửi log lỗi an toàn tới tab Log Lỗi."""
        err_fn = self.callbacks.get('error_log')
        if err_fn:
            err_fn(title, dev_log, category)

    def _safe_progress(self, progress_text, percentage):
        """Cập nhật tiến trình an toàn."""
        prog_fn = self.callbacks.get('progress')
        if prog_fn:
            prog_fn(progress_text, percentage)

    def _safe_update_status(self, entry_index, status_text, status_type, highlight_val=None):
        """Cập nhật trạng thái từng dòng trên bảng kết quả."""
        if hasattr(self.target_table, 'update_status'):
            self.target_table.after(0, lambda: self.target_table.update_status(entry_index, status_text, status_type, highlight_val))

    def _safe_update_highlight(self, entry_index, highlight_text):
        """Cập nhật kết quả highlight vào bảng."""
        if hasattr(self.target_table, 'update_highlight'):
            self.target_table.after(0, lambda: self.target_table.update_highlight(entry_index, highlight_text))

    def run(self):
        """Luồng chính thực thi trích xuất từng video."""
        total = len(self.entries)
        if total == 0:
            self._safe_log("Danh sách video trống.", 'warning')
            self._finish()
            return

        headless = self.options.get('headless', True)
        timeout = self.options.get('timeout', 60)
        enable_limit = self.options.get('enable_limit', True)
        max_minutes = self.options.get('max_minutes', 2.0)
        user_data_dir = self.options.get('user_data_dir', get_default_user_data_dir())
        profile_folder = self.options.get('profile_folder', 'Default')
        profile_label = self.options.get('profile_label', '')

        log_msg = f"Bắt đầu kết nối trình duyệt Gemini Web (Headless: {headless}, Timeout: {timeout}s)"
        if profile_label:
            log_msg = f"Bắt đầu kết nối trình duyệt Gemini Web [{profile_label}] (Headless: {headless}, Timeout: {timeout}s)..."
        self._safe_log(log_msg)
        self._safe_progress("Đang khởi động trình duyệt...", 0)

        # Khởi tạo controller
        self.controller = GeminiWebController(
            user_data_dir=user_data_dir,
            profile_folder=profile_folder,
            headless=headless,
            timeout_seconds=timeout
        )

        ok, msg, dev_log = self.controller.start()
        if not ok:
            self._safe_log(f"❌ {msg}", 'error')
            self._safe_error_log("Khởi động Trình duyệt", f"{msg}\n\n{dev_log}", 'error')
            self._finish()
            return

        success_count = 0
        for i, entry in enumerate(self.entries):
            if self._is_cancelled:
                self._safe_log("Đã dừng tiến trình theo yêu cầu.", 'warning')
                break

            idx = entry['index']
            title = entry['title']
            url = entry['url']

            pct = int((i / total) * 100)
            self._safe_progress(f"[{i+1}/{total}] Đang trích highlight cho: {title[:35]}...", pct)
            self._safe_update_status(idx, "Đang xử lý...", 'running')
            self._safe_log(f"[{i+1}/{total}] 🌐 Đang gửi yêu cầu tới Gemini Web: {title[:40]}...")

            # Chuẩn bị prompt
            prompt_tpl = self.prompt_template
            if "{title}" not in prompt_tpl:
                prompt_tpl += "\n\nTiêu đề video: {title}"
            if "{url}" not in prompt_tpl:
                prompt_tpl += "\nLink video: {url}"

            prompt = prompt_tpl.format(title=title, url=url)

            MAX_RETRIES = 3
            success_this_video = False

            for attempt in range(1, MAX_RETRIES + 1):
                if self._is_cancelled:
                    break

                # Mở new chat mỗi lượt để xóa ngữ cảnh cũ
                if attempt > 1 or i > 0:
                    self.controller.new_chat()

                if attempt > 1:
                    self._safe_log(
                        f"🔄 Thử lại ({attempt}/{MAX_RETRIES}) cho [{title[:30]}...]: Tạo chat mới và gửi lại prompt...",
                        'warning'
                    )

                raw_res, ok_resp, dev_log = self.controller.send_prompt_and_get_response(
                    prompt, stop_checker=self.is_stopped
                )

                if self._is_cancelled:
                    break

                if not ok_resp:
                    if attempt == MAX_RETRIES:
                        self._safe_update_status(idx, "Lỗi Gemini Web", 'error')
                        self._safe_log(f"❌ Lỗi xử lý cho [{title[:30]}...]: {raw_res}", 'error')
                        self._safe_error_log(title, dev_log, 'error')
                    continue

                # Kiểm tra đính kèm video và kiểm tra tính hợp lệ
                has_video_attached, attach_reason = self.controller.verify_video_attachment(url)
                is_valid, valid_reason = check_response_validity(raw_res, has_video_attached)

                if not is_valid:
                    self._safe_log(
                        f"⚠️ Cảnh báo [{title[:30]}...]: {valid_reason}. (Bỏ qua kết quả không đính kèm video).",
                        'warning'
                    )
                    if attempt < MAX_RETRIES:
                        time.sleep(1.5)
                        continue
                    else:
                        self._safe_update_status(idx, "Không đính kèm video", 'error')
                        self._safe_error_log(
                            title,
                            f"Phát hiện Gemini không đính kèm/truy cập được video sau {MAX_RETRIES} lần thử:\n{valid_reason}\n\nNội dung phản hồi:\n{raw_res[:500]}",
                            'error'
                        )
                        break

                cleaned_timestamps = _clean_timestamps(raw_res)

                if not cleaned_timestamps:
                    if attempt < MAX_RETRIES:
                        self._safe_log(f"⚠️ Trả về không đúng định dạng timestamp cho [{title[:30]}...]. Thử lại...", 'warning')
                        continue
                    else:
                        self._safe_update_status(idx, "Sai định dạng", 'error')
                        self._safe_log(f"⚠️ Trả về không đúng định dạng timestamp cho [{title[:30]}...]", 'warning')
                        self._safe_error_log(
                            title,
                            f"Phản hồi từ Gemini Web không khớp format MM:SS,MM:SS:\n{raw_res[:500]}",
                            'warning'
                        )
                        break

                # Kiểm tra thời lượng nếu bật giới hạn
                if enable_limit:
                    total_dur = calculate_total_highlight_duration(cleaned_timestamps)
                    if total_dur > max_minutes * 60:
                        dur_min = round(total_dur / 60, 1)
                        self._safe_log(
                            f"⚠️ Highlight ({dur_min} phút) vượt giới hạn {max_minutes} phút. Đang tự động thử lại lần 2 với yêu cầu rút ngắn...",
                            'warning'
                        )
                        self._safe_update_status(idx, "Chạy lại lần 2...", 'running')

                        retry_prompt = (
                            f"{prompt}\n\n"
                            f"[QUAN TRỌNG] Kết quả trích xuất trước bị dài quá ({dur_min} phút).\n"
                            f"Hãy rút ngắn các mốc thời gian và giảm số đoạn highlight để tổng thời lượng dưới {max_minutes} phút."
                        )

                        self.controller.new_chat()
                        retry_res, retry_ok, retry_dev = self.controller.send_prompt_and_get_response(
                            retry_prompt, stop_checker=self.is_stopped
                        )

                        if retry_ok:
                            has_retry_attached, _ = self.controller.verify_video_attachment(url)
                            retry_valid, _ = check_response_validity(retry_res, has_retry_attached)
                            if retry_valid:
                                cleaned_retry = _clean_timestamps(retry_res)
                                if cleaned_retry:
                                    cleaned_timestamps = cleaned_retry

                # Cập nhật kết quả thành công
                self._safe_update_highlight(idx, cleaned_timestamps)
                self._safe_update_status(idx, "Hoàn thành", 'success')
                self._safe_log(f"✅ Đã trích highlight thành công cho: {title[:35]}...", 'success')
                success_count += 1
                success_this_video = True
                break

        self._safe_progress(f"Đã xử lý xong {success_count}/{total} video.", 100)
        self._safe_log(f"🎉 Hoàn thành tiến trình Gemini Web! Thành công {success_count}/{total} video.", 'success')
        self._finish()

    def _finish(self):
        """Dọn dẹp sau khi kết thúc worker."""
        if self.controller:
            self.controller.close()
            self.controller = None

        finish_fn = self.callbacks.get('finish')
        if finish_fn:
            finish_fn()

