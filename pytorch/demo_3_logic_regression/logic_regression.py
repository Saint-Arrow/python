import torch
import torch.nn as nn


class logic_regression_model(nn.Module):
    def __init__(self):
        super(logic_regression_model, self).__init__()
        #定义层,nn.Linear(输入特征数, 输出特征数),
        self.linear = nn.Linear(1, 1)
        self.sigmoid = nn.Sigmoid() 

    def forward(self, x):
        x=self.linear(x)
        x=self.sigmoid(x)
        return (x)

# 定义好了模型, 手动定义损失函数和优化器（通常在训练开始前做一次）
model=logic_regression_model()
criterion = nn.BCELoss()  # 实例化二元交叉熵损失函数
optimizer = torch.optim.SGD(model.parameters(), lr=0.01)

# 定义训练集数据：x=1~50，y: <23为0，>=23为1
x = torch.arange(1, 51, dtype=torch.float32).view(-1, 1)
y = (x >= 23).float()
## 预期结果 b=-23w

# 2. 在训练循环中手动调用
for epoch in range(40000):
    y_predit=model(x)    
    loss = criterion(y_predit, y)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    if(loss<0.1):
        print('训练次数', epoch+1)
        break;
    if(epoch%50==0):    
        print(f'Epoch [{epoch+1}], Loss: {loss.item():.4f}')
        print('训练中,b/w=', model.linear.bias.item() / model.linear.weight.item())  

print('训练完成，参数为:', model.linear.weight.item(), model.linear.bias.item())  
print('b/w=', model.linear.bias.item() / model.linear.weight.item())      
