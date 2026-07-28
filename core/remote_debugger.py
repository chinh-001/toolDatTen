"""
Remote Debugger Module - Quản lý khởi chạy và kết nối Chrome qua Remote Debugging Port (CDP).
Giúp trình duyệt chạy hoàn toàn như Chrome thực do người dùng mở, bảo toàn 100% session đăng nhập
Google/Gemini mà không bị Google phát hiện automation hay yêu cầu 'Xác minh danh tính'.
"""

import os
import sys
import time
import socket
import subprocess


def is_port_listening(port=9222, host="127.0.0.1", timeout=1.0):
    """
    Kiểm tra xem Remote Debugging Port đã sẵn sàng lắng nghe kết nối hay chưa.

    Args:
        port (int): Cổng remote debugging (mặc định 9222).
        host (str): Địa chỉ host (mặc định 127.0.0.1).
        timeout (float): Thời gian chờ kết nối socket (giây).

    Returns:
        bool: True nếu cổng đang lắng nghe kết nối.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.close()
        return True
    except (OSError, socket.error):
        return False


def launch_chrome_remote_debugging(chrome_path, user_data_dir, profile_folder="Default", port=9222, headless=False):
    """
    Khởi chạy Google Chrome thực dưới dạng tiến trình hệ thống với cờ --remote-debugging-port.

    Args:
        chrome_path (str): Đường dẫn file thực thi Chrome (chrome.exe).
        user_data_dir (str): Thư mục User Data của Chrome.
        profile_folder (str): Tên thư mục profile ("Default", "Profile 1", ...).
        port (int): Cổng remote debugging.
        headless (bool): Bật/tắt chế độ ẩn.

    Returns:
        subprocess.Popen: Đối tượng tiến trình Chrome vừa khởi chạy.
    """
    if not chrome_path or not os.path.exists(chrome_path):
        raise FileNotFoundError(f"Không tìm thấy file Chrome thực thi tại: {chrome_path}")

    cmd = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        f"--profile-directory={profile_folder}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-search-engine-choice-screen",
    ]

    if headless:
        cmd.append("--headless=new")

    # Khởi chạy tiến trình độc lập không bị ràng buộc bởi Python
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    )
    return process


def ensure_cdp_chrome_ready(chrome_path, user_data_dir, profile_folder="Default", port=9222, headless=False, max_wait_seconds=15):
    """
    Đảm bảo cổng Remote Debugging CDP hoạt động. Nếu chưa mở thì tự động kích hoạt Chrome.

    Args:
        chrome_path (str): Đường dẫn Chrome.
        user_data_dir (str): Thư mục User Data.
        profile_folder (str): Thư mục profile.
        port (int): Cổng CDP.
        headless (bool): Chế độ ẩn.
        max_wait_seconds (int): Thời gian chờ tối đa (giây).

    Returns:
        tuple: (bool, str, subprocess.Popen or None) -> (Thành công, Thông báo, Process nếu có)
    """
    if is_port_listening(port=port):
        return True, f"Cổng Remote Debugging {port} đã sẵn sàng.", None

    proc = launch_chrome_remote_debugging(
        chrome_path=chrome_path,
        user_data_dir=user_data_dir,
        profile_folder=profile_folder,
        port=port,
        headless=headless
    )

    start_time = time.time()
    while time.time() - start_time < max_wait_seconds:
        if is_port_listening(port=port):
            return True, f"Khởi chạy Chrome thành công với cổng Remote Debugging {port}.", proc
        time.sleep(0.5)

    return False, f"Chrome mở nhưng cổng {port} không lắng nghe sau {max_wait_seconds}s.", proc
