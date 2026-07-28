"""
Video Name Extractor - Core module trích xuất tên file video, định dạng cách dòng và xuất file .txt.
Hỗ trợ sắp xếp theo số thứ tự (từ nhỏ -> lớn, video không có số ở cuối).
"""

import os
import re
from core.scanner import scan_video_folder


def sort_video_names_numerically(video_names):
    """
    Sắp xếp danh sách tên video theo số thứ tự từ nhỏ đến lớn.
    Ưu tiên số thứ tự ở đầu hoặc trong tên file (đã loại bỏ đuôi mở rộng .mp4, .mkv...).
    Các video KHÔNG có số thứ tự sẽ tự động đứng ở cuối danh sách.

    Args:
        video_names (list[str]): Danh sách tên video.

    Returns:
        list[str]: Danh sách tên video đã sắp xếp.
    """
    def sort_key(name):
        # Bỏ đuôi mở rộng file trước khi tìm số để tránh trường hợp .mp4 chứa số 4
        name_no_ext = os.path.splitext(name)[0]

        # 1. Thử tìm số ở đầu tên file (ví dụ: "01_Video", "2. Lesson", "10 - Intro")
        leading_match = re.match(r'^\s*(\d+)', name_no_ext)
        if leading_match:
            num = int(leading_match.group(1))
            return (0, num, name.lower())

        # 2. Thử tìm số bất kỳ trong tên file (ví dụ: "Lesson 5", "Bai_12")
        any_match = re.search(r'\d+', name_no_ext)
        if any_match:
            num = int(any_match.group())
            return (0, num, name.lower())

        # 3. Không có số -> Xếp ở cuối cùng (1 > 0)
        return (1, 0, name.lower())

    return sorted(video_names, key=sort_key)


def extract_video_names(folder_path, keep_extension=False, sort_by_number=True):
    """
    Quét thư mục và trả về danh sách tên các file video đã được sắp xếp.

    Args:
        folder_path (str): Đường dẫn thư mục video.
        keep_extension (bool): Nếu True thì giữ đuôi file (ví dụ: 'video.mp4'),
                               Nếu False thì chỉ lấy tên không đuôi (ví dụ: 'video').
        sort_by_number (bool): Sắp xếp theo số thứ tự tăng dần, video không số ở cuối.

    Returns:
        list[str]: Danh sách tên các file video.

    Raises:
        FileNotFoundError, NotADirectoryError: Các lỗi từ scan_video_folder.
    """
    video_files = scan_video_folder(folder_path)
    if keep_extension:
        names = [item['name'] for item in video_files]
    else:
        names = [item['name_no_ext'] for item in video_files]

    if sort_by_number:
        names = sort_video_names_numerically(names)

    return names


def format_video_names_spaced(video_names, double_spacing=True):
    """
    Định dạng danh sách tên video thành chuỗi văn bản với các dòng được giãn ra (cách dòng)
    để người dùng dễ đọc, xem và copy.

    Args:
        video_names (list[str]): Danh sách tên video.
        double_spacing (bool): Nếu True thì giữa các tên có 1 dòng trống (phân cách bởi \\n\\n).
                              Nếu False thì mỗi tên 1 dòng (\\n).

    Returns:
        str: Chuỗi văn bản đã định dạng.
    """
    if not video_names:
        return ""

    separator = "\n\n" if double_spacing else "\n"
    return separator.join(video_names)


def export_names_to_txt_file(file_path, video_names, double_spacing=True):
    """
    Xuất danh sách tên video ra file .txt với mã hóa UTF-8.

    Args:
        file_path (str): Đường dẫn file .txt cần ghi.
        video_names (list[str]): Danh sách tên video.
        double_spacing (bool): Định dạng cách dòng hay không.

    Returns:
        tuple[bool, str or None, int]: (Thành công hay không, Thông báo lỗi nếu có, Số lượng tên đã xuất)
    """
    try:
        formatted_text = format_video_names_spaced(video_names, double_spacing=double_spacing)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(formatted_text)
        return True, None, len(video_names)
    except Exception as e:
        return False, str(e), 0


def quick_export_folder_to_txt(folder_path, output_txt_path, keep_extension=False, double_spacing=True, sort_by_number=True):
    """
    Tự động trích lấy tất cả tên file video từ thư mục folder_path và xuất thẳng ra file output_txt_path.

    Args:
        folder_path (str): Thư mục chứa các file video (Input).
        output_txt_path (str): Đường dẫn file .txt xuất ra (Output).
        keep_extension (bool): Có giữ đuôi mở rộng file (.mp4...) hay không.
        double_spacing (bool): Cách dòng giữa các tên video.
        sort_by_number (bool): Sắp xếp theo số thứ tự nhỏ -> lớn, video không số nằm ở cuối.

    Returns:
        tuple[bool, str, int, str]: (Thành công hay không, Chuỗi định dạng, Số lượng video, Thông báo lỗi/thành công)
    """
    try:
        names = extract_video_names(folder_path, keep_extension=keep_extension, sort_by_number=sort_by_number)
        if not names:
            return False, "", 0, "Không tìm thấy file video nào trong thư mục được chọn."

        formatted_text = format_video_names_spaced(names, double_spacing=double_spacing)
        with open(output_txt_path, 'w', encoding='utf-8') as f:
            f.write(formatted_text)

        return True, formatted_text, len(names), None
    except Exception as e:
        return False, "", 0, str(e)
