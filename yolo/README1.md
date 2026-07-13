# YOLOv5 使用说明

## 虚拟环境信息

- **项目路径**: `f:\WORK\VHD_CWJ_File\tool\python\python\yolo\yolov5`
- **虚拟环境类型**: virtualenv (非 conda)
- **虚拟环境路径**: `f:\WORK\VHD_CWJ_File\tool\python\python\yolo\yolov5\venv`
- **Python 版本**: Python 3.8.4
- **PyTorch 版本**: 2.4.1+cpu

## 激活虚拟环境

在 Windows PowerShell 中运行:
```powershell
cd f:\WORK\VHD_CWJ_File\tool\python\python\yolo\yolov5
.\venv\Scripts\Activate.ps1
```

或者在 CMD 中运行:
```cmd
cd f:\WORK\VHD_CWJ_File\tool\python\python\yolo\yolov5
.\venv\Scripts\activate.bat
```

## 安装依赖

依赖已安装在虚拟环境中。如需重新安装:
```powershell
.\venv\Scripts\pip install -r requirements.txt
```

## 示例验证

运行目标检测示例:
```powershell
.\venv\Scripts\python detect.py --source data\images --weights yolov5s.pt --conf 0.25
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

自动下载路径: `f:\WORK\VHD_CWJ_File\tool\python\python\yolo\yolov5`
