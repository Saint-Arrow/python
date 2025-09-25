import numpy as np

# 定义XYZ到xy的转换函数
def XYZ_to_Yxy(xyz):
    x, y, z = xyz
    sum_xyz = x + y + z
    if sum_xyz == 0:
        return 0, 0
    return y,x / sum_xyz, y / sum_xyz

def cie1931_rgb_2_xy(M,rgb):
    xyz=np.dot(M, rgb)
    # 转换为xy坐标
    Yxy = XYZ_to_Yxy(np.array(xyz).flatten())
    return Yxy
    


# 已知xyz在rg坐标系中的坐标
a=np.mat([[1.275,-0.278,0.003],[-1.739,2.767,-0.028],[-0.743,0.141,1.602]])
#计算 RGB转XYZ的矩阵
rgb2XYZ=np.linalg.inv(a.T)
#print(f"rgb2XYZ:{rgb2XYZ}")

#计算归一化系数，根据等能白光的坐标不变以及Y不变
white=np.array([1,1,1])
whiteM=np.dot(rgb2XYZ,white)
print(f"whiteM:{whiteM}")
k0=whiteM[0,1]/whiteM[0,0]
k1=1
k2=whiteM[0,1]/whiteM[0,2]
k=np.mat([[k0,0,0],[0,k1,0],[0,0,k2]])
print(f"k: {k}")

res=np.dot(k,rgb2XYZ)
print(f"res: {res}")


if __name__ == "__main__":
    rgb=np.array([1,1,1]) 
    Yxy=cie1931_rgb_2_xy(res,rgb)
    print(f"RGB值: {rgb}，对应的CIE 1931 Yxy坐标: {Yxy}")
    rgb=np.array([1.275,-0.278,0.003])    
    Yxy=cie1931_rgb_2_xy(res,rgb)
    print(f"RGB值: {rgb}，对应的CIE 1931 Yxy坐标: {Yxy}")
    rgb=np.array([-1.739,2.767,-0.028])    
    Yxy=cie1931_rgb_2_xy(res,rgb)
    print(f"RGB值: {rgb}，对应的CIE 1931 Yxy坐标: {Yxy}")
    rgb=np.array([1,0,0])    
    Yxy=cie1931_rgb_2_xy(res,rgb)
    print(f"RGB值: {rgb}，对应的CIE 1931 Yxy坐标: {Yxy}")
    rgb=np.array([0,1,0])    
    Yxy=cie1931_rgb_2_xy(res,rgb)
    print(f"RGB值: {rgb}，对应的CIE 1931 Yxy坐标: {Yxy}")