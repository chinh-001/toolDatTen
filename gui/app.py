"""
Main Application Window - Giao diện chính của tool với hệ thống Tabs (Notebook).
Quản lý cửa sổ chính, style hệ thống, và LogPanel chung.
"""

import tkinter as tk
from tkinter import ttk

from gui.widgets import LogPanel
from gui.tab_rename import RenameTab
from gui.tab_highlight import HighlightTab
from gui.tab_gemini_web import GeminiWebTab
from gui.tab_duration_checker import DurationCheckerTab
from gui.tab_highlight_duration import HighlightDurationTab
from gui.tab_highlight_formatter import HighlightFormatterTab
from utils.constants import WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_TITLE


class App(tk.Tk):
    """Cửa sổ chính của ứng dụng."""
    
    def __init__(self):
        super().__init__()
        
        self.title(WINDOW_TITLE)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(900, 700)
        
        # Styling
        self._setup_styles()
        
        # Build UI
        self._build_ui()
        
        # Center window
        self._center_window()
    
    def _setup_styles(self):
        """Cấu hình style cho ttk widgets."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Frame & Label
        style.configure('TFrame', background='#f5f6fa')
        style.configure('Header.TLabel',
                        font=('Segoe UI', 14, 'bold'),
                        background='#f5f6fa',
                        foreground='#2c3e50')
        style.configure('Section.TLabelframe',
                        font=('Segoe UI', 10, 'bold'),
                        background='#f5f6fa')
        style.configure('Section.TLabelframe.Label',
                        font=('Segoe UI', 10, 'bold'),
                        background='#f5f6fa',
                        foreground='#34495e')
        style.configure('TLabel',
                        font=('Segoe UI', 10),
                        background='#f5f6fa')
        style.configure('TButton',
                        font=('Segoe UI', 10),
                        padding=(12, 6))
        style.configure('Action.TButton',
                        font=('Segoe UI', 10, 'bold'),
                        padding=(16, 8))
        style.configure('TEntry',
                        font=('Segoe UI', 10))
        
        # Notebook (Tabs)
        style.configure('TNotebook', background='#f5f6fa', borderwidth=0)
        style.configure('TNotebook.Tab',
                        font=('Segoe UI', 10, 'bold'),
                        padding=(20, 8),
                        background='#dcdde1',
                        foreground='#2c3e50')
        style.map('TNotebook.Tab',
                  background=[('selected', '#ffffff')],
                  foreground=[('selected', '#3498db')])

        # Treeview
        style.configure('Treeview',
                        font=('Segoe UI', 9),
                        rowheight=26)
        style.configure('Treeview.Heading',
                        font=('Segoe UI', 9, 'bold'))
        
        self.configure(bg='#f5f6fa')
    
    def _center_window(self):
        """Đặt cửa sổ ở giữa màn hình."""
        self.update_idletasks()
        x = (self.winfo_screenwidth() - WINDOW_WIDTH) // 2
        y = (self.winfo_screenheight() - WINDOW_HEIGHT) // 2
        self.geometry(f"+{x}+{y}")
    
    def _build_ui(self):
        """Xây dựng toàn bộ giao diện với hệ thống Tabs."""
        # Main container với padding
        main = ttk.Frame(self, padding=12)
        main.pack(fill='both', expand=True)
        
        # Header
        header = ttk.Label(main, text="🎬 " + WINDOW_TITLE, style='Header.TLabel')
        header.pack(anchor='w', pady=(0, 6))
        
        # Separator
        ttk.Separator(main, orient='horizontal').pack(fill='x', pady=(0, 6))
        
        # ===== SYSTEM TABS (NOTEBOOK) =====
        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill='both', expand=True, pady=(0, 8))
        
        # Shared Log Panel (ở dưới cùng)
        log_frame = ttk.LabelFrame(main, text="📝 Nhật ký hoạt động (Log)",
                                   style='Section.TLabelframe', padding=4)
        log_frame.pack(fill='x', side='bottom', pady=(4, 0))
        
        self.log_panel = LogPanel(log_frame)
        self.log_panel.pack(fill='x')
        
        # Khởi tạo các Tab và nạp vào Notebook
        self.tab_rename = RenameTab(self.notebook, log_panel=self.log_panel)
        self.tab_highlight = HighlightTab(self.notebook, log_panel=self.log_panel)
        self.tab_gemini_web = GeminiWebTab(self.notebook, log_panel=self.log_panel)
        self.tab_duration_checker = DurationCheckerTab(self.notebook, log_panel=self.log_panel)
        self.tab_highlight_duration = HighlightDurationTab(self.notebook, log_panel=self.log_panel)
        self.tab_highlight_formatter = HighlightFormatterTab(self.notebook, log_panel=self.log_panel)
        
        self.notebook.add(self.tab_rename, text="📁 Đổi Tên Video")
        self.notebook.add(self.tab_highlight, text="🎬 Trích Highlight AI (API)")
        self.notebook.add(self.tab_gemini_web, text="🌐 Trích Highlight Gemini Web")
        self.notebook.add(self.tab_duration_checker, text="⏱️ Check File Video")
        self.notebook.add(self.tab_highlight_duration, text="⏱️ Thời Lượng Highlight")
        self.notebook.add(self.tab_highlight_formatter, text="📊 Trình Bày Link & Highlight")
        
        # Log khởi động
        self.log_panel.log("Hệ thống khởi động thành công. Sẵn sàng hoạt động.")
