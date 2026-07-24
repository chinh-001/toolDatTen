"""
Highlight Splitter Core Module - Module xử lý phân tách và cắt gọt các đoạn highlight video quá dài.

Chức năng chính:
1. Trích xuất đúng 1 dòng highlight duy nhất (độ dài 60s - 90s / 1p - 1p30s) cho mỗi video đầu vào (mode='single').
2. Giới hạn thời lượng tối đa của MỖI PHÂN ĐOẠN (segment) không quá max_segment_sec (mặc định 8 giây) giúp người xem không bị nhàm chán.
3. Phân tách danh sách segment thời gian highlight thành nhiều Phần (Part X/Y) nếu người dùng chọn mode='split'.
4. Xuất dữ liệu highlight đã cắt ra định dạng TSV/CSV phục vụ copy vào Excel.
"""

import math
import csv
import io
from core.highlight_duration_calculator import (
    parse_highlight_segments,
    format_duration_str,
    pad_ts,
)


def slice_segments_by_max_len(segments, max_segment_sec=8.0):
    """
    Cắt nhỏ từng mốc segment nếu thời lượng của nó lớn hơn max_segment_sec (mặc định 8 giây).

    Ví dụ: Segment (00:10, 00:40) = 30s với max_segment_sec = 8s sẽ được chia thành:
    - (00:10, 00:18, 8s)
    - (00:18, 00:26, 8s)
    - (00:26, 00:34, 8s)
    - (00:34, 00:40, 6s)

    Args:
        segments (list[tuple]): Danh sách (start_sec, end_sec, dur_sec).
        max_segment_sec (float): Giới hạn tối đa cho 1 phân đoạn (giây). Nếu <= 0 thì giữ nguyên.

    Returns:
        list[tuple]: Danh sách các phân đoạn đã được cắt nhỏ (tối đa max_segment_sec mỗi phân đoạn).
    """
    if not segments or not max_segment_sec or max_segment_sec <= 0:
        return list(segments)

    sliced = []
    for s, e, d in segments:
        s_flt = float(s)
        e_flt = float(e)
        d_flt = float(d)

        if d_flt <= max_segment_sec:
            sliced.append((round(s_flt, 2), round(e_flt, 2), round(d_flt, 2)))
        else:
            s_curr = s_flt
            while s_curr < e_flt:
                s_next = min(e_flt, round(s_curr + max_segment_sec, 2))
                dur = round(s_next - s_curr, 2)
                if dur > 0.01:
                    sliced.append((round(s_curr, 2), round(s_next, 2), dur))
                s_curr = s_next

    return sliced


def expand_segments_to_min_target(work_segments, min_target_sec, max_segment_sec=8.0):
    """
    Nới rộng các mốc phân đoạn để tổng thời lượng đạt tối thiểu min_target_sec.
    Ưu tiên nới các phân đoạn hiện có up to max_segment_sec, sau đó nới phân đoạn cuối cùng nếu cần.
    """
    if not work_segments:
        return work_segments

    total_seconds = sum(s[2] for s in work_segments)
    needed = round(min_target_sec - total_seconds, 2)
    if needed <= 0:
        return work_segments

    expanded = list(work_segments)

    # Bước 1: Thử nới rộng các segment hiện có chưa đạt max_segment_sec
    if max_segment_sec and max_segment_sec > 0:
        for i in range(len(expanded)):
            if needed <= 0.01:
                break
            s, e, d = expanded[i]
            cap = max_segment_sec - d
            if cap > 0:
                add = min(needed, cap)
                expanded[i] = (s, round(e + add, 2), round(d + add, 2))
                needed = round(needed - add, 2)

    # Bước 2: Nếu vẫn còn thiếu (chưa đạt min_target_sec), nới rộng phân đoạn cuối cùng
    if needed > 0.01:
        s, e, d = expanded[-1]
        expanded[-1] = (s, round(e + needed, 2), round(d + needed, 2))

    return expanded


