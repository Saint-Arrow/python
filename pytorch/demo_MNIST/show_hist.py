"""
显示图片的灰度直方图（0-255），用于分析图像数据分布。
用法: python show_hist.py <图片路径>
示例: python show_hist.py 8.bmp
"""
import sys
import os
import numpy as np
from PIL import Image

if len(sys.argv) < 2:
    print('用法: python show_hist.py <图片路径>')
    sys.exit(1)

img_path = sys.argv[1]
if not os.path.exists(img_path):
    print(f'错误: 文件不存在 -> {img_path}')
    sys.exit(1)

# 打开图片并转灰度
img = Image.open(img_path).convert('L')
arr = np.array(img)

print(f'图片: {img_path}')
print(f'尺寸: {img.size[0]}x{img.size[1]}')
print(f'像素统计: min={arr.min()}, max={arr.max()}, mean={arr.mean():.2f}')

# 统计直方图数据
hist = np.bincount(arr.flatten(), minlength=256)

# 终端字符画直方图（无需 matplotlib）
max_count = hist.max()
bar_width = 50
print(f'\n灰度直方图 (共 {arr.size} 像素):')
print('-' * 70)
for i in range(0, 256, 8):
    bucket = hist[i:i+8].sum()
    bar_len = int(bucket / max_count * bar_width) if max_count > 0 else 0
    bar = '█' * bar_len
    print(f'{i:3d}-{i+7:3d} | {bar} {bucket}')
print('-' * 70)


