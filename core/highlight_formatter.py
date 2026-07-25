"""
Highlight Formatter Core Module - Module xử lý trình bày và làm sạch dữ liệu Link Video & Highlight.

Chức năng chính:
1. Phân tách linh hoạt dữ liệu thô nhập vào (xen kẽ dòng, tab-separated từ Excel, hoặc hỗn hợp).
2. Làm sạch và tự động sửa các mốc timestamp dở dang (ví dụ: '48:' -> '48:00').
3. Tính toán chính xác thời lượng từng đoạn và tổng thời lượng highlight.
4. Trình bày dữ liệu theo cú pháp dạng văn bản chuẩn ([link video] \\n [highlight video]).
5. Trình bày dữ liệu dạng TSV / CSV chuẩn phục vụ copy-paste hoặc xuất file cho Google Sheets / Excel không bị lỗi.
"""

import re
import csv
import io


def parse_time_to_seconds(time_str):
    """
    Chuyển đổi chuỗi thời gian (H:MM:SS, MM:SS hoặc SS) thành số giây.
    """
    if not time_str:
        return 0.0
        
    clean = time_str.strip().replace(' ', '')
    parts = clean.split(':')
    try:
        if len(parts) == 3:  # H:MM:SS
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:  # MM:SS
            sec = float(parts[1]) if parts[1] else 0.0
            return int(parts[0]) * 60 + sec
        elif len(parts) == 1:  # SS
            return float(parts[0])
    except (ValueError, TypeError):
        pass
    return 0.0