def trim_to_single_highlight(segments, min_target_sec=60.0, max_target_sec=90.0, max_segment_sec=8.0):
    """
    Trích xuất và cắt đúng 1 chuỗi highlight duy nhất cho 1 video sao cho:
    - Mỗi phân đoạn nhỏ không vượt quá max_segment_sec (mặc định 8 giây).
    - Tổng thời lượng nằm trong khoảng [min_target_sec, max_target_sec] (mặc định 60s - 90s).

    Args:
        segments (list[tuple]): Danh sách các mốc (start_sec, end_sec, dur_sec).
        min_target_sec (float): Thời lượng tối thiểu (giây), mặc định 60.0 (1 phút).
        max_target_sec (float): Thời lượng tối đa (giây), mặc định 90.0 (1 phút 30 giây).
        max_segment_sec (float): Giới hạn độ dài tối đa mỗi mốc (giây), mặc định 8.0s.

    Returns:
        dict: Chứa thông tin chuỗi highlight đã cắt duy nhất.
    """
    if not segments:
        return {
            'chunk_index': 1,
            'segments': [],
            'total_seconds': 0.0,
            'duration_formatted': "00m 00s",
            'cleaned_str': ""
        }

    # Cắt nhỏ từng phân đoạn nếu dài hơn max_segment_sec (8s)
    work_segments = slice_segments_by_max_len(segments, max_segment_sec=max_segment_sec)
    total_seconds = sum(s[2] for s in work_segments)

    # Nếu tổng thời lượng < min_target_sec, nới rộng mốc để đạt min_target_sec
    if total_seconds < min_target_sec and work_segments:
        work_segments = expand_segments_to_min_target(work_segments, min_target_sec, max_segment_sec)
        total_seconds = sum(s[2] for s in work_segments)

    # Nếu tổng thời lượng đã <= max_target_sec, giữ các segment đã được nới đủ min_target_sec
    if total_seconds <= max_target_sec:
        cleaned_pairs = [f"{pad_ts(s[0])},{pad_ts(s[1])}" for s in work_segments]
        return {
            'chunk_index': 1,
            'segments': work_segments,
            'total_seconds': round(total_seconds, 2),
            'duration_formatted': format_duration_str(total_seconds),
            'cleaned_str': ";".join(cleaned_pairs)
        }

    selected_segs = []
    current_dur = 0.0

    for s, e, d in work_segments:
        s_flt, e_flt, d_flt = float(s), float(e), float(d)

        if current_dur + d_flt <= max_target_sec:
            selected_segs.append((round(s_flt, 2), round(e_flt, 2), round(d_flt, 2)))
            current_dur += d_flt
            if current_dur >= min_target_sec:
                break
        elif current_dur >= min_target_sec:
            break
        else:
            needed = min(max_target_sec - current_dur, max_target_sec)
            if needed > 0.01:
                mid = round(s_flt + needed, 2)
                d1 = round(needed, 2)
                selected_segs.append((round(s_flt, 2), mid, d1))
                current_dur += d1
            break

    c_dur = sum(s[2] for s in selected_segs)
    if c_dur < min_target_sec and selected_segs:
        selected_segs = expand_segments_to_min_target(selected_segs, min_target_sec, max_segment_sec)
        c_dur = sum(s[2] for s in selected_segs)

    cleaned_pairs = [f"{pad_ts(s[0])},{pad_ts(s[1])}" for s in selected_segs]

    return {
        'chunk_index': 1,
        'segments': selected_segs,
        'total_seconds': round(c_dur, 2),
        'duration_formatted': format_duration_str(c_dur),
        'cleaned_str': ";".join(cleaned_pairs)
    }


