from pathlib import Path
import PyPDF2
import os

def parse_page_ranges(range_str):
    """
    解析页面范围字符串，返回页面索引列表。
    
    Args:
        range_str (str): 页面范围字符串，格式如 "0-3,4,6"
        
    Returns:
        list: 页面索引列表，如 [0, 1, 2, 3, 4, 6]
    """
    pages = []
    if not range_str:
        return pages
    
    for part in range_str.split(','):
        part = part.strip()
        if '-' in part:
            # 处理范围，如 "0-3"
            start, end = part.split('-')
            start, end = int(start.strip()), int(end.strip())
            pages.extend(range(start, end + 1))
        else:
            # 处理单个页面，如 "4"
            pages.append(int(part))
    
    return pages



