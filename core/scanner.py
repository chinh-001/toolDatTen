"""
Scanner module - Quét thư mục video và trả về danh sách file video.
"""

import os
from utils.constants import VIDEO_EXTENSIONS


def scan_video_folder(folder_path):
    """
    Quét thư mục và trả về danh sách file video.
    
    Args:
        folder_path (str): Đường dẫn thư mục cần quét.
        
    Returns:
        list[dict]: Danh sách dict với keys:
            - 'name': Tên file đầy đủ (ví dụ: 'video.mp4')
            - 'name_no_ext': Tên file không có extension (ví dụ: 'video')
            - 'ext': Extension (ví dụ: '.mp4')
            - 'path': Đường dẫn đầy đủ
            - 'size': Kích thước file (bytes)
    
    Raises:
        FileNotFoundError: Nếu thư mục không tồn tại.
        NotADirectoryError: Nếu path không phải thư mục.
    """
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Thư mục không tồn tại: {folder_path}")
    
    if not os.path.isdir(folder_path):
        raise NotADirectoryError(f"Đường dẫn không phải thư mục: {folder_path}")
    
    video_files = []
    
    for filename in os.listdir(folder_path):
        filepath = os.path.join(folder_path, filename)
        
        # Chỉ lấy file, bỏ qua thư mục con
        if not os.path.isfile(filepath):
            continue
        
        name_no_ext, ext = os.path.splitext(filename)
        
        # Kiểm tra extension có phải video không (case-insensitive)
        if ext.lower() in VIDEO_EXTENSIONS:
            video_files.append({
                'name': filename,
                'name_no_ext': name_no_ext,
                'ext': ext,
                'path': filepath,
                'size': os.path.getsize(filepath),
            })
    
    # Sắp xếp theo tên file
    video_files.sort(key=lambda x: x['name'].lower())
    
    return video_files
