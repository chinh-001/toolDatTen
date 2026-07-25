"""
Profile Copier Module - Xử lý sao chép Chrome Profile sang thư mục cách ly tạm thời.
Giúp Playwright khởi chạy trình duyệt bằng Profile thật đã đăng nhập mà không bị lỗi
'user data directory is already in use' ngay cả khi Chrome đang mở lướt web trên máy.
"""

import os
import shutil
import time

# Các thư mục cache nặng không cần thiết cho session đăng nhập
EXCLUDE_CACHE_DIRS = {
    "cache", "code cache", "gpucache", "media cache", "service worker",
    "crashpad", "file system", "system code cache", "dawncache",
    "blob_storage", "grshadercache", "graphitedawncache", "application cache",
    "cachestorage", "extensions", "extension state", "storage/ext",
    "optimization_guide_prediction_models", "history", "history-journal"
}

def get_temp_profiles_base_dir():
    """Lấy thư mục gốc chứa các profile cách ly tạm thời (.browser_data/temp_profiles)."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    temp_dir = os.path.join(base_dir, ".browser_data", "temp_profiles")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def safe_copy_file(src_path, dst_path, skipped_files=None, rel_path=""):
    """
    Sao chép file an toàn. Nếu file bị Chrome khóa exclusively, thử đọc luồng nhị phân.
    Nếu vẫn không copy được, ghi nhận file vào skipped_files.
    """
    try:
        shutil.copy2(src_path, dst_path)
        return True
    except (PermissionError, OSError):
        pass

    # Thử đọc trực tiếp với shared mode
    try:
        with open(src_path, "rb") as fsrc:
            with open(dst_path, "wb") as fdst:
                shutil.copyfileobj(fsrc, fdst, length=64 * 1024)
        return True
    except Exception as e:
        if skipped_files is not None and rel_path:
            skipped_files.append(f"{rel_path} ({type(e).__name__})")
        return False


def copy_directory_selectively(src_dir, dst_dir, skipped_files=None, base_src_dir=None):
    """
    Sao chép thư mục Profile theo cách chọn lọc:
    Loại bỏ các thư mục Cache dung lượng lớn để quá trình sao chép siêu nhanh (1-2s).
    """
    if not os.path.exists(src_dir):
        return

    if base_src_dir is None:
        base_src_dir = src_dir

    os.makedirs(dst_dir, exist_ok=True)

    for item in os.listdir(src_dir):
        src_item = os.path.join(src_dir, item)
        dst_item = os.path.join(dst_dir, item)

        # Loại bỏ thư mục Lock hoặc Cache dư thừa
        item_lower = item.lower()
        if item_lower in EXCLUDE_CACHE_DIRS or item in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
            continue

        if os.path.isdir(src_item):
            copy_directory_selectively(src_item, dst_item, skipped_files=skipped_files, base_src_dir=base_src_dir)
        else:
            rel_path = os.path.relpath(src_item, base_src_dir)
            safe_copy_file(src_item, dst_item, skipped_files=skipped_files, rel_path=rel_path)


def prepare_isolated_chrome_profile(user_data_dir, profile_folder="Default"):
    """
    Tạo một bản sao cách ly của Chrome Profile để Playwright có thể mở độc lập mà không đụng độ
    với phiên làm việc Chrome đang mở trên máy.

    Args:
        user_data_dir (str): Thư mục User Data của Chrome (hoặc thư mục app profile).
        profile_folder (str): Tên thư mục profile ("Default", "Profile 1", "Profile 2", ...).

    Returns:
        tuple: (temp_user_data_dir, profile_folder_name, skipped_files_list)
    """
    skipped_files = []
    if not user_data_dir or not os.path.exists(user_data_dir):
        # Nếu đường dẫn không tồn tại, trả về nguyên bản
        return user_data_dir, profile_folder, skipped_files

    local_state_path = os.path.join(user_data_dir, "Local State")
    is_system_chrome = os.path.exists(local_state_path)

    # Đặt tên thư mục tạm cách ly
    safe_folder_name = profile_folder.replace(" ", "_")
    temp_base = get_temp_profiles_base_dir()
    isolated_dir = os.path.join(temp_base, f"isolated_{safe_folder_name}")

    os.makedirs(isolated_dir, exist_ok=True)

    if is_system_chrome:
        # 1. Copy file Local State từ thư mục gốc User Data (cần cho decrypt cookie DPAPI)
        temp_local_state = os.path.join(isolated_dir, "Local State")
        safe_copy_file(local_state_path, temp_local_state, skipped_files=skipped_files, rel_path="Local State")

        # 2. Copy thư mục profile tương ứng (Default / Profile 1 / ...)
        src_profile_dir = os.path.join(user_data_dir, profile_folder)
        dst_profile_dir = os.path.join(isolated_dir, profile_folder)

        if os.path.exists(src_profile_dir):
            copy_directory_selectively(src_profile_dir, dst_profile_dir, skipped_files=skipped_files, base_src_dir=src_profile_dir)
            # Đồng thời sao chép sang thư mục Default để Playwright nhận diện đúng 100% dù có/không flag --profile-directory
            if profile_folder != "Default":
                dst_default_dir = os.path.join(isolated_dir, "Default")
                copy_directory_selectively(src_profile_dir, dst_default_dir, skipped_files=skipped_files, base_src_dir=src_profile_dir)
        else:
            # Nếu thư mục profile con không tồn tại, copy trực tiếp user_data_dir
            copy_directory_selectively(user_data_dir, os.path.join(isolated_dir, "Default"), skipped_files=skipped_files, base_src_dir=user_data_dir)
            profile_folder = "Default"

        return isolated_dir, profile_folder, skipped_files
    else:
        # Đối với App Profiles riêng biệt
        copy_directory_selectively(user_data_dir, os.path.join(isolated_dir, "Default"), skipped_files=skipped_files, base_src_dir=user_data_dir)
        return isolated_dir, "Default", skipped_files


def clean_temp_profiles():
    """Dọn dẹp các thư mục profile tạm thời cũ."""
    temp_base = get_temp_profiles_base_dir()
    if not os.path.exists(temp_base):
        return

    for item in os.listdir(temp_base):
        item_path = os.path.join(temp_base, item)
        if os.path.isdir(item_path) and item.startswith("isolated_"):
            try:
                # Xóa nếu tạo lâu hơn 6 giờ
                mtime = os.path.getmtime(item_path)
                if time.time() - mtime > 6 * 3600:
                    shutil.rmtree(item_path, ignore_errors=True)
            except Exception:
                pass
