"""
Matcher module - Đối chiếu tiêu đề với tên file video bằng fuzzy matching.
Nâng cấp: So khớp không dấu tiếng Việt, so khớp theo từ (token-based) và lọc bỏ thẻ rác.
"""

import re
import unicodedata
from difflib import SequenceMatcher

from utils.constants import DEFAULT_MATCH_THRESHOLD

# Các thẻ thông số nhiễu thường gặp trong tên file video tải về
NOISE_TAGS = {
    '1080p', '720p', '480p', '360p', '4k', '2k', 'fhd', 'hd', 'sd',
    'bluray', 'webrip', 'webdl', 'web-dl', 'h264', 'x264', 'h265', 'x265',
    'aac', 'mp3', 'mp4', 'mkv', 'avi', 'mov', 'engsub', 'vietsub', 'sub',
    'full', 'raw', 'encode', 'remux', 'hevc', 'web', 'dl', 'rip', 'vs'
}


def _remove_vietnamese_accents(text):
    """
    Loại bỏ dấu tiếng Việt để so khớp không dấu chuẩn xác.
    """
    text = unicodedata.normalize('NFD', text)
    # Mn đại diện cho Nonspacing Mark (dấu phụ tiếng Việt)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    # Thay chữ đ/Đ thành d/D
    text = text.replace('đ', 'd').replace('Đ', 'D')
    return text


def _normalize_text(text, remove_accents=False):
    """
    Chuẩn hóa văn bản:
    - Unicode NFC
    - Viết thường (lowercase)
    - Loại bỏ dấu phụ nếu được yêu cầu
    - Thay thế các ký tự ngăn cách phổ biến thành khoảng trắng
    - Loại bỏ các từ rác phổ biến
    """
    if not text:
        return ""
        
    text = unicodedata.normalize('NFC', text)
    text = text.lower().strip()
    
    if remove_accents:
        text = _remove_vietnamese_accents(text)
        
    # Thay thế các ký tự phân cách phổ biến thành khoảng trắng
    text = re.sub(r'[#\[\](){}|_\-–—•·\\/*+?.,:;!@$%^&~`="]', ' ', text)
    
    # Loại bỏ các tag nhiễu
    words = text.split()
    cleaned_words = [w for w in words if w not in NOISE_TAGS]
    
    return " ".join(cleaned_words)


def calculate_similarity(title, filename):
    """
    Tính điểm tương đồng giữa tiêu đề và tên file (0-100).
    Sử dụng kết hợp:
    1. So khớp ký tự SequenceMatcher (có dấu & không dấu).
    2. So khớp theo từ (Token-based Jaccard & Containment) giúp không bị ảnh hưởng bởi đảo thứ tự từ.
    3. Kiểm tra chứa chuỗi con không dấu (Partial match).
    """
    # 1. So khớp có dấu
    norm_title = _normalize_text(title, remove_accents=False)
    norm_filename = _normalize_text(filename, remove_accents=False)
    
    if not norm_title or not norm_filename:
        return 0.0
        
    # 2. So khớp không dấu
    unsigned_title = _normalize_text(title, remove_accents=True)
    unsigned_filename = _normalize_text(filename, remove_accents=True)
    
    # --- PHƯƠNG PHÁP 1: SequenceMatcher Ratio (Độ tương đồng ký tự) ---
    ratio_accent = SequenceMatcher(None, norm_title, norm_filename).ratio() * 100
    ratio_unsigned = SequenceMatcher(None, unsigned_title, unsigned_filename).ratio() * 100
    best_char_ratio = max(ratio_accent, ratio_unsigned)
    
    # --- PHƯƠNG PHÁP 2: Token-based Match (Độ tương đồng theo từ) ---
    words_title = unsigned_title.split()
    words_file = unsigned_filename.split()
    
    set_title = set(words_title)
    set_file = set(words_file)
    
    intersection = set_title.intersection(set_file)
    union = set_title.union(set_file)
    
    # Chỉ số Jaccard (Tỉ lệ từ trùng khớp trên tổng số từ)
    jaccard = (len(intersection) / len(union) * 100) if union else 0.0
    
    # Tỉ lệ bao phủ (Từ của tiêu đề nằm trong tên file hoặc ngược lại)
    contain_title = (len(intersection) / len(set_title) * 100) if set_title else 0.0
    contain_file = (len(intersection) / len(set_file) * 100) if set_file else 0.0
    best_containment = max(contain_title, contain_file)
    
    # Điểm kết hợp từ: Ưu tiên bao phủ hơn nhưng phạt nếu lệch quá nhiều từ khác biệt
    token_score = 0.4 * jaccard + 0.6 * best_containment
    
    # --- PHƯƠNG PHÁP 3: Containment Chuỗi con không dấu ---
    containment_score = 0.0
    if unsigned_title in unsigned_filename:
        containment_score = (len(unsigned_title) / len(unsigned_filename)) * 100
        # Đặt mức tối thiểu cho so khớp chứa con hợp lệ
        containment_score = max(containment_score, 80.0)
    elif unsigned_filename in unsigned_title:
        containment_score = (len(unsigned_filename) / len(unsigned_title)) * 100
        containment_score = max(containment_score, 80.0)
        
    # --- PHƯƠNG PHÁP 4: Khớp tuyệt đối ---
    if unsigned_title == unsigned_filename:
        return 100.0
        
    # Lấy điểm cao nhất trong các phương pháp so khớp
    final_score = max(best_char_ratio, token_score, containment_score)
    return round(final_score, 1)


