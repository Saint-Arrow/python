import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import torch
import torch.nn as nn
import torchvision
import torchvision.transforms as transforms
import torch_directml
device = torch_directml.device()
# ---------------训练集下载---------------------------

transform = transforms.Compose([
    transforms.RandomHorizontalFlip(0.3),      # 随机水平翻转
    transforms.RandomRotation(15),          # 随机旋转 ±15°
    transforms.ToTensor(),
    transforms.Normalize((0.5,0.5,0.5), (0.5,0.5,0.5))
])
#自动下载比较慢，可以从这里手动下载，https://zhuanlan.zhihu.com/p/129078357?spm=a2c6h.12873639.article-detail.6.2af86b9362neKm
download_data = False
#download_data = True
import os
_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

# 下载并加载训练集 (download=True 会自动下载)
train_dataset = torchvision.datasets.CIFAR10(
    root=_data_dir,   # 数据存放目录（相对于脚本所在目录）
    train=True,         # True 表示这是训练集 (60000张)
    download=download_data,      # 数据已手动下载，设为 False
    transform=transform
)

# 下载并加载测试集
test_dataset = torchvision.datasets.CIFAR10(
    root=_data_dir,
    train=False,        # False 表示这是测试集 (10000张)
    download=download_data, 
    transform=transform
)
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


model = CIFAR10().to(device)
criterion = nn.CrossEntropyLoss()    # 多分类标配，内部包含 softmax
optimizer = torch.optim.SGD(model.parameters(), lr=0.01)


# ---------------数据加载---------------------------

from torch.utils.data import DataLoader

train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)
test_loader = DataLoader(test_dataset, batch_size=64, shuffle=False)
# batch_size=64：每次喂 batch_size 张图进模型，和之前一次喂全部数据不同
# shuffle=True：每个 epoch 打乱顺序，防止模型"记住"顺序


# ---------------训练模型---------------------------
for epoch in range(10):              # 训练 10 轮
    running_loss = 0.0
    for batch_x, batch_y in train_loader:
        batch_x = batch_x.to(device)
        batch_y = batch_y.to(device)
        output = model(batch_x)
        loss = criterion(output, batch_y)
        optimizer.zero_grad()
        loss.backward()
        #optimizer.step()
        with torch.no_grad():
            for p in model.parameters():
                if p.grad is not None:
                    p.grad.data.mul_(0.01)   # grad *= lr，原地操作
                    p.data.sub_(p.grad.data) # param -= grad，原地操作
        running_loss += loss.item()
        del output, loss, batch_x, batch_y   # 及时释放显存引用
    print(f'Epoch {epoch+1}, Loss: {running_loss / len(train_loader):.4f}')



#  ---------------测试模型---------------------------  
correct = 0
total = 0
with torch.no_grad():                # 测试时不计算梯度
    for images, labels in test_loader:
        images = images.to(device)
        labels = labels.to(device)
        outputs = model(images)
        _, predicted = torch.max(outputs, 1)   # 取最大值的下标作为预测类别
        total += labels.size(0)
        correct += (predicted == labels).sum().item()
print(f'测试集总数: {total}, 准确率: {100 * correct / total:.2f}%')


torch.save(model, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cifar10.pth'))