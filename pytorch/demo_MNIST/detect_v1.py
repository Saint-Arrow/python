import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.transforms as transforms
import os
import sys
import numpy as np
from PIL import Image

# ---------------加载模型---------------------------
# ---------------模型以及loss定义---------------------------
class MNIST(nn.Module):
    def __init__(self):
        super().__init__()
        # 1. 卷积层：负责提取 28x28 图片的特征
        # 输入通道 1 (灰度图)，输出 32 个通道，卷积核大小 3x3
        self.conv1 = nn.Conv2d(in_channels=1, out_channels=32, kernel_size=3)
        # 再卷积一次，提取更深层特征
        self.conv2 = nn.Conv2d(in_channels=32, out_channels=64, kernel_size=3)
        
        # 2. 池化层：负责缩小尺寸
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)
        
        # 3. 展平层：把二维特征图拍扁成一维
        self.flatten = nn.Flatten()
        
        # 4. 全连接层：负责分类
        # 注意这里的 1600 是怎么来的：
        # 28x28 经过 3x3 卷积变成 26x26，再经过 2x2 池化变成 13x13
        # 13x13 经过 3x3 卷积变成 11x11，再经过 2x2 池化变成 5x5（向下取整）
        # 所以展平后的特征数是：64(通道数) * 5 * 5 = 1600
        self.fc1 = nn.Linear(64 * 5 * 5, 128)
        self.fc2 = nn.Linear(128, 10) # 最后输出 10 个数字的概率

    def forward(self, x):
        x = self.pool(F.relu(self.conv1(x))) # 28x28 -> 13x13
        x = self.pool(F.relu(self.conv2(x))) # 13x13 -> 6x6 (这里为了简化计算，PyTorch默认向下取整)
        
        x = self.flatten(x)                  # 拍扁成一维向量
        x = F.relu(self.fc1(x))              # 全连接分类
        x = self.fc2(x)
        return x

_model_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(_model_dir, 'mnist.pth')

import warnings
with warnings.catch_warnings():
    warnings.simplefilter('ignore', FutureWarning)
    model = torch.load(model_path, map_location='cpu')  # 加载完整模型
model.eval()  # 切换到评估模式（关闭 Dropout/BatchNorm 的训练行为）

print(f'已加载模型: {model_path}')

# ---------------加载自定义图片---------------------------
if len(sys.argv) < 2:
    print('用法: python detect.py <图片路径> [--inv] [--thr N]')
    print('  --inv        对图片像素取反（白底黑字 -> 黑底白字）')
    print('  --thr N      启用二值化，阈值N（>N→255, <=N→0），不指定则保留原始灰度')
    sys.exit(1)

img_path = sys.argv[1]
invert = '--inv' in sys.argv

# 解析阈值参数（仅显式指定时才启用二值化）
threshold = None
if '--thr' in sys.argv:
    idx = sys.argv.index('--thr')
    if idx + 1 < len(sys.argv):
        threshold = int(sys.argv[idx + 1])
    else:
        print('错误: --thr 需要跟一个整数参数')
        sys.exit(1)
if not os.path.exists(img_path):
    print(f'错误: 文件不存在 -> {img_path}')
    sys.exit(1)

# 打开图片并转灰度
img = Image.open(img_path).convert('L')  # 转为灰度图

# 检查尺寸是否为 28x28
w, h = img.size
if w != 28 or h != 28:
    print(f'错误: 图片尺寸必须是 28x28，当前为 {w}x{h}')
    sys.exit(1)

# 二值化（可选，仅当指定 --thr 时启用）
# MNIST训练数据保留了笔画边缘的灰度过渡，强制二值化可能丢失边缘信息
if threshold is not None:
    img = img.point(lambda p: 255 if p > threshold else 0)
    print(f'已二值化（阈值={threshold}）')

# 像素取反：白底黑字 -> 黑底白字，匹配MNIST训练数据格式
if invert:
    from PIL import ImageOps
    img = ImageOps.invert(img)
    print('已对图片像素取反')

# 质心居中：MNIST训练数据按数字像素质心对齐到图像中心,非常影响数字识别,训练数据自带居中，但你的 BMP 图片没有居中
# arr = np.array(img).astype(np.float64)
# mass_y, mass_x = np.mgrid[0:28, 0:28]
# cog_x = np.sum(arr * mass_x) / (np.sum(arr) + 1e-8)
# cog_y = np.sum(arr * mass_y) / (np.sum(arr) + 1e-8)
# shift_x = 14 - cog_x
# shift_y = 14 - cog_y
# if abs(shift_x) > 0.5 or abs(shift_y) > 0.5:
#     from PIL import Image as PILImage
#     img = PILImage.fromarray(arr.astype(np.uint8))
#     img = img.transform((28, 28), PILImage.AFFINE, (1, 0, -shift_x, 0, 1, -shift_y))
#     print(f'已质心居中（偏移: x={shift_x:+.1f}, y={shift_y:+.1f}）')



# 预处理：转Tensor(0~1) -> 用MNIST全局均值/标准差归一化
transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.1307,), (0.3081,))
])

image = transform(img)          # [1, 28, 28]
image_batch = image.unsqueeze(0)  # [1, 1, 28, 28] 增加 batch 维度

# ---------------推理---------------------------
with torch.no_grad():
    output = model(image_batch)
    probs = torch.softmax(output, dim=1)[0]  # 各类别概率
    predicted = torch.argmax(probs, dim=0).item()
    confidence = probs[predicted].item() * 100

print(f'图片: {img_path}')
print(f'推理结果: {predicted}（置信度: {confidence:.1f}%）')
print(f'概率分布: {dict((i, f"{p.item()*100:.1f}%") for i, p in enumerate(probs))}')
