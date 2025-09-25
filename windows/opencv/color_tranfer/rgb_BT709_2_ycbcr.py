import numpy as np

def rgb_2_YCbCr(ER,EG,EB):
    #y:0~1 cb/cr:-0.5~0.5
    EY=0.2126 *ER+0.7152*EG+0.0722*EB
    ECB=(EB-EY)/1.8556
    ECR=(ER-EY)/1.5748
    return np.array([EY,ECB,ECR])

if __name__ == "__main__":
    rgb=np.array([1,1,1]) 
    YCbCr=rgb_2_YCbCr(rgb[0],rgb[1],rgb[2])
    print(f"RGB值: {rgb}，对应的YCbCr坐标: {YCbCr}")
    rgb=np.array([1,0,0])    
    YCbCr=rgb_2_YCbCr(rgb[0],rgb[1],rgb[2])
    print(f"RGB值: {rgb}，对应的YCbCr坐标: {YCbCr}")
    rgb=np.array([0,1,0])    
    YCbCr=rgb_2_YCbCr(rgb[0],rgb[1],rgb[2])
    print(f"RGB值: {rgb}，对应的YCbCr坐标: {YCbCr}")
    rgb=np.array([0,0,1])    
    YCbCr=rgb_2_YCbCr(rgb[0],rgb[1],rgb[2])
    print(f"RGB值: {rgb}，对应的YCbCr坐标: {YCbCr}")   