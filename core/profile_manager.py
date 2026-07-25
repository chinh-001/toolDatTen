"""
Profile Manager Module - Quản lý và tự động phát hiện các Profile trình duyệt (Chrome, Edge, App Profiles).
Cho phép người dùng chọn profile đã đăng nhập tài khoản Google để tự động hóa Gemini Web.
"""

import os
import json
import shutil
import re

def get_base_browser_data_dir():
    """Lấy thư mục gốc chứa dữ liệu browser profile của app (.browser_data)."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    browser_data_dir = os.path.join(base_dir, ".browser_data")
    os.makedirs(browser_data_dir, exist_ok=True)
    return browser_data_dir


def detect_system_chrome_profiles():
    """Phát hiện các profile Google Chrome đã cài đặt trên máy tính (Windows)."""
    profiles = []
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        return profiles

    chrome_user_data = os.path.join(local_app_data, "Google", "Chrome", "User Data")
    local_state_path = os.path.join(chrome_user_data, "Local State")

    if os.path.exists(local_state_path):
        try:
            with open(local_state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            info_cache = data.get("profile", {}).get("info_cache", {})
            for folder_name, info in info_cache.items():
                name = info.get("name", folder_name)
                user_name = info.get("user_name", "")
                gaia_name = info.get("gaia_name", "")
                is_using_default_name = info.get("is_using_default_name", False)

                display = name
                account_info = user_name or gaia_name
                if account_info:
                    display += f" ({account_info})"

                prof_id = f"chrome_{folder_name}"
                profiles.append({
                    "id": prof_id,
                    "type": "chrome",
                    "name": name,
                    "folder": folder_name,
                    "user_data_dir": chrome_user_data,
                    "label": f"Chrome: {display}",
                    "has_google_login": bool(account_info)
                })
        except Exception as e:
            print(f"Lỗi khi đọc Chrome Local State: {e}")

    return profiles


def detect_system_edge_profiles():
    """Phát hiện các profile Microsoft Edge đã cài đặt trên máy tính (Windows)."""
    profiles = []
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        return profiles

    edge_user_data = os.path.join(local_app_data, "Microsoft", "Edge", "User Data")
    local_state_path = os.path.join(edge_user_data, "Local State")

    if os.path.exists(local_state_path):
        try:
            with open(local_state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            info_cache = data.get("profile", {}).get("info_cache", {})
            for folder_name, info in info_cache.items():
                name = info.get("name", folder_name)
                user_name = info.get("user_name", "")
                display = name
                if user_name:
                    display += f" ({user_name})"

                prof_id = f"edge_{folder_name}"
                profiles.append({
                    "id": prof_id,
                    "type": "edge",
                    "name": name,
                    "folder": folder_name,
                    "user_data_dir": edge_user_data,
                    "label": f"Edge: {display}",
                    "has_google_login": bool(user_name)
                })
        except Exception as e:
            print(f"Lỗi khi đọc Edge Local State: {e}")

    return profiles


def get_app_profiles():
    """Lấy danh sách các profile riêng biệt của ứng dụng trong .browser_data/profiles/."""
    profiles = []
    base_dir = get_base_browser_data_dir()
    profiles_dir = os.path.join(base_dir, "profiles")
    os.makedirs(profiles_dir, exist_ok=True)

    # Khởi tạo các Profile mặc định nếu chưa có
    default_slots = ["Profile_1", "Profile_2", "Profile_3"]
    for slot in default_slots:
        slot_dir = os.path.join(profiles_dir, slot)
        os.makedirs(slot_dir, exist_ok=True)

    for item in sorted(os.listdir(profiles_dir)):
        if item.startswith("isolated_"):
            continue
        item_path = os.path.join(profiles_dir, item)
        if os.path.isdir(item_path):
            clean_name = item.replace("_", " ")
            profiles.append({
                "id": f"app_{item}",
                "type": "app",
                "name": clean_name,
                "folder": "Default",
                "user_data_dir": item_path,
                "label": f"App Profile: {clean_name}",
                "has_google_login": False
            })

    return profiles


def is_system_chrome_running():
    """Kiểm tra xem trình duyệt Google Chrome có đang chạy trên Windows hay không."""
    try:
        import subprocess
        out = subprocess.check_output(['tasklist', '/FI', 'IMAGENAME eq chrome.exe'], stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore')
        return 'chrome.exe' in out.lower()
    except Exception:
        return False


def get_all_profiles():
    """
    Lấy toàn bộ các profile có sẵn (App Profiles khuyên dùng, Chrome hệ thống, Edge hệ thống).

    Returns:
        list: Danh sách các dict profile {"id": str, "label": str, ...}
    """
    all_profs = []

    # 1. App Profiles riêng biệt (ƯU TIÊN HÀNG ĐẦU - Khuyên dùng vì 100% ổn định vĩnh viễn)
    app_profs = get_app_profiles()
    for ap in app_profs:
        all_profs.append({
            "id": ap["id"],
            "type": "app",
            "name": ap["name"],
            "folder": "Default",
            "user_data_dir": ap["user_data_dir"],
            "label": f"⭐ {ap['name']} (Tool Profile - Khuyên dùng 100% Ổn định)",
            "has_google_login": False
        })

    # Tùy chọn tự động quét profile Chrome hệ thống
    all_profs.append({
        "id": "auto_detect",
        "type": "auto",
        "name": "⚡ Tự động chọn Chrome Profile hệ thống",
        "folder": "Default",
        "user_data_dir": "",
        "label": "⚡ Tự động chọn Chrome Profile hệ thống",
        "has_google_login": True
    })

    # 2. Chrome hệ thống (Sắp xếp các profile đã đăng nhập lên đầu)
    chrome_profs = detect_system_chrome_profiles()
    logged_in_chrome = [p for p in chrome_profs if p.get("has_google_login")]
    other_chrome = [p for p in chrome_profs if not p.get("has_google_login")]

    for cp in logged_in_chrome + other_chrome:
        all_profs.append({
            "id": cp["id"],
            "type": "chrome",
            "name": cp["name"],
            "folder": cp["folder"],
            "user_data_dir": cp["user_data_dir"],
            "label": cp["label"],
            "has_google_login": cp["has_google_login"]
        })

    # 3. Edge hệ thống
    edge_profs = detect_system_edge_profiles()
    for ep in edge_profs:
        all_profs.append({
            "id": ep["id"],
            "type": "edge",
            "name": ep["name"],
            "folder": ep["folder"],
            "user_data_dir": ep["user_data_dir"],
            "label": ep["label"],
            "has_google_login": ep["has_google_login"]
        })

    return all_profs


def resolve_profile_info(profile_id_or_label):
    """
    Xác định dict thông tin profile đầy đủ (user_data_dir, folder, label, v.v.).

    Args:
        profile_id_or_label (str): Mã hoặc nhãn profile.

    Returns:
        dict: Dict chứa thông tin profile.
    """
    all_profs = get_all_profiles()

    selected_prof = None
    if profile_id_or_label and profile_id_or_label != "auto_detect":
        for p in all_profs:
            if p["id"] == profile_id_or_label or p["label"] == profile_id_or_label:
                selected_prof = p
                break

    # Nếu là auto_detect hoặc không tìm thấy profile cụ thể
    if not selected_prof or selected_prof["type"] == "auto":
        # Ưu tiên 1: Chọn Chrome profile hệ thống có Google login
        chrome_profs = detect_system_chrome_profiles()
        for cp in chrome_profs:
            if cp.get("has_google_login"):
                return cp
        # Ưu tiên 2: Chọn Chrome profile bất kỳ đầu tiên
        if chrome_profs:
            return chrome_profs[0]

        # Ưu tiên 3: App Profile 1
        p1_dir = os.path.join(get_base_browser_data_dir(), "profiles", "Profile_1")
        os.makedirs(p1_dir, exist_ok=True)
        return {
            "id": "app_Profile_1",
            "type": "app",
            "name": "Profile 1",
            "folder": "Default",
            "user_data_dir": p1_dir,
            "label": "App Profile: Profile 1",
            "has_google_login": False
        }

    return selected_prof


def resolve_profile_dir(profile_id):
    """Giữ hàm tương thích cũ: trả về đường dẫn user_data_dir."""
    info = resolve_profile_info(profile_id)
    return info["user_data_dir"]


def create_new_app_profile(profile_name):
    """
    Tạo một app profile mới trong .browser_data/profiles/.

    Args:
        profile_name (str): Tên profile do người dùng đặt.

    Returns:
        dict: Thông tin profile mới vừa tạo.
    """
    sanitized = re.sub(r'[^\w\s-]', '', profile_name).strip().replace(' ', '_')
    if not sanitized:
        sanitized = "Profile_Moi"

    profiles_dir = os.path.join(get_base_browser_data_dir(), "profiles")
    target_dir = os.path.join(profiles_dir, sanitized)
    os.makedirs(target_dir, exist_ok=True)

    prof_id = f"app_{sanitized}"
    return {
        "id": prof_id,
        "type": "app",
        "name": profile_name,
        "folder": "Default",
        "user_data_dir": target_dir,
        "label": f"App Profile: {profile_name}",
        "has_google_login": False
    }

