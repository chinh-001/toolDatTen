"""
Highlight Duration Calculator Core Module - Module xử lý tính toán thời lượng highlight.

Chức năng chính:
1. Phân tách dữ liệu thô 3 cột (Tiêu đề, Link video, Highlight timestamps).
2. Trích xuất và chuẩn hóa các mốc thời gian highlight.
3. Tính toán tổng thời lượng highlight (tính bằng giây và chuỗi định dạng phút:giây).
4. Phân loại và lọc danh sách video theo ngưỡng thời lượng tùy chỉnh (dưới ngưỡng = màu xanh, trên ngưỡng = màu đỏ).
5. Xuất dữ liệu ra định dạng TSV/CSV phục vụ sao chép dán vào Excel / Google Sheets.
"""

import re
import csv
import io


def parse_time_to_seconds(time_str):
    """
    Chuyển đổi chuỗi thời gian (H:MM:SS, MM:SS hoặc SS) thành số giây.
    
    Args:
        time_str (str): Chuỗi thời gian (ví dụ: '01:25', '01:20:15', '45').
        
    Returns:
        float: Số giây tương ứng, hoặc 0.0 nếu không hợp lệ.
    """
    if not time_str:
        return 0.0
        
    clean = time_str.strip().replace(' ', '')
    parts = clean.split(':')
    try:
        if len(parts) == 3:  # H:MM:SS
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:  # MM:SS
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 1:  # SS
            return float(parts[0])
    except (ValueError, TypeError):
        pass
    return 0.0


def format_duration_str(seconds):
    """
    Định dạng số giây thành chuỗi thời lượng dễ đọc (vd: 90 -> '01m 30s', 3665 -> '01h 01m 05s').
    
    Args:
        seconds (float/int): Số giây.
        
    Returns:
        str: Chuỗi thời lượng đã định dạng.
    """
    sec = int(round(seconds))
    if sec <= 0:
        return "00m 00s"
        
    hours = sec // 3600
    minutes = (sec % 3600) // 60
    secs = sec % 60
    
    if hours > 0:
        return f"{hours:02d}h {minutes:02d}m {secs:02d}s"
    return f"{minutes:02d}m {secs:02d}s"


def pad_ts(seconds):
    """Định dạng số giây thành MM:SS chuẩn."""
    sec = int(round(seconds))
    m = sec // 60
    s = sec % 60
    return f"{m:02d}:{s:02d}"