def split_highlight_segments(segments, min_target_sec=60.0, max_target_sec=90.0, max_segment_sec=8.0):
    """
    Phân tách danh sách các segment highlight thành nhiều phần (chunks)
    sao cho mỗi phân đoạn <= max_segment_sec (8s) và mỗi phần tổng [min_target_sec, max_target_sec].
    """
    if not segments:
        return []

    work_segments = slice_segments_by_max_len(segments, max_segment_sec=max_segment_sec)
    total_seconds = sum(s[2] for s in work_segments)

    if total_seconds <= max_target_sec:
        cleaned_pairs = [f"{pad_ts(s[0])},{pad_ts(s[1])}" for s in work_segments]
        return [{
            'chunk_index': 1,
            'segments': work_segments,
            'total_seconds': round(total_seconds, 2),
            'duration_formatted': format_duration_str(total_seconds),
            'cleaned_str': ";".join(cleaned_pairs)
        }]

    num_chunks = max(1, math.ceil(total_seconds / max_target_sec))
    ideal_target = total_seconds / num_chunks
    target_sec = max(min_target_sec, min(max_target_sec, ideal_target))

    chunks_result = []
    current_segs = []
    current_dur = 0.0

    queue = [[float(s[0]), float(s[1]), float(s[2])] for s in work_segments]

    while queue:
        s, e, d = queue.pop(0)

        if current_dur + d <= target_sec:
            current_segs.append((round(s, 2), round(e, 2), round(d, 2)))
            current_dur += d

        elif current_dur >= min_target_sec:
            chunks_result.append(current_segs)
            current_segs = []
            current_dur = 0.0
            queue.insert(0, [s, e, d])

        else:
            needed = target_sec - current_dur
            if needed <= 0:
                needed = max_target_sec - current_dur

            needed = min(needed, d)
            if needed > 0.01:
                mid = round(s + needed, 2)
                d1 = round(needed, 2)
                d2 = round(d - needed, 2)

                current_segs.append((round(s, 2), mid, d1))
                current_dur += d1

                chunks_result.append(current_segs)
                current_segs = []
                current_dur = 0.0

                if d2 > 0.01:
                    queue.insert(0, [mid, round(e, 2), d2])
            else:
                chunks_result.append(current_segs)
                current_segs = [(round(s, 2), round(e, 2), round(d, 2))]
                current_dur = d

    if current_segs:
        last_dur = sum(s[2] for s in current_segs)
        if chunks_result and last_dur < 15.0:
            prev_chunk_dur = sum(s[2] for s in chunks_result[-1])
            if prev_chunk_dur + last_dur <= max_target_sec + 5.0:
                chunks_result[-1].extend(current_segs)
            else:
                chunks_result.append(current_segs)
        else:
            chunks_result.append(current_segs)

    formatted_chunks = []
    for idx, c_segs in enumerate(chunks_result, 1):
        c_dur = sum(s[2] for s in c_segs)
        cleaned_pairs = [f"{pad_ts(s[0])},{pad_ts(s[1])}" for s in c_segs]
        formatted_chunks.append({
            'chunk_index': idx,
            'segments': c_segs,
            'total_seconds': round(c_dur, 2),
            'duration_formatted': format_duration_str(c_dur),
            'cleaned_str': ";".join(cleaned_pairs)
        })

    return formatted_chunks


