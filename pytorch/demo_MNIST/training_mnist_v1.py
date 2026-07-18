import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision
import torchvision.transforms as transforms

# ---------------训练集下载---------------------------
# 下载文件，data/MNIST/raw/，如果是手动下载的话，还需要手动解压gz文件才行
# https://ossci-datasets.s3.amazonaws.com/mnist/train-images-idx3-ubyte.gz
# https://ossci-datasets.s3.amazonaws.com/mnist/train-labels-idx1-ubyte.gz
# https://ossci-datasets.s3.amazonaws.com/mnist/t10k-images-idx3-ubyte.gz
# https://ossci-datasets.s3.amazonaws.com/mnist/t10k-labels-idx1-ubyte.gz
# 定义对图片的预处理：将图片转为张量，并做归一化
# 当你把 MNIST 图片转成 Tensor 时，原本 0~255 的像素值会被除以 255，缩放到 0.0 到 1.0 之间
# Z-score 标准化 新像素值 = (原像素值 - 均值) / 标准差,0.1307/0.3081是专属于 MNIST 这个手写数字数据集的
transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.1307,), (0.3081,))
])
download_data = False
import os
_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

# 下载并加载训练集 (download=True 会自动下载)
train_dataset = torchvision.datasets.MNIST(
    root=_data_dir,   # 数据存放目录（相对于脚本所在目录）
    train=True,         # True 表示这是训练集 (60000张)
    download=download_data,      # 数据已手动下载，设为 False
    transform=transform
)

# 下载并加载测试集
test_dataset = torchvision.datasets.MNIST(
    root=_data_dir,
    train=False,        # False 表示这是测试集 (10000张)
    download=download_data, 
    transform=transform
)
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


model = MNIST()
criterion = nn.CrossEntropyLoss()    # 多分类标配，内部包含 softmax
optimizer = torch.optim.SGD(model.parameters(), lr=0.01)


# ---------------数据加载---------------------------

from torch.utils.data import DataLoader

train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)
test_loader = DataLoader(test_dataset, batch_size=1000, shuffle=False)
# batch_size=64：每次喂 64 张图进模型，和之前一次喂全部数据不同
# shuffle=True：每个 epoch 打乱顺序，防止模型"记住"顺序


# ---------------训练模型---------------------------
for epoch in range(5):              # 训练 10 轮
    for batch_x, batch_y in train_loader:
        output = model(batch_x)
        loss = criterion(output, batch_y)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
    print(f'Epoch {epoch+1}, Loss: {loss.item():.4f}')



#  ---------------测试模型---------------------------  
correct = 0
total = 0
with torch.no_grad():                # 测试时不计算梯度
    for images, labels in test_loader:
        outputs = model(images)
        _, predicted = torch.max(outputs, 1)   # 取最大值的下标作为预测类别
        total += labels.size(0)
        correct += (predicted == labels).sum().item()
print(f'测试集准确率: {100 * correct / total:.2f}%')


torch.save(model, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mnist.pth'))