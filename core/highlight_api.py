"""
Highlight API Module - Thực hiện gọi Gemini API bằng thư viện urllib built-in của Python.
Không cần cài đặt bất kỳ package ngoài nào (như requests hay google-generativeai).
"""

import re
import json
import urllib.request
import urllib.error
from utils.constants import GEMINI_API_BASE


def validate_api_key(api_key, model_id="gemini-2.0-flash"):
    """
    Kiểm tra API Key có hợp lệ không bằng cách gửi một request test nhỏ đến Gemini.

    Args:
        api_key (str): Google Gemini API Key.
        model_id (str): ID model Gemini để test.

    Returns:
        tuple: (bool, str, dict) -> (Thành công hay không, Thông báo chi tiết, Metadata chứa log dev)
    """
    error_meta = {"dev_log": ""}
    if not api_key or not api_key.strip():
        return False, "API Key không được để trống.", error_meta

    url = f"{GEMINI_API_BASE}/{model_id}:generateContent?key={api_key.strip()}"
    headers = {"Content-Type": "application/json"}
    
    # Payload cực nhỏ để test key nhanh
    data = {
        "contents": [{"parts": [{"text": "Hi"}]}],
        "generationConfig": {"maxOutputTokens": 5}
    }

    masked_key = api_key.strip()[:6] + "..." + api_key.strip()[-4:] if len(api_key.strip()) > 10 else api_key.strip()

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            if "candidates" in res_data:
                return True, "Kết nối Gemini API thành công!", error_meta
            
            dev_log = (
                f"--- Validate API Key Success but Response Format Mismatch ---\n"
                f"Model: {model_id}\n"
                f"API Key: {masked_key}\n"
                f"Response JSON:\n{json.dumps(res_data, indent=2, ensure_ascii=False)}\n"
                f"----------------------------------------------------------"
            )
            error_meta["dev_log"] = dev_log
            return False, "Phản hồi từ API không đúng định dạng mong đợi.", error_meta
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
            err_json = json.loads(err_body)
            error_msg = err_json.get("error", {}).get("message", str(e))
        except Exception:
            err_body = "N/A"
            error_msg = str(e)
            
        dev_log = (
            f"--- Gemini API HTTP Error ({e.code}) ---\n"
            f"Model: {model_id}\n"
            f"API Key: {masked_key}\n"
            f"Request URL: {GEMINI_API_BASE}/{model_id}:generateContent?key={masked_key}\n"
            f"Error Code: {e.code}\n"
            f"Error Reason: {e.reason}\n"
            f"Response Body:\n{err_body}\n"
            f"----------------------------------------"
        )
        error_meta["dev_log"] = dev_log
        return False, f"Lỗi API ({e.code}): {error_msg}", error_meta
    except urllib.error.URLError as e:
        dev_log = (
            f"--- Network Connection Error ---\n"
            f"Model: {model_id}\n"
            f"API Key: {masked_key}\n"
            f"Reason: {e.reason}\n"
            f"Check your internet connection or proxy settings.\n"
            f"--------------------------------"
        )
        error_meta["dev_log"] = dev_log
        return False, f"Lỗi kết nối mạng: {e.reason}", error_meta
    except Exception as e:
        import traceback
        dev_log = (
            f"--- Unexpected Exception in Validate API Key ---\n"
            f"Model: {model_id}\n"
            f"API Key: {masked_key}\n"
            f"Exception: {type(e).__name__}: {str(e)}\n"
            f"Traceback:\n{traceback.format_exc()}\n"
            f"-------------------------------------------------"
        )
        error_meta["dev_log"] = dev_log
        return False, f"Lỗi không xác định: {str(e)}", error_meta


