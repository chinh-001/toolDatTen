"""
Tool Đổi Tên Video Theo Danh Sách - Entry Point

Chạy: python main.py
"""

import sys
import os

# Thêm thư mục gốc vào path để import module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.app import App


def main():
    """Khởi chạy ứng dụng."""
    app = App()
    app.mainloop()


if __name__ == '__main__':
    main()
