# YOLOv5 使用说明

## 虚拟环境信息

- **项目路径**: `f:\WORK\VHD_CWJ_File\tool\python\python\pytorch\yolov5`
- **虚拟环境类型**: conda (miniconda)
- **虚拟环境名称**: `yolov5_env`
- **环境位置**: `E:\ProgramData\Miniconda3\envs\yolov5_env`
- **Python 版本**: Python 3.8.20
- **PyTorch 版本**: 2.4.1+cpu
- **torchvision 版本**: 0.19.1+cpu
- **matplotlib 版本**: 3.7.5

## 激活虚拟环境

在 PowerShell 或 CMD 中运行:
```powershell
conda activate yolov5_env
```

## 安装依赖

环境已创建并安装好依赖。如需重新安装:
```powershell
# 创建环境
conda create -n yolov5_env python=3.8

# 安装 PyTorch (CPU版)
conda run -n yolov5_env pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# 安装 matplotlib
conda run -n yolov5_env pip install matplotlib
```

## 示例验证

运行目标检测示例:
```powershell
conda activate yolov5_env
cd f:\WORK\VHD_CWJ_File\tool\python\python\pytorch\yolov5
python detect.py --source data\images --weights yolov5s.pt --conf 0.25
```

### 检测结果
- **bus.jpg**: 检测到 4 persons, 1 bus
- **zidane.jpg**: 检测到 2 persons, 2 ties

检测结果保存在: `runs\detect\exp`

## 可用脚本

| 脚本 | 功能 |
|------|------|
| train.py | 训练模型 |
| detect.py | 目标检测 |
| val.py | 模型验证 |
| export.py | 模型导出 |

## 预训练权重

- yolov5s.pt (small) - 已下载
- yolov5m.pt (medium)
- yolov5l.pt (large)
- yolov5x.pt (extra large)

自动下载路径: `f:\WORK\VHD_CWJ_File\tool\python\python\pytorch\yolov5`
