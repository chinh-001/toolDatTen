"""
Key Rotator - Quản lý và xoay vòng nhiều Gemini API Key.

Khi một key bị rate limit (429), chuyển ngay sang key tiếp theo.
Chỉ chờ khi TẤT CẢ key đều bị chặn.

Bao gồm RateLimiter để chủ động tránh 429 bằng cách theo dõi RPM.
"""

import time
from collections import deque


class KeyRotator:
    """
    Quản lý danh sách API keys với chiến lược round-robin.
    Tự động bỏ qua key đang bị rate limit.
    Hỗ trợ block key theo từng model (daily quota) hoặc chung (per-minute rate limit).
    """

    def __init__(self, keys_text):
        """
        Khởi tạo từ chuỗi nhiều key (phân cách bằng dấu phẩy, xuống dòng, hoặc dấu chấm phẩy).

        Args:
            keys_text (str): Chuỗi chứa nhiều key phân cách nhau.
        """
        # Tách key theo nhiều loại separator
        raw_keys = keys_text.replace(';', '\n').replace(',', '\n').split('\n')
        self._keys = [k.strip() for k in raw_keys if k.strip()]
        self._index = 0
        # Theo dõi key nào đang bị block và thời điểm hết block (rate limit chung)
        self._blocked_until = {}  # key -> timestamp hết block
        # Theo dõi key+model bị block do daily quota
        # Key: (api_key, model_id) -> timestamp hết block (thường là 24h)
        self._model_blocked_until = {}

    def reset_blocks(self):
        """Reset trạng thái block rate-limit (chung) của tất cả các key.
        KHÔNG reset block daily quota vì daily quota không thể phục hồi bằng cách chờ vài phút.
        """
        self._blocked_until.clear()

    def reset_all_blocks(self):
        """Reset tất cả trạng thái block (cả rate-limit lẫn daily quota)."""
        self._blocked_until.clear()
        self._model_blocked_until.clear()

    def get_current_key(self, model_id=None):
        """
        Lấy key hiện tại đang sẵn sàng sử dụng.
        Nếu key hiện tại đang bị block, tự xoay sang key tiếp theo.

        Args:
            model_id (str, optional): Model ID đang sử dụng. Nếu có, cũng kiểm tra
                                       block theo model (daily quota).

        Returns:
            str hoặc None: API key sẵn sàng, hoặc None nếu tất cả đều bị block.
        """
        if not self._keys:
            return None

        now = time.time()
        checked = 0

        while checked < len(self._keys):
            key = self._keys[self._index % len(self._keys)]
            blocked_until = self._blocked_until.get(key, 0)

            if now >= blocked_until:
                # Key không bị block rate-limit chung
                # Kiểm tra thêm block theo model (daily quota) nếu có model_id
                if model_id:
                    model_blocked = self._model_blocked_until.get((key, model_id), 0)
                    if now < model_blocked:
                        # Key bị block daily quota cho model này -> thử key khác
                        self._index = (self._index + 1) % len(self._keys)
                        checked += 1
                        continue
                # Key sẵn sàng
                return key

            # Key đang bị block, thử key tiếp theo
            self._index = (self._index + 1) % len(self._keys)
            checked += 1

        # Tất cả key đều bị block
        return None

    def rotate(self):
        """Chuyển sang key tiếp theo (round-robin)."""
        if self._keys:
            self._index = (self._index + 1) % len(self._keys)

    def mark_rate_limited(self, key, wait_seconds=60):
        """
        Đánh dấu key đang bị rate limit (per-minute).
        Key sẽ tự động được mở lại sau wait_seconds.

        Args:
            key (str): API key bị chặn.
            wait_seconds (float): Thời gian chờ (giây) trước khi key được dùng lại.
        """
        self._blocked_until[key] = time.time() + wait_seconds
        # Tự động xoay sang key tiếp theo
        self.rotate()

    def mark_model_exhausted(self, key, model_id, wait_seconds=86400):
        """
        Đánh dấu key bị hết daily quota cho 1 model cụ thể.
        Key vẫn có thể dùng cho model khác.

        Args:
            key (str): API key.
            model_id (str): Model ID bị hết quota.
            wait_seconds (float): Thời gian block (mặc định 24h).
        """
        self._model_blocked_until[(key, model_id)] = time.time() + wait_seconds
        self.rotate()

    def is_all_keys_model_exhausted(self, model_id):
        """
        Kiểm tra xem TẤT CẢ key có bị hết daily quota cho model này không.

        Args:
            model_id (str): Model ID cần kiểm tra.

        Returns:
            bool: True nếu tất cả key đều bị block daily quota cho model này.
        """
        if not self._keys:
            return True
        now = time.time()
        for key in self._keys:
            blocked_until = self._model_blocked_until.get((key, model_id), 0)
            if now >= blocked_until:
                return False  # Có ít nhất 1 key chưa bị block cho model này
        return True

    def get_min_wait_time(self, model_id=None):
        """
        Trả về thời gian chờ tối thiểu (giây) cho đến khi có ít nhất 1 key sẵn sàng.
        Dùng khi tất cả key đều bị block.

        Args:
            model_id (str, optional): Nếu có, tính cả block theo model.

        Returns:
            float: Số giây cần chờ. 0 nếu đã có key sẵn sàng.
        """
        if not self._keys:
            return 0

        now = time.time()
        min_wait = float('inf')

        for key in self._keys:
            # Kiểm tra block rate-limit chung
            blocked_until = self._blocked_until.get(key, 0)
            remaining = blocked_until - now
            
            if model_id:
                # Cũng kiểm tra block daily quota cho model cụ thể
                model_blocked = self._model_blocked_until.get((key, model_id), 0)
                remaining = max(remaining, model_blocked - now)
            
            if remaining <= 0:
                return 0  # Có key sẵn sàng
            min_wait = min(min_wait, remaining)

        return max(0, min_wait)

    @property
    def count(self):
        """Số lượng key trong danh sách."""
        return len(self._keys)

    @property
    def first_key(self):
        """Key đầu tiên (dùng cho validate)."""
        return self._keys[0] if self._keys else ""

    def get_all_keys_text(self):
        """Trả về chuỗi tất cả key phân cách bằng dấu phẩy."""
        return ",".join(self._keys)


