"""显示图片的直方图（支持灰度 / RGB 多通道），用于分析图像数据分布。
用法: python show_hist.py <图片路径> [--gray]
示例:
  python show_hist.py 8.bmp          # 自动检测，彩色图显示 R/G/B 各通道
  python show_hist.py photo.jpg      # 彩色图片
  python show_hist.py 8.bmp --gray   # 强制转为灰度显示
"""
import sys
import os
import numpy as np
from PIL import Image

# --------------- 参数解析 ---------------
force_gray = '--gray' in sys.argv
argv = [a for a in sys.argv[1:] if not a.startswith('--')]

if len(argv) < 1:
    print('用法: python show_hist.py <图片路径> [--gray]')
    sys.exit(1)

img_path = argv[0]
if not os.path.exists(img_path):
    print(f'错误: 文件不存在 -> {img_path}')
    sys.exit(1)

# --------------- 加载图片 ---------------
img_orig = Image.open(img_path)
mode = img_orig.mode          # L / RGB / RGBA / P ...

if force_gray:
    img = img_orig.convert('L')
    channels = {'Gray': np.array(img)}
else:
    if mode in ('RGB', 'RGBA'):
        img = img_orig.convert('RGB')
        arr_rgb = np.array(img)
        channels = {
            'R': arr_rgb[:, :, 0],
            'G': arr_rgb[:, :, 1],
            'B': arr_rgb[:, :, 2],
        }
    else:
        # 灰度或其他单通道模式
        img = img_orig.convert('L')
        channels = {'Gray': np.array(img)}

# --------------- 基本信息 ---------------
print(f'图片  : {img_path}')
print(f'尺寸  : {img_orig.size[0]}x{img_orig.size[1]}')
print(f'模式  : {mode}' + (' (强制灰度)' if force_gray and mode != 'L' else ''))

# 整体统计（所有通道合并）
all_pixels = np.concatenate([ch.flatten() for ch in channels.values()])
print(f'像素统计: min={all_pixels.min()}, max={all_pixels.max()}, mean={all_pixels.mean():.2f}')

# --------------- 终端字符画直方图 ---------------
bar_width = 40

def print_channel_hist(name, arr, color_code=''):
    """打印单通道直方图（按 16 级分桶，每桶 16 个灰度值）"""
    hist = np.bincount(arr.flatten(), minlength=256)
    max_count = hist.max()
    total = arr.size
    print(f'\n[{name}] 通道直方图 (共 {total} 像素)'
          f'  min={arr.min()}  max={arr.max()}  mean={arr.mean():.2f}')
    print('-' * 72)
    for i in range(0, 256, 16):
        bucket = hist[i:i+16].sum()
        bar_len = int(bucket / max_count * bar_width) if max_count > 0 else 0
        bar = '█' * bar_len
        pct = bucket / total * 100
        print(f'{i:3d}-{i+15:3d} | {bar:<{bar_width}} {bucket:>7d} ({pct:5.2f}%)')
    print('-' * 72)

for ch_name, ch_arr in channels.items():
    print_channel_hist(ch_name, ch_arr)

# --------------- 通道对比（仅彩色图） ---------------
if len(channels) > 1:
    print('\n[通道对比摘要]')
    print(f'{"通道":<6} {"min":>5} {"max":>5} {"mean":>8} {"std":>8} {"<50占比":>10} {">200占比":>10}')
    print('-' * 60)
    for ch_name, ch_arr in channels.items():
        low_pct  = (ch_arr < 50).sum()  / ch_arr.size * 100
        high_pct = (ch_arr > 200).sum() / ch_arr.size * 100
        print(f'{ch_name:<6} {ch_arr.min():>5} {ch_arr.max():>5} '
              f'{ch_arr.mean():>8.2f} {ch_arr.std():>8.2f} '
              f'{low_pct:>9.2f}% {high_pct:>9.2f}%')
    print('-' * 60)
