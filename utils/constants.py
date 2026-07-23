"""
Constants cho tool đổi tên video và trích highlight.
"""

# Các extension video được hỗ trợ
VIDEO_EXTENSIONS = {
    '.mp4', '.mkv', '.avi', '.mov', '.webm',
    '.flv', '.wmv', '.m4v', '.ts', '.3gp',
    '.mpg', '.mpeg', '.vob', '.ogv',
}

# Ngưỡng fuzzy match mặc định (0-100)
DEFAULT_MATCH_THRESHOLD = 60

# Số bắt đầu mặc định
DEFAULT_START_NUMBER = 1

# Dấu phân cách mặc định
DEFAULT_SEPARATOR = "-- "

# Mã prefix mặc định (rỗng)
DEFAULT_CODE_PREFIX = ""

# Kích thước cửa sổ
WINDOW_WIDTH = 1050
WINDOW_HEIGHT = 800
WINDOW_TITLE = "Tool Đổi Tên & Trích Highlight Video AI"

# Màu sắc cho matching
COLOR_MATCH_GOOD = "#2ecc71"      # Xanh lá - khớp tốt (>= 80%)
COLOR_MATCH_MEDIUM = "#f39c12"    # Vàng cam - khớp vừa (>= threshold)
COLOR_MATCH_NONE = "#e74c3c"      # Đỏ - không tìm thấy

# Ngưỡng phân loại màu
THRESHOLD_GOOD = 80

# Gemini API Constants
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Danh sách model Gemini có thể chọn (tên hiển thị -> {id, rpm})
GEMINI_MODELS = {
    "gemini-3.5-flash (mới nhất, 15 RPM)": "gemini-3.5-flash",
    "gemini-3.1-flash-lite (mới, rất nhanh, 30 RPM)": "gemini-3.1-flash-lite",
    "gemini-2.0-flash (nhanh, 15 RPM)": "gemini-2.0-flash",
    "gemini-2.0-flash-lite (rất nhanh, 30 RPM)": "gemini-2.0-flash-lite",
    "gemini-1.5-flash (ổn định, 15 RPM)": "gemini-1.5-flash",
}

# RPM (requests per minute) tối đa cho từng model trên free tier
GEMINI_MODEL_RPM = {
    "gemini-3.5-flash": 15,
    "gemini-3.1-flash-lite": 30,
    "gemini-2.0-flash": 15,
    "gemini-2.0-flash-lite": 30,
    "gemini-1.5-flash": 15,
}

# Model mặc định
DEFAULT_MODEL_NAME = "gemini-2.0-flash (nhanh, 15 RPM)"

# Prompt mặc định cho trích highlight
DEFAULT_HIGHLIGHT_PROMPT = (
    "Hãy phân tích nội dung video theo tiêu đề và đường dẫn URL bên dưới để trích xuất các mốc thời gian highlight quan trọng nhất "
    "(ví dụ: phần giới thiệu, nội dung chính, cao trào, kết quả).\n"
    "Quy tắc bắt buộc:\n"
    "1. Trả về kết quả TRỰC TIẾP và CHỈ bao gồm các đoạn highlight theo định dạng chuẩn xác sau: MM:SS,MM:SS;MM:SS,MM:SS;...\n"
    "   Ví dụ: 00:12,00:17;00:25,00:33;01:20,01:25\n"
    "2. TUYỆT ĐỐI KHÔNG thêm bất kỳ văn bản giải thích, lời chào, hay ký tự markdown (như ```) nào ngoài định dạng trên.\n"
    "3. Các mốc thời gian phải tăng dần hợp lý, thời lượng mỗi đoạn highlight từ 5 giây đến 2 phút.\n"
    "Tiêu đề video: {title}\n"
    "Link video: {url}"
)


# Ngưỡng thời lượng video mặc định (tính bằng giây - 60s = 1 phút)
DEFAULT_DURATION_THRESHOLD_SEC = 60

