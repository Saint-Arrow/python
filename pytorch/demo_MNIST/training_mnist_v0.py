import torch
import torch.nn as nn
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
        super(MNIST, self).__init__()
        self.flatten = nn.Flatten()          # 28x28 -> 784
        self.fc1 = nn.Linear(784, 128)
        self.relu = nn.ReLU()                # 激活函数
        self.fc3 = nn.Linear(128, 10)

    def forward(self, x):
        x = self.flatten(x)
        x = self.relu(self.fc1(x))
        x = self.fc3(x)
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
for epoch in range(10):              # 训练 10 轮
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