def parse_highlight_segments(highlight_text):
    """
    Trích xuất danh sách các đoạn highlight và tính toán chuẩn xác tổng thời lượng.
    
    Hỗ trợ nhiều định dạng:
    - Định dạng chuẩn Gemini API: "03:12,03:27;00:26,00:35;00:49,01:03"
    - Ranges nối dấu gạch ngang/mũi tên: "00:12-00:45, 01:10-02:30", "0:12 to 0:45"
    - Xuống dòng hoặc phân cách dấu gạch đứng |
    
    Args:
        highlight_text (str): Chuỗi highlight thô từ cột 3.
        
    Returns:
        dict: {
            'total_seconds': float,
            'duration_formatted': str,
            'segment_count': int,
            'segments': list[tuple(start_sec, end_sec, segment_sec)],
            'cleaned_str': str
        }
    """
    if not highlight_text or not str(highlight_text).strip():
        return {
            'total_seconds': 0.0,
            'duration_formatted': "00m 00s",
            'segment_count': 0,
            'segments': [],
            'cleaned_str': ""
        }
        
    text = str(highlight_text).strip()
    
    # Loại bỏ code block markdown nếu có
    if "```" in text:
        lines = [line for line in text.split("\n") if not line.strip().startswith("```")]
        text = "\n".join(lines)
        
    # Xóa quotes và ký tự rác bao quanh
    text = text.replace('"', '').replace("'", '').replace('[', '').replace(']', '')

    segments = []
    cleaned_pairs = []

    # Regex nhận diện mốc thời gian dạng MM:SS hoặc H:MM:SS
    ts_pattern = r'\b(?:\d{1,2}:)?\d{1,2}:\d{2}\b'

    # Bước 1: Thử phân tách theo các dấu phân cách đoạn (dấu chấm phẩy ;, xuống dòng \n, dấu |)
    chunks = re.split(r'[;\n|]', text)
    
    for chunk in chunks:
        chunk_str = chunk.strip()
        if not chunk_str:
            continue
            
        times = re.findall(ts_pattern, chunk_str)
        if len(times) >= 2:
            for i in range(0, len(times) - 1, 2):
                t1_sec = parse_time_to_seconds(times[i])
                t2_sec = parse_time_to_seconds(times[i+1])
                start_sec = min(t1_sec, t2_sec)
                end_sec = max(t1_sec, t2_sec)
                dur = round(end_sec - start_sec, 2)
                segments.append((start_sec, end_sec, dur))
                cleaned_pairs.append(f"{pad_ts(start_sec)},{pad_ts(end_sec)}")

    # Bước 2: Fallback nếu không có dấu chấm phẩy ;, tìm tất cả các cặp timestamp theo range separator
    if not segments:
        text_norm = re.sub(
            r'(\d{1,2}:\d{1,2}(?::\d{2})?)\s*(?:[-–—~]|->|-->|to|đến|\s+)\s*(\d{1,2}:\d{1,2}(?::\d{2})?)',
            r'\1,\2', text
        )
        pair_pattern = r'(\d{1,2}:\d{1,2}(?::\d{2})?)\s*,\s*(\d{1,2}:\d{1,2}(?::\d{2})?)'
        matches = re.findall(pair_pattern, text_norm)
        
        for t1_str, t2_str in matches:
            t1_sec = parse_time_to_seconds(t1_str)
            t2_sec = parse_time_to_seconds(t2_str)
            start_sec = min(t1_sec, t2_sec)
            end_sec = max(t1_sec, t2_sec)
            dur = round(end_sec - start_sec, 2)
            segments.append((start_sec, end_sec, dur))
            cleaned_pairs.append(f"{pad_ts(start_sec)},{pad_ts(end_sec)}")

    total_seconds = sum(s[2] for s in segments)
    cleaned_str = ";".join(cleaned_pairs)
    
    return {
        'total_seconds': round(total_seconds, 2),
        'duration_formatted': format_duration_str(total_seconds),
        'segment_count': len(segments),
        'segments': segments,
        'cleaned_str': cleaned_str
    }


def clean_cell_text(val):
    """Dọn dẹp khoảng trắng và dấu ngoặc kép thừa của cell."""
    if not val:
        return ""
    text = str(val).strip()
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1].strip()
    return text


def parse_3column_line(line):
    """
    Phân tách một dòng text thành (title, url, highlight).
    
    Ưu tiên dấu Tab (\t) trước (khi copy từ Excel/Google Sheets).
    Sau đó thử dấu Pipe (|), CSV, hoặc regex trích URL.
    
    Args:
        line (str): Một dòng văn bản.
        
    Returns:
        tuple: (title, url, highlight)
    """
    line_str = line.strip()
    if not line_str:
        return "", "", ""
        
    # 1. Thử phân tách bằng TAB (\t)
    parts_tab = [clean_cell_text(p) for p in line_str.split('\t')]
    if len(parts_tab) >= 3:
        title = parts_tab[0]
        url = parts_tab[1]
        highlight = "\t".join(parts_tab[2:])
        return title, url, highlight
    elif len(parts_tab) == 2:
        return parts_tab[0], parts_tab[1], ""

    # 2. Thử phân tách bằng PIPE (|)
    parts_pipe = [clean_cell_text(p) for p in line_str.split('|')]
    if len(parts_pipe) >= 3:
        title = parts_pipe[0]
        url = parts_pipe[1]
        highlight = "|".join(parts_pipe[2:])
        return title, url, highlight

    # 3. Tìm URL trong dòng
    url_match = re.search(r'(https?://[^\s,;\t|"]+)', line_str, re.IGNORECASE)
    if url_match:
        url = url_match.group(1).strip()
        before_url = line_str[:url_match.start()].strip(' ,;|\t"')
        after_url = line_str[url_match.end():].strip(' ,;|\t"')
        
        title = clean_cell_text(before_url) if before_url else "Không có tiêu đề"
        highlight = clean_cell_text(after_url)
        return title, url, highlight

    # Fallback: Coi cả dòng là tiêu đề
    return clean_cell_text(line_str), "", ""


