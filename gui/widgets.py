"""
Custom widgets cho GUI - Bảng kết quả và styled components.
"""

import tkinter as tk
from tkinter import ttk

from utils.constants import COLOR_MATCH_GOOD, COLOR_MATCH_MEDIUM, COLOR_MATCH_NONE, THRESHOLD_GOOD


class ResultTable(ttk.Frame):
    """
    Bảng hiển thị kết quả matching/rename với color coding.
    """
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._setup_table()
    
    def _setup_table(self):
        """Tạo Treeview với scrollbar."""
        # Columns
        columns = ('stt', 'title', 'matched_file', 'new_name', 'score', 'status')
        
        self.tree = ttk.Treeview(
            self,
            columns=columns,
            show='headings',
            selectmode='browse',
            height=10,
        )
        
        # Headings
        self.tree.heading('stt', text='#')
        self.tree.heading('title', text='Tiêu đề')
        self.tree.heading('matched_file', text='File khớp')
        self.tree.heading('new_name', text='Tên mới')
        self.tree.heading('score', text='Điểm')
        self.tree.heading('status', text='Trạng thái')
        
        # Column widths
        self.tree.column('stt', width=40, minwidth=40, anchor='center')
        self.tree.column('title', width=200, minwidth=120)
        self.tree.column('matched_file', width=200, minwidth=120)
        self.tree.column('new_name', width=250, minwidth=150)
        self.tree.column('score', width=60, minwidth=50, anchor='center')
        self.tree.column('status', width=100, minwidth=80, anchor='center')
        
        # Scrollbar
        scrollbar_y = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(self, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        # Tags cho màu sắc
        self.tree.tag_configure('good', background='#d5f5e3')
        self.tree.tag_configure('medium', background='#fdebd0')
        self.tree.tag_configure('no_match', background='#fadbd8')
        self.tree.tag_configure('success', background='#d5f5e3')
        self.tree.tag_configure('error', background='#fadbd8')
        
        # Layout
        self.tree.grid(row=0, column=0, sticky='nsew')
        scrollbar_y.grid(row=0, column=1, sticky='ns')
        scrollbar_x.grid(row=1, column=0, sticky='ew')
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
    
    def clear(self):
        """Xóa tất cả dữ liệu trong bảng."""
        for item in self.tree.get_children():
            self.tree.delete(item)
    
    def load_preview_results(self, match_results, rename_plan):
        """
        Hiển thị kết quả preview matching + rename plan.
        
        Args:
            match_results (list[dict]): Kết quả từ matcher.
            rename_plan (list[dict]): Kế hoạch đổi tên từ renamer.
        """
        self.clear()
        
        # Tạo map từ old_name -> new_name để tra cứu nhanh
        rename_map = {}
        for item in rename_plan:
            rename_map[item['old_name']] = item['new_name']
        
        for i, result in enumerate(match_results):
            matched_name = ""
            new_name = ""
            score_str = ""
            status_str = ""
            tag = 'no_match'
            
            if result['status'] == 'matched' and result['matched_file']:
                matched_name = result['matched_file']['name']
                new_name = rename_map.get(matched_name, "")
                score_str = f"{result['score']}%"
                
                if result['score'] >= THRESHOLD_GOOD:
                    status_str = "✅ Khớp tốt"
                    tag = 'good'
                else:
                    status_str = "⚠️ Khớp vừa"
                    tag = 'medium'
            else:
                score_str = f"{result['score']}%" if result['score'] > 0 else "—"
                status_str = "❌ Không tìm thấy"
                tag = 'no_match'
            
            self.tree.insert('', 'end', values=(
                i + 1,
                result['title'],
                matched_name,
                new_name,
                score_str,
                status_str,
            ), tags=(tag,))
    
    def load_rename_results(self, rename_results):
        """
        Hiển thị kết quả sau khi đổi tên.
        
        Args:
            rename_results (list[dict]): Kết quả từ renamer.execute_renames().
        """
        self.clear()
        
        for i, result in enumerate(rename_results):
            tag = 'success' if result['success'] else 'error'
            status = "✅ Thành công" if result['success'] else f"❌ {result['error']}"
            
            self.tree.insert('', 'end', values=(
                i + 1,
                "",
                result['old_name'],
                result['new_name'],
                "",
                status,
            ), tags=(tag,))


class LogPanel(ttk.Frame):
    """
    Panel hiển thị log hoạt động.
    """
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._setup_log()
    
    def _setup_log(self):
        """Tạo Text widget với scrollbar cho log."""
        self.text = tk.Text(
            self,
            height=6,
            wrap='word',
            state='disabled',
            font=('Consolas', 9),
            bg='#1e1e2e',
            fg='#cdd6f4',
            insertbackground='white',
            relief='flat',
            padx=8,
            pady=4,
        )
        
        scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        
        # Tags cho màu log
        self.text.tag_configure('info', foreground='#89b4fa')
        self.text.tag_configure('success', foreground='#a6e3a1')
        self.text.tag_configure('warning', foreground='#f9e2af')
        self.text.tag_configure('error', foreground='#f38ba8')
        
        self.text.grid(row=0, column=0, sticky='nsew')
        scrollbar.grid(row=0, column=1, sticky='ns')
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
    
    def log(self, message, level='info'):
        """
        Thêm message vào log.
        
        Args:
            message (str): Nội dung log.
            level (str): Mức log - 'info', 'success', 'warning', 'error'.
        """
        prefix_map = {
            'info': '[INFO]',
            'success': '[OK]',
            'warning': '[WARN]',
            'error': '[LỖI]',
        }
        prefix = prefix_map.get(level, '[INFO]')
        
        self.text.configure(state='normal')
        self.text.insert('end', f"{prefix} {message}\n", level)
        self.text.see('end')
        self.text.configure(state='disabled')
    
    def clear(self):
        """Xóa toàn bộ log."""
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        self.text.configure(state='disabled')


class ErrorLogPanel(ttk.Frame):
    """
    Panel chuyên hiển thị log lỗi dạng console với tính năng tự động xóa sau 5 phút.
    Hỗ trợ bôi đen copy toàn bộ hoặc từng phần dễ dàng.
    """

    EXPIRY_SECONDS = 300  # 5 phút

    def __init__(self, parent, tab_label_callback=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._entries = []  # Danh sách dict: {iid, timestamp, title, msg, level, after_id}
        self._next_iid = 0
        self._tab_label_callback = tab_label_callback
        self._setup_ui()

    def _setup_ui(self):
        """Tạo giao diện panel log lỗi dạng console."""
        # Header frame
        header_frame = ttk.Frame(self)
        header_frame.pack(fill='x', pady=(0, 4))

        self.lbl_count = ttk.Label(
            header_frame,
            text="✅ Chưa có lỗi",
            font=('Segoe UI', 9, 'italic'),
            foreground='#27ae60'
        )
        self.lbl_count.pack(side='left')

        # Nút copy all và nút clear
        btn_copy_all = ttk.Button(
            header_frame,
            text="📋 Copy tất cả lỗi",
            command=self.copy_all_errors,
        )
        btn_copy_all.pack(side='right', padx=2)

        btn_clear = ttk.Button(
            header_frame,
            text="🗑 Xóa tất cả",
            command=self.clear_all,
        )
        btn_clear.pack(side='right', padx=2)

        # Cấu trúc Text widget dạng console
        self.text_widget = tk.Text(
            self,
            height=8,
            wrap='word',
            font=('Consolas', 9),
            bg='#1e1e2e',
            fg='#f8f8f2',
            insertbackground='white',
            relief='flat',
            padx=8,
            pady=6,
            state='disabled'
        )
        
        # Tags cho màu sắc
        self.text_widget.tag_configure('timestamp', foreground='#6272a4')
        self.text_widget.tag_configure('title', foreground='#ff79c6', font=('Consolas', 9, 'bold'))
        self.text_widget.tag_configure('error', foreground='#ff5555')
        self.text_widget.tag_configure('warning', foreground='#ffb86c')
        self.text_widget.tag_configure('system', foreground='#8be9fd')

        scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=scrollbar.set)

        self.text_widget.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    def log_error(self, video_title, error_message, level='error'):
        """
        Thêm lỗi mới vào console log.
        """
        import time as _time
        timestamp = _time.strftime("%H:%M:%S")

        iid = self._next_iid
        self._next_iid += 1

        # Lên lịch xóa sau EXPIRY_SECONDS
        after_id = self.after(
            self.EXPIRY_SECONDS * 1000,
            lambda: self._remove_entry(iid)
        )

        entry = {
            'iid': iid,
            'timestamp': timestamp,
            'title': video_title,
            'msg': error_message,
            'level': level,
            'after_id': after_id
        }
        self._entries.append(entry)
        self._refresh_log()

    def _remove_entry(self, iid):
        """Xóa 1 log record khỏi danh sách và render lại."""
        self._entries = [e for e in self._entries if e['iid'] != iid]
        self._refresh_log()

    def clear_all(self):
        """Xóa tất cả lỗi và các timer."""
        for entry in self._entries:
            try:
                self.after_cancel(entry['after_id'])
            except (ValueError, tk.TclError):
                pass
        self._entries.clear()
        self._refresh_log()

    def copy_all_errors(self):
        """Copy toàn bộ text trong console lỗi vào clipboard."""
        raw_text = self.text_widget.get('1.0', 'end').strip()
        if not raw_text:
            return
        self.clipboard_clear()
        self.clipboard_append(raw_text)
        self.update()

    def _refresh_log(self):
        """Vẽ lại nội dung trong Text widget từ danh sách entry."""
        self.text_widget.configure(state='normal')
        self.text_widget.delete('1.0', 'end')

        for entry in self._entries:
            self.text_widget.insert('end', f"[{entry['timestamp']}] ", 'timestamp')
            
            if entry['title'] == "[Hệ thống]":
                self.text_widget.insert('end', f"{entry['title']}: ", 'system')
            else:
                self.text_widget.insert('end', f"[{entry['title']}]: ", 'title')
            
            tag = 'error' if entry['level'] == 'error' else 'warning'
            self.text_widget.insert('end', f"{entry['msg']}\n", tag)

        self.text_widget.see('end')
        self.text_widget.configure(state='disabled')

        count = len(self._entries)
        if count == 0:
            self.lbl_count.configure(text="✅ Chưa có lỗi", foreground='#27ae60')
        else:
            self.lbl_count.configure(
                text=f"⚠️ {count} lỗi (tự xóa sau 5 phút)",
                foreground='#e74c3c'
            )

        if self._tab_label_callback:
            self._tab_label_callback(count)

    @property
    def error_count(self):
        return len(self._entries)


class HighlightResultTable(ttk.Frame):
    """
    Bảng hiển thị danh sách video và kết quả trích xuất highlight.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._setup_table()

    def _setup_table(self):
        """Tạo Treeview với các cột cho phần Highlight."""
        columns = ('stt', 'title', 'url', 'highlight', 'status')

        self.tree = ttk.Treeview(
            self,
            columns=columns,
            show='headings',
            selectmode='browse',
            height=10,
        )

        # Headings
        self.tree.heading('stt', text='#')
        self.tree.heading('title', text='Tiêu đề')
        self.tree.heading('url', text='Link video')
        self.tree.heading('highlight', text='Đoạn Highlight')
        self.tree.heading('status', text='Trạng thái')

        # Column widths
        self.tree.column('stt', width=40, minwidth=40, anchor='center')
        self.tree.column('title', width=250, minwidth=150)
        self.tree.column('url', width=250, minwidth=150)
        self.tree.column('highlight', width=250, minwidth=150)
        self.tree.column('status', width=120, minwidth=100, anchor='center')

        # Scrollbars
        scrollbar_y = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(self, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        # Tags cho màu sắc dòng
        self.tree.tag_configure('pending', background='#ffffff')
        self.tree.tag_configure('running', background='#ebf5fb')  # Xanh lam nhạt
        self.tree.tag_configure('success', background='#d5f5e3')  # Xanh lá nhạt
        self.tree.tag_configure('warning', background='#fdebd0')  # Vàng cam nhạt (vượt giới hạn)
        self.tree.tag_configure('error', background='#fadbd8')    # Đỏ nhạt

        # Layout
        self.tree.grid(row=0, column=0, sticky='nsew')
        scrollbar_y.grid(row=0, column=1, sticky='ns')
        scrollbar_x.grid(row=1, column=0, sticky='ew')

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def clear(self):
        """Xóa toàn bộ dữ liệu trong bảng."""
        for item in self.tree.get_children():
            self.tree.delete(item)

    def load_entries(self, entries):
        """
        Hiển thị danh sách video đã phân tách.

        Args:
            entries (list[dict]): Danh sách các entry gồm 'title', 'url'.
        """
        self.clear()
        for entry in entries:
            self.tree.insert(
                '',
                'end',
                iid=str(entry['index']),  # Dùng index làm ID dòng để dễ update sau này
                values=(
                    entry['index'] + 1,
                    entry['title'],
                    entry['url'],
                    "",
                    "Chờ xử lý"
                ),
                tags=('pending',)
            )

    def update_highlight(self, entry_index, highlight_text):
        """
        Cập nhật kết quả highlight cho một dòng cụ thể mà không làm đổi trạng thái.

        Args:
            entry_index (int/str): ID dòng (chính là index của entry).
            highlight_text (str): Timestamps highlight kết quả.
        """
        iid = str(entry_index)
        if self.tree.exists(iid):
            current_vals = list(self.tree.item(iid, 'values'))
            current_vals[3] = highlight_text  # Cập nhật cột Highlight
            self.tree.item(iid, values=current_vals)

    def update_status(self, entry_index, status_text, tag='pending', highlight_val=None):
        """
        Cập nhật trạng thái và kết quả cho một dòng cụ thể.

        Args:
            entry_index (int/str): ID dòng (chính là index của entry).
            status_text (str): Trạng thái hiển thị ở cột Trạng thái.
            tag (str): Tag màu ('pending', 'running', 'success', 'error').
            highlight_val (str, optional): Timestamps highlight nếu có. Giữ nguyên nếu là None.
        """
        iid = str(entry_index)
        if self.tree.exists(iid):
            current_vals = list(self.tree.item(iid, 'values'))
            if highlight_val is not None:
                current_vals[3] = highlight_val  # Cập nhật cột Highlight nếu có giá trị
            current_vals[4] = status_text        # Cập nhật cột Trạng thái
            self.tree.item(iid, values=current_vals, tags=(tag,))
            self.tree.see(iid)  # Tự động cuộn đến dòng đang xử lý

    def get_selected_item(self):
        """
        Lấy thông tin dòng đang được chọn.

        Returns:
            dict hoặc None: Thông tin dòng đã chọn hoặc None.
        """
        selected = self.tree.selection()
        if not selected:
            return None
        
        iid = selected[0]
        values = self.tree.item(iid, 'values')
        return {
            'index': int(iid),
            'stt': values[0],
            'title': values[1],
            'url': values[2],
            'highlight': values[3],
            'status': values[4]
        }

    def get_selected_items(self):
        """
        Lấy danh sách tất cả các dòng đang được chọn trong bảng.

        Returns:
            list[dict]: Danh sách chứa thông tin các dòng đã chọn.
        """
        items = []
        for iid in self.tree.selection():
            values = self.tree.item(iid, 'values')
            items.append({
                'index': int(iid),
                'stt': values[0],
                'title': values[1],
                'url': values[2],
                'highlight': values[3],
                'status': values[4]
            })
        return items

    def get_selected_highlights(self):
        """
        Lấy thông tin các dòng đang chọn có chứa kết quả highlight.

        Returns:
            list[dict]: Danh sách items được chọn.
        """
        items = self.get_selected_items()
        if not items:
            single = self.get_selected_item()
            if single:
                items = [single]
        return items

    def get_all_items(self):
        """
        Lấy thông tin của toàn bộ các dòng trong bảng.

        Returns:
            list[dict]: Danh sách chứa thông tin từng dòng.
        """
        items = []
        for iid in self.tree.get_children():
            values = self.tree.item(iid, 'values')
            items.append({
                'index': int(iid),
                'stt': values[0],
                'title': values[1],
                'url': values[2],
                'highlight': values[3],
                'status': values[4]
            })
        return items

    def get_all_rows(self):
        """Alias cho get_all_items()."""
        return self.get_all_items()

    def get_successful_rows(self):
        """
        Lấy danh sách các dòng có trạng thái trích thành công.

        Returns:
            list[dict]: Danh sách chứa thông tin từng dòng thành công.
        """
        items = self.get_all_items()
        return [item for item in items if 'Thành công' in str(item.get('status', ''))]


