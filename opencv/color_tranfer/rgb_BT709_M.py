import numpy as np


def rgb_2_Yxy(M,rgb):
    Yxy=np.dot(M, rgb)
    return Yxy

def Yxy_2_XYZ(Yxy):
    Y,x,y=Yxy
    X=x*Y/y
    Z=(1-x-y)*Y/y
    return np.array([X,Y,Z])
def XYZ_2_Yxy(XYZ):
    X,Y,Z=XYZ
    x=X/(X+Y+Z)
    y=Y/(X+Y+Z)
    return np.array([Y,x,y])




rgb=np.mat([[1,0,0],[0,0,1],[0,0,1]])
rgb=rgb.T #转置，变成列向量,但是本质上就是单位矩阵，所以转置依旧是档位矩阵 

#EY=0.2126 *ER+0.7152*EG+0.0722*EB
XYZ_R=Yxy_2_XYZ([0.2126,0.64,0.33])
XYZ_G=Yxy_2_XYZ([0.7152,0.3,0.6])
XYZ_B=Yxy_2_XYZ([0.0722,0.15,0.06])
XYZ=np.mat([XYZ_R,XYZ_G,XYZ_B])
XYZ=XYZ.T

# M * rgb = M = XYZ
M=XYZ
print(f"M:{M}")
res=M


if __name__ == "__main__":
    rgb=np.mat([[1,1,1]]) 
    Yxy=XYZ_2_Yxy(np.dot(res,rgb.T))
    print(f"RGB值: {rgb}，对应的CIE 1931 Yxy坐标: {Yxy}")
 