def parse_3column_input(raw_text):
    """
    Phân tách toàn bộ văn bản thô 3 cột thành danh sách các dictionary entries.
    
    Args:
        raw_text (str): Văn bản thô từ user paste vào.
        
    Returns:
        list[dict]: Danh sách chứa kết quả phân tích cho từng dòng.
    """
    if not raw_text or not raw_text.strip():
        return []
        
    lines = [line for line in raw_text.strip().splitlines() if line.strip()]
    if not lines:
        return []
        
    entries = []
    
    for idx, line in enumerate(lines):
        title, url, highlight_raw = parse_3column_line(line)
        
        # Tính toán thông số highlight
        hl_info = parse_highlight_segments(highlight_raw)
        
        entry = {
            'row_index': idx + 1,
            'title': title,
            'url': url,
            'highlight_raw': highlight_raw,
            'highlight_clean': hl_info['cleaned_str'],
            'total_seconds': hl_info['total_seconds'],
            'duration_formatted': hl_info['duration_formatted'],
            'segment_count': hl_info['segment_count'],
            'is_valid': bool(title or url or hl_info['segment_count'] > 0),
            'status_msg': "Thành công" if hl_info['segment_count'] > 0 else "Không tìm thấy highlight"
        }
        entries.append(entry)
        
    return entries


def filter_entries_by_duration(entries, threshold_sec):
    """
    Phân loại danh sách entries thành 2 mảng: Dưới ngưỡng và Trên ngưỡng.
    
    Args:
        entries (list[dict]): Danh sách kết quả từ parse_3column_input.
        threshold_sec (float/int): Ngưỡng thời lượng tính bằng giây.
        
    Returns:
        tuple: (short_entries, long_entries)
            - short_entries: Danh sách video có total_seconds < threshold_sec (Dưới ngưỡng - Màu Xanh)
            - long_entries: Danh sách video có total_seconds >= threshold_sec (Trên ngưỡng - Màu Đỏ)
    """
    short_entries = []
    long_entries = []
    
    for item in entries:
        if item['total_seconds'] < threshold_sec:
            short_entries.append(item)
        else:
            long_entries.append(item)
            
    return short_entries, long_entries


def export_entries_to_tsv(entries):
    """
    Xuất danh sách entries thành chuỗi TSV (Tab-separated) chuẩn cho Excel.
    Cấu trúc cột: Tiêu đề \t Link \t Highlight \t Tổng thời lượng \t Số giây
    """
    output = io.StringIO()
    writer = csv.writer(output, delimiter='\t', lineterminator='\n')
    
    # Header
    writer.writerow(["Tiêu đề", "Link Video", "Highlight", "Tổng thời lượng", "Số giây"])
    
    for item in entries:
        writer.writerow([
            item['title'],
            item['url'],
            item['highlight_clean'] if item['highlight_clean'] else item['highlight_raw'],
            item['duration_formatted'],
            item['total_seconds']
        ])
        
    return output.getvalue()


def export_entries_to_csv(entries):
    """
    Xuất danh sách entries thành chuỗi CSV.
    """
    output = io.StringIO()
    writer = csv.writer(output, lineterminator='\n')
    
    # Header
    writer.writerow(["STT", "Tiêu đề", "Link Video", "Highlight", "Số đoạn", "Tổng thời lượng", "Số giây"])
    
    for idx, item in enumerate(entries, 1):
        writer.writerow([
            idx,
            item['title'],
            item['url'],
            item['highlight_clean'] if item['highlight_clean'] else item['highlight_raw'],
            item['segment_count'],
            item['duration_formatted'],
            item['total_seconds']
        ])
        
    return output.getvalue()
