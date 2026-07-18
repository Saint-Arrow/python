"""
PyTorch 求梯度最小 Demo
========================
演示: 多变量函数 y = x1^2 + x2^2 的梯度计算
数学上: dy/dx1 = 2*x1, dy/dx2 = 2*x2
"""

import torch

# 输入参数（可以修改这两个值）
x1 = torch.tensor(3.0, requires_grad=True)
x2 = torch.tensor(2.0, requires_grad=True)

# 定义计算: y = x1^2 + x2^2
y = x1 ** 2 + x2 ** 2

# 反向传播，自动计算所有 requires_grad=True 变量的梯度
y.backward()

# 输出结果
print(f"x1 = {x1.item()}, x2 = {x2.item()}")
print(f"y = x1^2 + x2^2 = {y.item()}")
print(f"dy/dx1 = 2*x1 = {x1.grad.item()}")  # 期望: 6.0
print(f"dy/dx2 = 2*x2 = {x2.grad.item()}")  # 期望: 4.0
