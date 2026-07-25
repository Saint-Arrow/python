import torch
import torch_directml

# 检查 DirectML 是否可用，并创建 dml 设备
if torch_directml.is_available():
    device = torch_directml.device()
    print(f"成功启用 DirectML 加速，当前设备: {device}")
else:
    device = torch.device("cpu")
    print("DirectML 不可用，已回退到 CPU")

dml = torch_directml.device()
tensor1 = torch.tensor([1]).to(dml)
tensor2 = torch.tensor([2]).to(dml)

result = tensor1 + tensor2
print(f"计算结果: {result.item()}")  # 期望输出: 3
print(f"计算设备: {result.device}")  # 期望输出包含 'privateuseone' 或 'dml'