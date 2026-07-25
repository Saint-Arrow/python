# PyTorch 课程学习路径

## 总览

共 13 课，分 5 个阶段。Lesson 1-6 已有代码，Lesson 7-13 待开发。

| 阶段 | 课程 | 代码状态 |
|------|------|----------|
| 一、基础入门 | Lesson 1-4 | ✅ 已有 |
| 二、CNN 与图像分类 | Lesson 5-6 | ✅ 已有 + ⬜ 待开发 |
| 三、目标检测 | Lesson 8 | ✅ 已有 |
| 四、序列与注意力 | Lesson 9-10 | ⬜ 待开发 |
| 五、生成模型与部署 | Lesson 11-13 | ⬜ 待开发 |

---

## 学习顺序与依赖关系

```
Lesson 1  损失函数
    ↓
Lesson 2  梯度计算
    ↓
Lesson 3  线性回归          ← 第一次完整训练
    ↓
Lesson 4  逻辑回归          ← 从回归到分类
    ↓
Lesson 5  MNIST             ← CNN 入门（灰度小图）
    ↓
Lesson 6  彩色图像分类       ← 灰度→彩色，多通道 + 数据增强         ⬜ 新增
    ↓
Lesson 7  迁移学习           ← 预训练模型微调，工程实战核心          ⬜ 新增
    ↓
Lesson 8  YOLOv5            ← 工业级检测框架
    ↓
Lesson 9  RNN/LSTM          ← 从空间(CNN)到时间(序列)
    ↓
Lesson 10 Transformer       ← 注意力机制，现代架构核心
    ↓
Lesson 11 GAN               ← 生成模型（对抗训练）
    ↓
Lesson 12 Autoencoder/VAE   ← 生成模型（无监督 + 变分推断）         ⬜ 新增
    ↓
Lesson 13 模型部署           ← 从训练到落地
```

> 每课依赖前一课的基础概念，必须按顺序学习。

---

## 已完成课程（Lesson 1-5, 8）

| # | 课程 | 目录 | 核心内容 |
|---|------|------|----------|
| 1 | 损失函数 | `demo_0_loss/` | MSE、CrossEntropy 计算与对比 |
| 2 | 梯度计算 | `demo_1_gradient/` | Autograd、`backward()`、梯度清零 |
| 3 | 线性回归 | `demo_2_linear_regression/` | $y=wx+b$ 完整训练流程 |
| 4 | 逻辑回归 | `demo_3_logic_regression/` | Sigmoid + BCE 二分类 |
| 5 | MNIST 手写数字识别 | `demo_MNIST/` | CNN 构建、训练、推理、自定义图片检测 |
| 8 | YOLOv5 目标检测 | `yolov5/` | 工业级检测框架使用与推理 |

---

## 待开发课程规划

### Lesson 6：彩色图像分类 — CIFAR-10

- **目标目录**: `demo_6_cifar10/`
- **前置知识**: Lesson 5 MNIST（已有 CNN 基础）
- **为什么需要这课**: MNIST 是灰度 28×28 小图，太简单；真实场景是彩色多类。本课填补灰度→彩色之间的能力断层。
- **要做什么**:
  1. 搭建 CNN 对 CIFAR-10（32×32 彩色，10 类）进行分类
  2. 实现数据增强（随机裁剪、水平翻转、颜色抖动）
  3. 对比有/无数据增强的训练效果
- **交付物**:
  - `cifar10_train.py` — 训练脚本（含数据增强）
  - `cifar10_eval.py` — 评估与可视化
- **核心知识点**:
  - RGB 3 通道输入 vs 灰度 1 通道的区别
  - 数据增强防止过拟合
  - Batch Normalization 的作用
  - 学习率调度（StepLR、CosineAnnealing）

### Lesson 7：迁移学习 — 预训练模型微调

- **目标目录**: `demo_7_transfer/`
- **前置知识**: Lesson 6 彩色图像分类
- **为什么需要这课**: 实际工程中几乎不会从零训练，都是拿预训练模型微调。这是从"学习"到"干活"的关键一步。
- **要做什么**:
  1. 用 torchvision 预训练的 ResNet18 微调 CIFAR-10
  2. 对比"从零训练" vs "微调"的精度和收敛速度
  3. 体验冻结层 vs 全量微调的差异
- **交付物**:
  - `transfer_cifar10.py` — 预训练 ResNet18 微调
  - `compare_train.py` — 从零 vs 微调对比实验
- **核心知识点**:
  - `torchvision.models` 预训练模型加载
  - 冻结 backbone、只训练分类头
  - 不同层学习率设置
  - 微调数据量对效果的影响