class RateLimiter:
    """
    Bộ kiểm soát tốc độ chủ động (proactive rate limiter).

    Theo dõi timestamp của từng request và tự tính thời gian chờ tối ưu
    dựa trên RPM thực tế của model, tránh bị 429 trước khi nó xảy ra.
    """

    def __init__(self, rpm_per_key, num_keys=1):
        """
        Args:
            rpm_per_key (int): Số request tối đa mỗi key mỗi phút (free tier).
            num_keys (int): Số lượng API key đang dùng.
        """
        self._rpm_per_key = max(1, rpm_per_key)
        self._num_keys = max(1, num_keys)
        # Tổng RPM có thể dùng = RPM mỗi key * số key
        self._total_rpm = self._rpm_per_key * self._num_keys
        # Lịch sử timestamp các request gần nhất (trong 60 giây gần nhất)
        self._request_history = deque()
        # Delay tối thiểu giữa các request (tính toán an toàn)
        # Thêm buffer 10% để tránh edge case
        self._min_delay = (60.0 / self._total_rpm) * 1.1

    def get_wait_time(self):
        """
        Tính thời gian cần chờ trước khi gửi request tiếp.

        Returns:
            float: Số giây cần chờ (0 nếu có thể gửi ngay).
        """
        now = time.time()
        window_start = now - 60.0

        # Dọn dẹp lịch sử cũ (ngoài cửa sổ 60 giây)
        while self._request_history and self._request_history[0] < window_start:
            self._request_history.popleft()

        requests_in_window = len(self._request_history)

        if requests_in_window >= self._total_rpm:
            # Đã đạt giới hạn RPM - phải chờ cho request cũ nhất hết hạn
            oldest = self._request_history[0]
            wait = (oldest + 60.0) - now + 1.0  # +1s buffer
            return max(0, wait)

        if self._request_history:
            # Đảm bảo delay tối thiểu giữa các request
            last_request = self._request_history[-1]
            elapsed = now - last_request
            if elapsed < self._min_delay:
                return self._min_delay - elapsed

        return 0

    def record_request(self):
        """Ghi nhận 1 request vừa được gửi."""
        self._request_history.append(time.time())

    def update_config(self, rpm_per_key, num_keys):
        """
        Cập nhật cấu hình khi user thay đổi model hoặc số key.

        Args:
            rpm_per_key (int): RPM mới mỗi key.
            num_keys (int): Số key mới.
        """
        self._rpm_per_key = max(1, rpm_per_key)
        self._num_keys = max(1, num_keys)
        self._total_rpm = self._rpm_per_key * self._num_keys
        self._min_delay = (60.0 / self._total_rpm) * 1.1

    @property
    def effective_rpm(self):
        """Tổng RPM hiệu dụng (tất cả key cộng lại)."""
        return self._total_rpm

    @property
    def min_delay_seconds(self):
        """Delay tối thiểu giữa các request (giây)."""
        return self._min_delay