def match_title_to_file(title, video_files, threshold=DEFAULT_MATCH_THRESHOLD):
    """
    Tìm file video khớp nhất với tiêu đề cho trước.
    
    Args:
        title (str): Tiêu đề cần tìm.
        video_files (list[dict]): Danh sách video files từ scanner.
        threshold (int): Ngưỡng tối thiểu để coi là khớp (0-100).
        
    Returns:
        tuple: (matched_file_dict, similarity_score) hoặc (None, 0) nếu không tìm thấy.
    """
    best_match = None
    best_score = 0.0
    
    for video in video_files:
        score = calculate_similarity(title, video['name_no_ext'])
        if score > best_score:
            best_score = score
            best_match = video
    
    if best_score >= threshold:
        return best_match, best_score
    
    return None, best_score


def match_all_titles(titles, video_files, threshold=DEFAULT_MATCH_THRESHOLD):
    """
    Đối chiếu toàn bộ danh sách tiêu đề với các file video.
    
    Mỗi file video chỉ được match với 1 tiêu đề (tiêu đề xuất hiện trước
    trong danh sách có ưu tiên cao hơn).
    
    Args:
        titles (list[str]): Danh sách tiêu đề (theo thứ tự).
        video_files (list[dict]): Danh sách video files từ scanner.
        threshold (int): Ngưỡng tối thiểu (0-100).
        
    Returns:
        list[dict]: Kết quả matching cho mỗi tiêu đề:
            - 'index': Số thứ tự (bắt đầu từ 0)
            - 'title': Tiêu đề gốc
            - 'matched_file': dict video file hoặc None
            - 'score': Điểm tương đồng
            - 'status': 'matched' | 'no_match'
    """
    results = []
    used_files = set()  # Tập hợp các file đã được match
    
    for idx, title in enumerate(titles):
        title = title.strip()
        if not title:
            continue
        
        # Lọc ra các file chưa được sử dụng
        available_files = [
            v for v in video_files 
            if v['path'] not in used_files
        ]
        
        matched_file, score = match_title_to_file(title, available_files, threshold)
        
        if matched_file:
            used_files.add(matched_file['path'])
            results.append({
                'index': idx,
                'title': title,
                'matched_file': matched_file,
                'score': score,
                'status': 'matched',
            })
        else:
            results.append({
                'index': idx,
                'title': title,
                'matched_file': None,
                'score': score,
                'status': 'no_match',
            })
    
    return results

