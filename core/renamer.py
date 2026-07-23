"""
Renamer module - Xử lý logic đổi tên file video.
"""

import os
import shutil


def generate_new_name(index, original_filename, code_prefix="", separator="-- ", start_number=1):
    """
    Tạo tên file mới theo format: {mã}{số}{dấu phân cách}{tiêu đề gốc}.{ext}
    
    Args:
        index (int): Index trong danh sách (bắt đầu từ 0).
        original_filename (str): Tên file gốc đầy đủ (bao gồm extension).
        code_prefix (str): Mã prefix do user nhập (ví dụ: "ABC", "VD", "").
        separator (str): Dấu phân cách (ví dụ: "-- ", ". ", ") ").
        start_number (int): Số bắt đầu đếm.
        
    Returns:
        str: Tên file mới.
        
    Examples:
        >>> generate_new_name(0, "video.mp4", "ABC", "-- ", 1)
        'ABC1-- video.mp4'
        >>> generate_new_name(2, "my clip.mkv", "", "-- ", 1)  
        '3-- my clip.mkv'
        >>> generate_new_name(0, "test.mp4", "VD", ". ", 10)
        'VD10. test.mp4'
    """
    number = start_number + index
    name_no_ext, ext = os.path.splitext(original_filename)
    
    new_name = f"{code_prefix}{number}{separator}{name_no_ext}{ext}"
    return new_name


def build_rename_plan(match_results, code_prefix="", separator="-- ", start_number=1):
    """
    Xây dựng kế hoạch đổi tên từ kết quả matching.
    Chỉ bao gồm các tiêu đề đã match thành công.
    
    Args:
        match_results (list[dict]): Kết quả từ matcher.match_all_titles().
        code_prefix (str): Mã prefix.
        separator (str): Dấu phân cách.
        start_number (int): Số bắt đầu.
        
    Returns:
        list[dict]: Kế hoạch đổi tên, mỗi item gồm:
            - 'old_path': Đường dẫn file cũ
            - 'old_name': Tên file cũ
            - 'new_name': Tên file mới
            - 'new_path': Đường dẫn file mới
            - 'title': Tiêu đề trong danh sách
            - 'score': Điểm matching
            - 'number': Số thứ tự
    """
    plan = []
    counter = 0  # Đếm riêng cho các file matched
    
    for result in match_results:
        if result['status'] != 'matched' or result['matched_file'] is None:
            continue
        
        matched = result['matched_file']
        new_name = generate_new_name(
            index=counter,
            original_filename=matched['name'],
            code_prefix=code_prefix,
            separator=separator,
            start_number=start_number,
        )
        
        old_path = matched['path']
        folder = os.path.dirname(old_path)
        new_path = os.path.join(folder, new_name)
        
        plan.append({
            'old_path': old_path,
            'old_name': matched['name'],
            'new_name': new_name,
            'new_path': new_path,
            'title': result['title'],
            'score': result['score'],
            'number': start_number + counter,
        })
        
        counter += 1
    
    return plan


def execute_renames(rename_plan):
    """
    Thực hiện đổi tên file theo kế hoạch.
    
    Args:
        rename_plan (list[dict]): Kế hoạch từ build_rename_plan().
        
    Returns:
        list[dict]: Kết quả thực hiện, mỗi item gồm:
            - 'old_name': Tên cũ
            - 'new_name': Tên mới
            - 'success': True/False
            - 'error': Thông báo lỗi (nếu có)
    """
    results = []
    
    for item in rename_plan:
        try:
            # Kiểm tra file nguồn tồn tại
            if not os.path.exists(item['old_path']):
                results.append({
                    'old_name': item['old_name'],
                    'new_name': item['new_name'],
                    'success': False,
                    'error': f"File không tồn tại: {item['old_name']}",
                })
                continue
            
            # Kiểm tra file đích đã tồn tại chưa
            if os.path.exists(item['new_path']):
                results.append({
                    'old_name': item['old_name'],
                    'new_name': item['new_name'],
                    'success': False,
                    'error': f"File đích đã tồn tại: {item['new_name']}",
                })
                continue
            
            # Thực hiện đổi tên
            os.rename(item['old_path'], item['new_path'])
            
            results.append({
                'old_name': item['old_name'],
                'new_name': item['new_name'],
                'success': True,
                'error': None,
            })
            
        except OSError as e:
            results.append({
                'old_name': item['old_name'],
                'new_name': item['new_name'],
                'success': False,
                'error': str(e),
            })
    
    return results
