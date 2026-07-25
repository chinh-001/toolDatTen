"""
Gemini Web Automation Module - Quản lý tương tác với trình duyệt qua Playwright.
Điều khiển Gemini Web (https://gemini.google.com/app) để gửi prompt và trích xuất dữ liệu trả về.
"""

import os
import sys
import time
import threading
from core.profile_copier import prepare_isolated_chrome_profile


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


def open_interactive_browser(user_data_dir=None, profile_folder="Default", headless=False, chrome_path=None):
    """
    Mở trình duyệt thực để người dùng xem hoặc đăng nhập tài khoản Google.
    Chạy ở thread riêng để không làm treo UI chính.

    Args:
        user_data_dir (str, optional): Thư mục User Data hoặc app profile.
        profile_folder (str): Tên thư mục profile ("Default", "Profile 1", ...).
        headless (bool): Bật/tắt chế độ ẩn. Mặc định False để người dùng thấy giao diện.
        chrome_path (str, optional): Đường dẫn file thực thi Chrome nếu có.
    """
    if user_data_dir is None:
        user_data_dir = get_default_user_data_dir()

    if not chrome_path:
        chrome_path = find_system_chrome_path()

    def run():
        try:
            from core.profile_manager import is_system_chrome_running
            local_state_exists = os.path.exists(os.path.join(user_data_dir, "Local State"))

            # Nếu là Chrome hệ thống và Chrome KHÔNG chạy -> Mở trực tiếp thư mục gốc không qua temp
            if local_state_exists and not is_system_chrome_running():
                target_user_data = user_data_dir
                target_folder = profile_folder
                skipped_files = []
            elif local_state_exists:
                target_user_data, target_folder, skipped_files = prepare_isolated_chrome_profile(user_data_dir, profile_folder)
            else:
                # App Profile riêng biệt
                target_user_data = user_data_dir
                target_folder = "Default"
                skipped_files = []

            _cleanup_browser_locks(target_user_data)

            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                launch_args = [
                    f"--profile-directory={target_folder}",
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-search-engine-choice-screen",
                    "--disable-features=LockProfileCookieDatabase",
                    "--disable-infobars",
                ]
                kwargs = {
                    "user_data_dir": target_user_data,
                    "headless": headless,
                    "args": launch_args,
                    "channel": "chrome",
                    "ignore_default_args": ["--enable-automation", "--disable-sync"],
                }
                if chrome_path and os.path.exists(chrome_path):
                    kwargs["executable_path"] = chrome_path

                try:
                    context = p.chromium.launch_persistent_context(**kwargs)
                except Exception:
                    kwargs.pop("channel", None)
                    context = p.chromium.launch_persistent_context(**kwargs)

                # Ẩn cờ navigator.webdriver để Google Accounts không báo lỗi "Trình duyệt không an toàn"
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """)

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

    def __init__(self, user_data_dir=None, profile_folder="Default", headless=True, timeout_seconds=60, chrome_path=None):
        """
        Khởi tạo bộ điều khiển.

        Args:
            user_data_dir (str, optional): Thư mục profile lưu session đăng nhập.
            profile_folder (str): Tên thư mục profile ("Default", "Profile 1", ...).
            headless (bool): Chạy ẩn trình duyệt hay hiện giao diện.
            timeout_seconds (int): Thời gian chờ tối đa cho mỗi phản hồi (giây).
            chrome_path (str, optional): Đường dẫn file thực thi Chrome.
        """
        self.raw_user_data_dir = user_data_dir or get_default_user_data_dir()
        self.profile_folder = profile_folder or "Default"
        self.user_data_dir = self.raw_user_data_dir
        self.headless = headless
        self.timeout_seconds = timeout_seconds
        self.chrome_path = chrome_path or find_system_chrome_path()
        self.skipped_files = []

        self._playwright = None
        self._context = None
        self._page = None
        self._is_running = False

    def start(self):
        """
        Khởi chạy trình duyệt và mở trang Gemini Web.

        Returns:
            tuple: (bool, str, str) -> (Thành công hay không, Thông báo người dùng, Log dev chi tiết)
        """
        try:
            from core.profile_manager import is_system_chrome_running
            local_state_exists = os.path.exists(os.path.join(self.raw_user_data_dir, "Local State"))

            # Nếu là Chrome hệ thống và Chrome KHÔNG đang mở -> Dùng trực tiếp 100% chính xác
            if local_state_exists and not is_system_chrome_running():
                self.user_data_dir = self.raw_user_data_dir
                target_folder = self.profile_folder
                self.skipped_files = []
            elif local_state_exists:
                # Nếu Chrome đang mở -> Dùng profile cách ly
                isolated_dir, folder_name, skipped_files = prepare_isolated_chrome_profile(self.raw_user_data_dir, self.profile_folder)
                self.user_data_dir = isolated_dir
                target_folder = folder_name
                self.skipped_files = skipped_files
            else:
                # App Profile riêng biệt
                self.user_data_dir = self.raw_user_data_dir
                target_folder = "Default"
                self.skipped_files = []

            _cleanup_browser_locks(self.user_data_dir)

            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()

            launch_args = [
                f"--profile-directory={target_folder}",
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-search-engine-choice-screen",
                "--disable-features=LockProfileCookieDatabase",
                "--disable-infobars",
            ]
            kwargs = {
                "user_data_dir": self.user_data_dir,
                "headless": self.headless,
                "args": launch_args,
                "channel": "chrome",
                "ignore_default_args": ["--enable-automation", "--disable-sync"],
            }
            if self.chrome_path and os.path.exists(self.chrome_path):
                kwargs["executable_path"] = self.chrome_path

            try:
                self._context = self._playwright.chromium.launch_persistent_context(**kwargs)
            except Exception:
                kwargs.pop("channel", None)
                self._context = self._playwright.chromium.launch_persistent_context(**kwargs)

            # Ẩn cờ navigator.webdriver để Google Accounts không báo lỗi "Trình duyệt không an toàn"
            self._context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
            
            # Đặt timeout chuẩn cho các thao tác
            self._page.set_default_timeout(15000)
            
            # Mở Gemini Web
            self._page.goto("https://gemini.google.com/app", timeout=45000)
            self._page.wait_for_timeout(2000)
            
            # Pre-check kiểm tra phiên đăng nhập ngay sau khi tải trang
            is_valid_login, user_msg, dev_log = self.verify_login_session()
            if not is_valid_login:
                self.close()
                return False, user_msg, dev_log

            self._is_running = True
            return True, "Kết nối Gemini Web thành công.", dev_log
        except Exception as e:
            import traceback
            dev_log = f"Exception khi khởi chạy Playwright:\n{traceback.format_exc()}"
            self.close()
            return False, f"Lỗi khởi chạy trình duyệt: {str(e)}", dev_log

    def verify_login_session(self):
        """
        Pre-check phiên đăng nhập Gemini Web và tạo log chẩn đoán chi tiết cho Dev.

        Returns:
            tuple: (bool, str, str) -> (Đã đăng nhập hợp lệ hay chưa, Thông báo người dùng, Log dev chi tiết)
        """
        dev_logs = []
        dev_logs.append("==================================================")
        dev_logs.append("CHẨN ĐOÁN PHIÊN ĐĂNG NHẬP GEMINI WEB")
        dev_logs.append("==================================================")
        dev_logs.append(f"- Profile Folder: {self.profile_folder}")
        dev_logs.append(f"- Thư mục gốc User Data: {self.raw_user_data_dir}")
        dev_logs.append(f"- Thư mục cách ly Playwright: {self.user_data_dir}")
        dev_logs.append(f"- Chế độ Trình duyệt: {'Headless (Ẩn)' if self.headless else 'Interactive (Hiện UI)'}")

        # Ghi nhận thông tin file session bị khóa
        skipped = getattr(self, 'skipped_files', [])
        if skipped:
            dev_logs.append(f"\n⚠️ CẢNH BÁO FILE BỊ KHÓA DO CHROME ĐANG CHẠY ({len(skipped)} files):")
            for sf in skipped[:10]:
                dev_logs.append(f"  • {sf}")
            if any("Cookies" in sf for sf in skipped):
                dev_logs.append("  ➜ CỰC KỲ QUAN TRỌNG: File Session 'Cookies' bị Chrome khóa. Session đăng nhập KHÔNG THỂ sao chép sang Playwright khi Chrome chưa đóng!")

        if not self._page or self._page.is_closed():
            dev_logs.append("\n❌ TRẠNG THÁI: Page Playwright bị đóng hoặc bằng None.")
            return False, "Phiên đăng nhập Gemini không hợp lệ - Trình duyệt bị đóng", "\n".join(dev_logs)

        try:
            current_url = self._page.url
            page_title = self._page.title()
        except Exception as e:
            current_url = f"Error getting URL: {e}"
            page_title = "Unknown"

        dev_logs.append(f"\n- URL hiện tại sau khi nạp: {current_url}")
        dev_logs.append(f"- Tiêu đề trang: {page_title}")

        # 1. ƯU TIÊN HÀNG ĐẦU: Kiểm tra sự xuất hiện của ô nhập prompt
        if self.check_login_status():
            dev_logs.append("\n✅ KẾT QUẢ: Tìm thấy ô nhập prompt thành công. Session hoạt động bình thường!")
            return True, "Đã xác nhận phiên đăng nhập Gemini hợp lệ.", "\n".join(dev_logs)

        # 2. Thử chờ 3 giây để trang nạp xong các thành phần Web App
        dev_logs.append("\n⏳ Chưa thấy ô nhập liệu, đang chờ thêm 3 giây để trang nạp xong...")
        self._page.wait_for_timeout(3000)

        if self.check_login_status():
            dev_logs.append("\n✅ KẾT QUẢ (Sau khi chờ 3s): Tìm thấy ô nhập prompt thành công.")
            return True, "Đã xác nhận phiên đăng nhập Gemini hợp lệ.", "\n".join(dev_logs)

        # 3. CHỈ KHI KHÔNG TÌM THẤY Ô NHẬP PROMPT -> Mới kiểm tra xem có phải chưa đăng nhập hay không
        if "accounts.google.com" in current_url:
            dev_logs.append("\n❌ KẾT QUẢ: Phát hiện bị chuyển hướng tới trang Đăng nhập Google (accounts.google.com).")
            dev_logs.append("💡 NGUYÊN NHÂN: Profile chưa được đăng nhập Google hoặc file Cookies bị Chrome đang mở khóa.")
            dev_logs.append("💡 HƯỚNG XỬ LÝ: Vui lòng ĐÓNG GOOGLE CHROME trên máy rồi bấm Trích Highlight lại, hoặc dùng nút '🌐 Mở Gemini Web' để đăng nhập 1 lần.")
            user_msg = "Phiên đăng nhập Gemini không hợp lệ - Bị chuyển hướng ra trang Đăng nhập Google"
            return False, user_msg, "\n".join(dev_logs)

        # Các selector Đăng nhập chuẩn xác
        signin_selectors = [
            'a[href*="accounts.google.com/ServiceLogin"]',
            'a[href*="accounts.google.com/v3/signin"]',
            'a[href*="accounts.google.com/InteractiveLogin"]',
            'a.gb_Ia[href*="accounts.google.com"]',
        ]
        found_signin = None
        for sel in signin_selectors:
            try:
                loc = self._page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    found_signin = sel
                    break
            except Exception:
                pass

        if found_signin:
            dev_logs.append(f"\n❌ KẾT QUẢ: Phát hiện nút Đăng nhập trên trang Gemini Web (Selector: '{found_signin}').")
            dev_logs.append("💡 NGUYÊN NHÂN: Profile chưa đăng nhập Google hoặc Cookies bị khóa do Chrome đang chạy.")
            dev_logs.append("💡 HƯỚNG XỬ LÝ: Hãy ĐÓNG CHROME trên máy hoặc chọn Profile có email Google đã đăng nhập.")
            user_msg = f"Phiên đăng nhập Gemini không hợp lệ - Chưa đăng nhập Google ('{found_signin}')"
            return False, user_msg, "\n".join(dev_logs)

        # Nếu không thấy cả nút đăng nhập lẫn ô prompt
        try:
            body_text = self._page.locator('body').inner_text()[:400].replace('\n', ' ')
            dev_logs.append(f"\n- Trích văn bản trang (400 ký tự đầu): {body_text}")
        except Exception:
            pass

        dev_logs.append("\n❌ KẾT QUẢ: Không tìm thấy ô nhập prompt lẫn nút Đăng nhập. Có thể mạng chậm hoặc giao diện Gemini bị đổi.")
        dev_logs.append("💡 HƯỚNG XỬ LÝ: Thử bỏ tích 'Chạy ẩn trình duyệt (Headless)' để quan sát trực tiếp màn hình Chrome.")
        user_msg = "Phiên đăng nhập Gemini không hợp lệ - Không thấy ô nhập liệu Gemini Web"
        return False, user_msg, "\n".join(dev_logs)

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