def extract_highlights(title, url, prompt_template, api_key, model_id="gemini-2.0-flash"):
    """
    Gửi request tới Gemini API để trích xuất highlight của 1 video.

    Args:
        title (str): Tiêu đề video.
        url (str): Link video.
        prompt_template (str): Template prompt chứa {title} và {url}.
        api_key (str): Gemini API Key.
        model_id (str): ID model Gemini (ví dụ: 'gemini-2.0-flash').

    Returns:
        tuple: (str, bool, dict) -> (Kết quả/lỗi, Thành công?, Metadata lỗi)
            Metadata chứa: is_rate_limit, retry_after_seconds, dev_log
    """
    error_meta = {"is_rate_limit": False, "retry_after_seconds": 0, "dev_log": ""}
    
    if not api_key or not api_key.strip():
        error_meta["dev_log"] = "--- API Key Error ---\nAPI Key is empty or whitespace.\n---------------------"
        return "Thiếu API Key", False, error_meta

    # Điền thông tin video vào template prompt
    # Nếu prompt của người dùng bị thiếu placeholders {title} hoặc {url},
    # tự động bổ sung vào cuối để tránh việc AI không nhận được thông tin video.
    temp_template = prompt_template
    if "{title}" not in temp_template:
        temp_template += "\n\nTiêu đề video: {title}"
    if "{url}" not in temp_template:
        temp_template += "\nLink video: {url}"

    try:
        prompt = temp_template.format(title=title, url=url)
    except Exception as e:
        dev_log = (
            f"--- Prompt Format Exception ---\n"
            f"Failed to format prompt template with title and url.\n"
            f"Prompt Template: {prompt_template}\n"
            f"Exception: {type(e).__name__}: {str(e)}\n"
            f"-------------------------------"
        )
        error_meta["dev_log"] = dev_log
        return f"Lỗi định dạng prompt", False, error_meta

    api_url = f"{GEMINI_API_BASE}/{model_id}:generateContent?key={api_key.strip()}"
    headers = {"Content-Type": "application/json"}
    
    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2,  # Thấp để đảm bảo kết quả chính xác theo format
        }
    }

    masked_key = api_key.strip()[:6] + "..." + api_key.strip()[-4:] if len(api_key.strip()) > 10 else api_key.strip()

    try:
        req = urllib.request.Request(
            api_url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            
            # Trích xuất text trả về từ Gemini JSON structure
            candidates = res_data.get("candidates", [])
            if not candidates:
                dev_log = (
                    f"--- Gemini API Empty Response ---\n"
                    f"Model: {model_id}\n"
                    f"API Key: {masked_key}\n"
                    f"Response JSON:\n{json.dumps(res_data, indent=2, ensure_ascii=False)}\n"
                    f"---------------------------------"
                )
                error_meta["dev_log"] = dev_log
                return "API không trả về kết quả nào.", False, error_meta
                
            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            
            # Kiểm tra từ chối hoặc báo không xem được video
            rejection_keywords = [
                "không thể xem video", "không thể truy cập video", "không tìm thấy video",
                "không có video đính kèm", "không mở được link", "tự sáng tạo", "mốc thời gian giả lập"
            ]
            text_lower = text.lower()
            for kw in rejection_keywords:
                if kw in text_lower:
                    dev_log = f"--- Rejection Detected in API Response ---\nFound keyword: '{kw}' in response text:\n{text}\n------------------------------------------"
                    error_meta["dev_log"] = dev_log
                    return f"AI từ chối hoặc không xem được video: {kw}", False, error_meta

            cleaned_text = _clean_timestamps(text)
            
            if cleaned_text:
                return cleaned_text, True, error_meta
            else:
                raw_preview = text.strip()[:500] + ("..." if len(text) > 500 else "")
                dev_log = (
                    f"--- Format Validation Error ---\n"
                    f"Model: {model_id}\n"
                    f"API Key: {masked_key}\n"
                    f"AI successfully responded, but output did not match the expected pattern.\n"
                    f"Expected format: MM:SS,MM:SS;MM:SS,MM:SS;...\n"
                    f"Raw Response Content:\n{raw_preview}\n"
                    f"-------------------------------"
                )
                error_meta["dev_log"] = dev_log
                return f"Định dạng trả về không khớp yêu cầu: {text.strip()[:100]}...", False, error_meta
                
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
            err_json = json.loads(err_body)
            error_msg = err_json.get("error", {}).get("message", str(e))
        except Exception:
            err_body = "N/A"
            err_json = {}
            error_msg = str(e)
        
        # Phân tích lỗi rate limit
        if e.code == 429:
            error_meta["is_rate_limit"] = True
            # Mặc định
            error_meta["is_daily_quota"] = False
            error_meta["retry_after_seconds"] = 60
            
            # Trích xuất thông tin chi tiết từ structured error response
            error_details = err_json.get("error", {}).get("details", [])
            
            # Bước 1: Phát hiện loại quota bị vượt (daily vs per-minute) TRƯỚC
            for detail in error_details:
                detail_type = detail.get("@type", "")
                if "QuotaFailure" in detail_type:
                    violations = detail.get("violations", [])
                    for violation in violations:
                        quota_id = violation.get("quotaId", "")
                        if "PerDay" in quota_id:
                            error_meta["is_daily_quota"] = True
                            # Khi hết quota ngày, đặt retry rất lâu cho key+model này
                            error_meta["retry_after_seconds"] = 86400  # 24 giờ
                            break
            
            # Bước 2: Trích xuất retryDelay từ RetryInfo (CHỈ khi KHÔNG phải daily quota)
            # Vì API trả về retryDelay = "6s" cho daily quota nhưng thực tế phải chờ 24h
            if not error_meta["is_daily_quota"]:
                for detail in error_details:
                    detail_type = detail.get("@type", "")
                    if "RetryInfo" in detail_type:
                        retry_delay_str = detail.get("retryDelay", "")
                        # Parse "6s", "60s", "120s" etc.
                        delay_match = re.search(r'([\d.]+)s', retry_delay_str)
                        if delay_match:
                            try:
                                error_meta["retry_after_seconds"] = float(delay_match.group(1))
                            except ValueError:
                                pass
            
            # Fallback: parse retry_after từ error message text nếu chưa có từ RetryInfo
            if error_meta["retry_after_seconds"] == 60 and not error_details:
                retry_match = re.search(
                    r'retry\s+(?:in|after)\s+([\d.]+)\s*(?:s|second|giây)?',
                    error_msg, re.IGNORECASE
                )
                if retry_match:
                    try:
                        error_meta["retry_after_seconds"] = float(retry_match.group(1))
                    except ValueError:
                        pass
        
        # Phát hiện model không khả dụng/không tồn tại/không được phép sử dụng
        error_meta["is_model_unavailable"] = False
        err_msg_lower = error_msg.lower()
        if (e.code in (400, 403, 404) and 
            ("not available" in err_msg_lower or 
             "no longer available" in err_msg_lower or 
             "not found" in err_msg_lower or 
             "unrecognized" in err_msg_lower or 
             "invalid model" in err_msg_lower)):
            error_meta["is_model_unavailable"] = True
        
        dev_log = (
            f"--- Gemini API HTTP Error ({e.code}) ---\n"
            f"Model: {model_id}\n"
            f"API Key: {masked_key}\n"
            f"Request URL: {GEMINI_API_BASE}/{model_id}:generateContent?key={masked_key}\n"
            f"Error Code: {e.code}\n"
            f"Error Reason: {e.reason}\n"
            f"Response Body:\n{err_body}\n"
            f"----------------------------------------"
        )
        error_meta["dev_log"] = dev_log
        return f"Lỗi API ({e.code}): {error_msg}", False, error_meta
    except urllib.error.URLError as e:
        dev_log = (
            f"--- Network Connection Error ---\n"
            f"Model: {model_id}\n"
            f"API Key: {masked_key}\n"
            f"Reason: {e.reason}\n"
            f"Check your internet connection or proxy settings.\n"
            f"--------------------------------"
        )
        error_meta["dev_log"] = dev_log
        return f"Lỗi kết nối: {e.reason}", False, error_meta
    except Exception as e:
        import traceback
        dev_log = (
            f"--- Unexpected Exception in API Call ---\n"
            f"Model: {model_id}\n"
            f"API Key: {masked_key}\n"
            f"Exception: {type(e).__name__}: {str(e)}\n"
            f"Traceback:\n{traceback.format_exc()}\n"
            f"----------------------------------------"
        )
        error_meta["dev_log"] = dev_log
        return f"Lỗi: {str(e)}", False, error_meta


def _clean_timestamps(raw_text):
    """
    Làm sạch kết quả trả về từ API để chỉ lấy chuỗi timestamps dạng MM:SS,MM:SS;...
    
    Xử lý nhiều trường hợp AI trả về không chuẩn:
    - Code block markdown (```text ... ```)
    - Markdown bold/italic (**text**, *text*)
    - Bullet points (-, *, •) và numbered lists (1., 2.)
    - Dấu ngoặc, quotes, backticks
    - Khoảng trắng thừa xung quanh timestamps
    - Dấu phân cách đa dạng (dấu chấm phẩy, xuống dòng, dấu |)
    - Timestamps dạng start-end (dấu gạch ngang thay dấu phẩy)
    
    Args:
        raw_text (str): Văn bản thô từ Gemini.

    Returns:
        str: Chuỗi timestamps sạch, hoặc rỗng nếu không khớp định dạng.
    """
    text = raw_text.strip()
    
    if not text:
        return ""
    
    # Bước 1: Loại bỏ code block markdown (```text ... ```)
    if "```" in text:
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)
    
    # Bước 2: Loại bỏ markdown formatting
    # Bold (**text**), italic (*text*), backticks (`text`)
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # Bước 3: Loại bỏ bullet points, numbered lists, và ký tự đầu dòng
    # Xử lý: "- 00:12,00:17" hoặc "1. 00:12,00:17" hoặc "• 00:12,00:17"
    text = re.sub(r'(?m)^\s*[-•*]\s+', '', text)
    text = re.sub(r'(?m)^\s*\d+[.)]\s+', '', text)
    
    # Bước 4: Loại bỏ quotes, ngoặc vuông, ngoặc tròn bao quanh
    text = text.replace('"', '').replace("'", '').replace('[', '').replace(']', '')
    text = text.replace('(', '').replace(')', '')
    
    # Bước 5: Chuẩn hoá các dấu phân cách từ start -> end thành dấu phẩy
    # "00:12-00:17", "00:12 to 00:17", "00:12 -> 00:17", "00:12~00:17", "00:12 đến 00:17"
    text = re.sub(r'(\d{1,2}:\d{1,2}(?::\d{1,2})?)\s*(?:[-–—~]|->|to|đến|till|until|\s+)\s*(\d{1,2}:\d{1,2}(?::\d{1,2})?)', r'\1,\2', text)
    
    # Bước 6: Tách timestamps từ text có thể chứa nhiều dòng hoặc dấu phân cách
    # Regex tìm tất cả các cặp timestamp dạng MM:SS,MM:SS hoặc H:MM:SS,H:MM:SS
    timestamp_pair_pattern = r'(\d{1,2}:\d{1,2}(?::\d{1,2})?)\s*,\s*(\d{1,2}:\d{1,2}(?::\d{1,2})?)'
    pairs = re.findall(timestamp_pair_pattern, text)
    
    def pad_ts(ts):
        """Đảm bảo các phần thời gian có đủ 2 chữ số (ví dụ: 0:12 -> 00:12, 1:5 -> 01:05)."""
        parts = ts.split(':')
        return ":".join([p.zfill(2) for p in parts])

    if pairs:
        # Ghép lại thành format chuẩn: start,end;start,end;...
        formatted_pairs = [f"{pad_ts(start)},{pad_ts(end)}" for start, end in pairs]
        result = ";".join(formatted_pairs)
        
        # Cắt bỏ dấu chấm phẩy thừa ở cuối
        result = result.rstrip(";")
        return result
    
    # Fallback: thử loại bỏ mọi khoảng trắng và kiểm tra format chuẩn
    clean_text = text.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", "")
    
    # Cắt bỏ dấu chấm phẩy thừa ở cuối
    if clean_text.endswith(";"):
        clean_text = clean_text[:-1]
    
    # Regex kiểm tra toàn bộ chuỗi đúng format
    full_pattern = r'^(\d{1,2}:)?\d{1,2}:\d{1,2},(\d{1,2}:)?\d{1,2}:\d{1,2}(;(\d{1,2}:)?\d{1,2}:\d{1,2},(\d{1,2}:)?\d{1,2}:\d{1,2})*$'
    if re.match(full_pattern, clean_text):
        # Pad toàn bộ các phần
        parts = []
        for pair in clean_text.split(";"):
            t_pts = pair.split(",")
            if len(t_pts) == 2:
                parts.append(f"{pad_ts(t_pts[0])},{pad_ts(t_pts[1])}")
        if parts:
            return ";".join(parts)
        return clean_text
        
    return ""


def parse_time_to_seconds(time_str):
    """
    Chuyển đổi chuỗi thời gian (H:MM:SS, MM:SS hoặc SS) thành số giây.
    
    Args:
        time_str (str): Chuỗi thời gian (ví dụ: '01:25', '01:20:15').
        
    Returns:
        float: Số giây tương ứng.
    """
    parts = time_str.strip().split(':')
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


def calculate_total_highlight_duration(highlight_str):
    """
    Tính tổng thời lượng (giây) của toàn bộ các đoạn highlight từ chuỗi kết quả.
    
    Args:
        highlight_str (str): Chuỗi dạng 'MM:SS,MM:SS;MM:SS,MM:SS;...'.
        
    Returns:
        float: Tổng thời lượng tính bằng giây.
    """
    if not highlight_str or not highlight_str.strip():
        return 0.0
        
    total_seconds = 0.0
    segments = highlight_str.split(';')
    for segment in segments:
        if not segment.strip():
            continue
        parts = segment.split(',')
        if len(parts) == 2:
            start_sec = parse_time_to_seconds(parts[0])
            end_sec = parse_time_to_seconds(parts[1])
            duration = end_sec - start_sec
            if duration > 0:
                total_seconds += duration
                
    return total_seconds

