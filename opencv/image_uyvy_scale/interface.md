## 接口定义

## 1. 命令行接口（CLI）

### 1.1 命令格式

```bash
python uyvy_scale.py -i in_uyvy.bin -s 3840x2160 -o out_uyvy.bin
```

### 1.2 参数说明
- `-i, --input`：输入 UYVY422（packed）原始文件路径（必填）
- `-s, --size`：输入分辨率，格式为 `WxH`（必填），例如 `3840x2160`
- `-o, --output`：输出文件路径（可选），默认 `out_uyvy.bin`
- `-d, --debug`：调试坐标字符串（可选），例如 `0x0`
  - 含义：打印输入图像中坐标 `(x, y)` 处对应的 UYVY 数据
  - 行为：**启用后不进行缩放**，只打印数据并退出（不写 `out_uyvy.bin`）

### 1.3 退出码/错误信息约定（建议）
- 参数格式错误、分辨率非法、文件大小不匹配等情况：打印明确错误信息并退出（非 0 退出码）。

## 2. 代码接口（Python 函数）

### 2.1 分辨率解析

```python
def parse_resolution(size: str) -> tuple[int, int]:
    """将 '3840x2160' 解析为 (3840, 2160)。非法格式抛 ValueError。"""
```

### 2.2 调试坐标解析（可选）

```python
def parse_debug_pos(pos: str) -> tuple[int, int]:
    """将 '0x0' 解析为 (0, 0)。非法格式抛 ValueError。"""
```

### 2.3 输入读取与校验

```python
def read_uyvy422(path: str, width: int, height: int) -> bytes:
    """
    读取 UYVY422 packed 原始数据。
    校验数据长度 == width * height * 2；不通过则抛 ValueError / IOError。
    """
```

### 2.4 调试打印（不缩放）

```python
def dump_uyvy_at(src: bytes, width: int, height: int, x: int, y: int) -> None:
    """
    打印坐标 (x, y) 所在的 UYVY422 packed 采样组（4 字节）：U, Y0, V, Y1。
    说明：
      - UYVY 是每 2 像素一组；若 x 为奇数，仍会打印其所在的“那一组”(x-1, x)。
    """
```

### 2.5 缩放核心（输出宽高各减半）

```python
def scale_uyvy422_half(src: bytes, width: int, height: int) -> bytes:
    """
    输入:
      - src: UYVY422 packed, 分辨率 width x height
    输出:
      - UYVY422 packed, 分辨率 (width//2) x (height//2)
    规则（按 2x2 像素块）:
      - Y: 取 4 个 Y 的平均值
      - U: 取上下两行对应的 2 个 U 的平均值
      - V: 取上下两行对应的 2 个 V 的平均值
    约束:
      - width 必须为偶数
      - width 与 height 必须能被 2 整除
    """
```

### 2.6 输出写入

```python
def write_bin(path: str, data: bytes) -> None:
    """将二进制数据写出到 path。"""
```

## 3. 数据格式约定（UYVY422 packed）

### 3.1 输入布局
- 每 2 个像素占 4 字节：`U0 Y0 V0 Y1`
- 每行按 `width` 像素连续存储（默认无额外 stride/padding）
- 输入总字节数应为：`width * height * 2`

### 3.2 输出布局
- 输出仍为 UYVY422 packed
- 输出分辨率为：`(width//2) x (height//2)`
- 输出总字节数应为：`(width//2) * (height//2) * 2`

