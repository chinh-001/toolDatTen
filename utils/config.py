"""
Config module - Quản lý cấu hình lưu trữ local (API key, settings).

File config được lưu tại cùng thư mục với tool, không commit vào repo.
"""

import json
import os

# Đường dẫn file config nằm cùng thư mục gốc của project
_CONFIG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_FILE = os.path.join(_CONFIG_DIR, '.config.json')


def _read_config():
    """
    Đọc toàn bộ config từ file JSON.

    Returns:
        dict: Dữ liệu config, trả về dict rỗng nếu file chưa tồn tại.
    """
    if not os.path.exists(_CONFIG_FILE):
        return {}

    try:
        with open(_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _write_config(data):
    """
    Ghi toàn bộ config ra file JSON.

    Args:
        data (dict): Dữ liệu config cần lưu.
    """
    try:
        with open(_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        raise IOError(f"Không thể lưu config: {e}")


def save_api_key(api_key):
    """
    Lưu API key vào file config local.

    Args:
        api_key (str): Google Gemini API key.
    """
    config = _read_config()
    config['gemini_api_key'] = api_key
    _write_config(config)


def load_api_key():
    """
    Đọc API key từ file config local.

    Returns:
        str: API key đã lưu, hoặc chuỗi rỗng nếu chưa có.
    """
    config = _read_config()
    return config.get('gemini_api_key', '')


def save_setting(key, value):
    """
    Lưu một setting tùy ý vào config.

    Args:
        key (str): Tên setting.
        value: Giá trị cần lưu (phải JSON serializable).
    """
    config = _read_config()
    config[key] = value
    _write_config(config)


def load_setting(key, default=None):
    """
    Đọc một setting từ config.

    Args:
        key (str): Tên setting.
        default: Giá trị mặc định nếu chưa có.

    Returns:
        Giá trị setting hoặc default.
    """
    config = _read_config()
    return config.get(key, default)