### Lesson 9：RNN/LSTM — 序列模型

- **目标目录**: `demo_9_rnn/`
- **前置知识**: Lesson 1-4 的训练循环基础
- **要做什么**:
  1. 用 `nn.RNN` 实现简单序列预测（如正弦波预测）
  2. 用 `nn.LSTM` 实现文本分类或情感分析
  3. 理解隐藏状态、时间步、序列输入输出
- **交付物**:
  - `sin_predict.py` — RNN 正弦波预测
  - `text_classify.py` — LSTM 文本分类
- **核心知识点**:
  - RNN 的梯度消失问题
  - LSTM 门控机制（forget/input/output gate）
  - 序列数据 vs 图像数据的维度差异

### Lesson 10：Transformer — 注意力机制

- **目标目录**: `demo_10_transformer/`
- **前置知识**: Lesson 9 的序列处理经验
- **要做什么**:
  1. 从零实现 Self-Attention 机制
  2. 搭建一个小型 Transformer 做序列到序列任务
  3. 理解位置编码、多头注意力
- **交付物**:
  - `self_attention.py` — 自注意力机制 demo
  - `mini_transformer.py` — 小型 Transformer 训练
- **核心知识点**:
  - Query / Key / Value 矩阵
  - Multi-Head Attention
  - Positional Encoding
  - Encoder-Decoder 结构

### Lesson 11：GAN — 生成对抗网络

- **目标目录**: `demo_11_gan/`
- **前置知识**: Lesson 5 的 CNN 基础（生成器/判别器都用卷积）
- **要做什么**:
  1. 实现 vanilla GAN 生成手写数字图片
  2. 可选：DCGAN（深度卷积 GAN）提升生成质量
  3. 观察训练过程中生成效果的变化
- **交付物**:
  - `gan_mnist.py` — 基于 MNIST 的 GAN 训练与生成
- **核心知识点**:
  - Generator vs Discriminator 的对抗训练
  - 训练不稳定的原因与技巧（标签平滑、梯度惩罚）
  - 生成质量评估（定性观察）

### Lesson 12：Autoencoder / VAE — 无监督学习与生成模型

- **目标目录**: `demo_12_ae_vae/`
- **前置知识**: Lesson 5 CNN 基础 + Lesson 11 GAN（对比理解）
- **为什么需要这课**: GAN 是"对抗"生成，AE/VAE 是"编码"生成，两条路线互补。同时覆盖无监督学习和降维能力。
- **要做什么**:
  1. 实现 Autoencoder 做 MNIST 压缩与重建
  2. 升级为 VAE，学会从潜在空间采样生成新图片
  3. 对比 AE vs VAE vs GAN 的生成效果
- **交付物**:
  - `autoencoder.py` — 自编码器（压缩 + 重建）
  - `vae_mnist.py` — 变分自编码器（生成新图片）
- **核心知识点**:
  - Encoder-Decoder 对称结构
  - 潜在空间（Latent Space）的概念
  - 重参数化技巧（Reparameterization Trick）
  - 无监督特征提取能力

### Lesson 13：模型部署 — 从训练到落地

- **目标目录**: `demo_13_deploy/`
- **前置知识**: Lesson 5 或 8 的已训练模型
- **要做什么**:
  1. 将 MNIST 模型导出为 ONNX 格式
  2. 用 TorchScript 导出并独立运行（脱离 Python）
  3. 了解部署推理的基本流程
- **交付物**:
  - `export_onnx.py` — 导出 ONNX 模型
  - `export_torchscript.py` — 导出 TorchScript 模型
- **核心知识点**:
  - `torch.onnx.export()` 的使用
  - `torch.jit.trace` / `torch.jit.script`
  - 训练模式 vs 推理模式的区别（`model.eval()`、`torch.no_grad()`）

---

## 开发优先级建议

```
优先级 1: Lesson 6  彩色图像分类   ← 填补灰度→彩色的能力断层
优先级 2: Lesson 7  迁移学习       ← 工程实战最常用，衔接 YOLOv5
优先级 3: Lesson 9  RNN/LSTM       ← 补齐序列处理能力
优先级 4: Lesson 10 Transformer    ← 当前主流架构，必须掌握
优先级 5: Lesson 11 GAN            ← 生成模型入门
优先级 6: Lesson 12 AE/VAE         ← 与 GAN 互补，无监督学习
优先级 7: Lesson 13 模型部署       ← 工程化收尾
```

## 环境信息

- **操作系统**: Windows
- **Python**: 3.8+
- **PyTorch**: 2.4.1+cpu（yolov5 环境）
- **conda 环境**: `yolov5_env`
