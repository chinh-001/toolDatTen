"""
Clipboard Formatter - Format dữ liệu highlight để copy vào clipboard.
Hỗ trợ dán vào Google Sheets / Excel với 3 cột riêng biệt:
Cột 1: Tiêu đề video
Cột 2: Link video
Cột 3: Đoạn Highlight của link đó
"""

from core.highlight_api import calculate_total_highlight_duration


def format_duration_friendly(total_seconds):
    """
    Format số giây thành chuỗi thời lượng dễ đọc.
    
    Args:
        total_seconds (float): Tổng số giây.
        
    Returns:
        str: Chuỗi dạng '1 phút 30 giây', '45 giây', '2 phút 0 giây'...
    """
    if total_seconds <= 0:
        return "0 giây"
    
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)
    
    if minutes > 0:
        return f"{minutes} phút {seconds} giây"
    return f"{seconds} giây"


def format_for_spreadsheet(items, filter_func=None, include_empty=True):
    """
    Format danh sách items thành chuỗi tab-separated 3 cột để dán vào Excel/Sheets.
    
    Cột 1: Tiêu đề video
    Cột 2: Link video (URL)
    Cột 3: Đoạn Highlight của link đó
    
    Args:
        items (list[dict]): Danh sách items từ bảng kết quả.
            Mỗi item cần có: 'title', 'url', 'highlight', 'status'.
        filter_func (callable, optional): Hàm lọc items. 
            Nhận 1 item dict, trả về True nếu muốn giữ lại.
        include_empty (bool): Nếu True, xuất tất cả dòng dù highlight rỗng để khớp hàng Excel.
    
    Returns:
        tuple: (str, int) -> (Chuỗi clipboard 3 cột, Số dòng đã format)
    """
    output_lines = []
    
    for item in items:
        # Áp dụng filter nếu có
        if filter_func and not filter_func(item):
            continue
            
        highlight_val = item.get('highlight', '')
        if not include_empty and not highlight_val:
            continue
        
        title = item.get('title', '')
        url = item.get('url', '')
        
        # Tab-separated 3 cột: Title \t URL \t Highlight
        output_lines.append(f"{title}\t{url}\t{highlight_val}")
    
    clipboard_text = "\n".join(output_lines)
    return clipboard_text, len(output_lines)


def format_single_for_spreadsheet(item_or_items):
    """
    Format 1 item hoặc danh sách items thành chuỗi tab-separated 3 cột.
    
    Args:
        item_or_items (dict hoặc list[dict]): Item hoặc danh sách items từ bảng kết quả.
    
    Returns:
        str: Chuỗi tab-separated 3 cột (Title \t URL \t Highlight).
    """
    if isinstance(item_or_items, list):
        lines = []
        for item in item_or_items:
            title = item.get('title', '')
            url = item.get('url', '')
            highlight_val = item.get('highlight', '')
            lines.append(f"{title}\t{url}\t{highlight_val}")
        return "\n".join(lines)
    elif isinstance(item_or_items, dict):
        title = item_or_items.get('title', '')
        url = item_or_items.get('url', '')
        highlight_val = item_or_items.get('highlight', '')
        return f"{title}\t{url}\t{highlight_val}"
    return ""

