"""
Parser module - Phân tách dữ liệu thô (tiêu đề + link video) từ input người dùng.

Hỗ trợ nhiều format:
- Tiêu đề và link trên cùng 1 dòng (phân cách bằng khoảng trắng, tab, |)
- Tiêu đề và link xen kẽ trên các dòng riêng
- Chỉ có link (không có tiêu đề)
"""

import re


# Regex nhận diện URL
_URL_PATTERN = re.compile(
    r'(https?://[^\s\t|,]+)',
    re.IGNORECASE
)


def _is_url(text):
    """
    Kiểm tra text có phải URL không.

    Args:
        text (str): Text cần kiểm tra.

    Returns:
        bool: True nếu text là URL.
    """
    return bool(_URL_PATTERN.fullmatch(text.strip()))


def _extract_url_from_line(line):
    """
    Trích xuất URL từ một dòng text.

    Args:
        line (str): Dòng text.

    Returns:
        tuple: (url, remaining_text) hoặc (None, line) nếu không tìm thấy.
    """
    match = _URL_PATTERN.search(line)
    if not match:
        return None, line.strip()

    url = match.group(1).strip()
    # Phần còn lại sau khi bỏ URL
    remaining = line[:match.start()] + line[match.end():]
    # Dọn dẹp ký tự phân cách thừa
    remaining = re.sub(r'[|\t]', ' ', remaining)
    remaining = re.sub(r'\s+', ' ', remaining).strip()

    return url, remaining


def parse_raw_input(raw_text):
    """
    Phân tách text thô thành danh sách {title, url}.

    Xử lý thông minh nhiều format input:
    1. Cùng 1 dòng: "Tiêu đề https://link..."
    2. Cùng 1 dòng: "https://link... Tiêu đề"
    3. Xen kẽ dòng: dòng lẻ = tiêu đề, dòng chẵn = link
    4. Phân cách tab/pipe: "Tiêu đề | https://link..."

    Args:
        raw_text (str): Text thô từ user paste vào.

    Returns:
        list[dict]: Danh sách entries, mỗi entry gồm:
            - 'title' (str): Tiêu đề video (có thể rỗng nếu không tìm được)
            - 'url' (str): URL video
            - 'index' (int): Số thứ tự (bắt đầu từ 0)
    """
    if not raw_text or not raw_text.strip():
        return []

    lines = [line.strip() for line in raw_text.strip().split('\n')]
    lines = [line for line in lines if line]  # Bỏ dòng trống

    if not lines:
        return []

    entries = []

    # Thử phân tách: mỗi dòng chứa cả title + URL
    same_line_entries = _try_parse_same_line(lines)
    if same_line_entries:
        entries = same_line_entries
    else:
        # Thử phân tách: xen kẽ dòng (title, url, title, url...)
        entries = _try_parse_alternating(lines)

    # Gán index
    for i, entry in enumerate(entries):
        entry['index'] = i

    return entries


def _try_parse_same_line(lines):
    """
    Thử phân tách khi mỗi dòng chứa cả title lẫn URL.

    Returns:
        list[dict] hoặc None nếu format không phù hợp.
    """
    entries = []
    lines_with_url = 0

    for line in lines:
        url, title = _extract_url_from_line(line)
        if url:
            lines_with_url += 1
            entries.append({
                'title': title if title else _title_from_url(url),
                'url': url,
            })

    # Nếu >= 50% dòng có URL → coi là format same-line
    if lines_with_url >= len(lines) * 0.5:
        return entries

    return None


def _try_parse_alternating(lines):
    """
    Thử phân tách khi title và URL nằm trên các dòng xen kẽ.

    Returns:
        list[dict]: Danh sách entries.
    """
    entries = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if _is_url(line):
            # Dòng hiện tại là URL, không có title riêng
            entries.append({
                'title': _title_from_url(line.strip()),
                'url': line.strip(),
            })
            i += 1
        else:
            # Dòng hiện tại có thể là title
            title = line
            url = ''

            # Kiểm tra dòng tiếp theo có phải URL không
            if i + 1 < len(lines) and _is_url(lines[i + 1]):
                url = lines[i + 1].strip()
                i += 2
            else:
                # Không có URL đi kèm, thử extract từ chính dòng này
                extracted_url, remaining = _extract_url_from_line(line)
                if extracted_url:
                    url = extracted_url
                    title = remaining if remaining else _title_from_url(url)
                i += 1

            if url:
                entries.append({
                    'title': title,
                    'url': url,
                })

    return entries


def _title_from_url(url):
    """
    Tạo title fallback từ URL (lấy phần cuối URL).

    Args:
        url (str): URL video.

    Returns:
        str: Title rút gọn.
    """
    # Lấy phần cuối URL bỏ query params
    path = url.split('?')[0].split('#')[0]
    parts = path.rstrip('/').split('/')
    if parts:
        return parts[-1][:60]
    return url[:60]


def sort_entries(entries, key='title', reverse=False):
    """
    Sắp xếp danh sách entries.

    Args:
        entries (list[dict]): Danh sách entries từ parse_raw_input().
        key (str): Trường để sắp xếp ('title', 'url', 'index').
        reverse (bool): Sắp xếp ngược nếu True.

    Returns:
        list[dict]: Danh sách đã sắp xếp (với index được cập nhật lại).
    """
    sorted_entries = sorted(entries, key=lambda x: x.get(key, '').lower(), reverse=reverse)

    # Cập nhật lại index
    for i, entry in enumerate(sorted_entries):
        entry['index'] = i

    return sorted_entries
