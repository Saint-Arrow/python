import torch
import torch.nn as nn


class linear_regression_model(nn.Module):
    def __init__(self):
        super(linear_regression_model, self).__init__()
        #定义层,nn.Linear(输入特征数, 输出特征数),
        self.linear = nn.Linear(1, 1)

    def forward(self, x):
        return self.linear(x)

# 定义好了模型, 手动定义损失函数和优化器（通常在训练开始前做一次）
model=linear_regression_model()
criterion = nn.MSELoss()  # 实例化损失函数
optimizer = torch.optim.SGD(model.parameters(), lr=0.01)

# 定义训练集数据
x=torch.tensor([[1.0],[2.0],[3.0]])
y=0.4*x+0.3

# 2. 在训练循环中手动调用
for epoch in range(2000):
    y_predit=model(x)    
    loss = criterion(y_predit, y)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    if(epoch%10==0):    
        print(f'Epoch [{epoch+1}], Loss: {loss.item():.4f}')
        print('训练完成，参数为:', model.linear.weight.item(), model.linear.bias.item())

print('训练完成，参数为:', model.linear.weight.item(), model.linear.bias.item())        