def pad_ts(seconds):
    """
    Định dạng số giây thành MM:SS chuẩn (hoặc HH:MM:SS nếu >= 1 giờ).
    """
    sec = int(round(seconds))
    if sec < 0:
        sec = 0
    hours = sec // 3600
    minutes = (sec % 3600) // 60
    secs = sec % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_duration_str(seconds):
    """
    Định dạng số giây thành chuỗi thời lượng dễ đọc (vd: '01m 30s', '01h 05m 12s').
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


def repair_timestamp_token(ts_token):
    """
    Sửa lỗi các mốc thời gian timestamp đơn bị lỗi / dở dang.
    Ví dụ:
    - '48:' -> '48:00'
    - '5:'  -> '05:00'
    - '12:5' -> '12:05'
    
    Args:
        ts_token (str): Chuỗi mốc thời gian thô.
        
    Returns:
        tuple: (repaired_ts_str, was_repaired, warning_msg)
    """
    if not ts_token:
        return "", False, ""

    token = ts_token.strip()
    
    # Lỗi kết thúc bằng dấu hai chấm (ví dụ: '48:', '05:')
    if re.match(r'^\d{1,2}:$', token):
        repaired = token + "00"
        return repaired, True, f"Tự động sửa timestamp '{token}' thành '{repaired}'"
        
    # Lỗi chỉ có 1 chữ số sau dấu hai chấm (ví dụ: '12:5' -> '12:05')
    m = re.match(r'^(\d{1,2}):(\d)$', token)
    if m:
        repaired = f"{int(m.group(1)):02d}:0{m.group(2)}"
        return repaired, True, f"Tự động sửa timestamp '{token}' thành '{repaired}'"

    # Định dạng chuẩn H:MM:SS hoặc MM:SS
    m_full = re.match(r'^(?:(\d{1,2}):)?(\d{1,2}):(\d{1,2})$', token)
    if m_full:
        h, m_val, s_val = m_full.groups()
        if h is not None:
            repaired = f"{int(h):02d}:{int(m_val):02d}:{int(s_val):02d}"
        else:
            repaired = f"{int(m_val):02d}:{int(s_val):02d}"
        return repaired, False, ""

    return token, False, ""


def repair_and_clean_highlight(raw_highlight):
    """
    Làm sạch, phân tích và sửa lỗi toàn bộ chuỗi highlight.
    
    Xử lý:
    - Loại bỏ dấu câu rác ở đầu/cuối chuỗi.
    - Sửa lỗi timestamp dở dang như '48:' thành '48:00'.
    - Ghép các cặp start,end chuẩn mực phân cách bởi dấu phẩy và chấm phẩy.
    
    Args:
        raw_highlight (str): Chuỗi highlight thô.
        
    Returns:
        dict: {
            'cleaned_str': str,           # Chuỗi highlight sạch dạng MM:SS,MM:SS;MM:SS,MM:SS
            'total_seconds': float,       # Tổng số giây
            'duration_formatted': str,    # Thời lượng hiển thị
            'segment_count': int,         # Số lượng đoạn highlight
            'warnings': list[str]         # Cảnh báo sửa lỗi (nếu có)
        }
    """
    if not raw_highlight or not str(raw_highlight).strip():
        return {
            'cleaned_str': '',
            'total_seconds': 0.0,
            'duration_formatted': '00m 00s',
            'segment_count': 0,
            'warnings': []
        }

    text = str(raw_highlight).strip()
    
    # Loại bỏ code blocks markdown nếu có
    if "```" in text:
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = " ".join(lines)

    text = text.replace('"', '').replace("'", '').replace('[', '').replace(']', '')
    
    warnings = []
    
    # Pattern khớp các timestamp hoàn chỉnh (12:34) hoặc dở dang (48: hoặc 5:)
    ts_pattern = r'(?:\b\d{1,2}:)?\d{1,2}:(?:\d{2}|\b|(?=[,;\s]|$))'
    
    # Phân tách theo dấu chấm phẩy ;, xuống dòng \n, hoặc dấu pipe |
    chunks = re.split(r'[;\n|]', text)
    
    segments = []
    cleaned_pairs = []

    for chunk in chunks:
        chunk_str = chunk.strip()
        if not chunk_str:
            continue
            
        tokens = re.findall(ts_pattern, chunk_str)
        if not tokens:
            continue

        # Sửa từng token
        repaired_tokens = []
        for tok in tokens:
            rep, was_rep, msg = repair_timestamp_token(tok)
            repaired_tokens.append(rep)
            if was_rep and msg:
                warnings.append(msg)

        # Ghép cặp (start, end)
        if len(repaired_tokens) >= 2:
            for i in range(0, len(repaired_tokens) - 1, 2):
                t1_str = repaired_tokens[i]
                t2_str = repaired_tokens[i+1]
                t1_sec = parse_time_to_seconds(t1_str)
                t2_sec = parse_time_to_seconds(t2_str)
                
                start_sec = min(t1_sec, t2_sec)
                end_sec = max(t1_sec, t2_sec)
                dur = round(end_sec - start_sec, 2)

                segments.append((start_sec, end_sec, dur))
                cleaned_pairs.append(f"{pad_ts(start_sec)},{pad_ts(end_sec)}")
        elif len(repaired_tokens) == 1:
            warnings.append(f"Loại bỏ mốc thời gian lẻ không tạo thành cặp: '{repaired_tokens[0]}'")

    # Fallback nếu dùng range separator (- hoặc ,)
    if not segments:
        raw_pairs = re.split(r'[;\n|]', text)
        for p in raw_pairs:
            m = re.findall(r'((?:\d{1,2}:)?\d{1,2}:?\d{0,2})\s*[\s,–—~-]+\s*((?:\d{1,2}:)?\d{1,2}:?\d{0,2})', p)
            for t1_raw, t2_raw in m:
                t1_rep, w1, msg1 = repair_timestamp_token(t1_raw)
                t2_rep, w2, msg2 = repair_timestamp_token(t2_raw)
                if w1: warnings.append(msg1)
                if w2: warnings.append(msg2)
                
                t1_sec = parse_time_to_seconds(t1_rep)
                t2_sec = parse_time_to_seconds(t2_rep)
                start_sec = min(t1_sec, t2_sec)
                end_sec = max(t1_sec, t2_sec)
                dur = round(end_sec - start_sec, 2)
                
                segments.append((start_sec, end_sec, dur))
                cleaned_pairs.append(f"{pad_ts(start_sec)},{pad_ts(end_sec)}")

    total_seconds = sum(s[2] for s in segments)
    cleaned_str = ";".join(cleaned_pairs)

    return {
        'cleaned_str': cleaned_str,
        'total_seconds': round(total_seconds, 2),
        'duration_formatted': format_duration_str(total_seconds),
        'segment_count': len(segments),
        'warnings': warnings
    }


def _extract_url(text):
    """Trích xuất URL YouTube/Web từ text line."""
    m = re.search(r'(https?://[^\s\t|,"]+)', text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _is_highlight_line(line):
    """Kiểm tra một dòng text có chứa các mốc thời gian highlight hay không."""
    return bool(re.search(r'(?:\b\d{1,2}:)?\d{1,2}:', line))


def parse_link_highlight_input(raw_text):
    """
    Phân tách linh hoạt dữ liệu thô nhập vào thành danh sách entries chuẩn.
    
    Hỗ trợ các dạng input:
    1. Cụm 3 dòng: Dòng 1 Tiêu đề, Dòng 2 Link video, Dòng 3 Chuỗi highlight.
    2. Cụm 2 dòng: Dòng 1 Link video, Dòng 2 Chuỗi highlight.
    3. Tab-separated (từ Excel / Google Sheets): Cột 1 Tiêu đề (optional), Cột 2 Link, Cột 3 Highlight.
    """
    if not raw_text or not raw_text.strip():
        return []

    lines = [line.strip() for line in raw_text.strip().splitlines() if line.strip()]
    if not lines:
        return []

    entries = []

    # Bước 1: Thử kiểm tra phân tách dạng Tab-separated (từ Excel copy sang)
    has_tabs = any('\t' in line for line in lines)
    if has_tabs:
        for idx, line in enumerate(lines):
            parts = [p.strip().strip('"') for p in line.split('\t') if p.strip()]
            url = None
            highlight = ""
            title = ""
            
            for part in parts:
                extracted_url = _extract_url(part)
                if extracted_url:
                    url = extracted_url
                elif _is_highlight_line(part):
                    highlight = part
                else:
                    if not title:
                        title = part

            if url:
                hl_info = repair_and_clean_highlight(highlight)
                entries.append({
                    'index': len(entries) + 1,
                    'title': title if title else _title_from_url(url),
                    'url': url,
                    'highlight_raw': highlight,
                    'highlight_clean': hl_info['cleaned_str'],
                    'segment_count': hl_info['segment_count'],
                    'total_seconds': hl_info['total_seconds'],
                    'duration_formatted': hl_info['duration_formatted'],
                    'warnings': hl_info['warnings']
                })
        if entries:
            return entries

    # Bước 2: Phân tách dạng Dòng liên tiếp (Hỗ trợ 3 dòng: Title -> URL -> Highlight, hoặc 2 dòng: URL -> Highlight)
    i = 0
    while i < len(lines):
        line = lines[i]
        url = _extract_url(line)
        
        if url:
            # Tìm tiêu đề ở dòng ngay trước đó (nếu có và dòng trước đó không phải URL hay timestamp)
            title = ""
            if i > 0:
                prev_line = lines[i - 1]
                if not _extract_url(prev_line) and not _is_highlight_line(prev_line):
                    title = prev_line

            highlight_raw = ""
            # Kiểm tra dòng tiếp theo có phải highlight timestamp hay không
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if not _extract_url(next_line) and _is_highlight_line(next_line):
                    highlight_raw = next_line
                    i += 1
            
            hl_info = repair_and_clean_highlight(highlight_raw)
            entries.append({
                'index': len(entries) + 1,
                'title': title if title else _title_from_url(url),
                'url': url,
                'highlight_raw': highlight_raw,
                'highlight_clean': hl_info['cleaned_str'],
                'segment_count': hl_info['segment_count'],
                'total_seconds': hl_info['total_seconds'],
                'duration_formatted': hl_info['duration_formatted'],
                'warnings': hl_info['warnings']
            })
        i += 1

    return entries


def _title_from_url(url):
    """Tạo tiêu đề ngắn từ URL nếu không có tiêu đề thô."""
    path = url.split('?')[0].split('#')[0]
    parts = path.rstrip('/').split('/')
    if parts and parts[-1]:
        return parts[-1][:50]
    return url[:50]


def format_entries_to_text(entries):
    """
    Trình bày danh sách entries theo cú pháp văn bản chuẩn:
    [link video]
    [highlight video]
    
    (có khoảng trắng cách giữa các video)
    """
    if not entries:
        return ""

    blocks = []
    for entry in entries:
        url = entry.get('url', '').strip()
        hl = entry.get('highlight_clean', '').strip()
        if not hl:
            hl = entry.get('highlight_raw', '').strip()
        blocks.append(f"{url}\n{hl}")

    return "\n\n".join(blocks)


def format_entries_to_tsv(entries, num_cols=2, include_header=True):
    """
    Xuất danh sách entries thành dạng TSV (Tab-separated) chuẩn cho Excel / Google Sheets.
    num_cols:
      - 2: Link Video \t Highlight Video
      - 3: Tiêu đề \t Link Video \t Highlight Video
      - 5: Tiêu đề \t Link Video \t Highlight Video \t Số đoạn \t Tổng thời lượng
    """
    output = io.StringIO()
    writer = csv.writer(output, delimiter='\t', lineterminator='\n')
    
    if num_cols == 2:
        if include_header:
            writer.writerow(["Link Video", "Highlight Video"])
        for item in entries:
            hl = item['highlight_clean'] if item['highlight_clean'] else item['highlight_raw']
            writer.writerow([item['url'], hl])
    elif num_cols == 3:
        if include_header:
            writer.writerow(["Tiêu đề", "Link Video", "Highlight Video"])
        for item in entries:
            hl = item['highlight_clean'] if item['highlight_clean'] else item['highlight_raw']
            writer.writerow([item['title'], item['url'], hl])
    else:
        if include_header:
            writer.writerow(["Tiêu đề", "Link Video", "Highlight Video", "Số đoạn", "Tổng thời lượng"])
        for item in entries:
            hl = item['highlight_clean'] if item['highlight_clean'] else item['highlight_raw']
            writer.writerow([
                item['title'],
                item['url'],
                hl,
                item['segment_count'],
                item['duration_formatted']
            ])

    return output.getvalue()


def format_entries_to_csv(entries):
    """
    Xuất danh sách entries thành dạng CSV.
    """
    output = io.StringIO()
    writer = csv.writer(output, lineterminator='\n')
    
    writer.writerow(["STT", "Tiêu đề", "Link Video", "Highlight Video", "Số đoạn", "Tổng thời lượng", "Số giây"])
    for idx, item in enumerate(entries, 1):
        hl = item['highlight_clean'] if item['highlight_clean'] else item['highlight_raw']
        writer.writerow([
            idx,
            item['title'],
            item['url'],
            hl,
            item['segment_count'],
            item['duration_formatted'],
            item['total_seconds']
        ])

    return output.getvalue()
