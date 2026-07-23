"""
Video Checker Module - Module kiểm tra thời lượng video và xử lý xóa file.
Được tách riêng theo chuẩn modular architecture.
"""

import os
import subprocess
import cv2
from core.scanner import scan_video_folder
from utils.constants import DEFAULT_DURATION_THRESHOLD_SEC


def get_video_duration(filepath):
    """
    Lấy thời lượng video (tính bằng giây) từ đường dẫn tệp.
    Sử dụng OpenCV cv2 làm phương pháp chính, fallback sang ffprobe nếu cv2 thất bại.

    Args:
        filepath (str): Đường dẫn tuyệt đối tới tệp video.

    Returns:
        float: Thời lượng tính bằng giây. Trả về 0.0 nếu không đọc được.
    """
    if not os.path.exists(filepath):
        return 0.0

    # 1. Thử dùng OpenCV (nhanh và sẵn có)
    try:
        cap = cv2.VideoCapture(filepath)
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()

            if fps > 0 and frame_count > 0:
                duration = frame_count / fps
                if duration > 0:
                    return float(duration)
    except Exception:
        pass

    # 2. Fallback: Thử dùng ffprobe qua subprocess (nếu hệ thống có cài ffmpeg/ffprobe)
    try:
        creationflags = 0
        if os.name == 'nt':
            creationflags = subprocess.CREATE_NO_WINDOW

        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprintwrappers=1:nokey=1',
            filepath
        ]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creationflags,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            duration = float(result.stdout.strip())
            if duration > 0:
                return duration
    except Exception:
        pass

    return 0.0


def format_duration(seconds):
    """
    Chuyển đổi thời lượng từ số giây thành chuỗi hiển thị dạng HH:MM:SS hoặc MM:SS.

    Args:
        seconds (float/int): Số giây.

    Returns:
        str: Chuỗi định dạng thời gian (ví dụ: '00:45', '01:30', '01:15:20').
    """
    if not seconds or seconds <= 0:
        return "00:00"

    total_sec = int(round(seconds))
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def format_file_size(size_in_bytes):
    """
    Chuyển đổi kích thước tệp từ bytes sang chuỗi định dạng KB, MB, GB.

    Args:
        size_in_bytes (int): Số bytes.

    Returns:
        str: Chuỗi định dạng kích thước (ví dụ: '15.4 MB').
    """
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    elif size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.1f} KB"
    elif size_in_bytes < 1024 * 1024 * 1024:
        return f"{size_in_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_in_bytes / (1024 * 1024 * 1024):.2f} GB"


def scan_and_check_durations(folder_path, threshold_sec=DEFAULT_DURATION_THRESHOLD_SEC, progress_callback=None, cancel_event=None):
    """
    Quét thư mục, đọc thời lượng từng video và phân loại theo ngưỡng threshold_sec.

    Args:
        folder_path (str): Thư mục chứa video.
        threshold_sec (float/int): Ngưỡng lọc thời lượng (giây). Mặc định 60s (1 phút).
        progress_callback (callable, optional): Callback nhận (current_idx, total_count, video_name, status_str).
        cancel_event (threading.Event, optional): Cờ để dừng quét giữa chừng.

    Returns:
        dict:
            - 'short_videos': Danh sách video < threshold_sec
            - 'long_videos': Danh sách video >= threshold_sec
            - 'total_count': Tổng số video đã quét
            - 'cancelled': True nếu bị người dùng hủy giữa chừng
    """
    raw_files = scan_video_folder(folder_path)
    total_count = len(raw_files)

    short_videos = []
    long_videos = []
    cancelled = False

    for idx, item in enumerate(raw_files):
        if cancel_event and cancel_event.is_set():
            cancelled = True
            break

        path = item['path']
        name = item['name']
        size = item['size']

        duration = get_video_duration(path)
        duration_str = format_duration(duration)
        size_str = format_file_size(size)

        video_info = {
            'name': name,
            'path': path,
            'size': size,
            'size_str': size_str,
            'duration': duration,
            'duration_str': duration_str,
            'ext': item['ext'],
            'is_short': (duration < threshold_sec)
        }

        if duration < threshold_sec:
            short_videos.append(video_info)
        else:
            long_videos.append(video_info)

        if progress_callback:
            progress_callback(idx + 1, total_count, name, f"Thời lượng: {duration_str}")

    return {
        'short_videos': short_videos,
        'long_videos': long_videos,
        'total_count': total_count,
        'cancelled': cancelled
    }


def delete_video_file(filepath):
    """
    Xóa một tệp video khỏi đĩa.

    Args:
        filepath (str): Đường dẫn tệp video.

    Returns:
        tuple[bool, str]: (Thành công hay không, Thông báo lỗi nếu thất bại).
    """
    try:
        if not os.path.exists(filepath):
            return False, "File không tồn tại trên đĩa"
        os.remove(filepath)
        return True, ""
    except Exception as e:
        return False, str(e)


def batch_delete_videos(filepath_list, progress_callback=None):
    """
    Xóa hàng loạt danh sách tệp video.

    Args:
        filepath_list (list[str]): Danh sách đường dẫn tệp cần xóa.
        progress_callback (callable, optional): Callback nhận (current_idx, total_count, path).

    Returns:
        dict:
            - 'success_count': Số tệp xóa thành công
            - 'fail_count': Số tệp lỗi
            - 'results': Danh sách dict {path, success, error}
    """
    total = len(filepath_list)
    success_count = 0
    fail_count = 0
    results = []

    for idx, path in enumerate(filepath_list):
        ok, err = delete_video_file(path)
        if ok:
            success_count += 1
        else:
            fail_count += 1

        results.append({
            'path': path,
            'name': os.path.basename(path),
            'success': ok,
            'error': err
        })

        if progress_callback:
            progress_callback(idx + 1, total, path)

    return {
        'success_count': success_count,
        'fail_count': fail_count,
        'results': results
    }
