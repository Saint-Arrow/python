import numpy as np

# 定义RGB到XYZ的转换矩阵,accord to rgb_BT709_M.py
M = np.array([
    [0.4124564, 0.3575761, 0.1804375],
    [0.2126729, 0.7151522, 0.0721750],
    [0.0193339, 0.1191920, 0.9503041]
])

# 定义Gamma校正函数
def srgb_to_linear(srgb):
    return np.where(srgb <= 0.018, srgb /4.5, ((srgb + 0.099) / 1.099) ** 2.22)


# 定义XYZ到xy的转换函数
def xyz_to_Yxy(xyz):
    x, y, z = xyz
    sum_xyz = x + y + z
    if sum_xyz == 0:
        return 0, 0
    return y,x / sum_xyz, y / sum_xyz


def bt709_rgb_2_xy(rgb,gamma_enable=False):
    if gamma_enable:
        rgb = srgb_to_linear(rgb)

    xyz=np.dot(M, rgb)
    
    # 转换为xy坐标
    Yxy = xyz_to_Yxy(xyz)
    return Yxy


if __name__ == "__main__":
    adjusted_rgb=np.array([1, 0, 0])  # 示例RGB值
    Yxy = bt709_rgb_2_xy(adjusted_rgb)
    print(f"RGB值: {adjusted_rgb}，对应的CIE 1931 Yxy坐标: {Yxy}")
    adjusted_rgb=np.array([0, 1, 0])  # 示例RGB值
    Yxy = bt709_rgb_2_xy(adjusted_rgb)
    print(f"RGB值: {adjusted_rgb}，对应的CIE 1931 Yxy坐标: {Yxy}")
    adjusted_rgb=np.array([0, 0, 1])  # 示例RGB值
    Yxy = bt709_rgb_2_xy(adjusted_rgb)
    print(f"RGB值: {adjusted_rgb}，对应的CIE 1931 Yxy坐标: {Yxy}")
    adjusted_rgb=np.array([1, 1, 1])  # 示例RGB值
    Yxy = bt709_rgb_2_xy(adjusted_rgb)
    print(f"RGB值: {adjusted_rgb}，对应的CIE 1931 Yxy坐标: {Yxy}")