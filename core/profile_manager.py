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

                display = name
                if user_name:
                    display += f" ({user_name})"
                elif gaia_name:
                    display += f" ({gaia_name})"

                prof_id = f"chrome_{folder_name}"
                profiles.append({
                    "id": prof_id,
                    "type": "chrome",
                    "name": name,
                    "folder": folder_name,
                    "user_data_dir": chrome_user_data,
                    "label": f"Chrome: {display}"
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
                    "label": f"Edge: {display}"
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
                "folder": item,
                "user_data_dir": item_path,
                "label": f"Profile: {clean_name}"
            })

    return profiles


def get_all_profiles():
    """
    Lấy toàn bộ các profile có sẵn (Chrome hệ thống, Edge hệ thống và App Profiles).

    Returns:
        list: Danh sách các dict profile {"id": str, "label": str, ...}
    """
    all_profs = []

    # 1. Chrome hệ thống (Tự động chuyển tới thư mục Profile trực tiếp)
    chrome_profs = detect_system_chrome_profiles()
    for cp in chrome_profs:
        direct_profile_path = os.path.join(cp["user_data_dir"], cp["folder"])
        all_profs.append({
            "id": cp["id"],
            "type": "chrome",
            "name": cp["name"],
            "folder": cp["folder"],
            "user_data_dir": direct_profile_path,
            "label": cp["label"]
        })

    # 2. Edge hệ thống
    edge_profs = detect_system_edge_profiles()
    for ep in edge_profs:
        direct_profile_path = os.path.join(ep["user_data_dir"], ep["folder"])
        all_profs.append({
            "id": ep["id"],
            "type": "edge",
            "name": ep["name"],
            "folder": ep["folder"],
            "user_data_dir": direct_profile_path,
            "label": ep["label"]
        })

    # 3. App profiles
    app_profs = get_app_profiles()
    all_profs.extend(app_profs)

    return all_profs


def resolve_profile_dir(profile_id):
    """
    Xác định đường dẫn thư mục user_data_dir thực tế cần dùng cho Playwright dựa trên profile_id.

    Args:
        profile_id (str): Mã định danh profile.

    Returns:
        str: Đường dẫn thư mục user_data_dir tuyệt đối.
    """
    all_profs = get_all_profiles()
    selected_prof = None
    for p in all_profs:
        if p["id"] == profile_id or p["label"] == profile_id:
            selected_prof = p
            break

    if not selected_prof:
        # Mặc định trả về Profile 1 của app
        p1 = os.path.join(get_base_browser_data_dir(), "profiles", "Profile_1")
        os.makedirs(p1, exist_ok=True)
        return p1

    return selected_prof["user_data_dir"]


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
        "folder": sanitized,
        "user_data_dir": target_dir,
        "label": f"Profile: {profile_name}"
    }
