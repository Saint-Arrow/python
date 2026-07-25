import torch
import torch.nn as nn
import torchvision.transforms as transforms
import os
import sys
import numpy as np
from PIL import Image

# ---------------加载模型---------------------------
# ---------------模型以及loss定义---------------------------
class CIFAR10(nn.Module):
    def __init__(self):
        super(CIFAR10, self).__init__()
        self.conv1=nn.Conv2d(3,6,5) # 3个输入通道，6个输出通道，5x5的卷积核
        self.pool=nn.MaxPool2d(2,2)         # 2x2的池化
        self.conv2=nn.Conv2d(6,16,5) # 6个输入通道，16个输出通道，5x5的卷积核

        self.flatten = nn.Flatten()
        self.fc1 = nn.Linear(16*5*5, 120)         # 16*5*5 -> 120
        self.fc2 = nn.Linear(120, 84)
        self.relu = nn.ReLU()                # 激活函数
        self.fc3 = nn.Linear(84, 10)

    def forward(self, x):
        x = self.pool(self.conv1(x))
        x = self.pool(self.conv2(x))
        x = self.flatten(x)
        x = self.relu(self.fc1(x))
        x = self.relu(self.fc2(x))
        x = self.fc3(x)
        return x


model = CIFAR10()

_model_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(_model_dir, 'cifar10.pth')

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
img = Image.open(img_path)

# 检查尺寸
w, h = img.size
if w != 32 or h != 32:
    print(f'错误: 图片尺寸必须是 32x32，当前为 {w}x{h}')
    sys.exit(1)

#图像数据0-255缩放到0-1
arr = np.array(img).astype(np.float32) / 255.0

# 像素取反：白底黑字 -> 黑底白字，匹配MNIST训练数据格式
if invert:
    arr = 1.0 - arr
    print('已对图片像素取反')

# # 质心居中：MNIST训练数据按数字像素质心对齐到图像中心,非常影响数字识别,训练数据自带居中，但你的 BMP 图片没有居中
# mass_y, mass_x = np.mgrid[0:32, 0:32]
# cog_x = np.sum(arr * mass_x) / (np.sum(arr) + 1e-8)
# cog_y = np.sum(arr * mass_y) / (np.sum(arr) + 1e-8)
# shift_x = 16 - cog_x
# shift_y = 16 - cog_y
# if abs(shift_x) > 0.5 or abs(shift_y) > 0.5:
#     from PIL import Image as PILImage
#     img_u8 = (arr * 255).astype(np.uint8)
#     img_tmp = PILImage.fromarray(img_u8)
#     img_tmp = img_tmp.transform((32, 32), PILImage.AFFINE, (1, 0, -shift_x, 0, 1, -shift_y))
#     arr = np.array(img_tmp).astype(np.float32) / 255.0
#     print(f'已质心居中（偏移: x={shift_x:+.1f}, y={shift_y:+.1f}）')

# 预处理：numpy [0,1] -> Tensor (C,H,W) -> 归一化
image = torch.from_numpy(arr.transpose(2, 0, 1))  # (H,W,C) -> (C,H,W)
image = transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))(image)
image_batch = image.unsqueeze(0)  # [1, 3, 32, 32] 增加 batch 维度

# ---------------推理---------------------------
with torch.no_grad():
    output = model(image_batch)
    probs = torch.softmax(output, dim=1)[0]  # 各类别概率
    predicted = torch.argmax(probs, dim=0).item()
    confidence = probs[predicted].item() * 100

print(f'图片: {img_path}')
print(f'推理结果: {predicted}（置信度: {confidence:.1f}%）')
print(f'概率分布: {dict((i, f"{p.item()*100:.1f}%") for i, p in enumerate(probs))}')