def split_long_entry(entry, min_target_sec=60.0, max_target_sec=90.0, mode='single', max_segment_sec=8.0):
    """
    Xử lý một entry video đơn lẻ.

    Args:
        entry (dict): Entry kết quả từ parse_3column_input.
        min_target_sec (float): Thời lượng tối thiểu (giây).
        max_target_sec (float): Thời lượng tối đa (giây).
        mode (str): 'single' (1 dòng / video) hoặc 'split' (chia nhiều phần).
        max_segment_sec (float): Giới hạn thời lượng tối đa của MỖI PHÂN ĐOẠN (mặc định 8s).

    Returns:
        list[dict]: Danh sách sub-entries.
    """
    raw_hl = entry.get('highlight_raw', '')
    if not raw_hl and entry.get('highlight_clean'):
        raw_hl = entry.get('highlight_clean')

    parsed_hl = parse_highlight_segments(raw_hl)
    segments = parsed_hl['segments']

    base_title = entry.get('original_title', entry.get('title', 'Video'))
    url = entry.get('url', '')
    row_idx = entry.get('row_index', 0)
    orig_id = entry.get('_orig_id', row_idx)

    if not segments:
        empty_entry = dict(entry)
        empty_entry['_orig_id'] = orig_id
        empty_entry['original_title'] = base_title
        empty_entry['highlight_raw'] = raw_hl
        return [empty_entry]

    if mode == 'single':
        chunk = trim_to_single_highlight(
            segments,
            min_target_sec=min_target_sec,
            max_target_sec=max_target_sec,
            max_segment_sec=max_segment_sec
        )
        sub_entry = {
            '_orig_id': orig_id,
            'row_index': row_idx,
            'original_title': base_title,
            'title': base_title,
            'url': url,
            'highlight_raw': raw_hl,
            'highlight_clean': chunk['cleaned_str'],
            'total_seconds': chunk['total_seconds'],
            'duration_formatted': chunk['duration_formatted'],
            'segment_count': len(chunk['segments']),
            'part_index': 1,
            'total_parts': 1,
            'is_valid': True,
            'status_msg': f"Đã cắt 1 dòng ({chunk['duration_formatted']})"
        }
        return [sub_entry]

    # mode == 'split'
    chunks = split_highlight_segments(
        segments,
        min_target_sec=min_target_sec,
        max_target_sec=max_target_sec,
        max_segment_sec=max_segment_sec
    )
    total_parts = len(chunks)

    sub_entries = []
    for chunk in chunks:
        part_idx = chunk['chunk_index']
        title_with_part = f"{base_title} (Phần {part_idx}/{total_parts})" if total_parts > 1 else base_title

        sub_entry = {
            '_orig_id': orig_id,
            'row_index': row_idx,
            'original_title': base_title,
            'title': title_with_part,
            'url': url,
            'highlight_raw': raw_hl,
            'highlight_clean': chunk['cleaned_str'],
            'total_seconds': chunk['total_seconds'],
            'duration_formatted': chunk['duration_formatted'],
            'segment_count': len(chunk['segments']),
            'part_index': part_idx,
            'total_parts': total_parts,
            'is_valid': True,
            'status_msg': f"Phần {part_idx}/{total_parts}" if total_parts > 1 else "OK"
        }
        sub_entries.append(sub_entry)

    return sub_entries


def split_long_entries(entries, min_target_sec=60.0, max_target_sec=90.0, mode='single', max_segment_sec=8.0):
    """
    Xử lý hàng loạt danh sách video entries theo thời lượng thành phẩm tùy chọn.

    Args:
        entries (list[dict]): Danh sách video entries.
        min_target_sec (float): Thời lượng thành phẩm tối thiểu mong muốn (giây).
        max_target_sec (float): Thời lượng thành phẩm tối đa mong muốn (giây).
        mode (str): 'single' (trích 1 dòng duy nhất) hoặc 'split' (chia nhiều phần).
        max_segment_sec (float): Giới hạn độ dài tối đa của 1 mốc segment (giây).

    Returns:
        list[dict]: Danh sách video entries sau khi cắt gọt.
    """
    result = []
    for entry in entries:
        sub_list = split_long_entry(
            entry,
            min_target_sec=min_target_sec,
            max_target_sec=max_target_sec,
            mode=mode,
            max_segment_sec=max_segment_sec
        )
        result.extend(sub_list)
    return result


def export_split_entries_to_tsv(entries):
    """
    Xuất danh sách split entries thành chuỗi TSV (Tab-separated) chuẩn cho Excel.
    Cấu trúc cột: Tiêu đề \t Link Video \t Highlight Cắt \t Thời lượng \t Số giây
    """
    output = io.StringIO()
    writer = csv.writer(output, delimiter='\t', lineterminator='\n')

    # Header
    writer.writerow(["Tiêu đề", "Link Video", "Highlight Cắt", "Thời lượng", "Số giây"])

    for item in entries:
        writer.writerow([
            item['title'],
            item['url'],
            item['highlight_clean'],
            item['duration_formatted'],
            item['total_seconds']
        ])

    return output.getvalue()


def export_split_entries_to_csv(entries):
    """
    Xuất danh sách split entries thành chuỗi CSV.
    """
    output = io.StringIO()
    writer = csv.writer(output, lineterminator='\n')

    # Header
    writer.writerow(["STT", "Tiêu đề", "Link Video", "Highlight Cắt", "Số đoạn", "Thời lượng", "Số giây"])

    for idx, item in enumerate(entries, 1):
        writer.writerow([
            idx,
            item['title'],
            item['url'],
            item['highlight_clean'],
            item['segment_count'],
            item['duration_formatted'],
            item['total_seconds']
        ])

    return output.getvalue()
