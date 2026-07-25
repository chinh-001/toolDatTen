"""
HighlightFormatterTab - Giao diện và logic cho Tab Trình Bày Dữ Liệu Link Video & Highlight.

Hỗ trợ:
1. Nhập/dán dữ liệu link video kèm chuỗi highlight timestamps.
2. Tự động sửa các timestamp bị dở dang (ví dụ '48:' -> '48:00').
3. Trình bày dữ liệu dưới dạng văn bản cú pháp:
   [link video]
   [highlight video]
4. Trình bày dữ liệu dưới dạng Bảng Excel / Google Sheets chuẩn (2 cột / 3 cột TSV) không lo lỗi khi paste.
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core.highlight_formatter import (
    parse_link_highlight_input,
    format_entries_to_text,
    format_entries_to_tsv,
    format_entries_to_csv,
    format_duration_str
)


class HighlightFormatterTab(ttk.Frame):
    """Tab Trình bày dữ liệu Link Video & Highlight cho Excel/Sheets."""

    def __init__(self, parent, log_panel, **kwargs):
        super().__init__(parent, **kwargs)
        self.log_panel = log_panel

        self._entries = []
        self._build_ui()

    def _build_ui(self):
        """Xây dựng giao diện cho Tab Trình Bày Link & Highlight."""
        # PanedWindow chia thành 2 phần: Top (Input) & Bottom (Output)
        paned = ttk.PanedWindow(self, orient='vertical')
        paned.pack(fill='both', expand=True, pady=4, padx=4)

        # --- PART 1: Top Input Frame ---
        top_frame = ttk.LabelFrame(
            paned,
            text="📥 Nhập Dữ Liệu Link Video & Highlight (Xen kẽ dòng hoặc dán từ Excel)",
            style='Section.TLabelframe',
            padding=8
        )
        paned.add(top_frame, weight=1)
        self._build_input_section(top_frame)

        # --- PART 2: Bottom Output Frame ---
        bottom_frame = ttk.LabelFrame(
            paned,
            text="📤 Kết Quả Trình Bày Dữ Liệu (Chuẩn Văn Bản & Bảng Excel / Google Sheets)",
            style='Section.TLabelframe',
            padding=8
        )
        paned.add(bottom_frame, weight=2)
        self._build_output_section(bottom_frame)

    def _build_input_section(self, parent):
        """Tạo ô nhập dữ liệu thô và các nút thao tác."""
        parent.columnconfigure(0, weight=1)

        lbl_hint = ttk.Label(
            parent,
            text="Dán dữ liệu thô gồm Tiêu đề, Link video & Highlight (Hỗ trợ cụm 3 dòng: Tiêu đề -> Link -> Highlight, hoặc dán từ Excel):",
            font=('Segoe UI', 9, 'bold')
        )
        lbl_hint.pack(anchor='w', pady=(0, 4))

        input_container = ttk.Frame(parent)
        input_container.pack(fill='both', expand=True, pady=(0, 6))

        self.txt_input = tk.Text(
            input_container,
            height=5,
            font=('Segoe UI', 9),
            wrap='none',
            bg='#ffffff',
            relief='solid',
            bd=1
        )
        sc_input_y = ttk.Scrollbar(input_container, orient='vertical', command=self.txt_input.yview)
        sc_input_x = ttk.Scrollbar(input_container, orient='horizontal', command=self.txt_input.xview)
        self.txt_input.configure(yscrollcommand=sc_input_y.set, xscrollcommand=sc_input_x.set)

        sc_input_y.pack(side='right', fill='y')
        sc_input_x.pack(side='bottom', fill='x')
        self.txt_input.pack(side='left', fill='both', expand=True)

        # Toolbar
        ctrl_row = ttk.Frame(parent)
        ctrl_row.pack(fill='x')

        btn_paste = ttk.Button(ctrl_row, text="📋 Dán từ Clipboard", command=self._on_paste_clipboard)
        btn_paste.pack(side='left', padx=(0, 6))

        btn_process = ttk.Button(
            ctrl_row,
            text="⚡ Xử Lý & Trình Bày Dữ Liệu",
            style='Action.TButton',
            command=self._on_process
        )
        btn_process.pack(side='left', padx=(0, 6))

        btn_clear = ttk.Button(ctrl_row, text="🧹 Xóa dữ liệu", command=self._on_clear)
        btn_clear.pack(side='left', padx=(0, 6))

    def _build_output_section(self, parent):
        """Tạo Notebook gồm 2 Tab hiển thị kết quả (Văn bản & Bảng Excel)."""
        self.output_notebook = ttk.Notebook(parent)
        self.output_notebook.pack(fill='both', expand=True)

        # --- TAB OUTPUT 1: Văn bản Cú pháp [Link]\n[Highlight] ---
        tab_text_frame = ttk.Frame(self.output_notebook, padding=6)
        self.output_notebook.add(tab_text_frame, text="📝 Kết Quả Dạng Văn Bản")
        self._build_output_text_tab(tab_text_frame)

        # --- TAB OUTPUT 2: Bảng Excel / Google Sheets ---
        tab_table_frame = ttk.Frame(self.output_notebook, padding=6)
        self.output_notebook.add(tab_table_frame, text="📊 Bảng Dữ Liệu Excel / Google Sheets")
        self._build_output_table_tab(tab_table_frame)

    def _build_output_text_tab(self, parent):
        """Giao diện hiển thị kết quả văn bản."""
        tb = ttk.Frame(parent)
        tb.pack(fill='x', pady=(0, 4))

        lbl_text_info = ttk.Label(
            tb,
            text="Dữ liệu được trình bày chuẩn cú pháp: [Link Video] \\n [Highlight Video]",
            font=('Segoe UI', 9, 'italic'),
            foreground='#2980b9'
        )
        lbl_text_info.pack(side='left', anchor='w')

        btn_copy_text = ttk.Button(
            tb,
            text="📋 Copy Toàn Bộ Văn Bản (Link + Highlight)",
            style='Action.TButton',
            command=self._copy_output_text
        )
        btn_copy_text.pack(side='right')

        # Text Widget cho Output Text
        txt_container = ttk.Frame(parent)
        txt_container.pack(fill='both', expand=True)

        self.txt_output_text = tk.Text(
            txt_container,
            font=('Consolas', 10),
            wrap='none',
            bg='#fafafa',
            relief='solid',
            bd=1
        )
        sc_out_y = ttk.Scrollbar(txt_container, orient='vertical', command=self.txt_output_text.yview)
        sc_out_x = ttk.Scrollbar(txt_container, orient='horizontal', command=self.txt_output_text.xview)
        self.txt_output_text.configure(yscrollcommand=sc_out_y.set, xscrollcommand=sc_out_x.set)

        sc_out_y.pack(side='right', fill='y')
        sc_out_x.pack(side='bottom', fill='x')
        self.txt_output_text.pack(side='left', fill='both', expand=True)

    def _build_output_table_tab(self, parent):
        """Giao diện hiển thị Bảng Treeview cho Excel / Google Sheets."""
        tb = ttk.Frame(parent)
        tb.pack(fill='x', pady=(0, 4))

        self.lbl_stats = ttk.Label(
            tb,
            text="Tổng số video: 0 | Tổng thời lượng: 00m 00s",
            font=('Segoe UI', 9, 'bold'),
            foreground='#27ae60'
        )
        self.lbl_stats.pack(side='left', anchor='w')

        btn_export = ttk.Button(
            tb,
            text="📥 Xuất File TSV / CSV...",
            command=self._export_to_file
        )
        btn_export.pack(side='right', padx=(6, 0))

        btn_copy_3col = ttk.Button(
            tb,
            text="📋 Copy 3 Cột (Tiêu đề | Link | Highlight)",
            style='Action.TButton',
            command=lambda: self._copy_excel_tsv(num_cols=3)
        )
        btn_copy_3col.pack(side='right', padx=(6, 0))

        btn_copy_2col = ttk.Button(
            tb,
            text="📋 Copy 2 Cột (Link | Highlight)",
            command=lambda: self._copy_excel_tsv(num_cols=2)
        )
        btn_copy_2col.pack(side='right')

        # Treeview Table
        cols = ('stt', 'title', 'url', 'highlight', 'segments', 'duration')
        self.tree_table = ttk.Treeview(parent, columns=cols, show='headings', selectmode='extended')

        self.tree_table.heading('stt', text='#')
        self.tree_table.heading('title', text='Tiêu Đề Video')
        self.tree_table.heading('url', text='Link Video')
        self.tree_table.heading('highlight', text='Chuỗi Highlight Clean')
        self.tree_table.heading('segments', text='Số đoạn')
        self.tree_table.heading('duration', text='Thời lượng')

        self.tree_table.column('stt', width=40, minwidth=40, anchor='center')
        self.tree_table.column('title', width=180, minwidth=100)
        self.tree_table.column('url', width=250, minwidth=150)
        self.tree_table.column('highlight', width=300, minwidth=180)
        self.tree_table.column('segments', width=70, minwidth=50, anchor='center')
        self.tree_table.column('duration', width=100, minwidth=70, anchor='center')

        sc_y = ttk.Scrollbar(parent, orient='vertical', command=self.tree_table.yview)
        sc_x = ttk.Scrollbar(parent, orient='horizontal', command=self.tree_table.xview)
        self.tree_table.configure(yscrollcommand=sc_y.set, xscrollcommand=sc_x.set)

        sc_y.pack(side='right', fill='y')
        sc_x.pack(side='bottom', fill='x')
        self.tree_table.pack(side='top', fill='both', expand=True)

        # Tag định dạng cảnh báo sửa lỗi timestamp
        self.tree_table.tag_configure('repaired_row', background='#fef9e7')

        # Context Menu setup
        self._build_context_menu()

    def _build_context_menu(self):
        """Menu chuột phải cho Bảng."""
        self.menu_context = tk.Menu(self, tearoff=0)
        self.menu_context.add_command(label="🔗 Copy Link Video", command=self._copy_selected_url)
        self.menu_context.add_command(label="🎬 Copy Chuỗi Highlight", command=self._copy_selected_highlight)
        self.menu_context.add_separator()
        self.menu_context.add_command(label="📄 Copy Cả Dòng (Form Excel)", command=self._copy_selected_row)

        self.tree_table.bind("<Button-3>", self._show_context_menu)

    # ==========================================
    # Handlers & Actions
    # ==========================================

    def _on_paste_clipboard(self):
        """Dán văn bản từ bộ nhớ tạm và tự động xử lý."""
        try:
            clip_text = self.clipboard_get()
            if not clip_text or not clip_text.strip():
                messagebox.showwarning("Clipboard rỗng", "Bộ nhớ tạm không chứa văn bản nào!")
                return
            
            self.txt_input.delete('1.0', tk.END)
            self.txt_input.insert('1.0', clip_text)
            self._on_process()
        except tk.TclError:
            messagebox.showwarning("Clipboard rỗng", "Không lấy được dữ liệu từ bộ nhớ tạm!")

    def _on_clear(self):
        """Xóa sạch dữ liệu nhập và kết quả."""
        self.txt_input.delete('1.0', tk.END)
        self.txt_output_text.delete('1.0', tk.END)
        self._entries = []
        self._render_table()
        self.log_panel.log("Đã xóa sạch dữ liệu nhập và bảng kết quả.", 'info')

    def _on_process(self):
        """Phân tích dữ liệu, sửa lỗi timestamp, trình bày kết quả."""
        raw_text = self.txt_input.get('1.0', tk.END).strip()
        if not raw_text:
            messagebox.showwarning("Thiếu dữ liệu", "Vui lòng nhập hoặc dán dữ liệu link & highlight vào ô nhập liệu!")
            return

        self._entries = parse_link_highlight_input(raw_text)
        if not self._entries:
            messagebox.showwarning("Không phân tích được", "Không tìm thấy URL hợp lệ nào từ văn bản đã nhập!")
            return

        # Render kết quả dạng Văn bản
        formatted_text = format_entries_to_text(self._entries)
        self.txt_output_text.delete('1.0', tk.END)
        self.txt_output_text.insert('1.0', formatted_text)

        # Render kết quả dạng Bảng
        self._render_table()

        # Thống kê cảnh báo
        warnings_count = sum(len(e['warnings']) for e in self._entries)
        total_sec = sum(e['total_seconds'] for e in self._entries)
        
        msg = f"Đã xử lý thành công {len(self._entries)} video (Tổng thời lượng: {format_duration_str(total_sec)})."
        if warnings_count > 0:
            msg += f" Phát hiện {warnings_count} mốc timestamp dở dang đã được tự động sửa chữa."
            self.log_panel.log(msg, 'warning')
        else:
            self.log_panel.log(msg, 'success')

    def _render_table(self):
        """Nạp danh sách entries vào Treeview."""
        for item in self.tree_table.get_children():
            self.tree_table.delete(item)

        total_sec = sum(e['total_seconds'] for e in self._entries)
        for idx, entry in enumerate(self._entries, 1):
            has_warning = bool(entry.get('warnings'))
            tags = ('repaired_row',) if has_warning else ()

            self.tree_table.insert(
                '', 'end', iid=f"row_{idx}",
                values=(
                    idx,
                    entry['title'],
                    entry['url'],
                    entry['highlight_clean'] if entry['highlight_clean'] else entry['highlight_raw'],
                    entry['segment_count'],
                    entry['duration_formatted']
                ),
                tags=tags
            )

        self.lbl_stats.configure(
            text=f"🟢 Tổng số video: {len(self._entries)} | Tổng thời lượng: {format_duration_str(total_sec)}"
        )

    def _copy_output_text(self):
        """Copy kết quả dạng văn bản ([Link]\n[Highlight]) vào Clipboard."""
        output_text = self.txt_output_text.get('1.0', tk.END).strip()
        if not output_text:
            messagebox.showinfo("Thông báo", "Chưa có kết quả văn bản nào để copy!")
            return

        self.clipboard_clear()
        self.clipboard_append(output_text)
        self.update()
        
        self.log_panel.log(f"📋 Đã copy {len(self._entries)} video chuẩn cú pháp (Link + Highlight) vào Clipboard.", 'success')
        messagebox.showinfo(
            "Thành công",
            f"Đã sao chép kết quả {len(self._entries)} video vào Clipboard!\nBạn có thể Ctrl+V dán trực tiếp vào Google Sheets / Excel."
        )

    def _copy_excel_tsv(self, num_cols=2):
        """Copy bảng dữ liệu dưới dạng TSV chuẩn cho Excel / Google Sheets."""
        if not self._entries:
            messagebox.showinfo("Thông báo", "Chưa có dữ liệu nào trong bảng để copy!")
            return

        tsv_data = format_entries_to_tsv(self._entries, num_cols=num_cols)
        self.clipboard_clear()
        self.clipboard_append(tsv_data)
        self.update()

        label = f"{num_cols} cột"
        self.log_panel.log(f"📋 Đã copy {len(self._entries)} dòng bảng ({label}) chuẩn TSV Excel vào Clipboard.", 'success')
        messagebox.showinfo(
            "Thành công",
            f"Đã sao chép {len(self._entries)} dòng ({label}) chuẩn Excel!\nBạn có thể Ctrl+V dán trực tiếp vào Google Sheets hoặc Excel."
        )

    def _export_to_file(self):
        """Xuất danh sách dữ liệu ra file TSV / CSV."""
        if not self._entries:
            messagebox.showinfo("Thông báo", "Không có dữ liệu để xuất file!")
            return

        file_path = filedialog.asksaveasfilename(
            title="Chọn vị trí lưu file",
            defaultextension=".csv",
            filetypes=[("File CSV", "*.csv"), ("File Text TSV", "*.txt"), ("Tất cả tệp", "*.*")],
            initialfile="link_and_highlight_formatted.csv"
        )
        if not file_path:
            return

        try:
            if file_path.endswith('.txt') or file_path.endswith('.tsv'):
                content = format_entries_to_tsv(self._entries, num_cols=3)
            else:
                content = format_entries_to_csv(self._entries)

            with open(file_path, 'w', encoding='utf-8-sig') as f:
                f.write(content)

            self.log_panel.log(f"💾 Đã xuất {len(self._entries)} dòng dữ liệu thành công ra: {file_path}", 'success')
            messagebox.showinfo("Xuất file thành công", f"Đã lưu thành công tại:\n{file_path}")
        except Exception as e:
            self.log_panel.log(f"❌ Lỗi khi lưu file: {e}", 'error')
            messagebox.showerror("Lỗi lưu file", str(e))

    # Context Menu Actions
    def _show_context_menu(self, event):
        item = self.tree_table.identify_row(event.y)
        if item:
            self.tree_table.selection_set(item)
            self.menu_context.post(event.x_root, event.y_root)

    def _get_selected_row_values(self):
        selected = self.tree_table.selection()
        if not selected:
            return None
        return self.tree_table.item(selected[0], 'values')

    def _copy_selected_url(self):
        vals = self._get_selected_row_values()
        if vals:
            self.clipboard_clear()
            self.clipboard_append(vals[2])
            self.update()
            self.log_panel.log(f"📋 Copied Link Video: {vals[2]}", 'info')

    def _copy_selected_highlight(self):
        vals = self._get_selected_row_values()
        if vals:
            self.clipboard_clear()
            self.clipboard_append(vals[3])
            self.update()
            self.log_panel.log(f"📋 Copied Highlight: {vals[3]}", 'info')

    def _copy_selected_row(self):
        vals = self._get_selected_row_values()
        if vals:
            row_tsv = f"{vals[1]}\t{vals[2]}\t{vals[3]}\t{vals[4]}\t{vals[5]}"
            self.clipboard_clear()
            self.clipboard_append(row_tsv)
            self.update()
            self.log_panel.log(f"📋 Copied row: {vals[1]}", 'info')
