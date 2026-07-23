"""
Gemini Web Automation Module - Quản lý tương tác với trình duyệt qua Playwright.
Điều khiển Gemini Web (https://gemini.google.com/app) để gửi prompt và trích xuất dữ liệu trả về.
"""

import os
import sys
import time
import threading


def get_default_user_data_dir():
    """Lấy đường dẫn mặc định lưu dữ liệu browser profile (.browser_data trong thư mục gốc)."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    user_data_dir = os.path.join(base_dir, ".browser_data")
    os.makedirs(user_data_dir, exist_ok=True)
    return user_data_dir

def _cleanup_browser_locks(user_data_dir):
    """Xóa các file lock/session cũ để tránh lỗi 'Target page, context or browser has been closed'."""
    if not user_data_dir or not os.path.exists(user_data_dir):
        return
    lock_files = ["SingletonLock", "SingletonSocket", "SingletonCookie"]
    for f in lock_files:
        fpath = os.path.join(user_data_dir, f)
        try:
            if os.path.exists(fpath):
                os.remove(fpath)
        except Exception:
            pass


def find_system_chrome_path():
    """Tự động tìm đường dẫn file thực thi Google Chrome hoặc Edge trên Windows."""
    possible_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None


def open_interactive_browser(user_data_dir=None, headless=False, chrome_path=None):
    """
    Mở trình duyệt thực để người dùng đăng nhập tài khoản Google hoặc kiểm tra thủ công.
    Chạy ở thread riêng để không làm treo UI chính.

    Args:
        user_data_dir (str, optional): Thư mục profile.
        headless (bool): Bật/tắt chế độ ẩn. Mặc định False để người dùng thấy giao diện.
        chrome_path (str, optional): Đường dẫn file thực thi Chrome nếu có.
    """
    if user_data_dir is None:
        user_data_dir = get_default_user_data_dir()

    if not chrome_path:
        chrome_path = find_system_chrome_path()

    def run():
        try:
            _cleanup_browser_locks(user_data_dir)
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                launch_args = [
                    "--no-sandbox",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-search-engine-choice-screen",
                    "--disable-features=LockProfileCookieDatabase",
                ]
                kwargs = {
                    "user_data_dir": user_data_dir,
                    "headless": headless,
                    "args": launch_args,
                    "ignore_default_args": ["--disable-sync"],
                }
                if chrome_path and os.path.exists(chrome_path):
                    kwargs["executable_path"] = chrome_path

                context = p.chromium.launch_persistent_context(**kwargs)
                page = context.pages[0] if context.pages else context.new_page()
                page.goto("https://gemini.google.com/app", timeout=60000)
                
                # Giữ trình duyệt mở cho tới khi người dùng đóng tất cả cửa sổ
                while context.pages:
                    time.sleep(1)
        except Exception as e:
            print(f"Lỗi khi mở trình duyệt thủ công: {e}")

    threading.Thread(target=run, daemon=True).start()


class GeminiWebController:
    """Bộ điều khiển Playwright tương tác trực tiếp với Gemini Web."""

    def __init__(self, user_data_dir=None, headless=True, timeout_seconds=60, chrome_path=None):
        """
        Khởi tạo bộ điều khiển.

        Args:
            user_data_dir (str, optional): Thư mục profile lưu session đăng nhập.
            headless (bool): Chạy ẩn trình duyệt hay hiện giao diện.
            timeout_seconds (int): Thời gian chờ tối đa cho mỗi phản hồi (giây).
            chrome_path (str, optional): Đường dẫn file thực thi Chrome.
        """
        self.user_data_dir = user_data_dir or get_default_user_data_dir()
        self.headless = headless
        self.timeout_seconds = timeout_seconds
        self.chrome_path = chrome_path or find_system_chrome_path()

        self._playwright = None
        self._context = None
        self._page = None
        self._is_running = False

    def start(self):
        """
        Khởi chạy trình duyệt và mở trang Gemini Web.

        Returns:
            tuple: (bool, str) -> (Thành công hay không, Thông báo chi tiết)
        """
        try:
            _cleanup_browser_locks(self.user_data_dir)
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()

            launch_args = [
                "--no-sandbox",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-search-engine-choice-screen",
                "--disable-features=LockProfileCookieDatabase",
            ]
            kwargs = {
                "user_data_dir": self.user_data_dir,
                "headless": self.headless,
                "args": launch_args,
                "ignore_default_args": ["--disable-sync"],
            }
            if self.chrome_path and os.path.exists(self.chrome_path):
                kwargs["executable_path"] = self.chrome_path

            self._context = self._playwright.chromium.launch_persistent_context(**kwargs)
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
            
            # Đặt timeout chuẩn cho các thao tác
            self._page.set_default_timeout(15000)
            
            # Mở Gemini Web
            self._page.goto("https://gemini.google.com/app", timeout=45000)
            self._page.wait_for_timeout(2000)
            
            # Pre-check kiểm tra phiên đăng nhập ngay sau khi tải trang
            is_valid_login, login_err = self.verify_login_session()
            if not is_valid_login:
                self.close()
                return False, login_err

            self._is_running = True
            return True, "Kết nối Gemini Web thành công."
        except Exception as e:
            self.close()
            return False, f"Lỗi khởi chạy trình duyệt: {str(e)}"

    def verify_login_session(self):
        """
        Pre-check phiên đăng nhập Gemini Web ngay sau khi mở trang.
        Nếu phát hiện nút "Đăng nhập" hoặc không tìm thấy ô nhập prompt, trả về lỗi ngay.

        Returns:
            tuple: (bool, str) -> (Đã đăng nhập hợp lệ hay chưa, Thông báo lỗi chi tiết nếu chưa)
        """
        if not self._page or self._page.is_closed():
            return False, "Phiên đăng nhập Gemini không hợp lệ - cần đăng nhập lại profile"

        # 1. Kiểm tra sự xuất hiện của nút "Đăng nhập" (Sign in)
        signin_selectors = [
            'a[href*="accounts.google.com"]',
            'button:has-text("Đăng nhập")',
            'a:has-text("Đăng nhập")',
            'button:has-text("Sign in")',
            'a:has-text("Sign in")',
            '.gb_Ia',  # Google Account Sign-in button class
        ]
        for sel in signin_selectors:
            try:
                loc = self._page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    return False, "Phiên đăng nhập Gemini không hợp lệ - cần đăng nhập lại profile"
            except Exception:
                pass

        # 2. Kiểm tra sự xuất hiện của ô nhập prompt
        if self.check_login_status():
            return True, "Đã xác nhận phiên đăng nhập Gemini hợp lệ."

        # Thử chờ 2.5 giây nếu trang đang nạp chậm
        self._page.wait_for_timeout(2500)

        # Kiểm tra lại nút Đăng nhập sau khi chờ
        for sel in signin_selectors:
            try:
                loc = self._page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    return False, "Phiên đăng nhập Gemini không hợp lệ - cần đăng nhập lại profile"
            except Exception:
                pass

        if self.check_login_status():
            return True, "Đã xác nhận phiên đăng nhập Gemini hợp lệ."

        return False, "Phiên đăng nhập Gemini không hợp lệ - cần đăng nhập lại profile"

    def check_login_status(self):
        """
        Kiểm tra người dùng đã đăng nhập và sẵn sàng gửi prompt chưa.

        Returns:
            bool: True nếu tìm thấy ô nhập prompt của Gemini Web.
        """
        if not self._page or self._page.is_closed():
            return False

        input_selectors = [
            'rich-textarea div[contenteditable="true"]',
            'div.ql-editor[contenteditable="true"]',
            'div[aria-label*="prompt" i]',
            'div[aria-label*="nhập" i]',
            'div[contenteditable="true"]',
        ]
        for sel in input_selectors:
            try:
                loc = self._page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    return True
            except Exception:
                pass
        return False

    def _dismiss_overlays(self):
        """Đóng hoặc loại bỏ các backdrop overlay / dialog làm chắn pointer events."""
        if not self._page or self._page.is_closed():
            return
        try:
            self._page.keyboard.press("Escape")
            self._page.evaluate("""
                () => {
                    const backdrops = document.querySelectorAll('.cdk-overlay-backdrop');
                    backdrops.forEach(el => el.remove());
                    const closeBtns = document.querySelectorAll('.cdk-overlay-container button[aria-label*="Close" i], .cdk-overlay-container button[aria-label*="Đóng" i]');
                    closeBtns.forEach(btn => {
                        try { btn.click(); } catch(e) {}
                    });
                }
            """)
        except Exception:
            pass

    def new_chat(self):
        """Tạo cuộc trò chuyện mới trên Gemini Web để xóa ngữ cảnh cũ."""
        if not self._page or self._page.is_closed():
            return False

        try:
            self._dismiss_overlays()
            new_chat_selectors = [
                'button[aria-label*="Trò chuyện mới" i]',
                'button[aria-label*="New chat" i]',
                'button[aria-label*="Cuộc trò chuyện mới" i]',
                'a[href="/app"]',
            ]
            for sel in new_chat_selectors:
                loc = self._page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    try:
                        loc.first.click(force=True, timeout=3000)
                    except Exception:
                        try:
                            loc.first.evaluate("el => el.click()")
                        except Exception:
                            pass
                    self._page.wait_for_timeout(1500)
                    return True
            
            # Fallback: Điều hướng lại trang /app
            self._page.goto("https://gemini.google.com/app", timeout=30000)
            self._page.wait_for_timeout(1500)
            return True
        except Exception:
            return False

    def send_prompt_and_get_response(self, prompt_text, stop_checker=None):
        """
        Gửi prompt vào Gemini Web, nhấn Gửi, và chờ trích xuất phản hồi trả về.

        Args:
            prompt_text (str): Nội dung câu lệnh gửi cho AI.
            stop_checker (callable, optional): Hàm kiểm tra nếu tiến trình bị dừng từ người dùng.

        Returns:
            tuple: (str, bool, str) -> (Nội dung phản hồi / thông báo lỗi, Thành công hay không, Chi tiết log dev)
        """
        if not self._page or self._page.is_closed():
            return "Trình duyệt chưa khởi chạy hoặc đã bị đóng.", False, "Page is closed or None."

        try:
            self._dismiss_overlays()

            # 1. Tìm ô nhập
            input_el = None
            input_selectors = [
                'rich-textarea div[contenteditable="true"]',
                'div.ql-editor[contenteditable="true"]',
                'div[aria-label*="prompt" i]',
                'div[aria-label*="nhập" i]',
                'div[contenteditable="true"]',
            ]
            for sel in input_selectors:
                loc = self._page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    input_el = loc.first
                    break

            if not input_el:
                return (
                    "Không tìm thấy ô nhập liệu của Gemini Web. Vui lòng kiểm tra lại kết nối mạng hoặc giao diện trang web.",
                    False,
                    "Cannot locate input element."
                )

            # Ghi nhận phản hồi cũ trước khi gửi prompt mới
            prev_last_text = ""
            response_selectors = [
                'model-response',
                'div.response-container-content',
                'div.message-content',
                'div.markdown-main-panel',
                '.markdown',
            ]
            for r_sel in response_selectors:
                loc = self._page.locator(r_sel)
                if loc.count() > 0:
                    try:
                        prev_last_text = loc.last.inner_text().strip()
                        if prev_last_text:
                            break
                    except Exception:
                        pass

            # Focus và điền văn bản
            input_el.focus()
            self._page.keyboard.press("Control+A")
            self._page.keyboard.press("Backspace")
            self._page.wait_for_timeout(200)

            self._page.keyboard.insert_text(prompt_text)
            self._page.wait_for_timeout(500)

            if stop_checker and stop_checker():
                return "Đã dừng tiến trình theo yêu cầu", False, "Stopped by user before sending"

            # 2. Tìm nút Gửi
            send_btn = None
            send_selectors = [
                'button[aria-label*="Send" i]',
                'button[aria-label*="Gửi" i]',
                'button.send-button',
                'button[aria-label*="Submit" i]',
            ]
            for sel in send_selectors:
                loc = self._page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    send_btn = loc.first
                    break

            self._dismiss_overlays()
            if send_btn:
                try:
                    send_btn.click(force=True, timeout=3000)
                except Exception:
                    try:
                        send_btn.evaluate("el => el.click()")
                    except Exception:
                        self._page.keyboard.press("Enter")
            else:
                self._page.keyboard.press("Enter")

            self._page.wait_for_timeout(1000)

            # 3. Theo dõi tiến trình streaming phản hồi
            last_text = ""
            stable_count = 0
            start_time = time.time()
            max_wait = self.timeout_seconds

            while time.time() - start_time < max_wait:
                if stop_checker and stop_checker():
                    return "Đã dừng tiến trình theo yêu cầu", False, "Stopped during streaming"

                self._page.wait_for_timeout(1000)

                # Kiểm tra văn bản phản hồi mới nhất (khác văn bản cũ trước khi gửi)
                current_text = ""
                for r_sel in response_selectors:
                    loc = self._page.locator(r_sel)
                    if loc.count() > 0:
                        try:
                            txt = loc.last.inner_text().strip()
                            if txt and txt != prev_last_text:
                                current_text = txt
                                break
                        except Exception:
                            pass

                # Kiểm tra tính ổn định của câu trả lời (khi AI ngừng gõ trong 2 giây)
                if current_text and current_text == last_text:
                    stable_count += 1
                    if stable_count >= 2:
                        return current_text, True, "Response captured successfully"
                else:
                    if current_text:
                        last_text = current_text
                        stable_count = 0

            if last_text:
                return last_text, True, "Timeout reached but captured partial response"
            else:
                return "Gemini Web không trả về câu trả lời trong thời gian quy định.", False, f"Timeout after {max_wait}s"

        except Exception as e:
            import traceback
            dev_log = f"Exception in send_prompt_and_get_response:\n{traceback.format_exc()}"
            return f"Lỗi tương tác Gemini Web: {str(e)}", False, dev_log

    def verify_video_attachment(self, prompt_url=None):
        """
        Kiểm tra xem trên trang Gemini Web hiện tại có đính kèm/xác nhận video YouTube hay không.

        Returns:
            tuple: (bool, str) -> (Có video đính kèm hay không, Lý do chi tiết)
        """
        if not self._page or self._page.is_closed():
            return False, "Trình duyệt chưa sẵn sàng hoặc đã bị đóng."

        try:
            yt_selectors = [
                'youtube-chip',
                'a[href*="youtube.com"]',
                'a[href*="youtu.be"]',
                '.youtube-player',
                '.video-card',
                'extension-response-chip',
                'div[aria-label*="YouTube" i]',
                'iframe[src*="youtube"]',
                'mat-chip[aria-label*="YouTube" i]',
                'div.media-container',
                'div.attachment-container'
            ]
            for sel in yt_selectors:
                try:
                    if self._page.locator(sel).count() > 0:
                        return True, f"Tìm thấy phần tử video YouTube trên giao diện ({sel})."
                except Exception:
                    pass

            if prompt_url:
                clean_url = prompt_url.strip().split('&')[0]
                try:
                    page_html = self._page.content()
                    if clean_url in page_html or "youtube.com" in page_html or "youtu.be" in page_html:
                        return True, "Tìm thấy tham chiếu URL YouTube trong ngữ cảnh trang Gemini Web."
                except Exception:
                    pass

            return False, "Không phát hiện đính kèm hoặc tham chiếu video YouTube trong chat Gemini Web."
        except Exception as e:
            return False, f"Lỗi khi kiểm tra đính kèm video: {str(e)}"

    def close(self):
        """Đóng trình duyệt và giải phóng tài nguyên."""

        self._is_running = False
        try:
            if self._context:
                self._context.close()
                self._context = None
        except Exception:
            pass

        try:
            if self._playwright:
                self._playwright.stop()
                self._playwright = None
        except Exception:
            pass
