
import cv2
import numpy as np
import os

path = os.path.dirname(__file__)
os.chdir(path)


#读取图片,cv2.IMREAD_GRAYSCALE可以只提取灰度信息
img = cv2.imread("colorCheck.jpg")
img=cv2.resize(img,(800,800))
#shape函数返回图片信息，如果是灰度图片，那返回值只有行和列的元祖，否则，还会返回通道数
info=img.shape
#提取指定通道的数据，b=cv2.split(img)[0]
b,g,r=cv2.split(img)
#通道数据重新合并
img2=cv2.merge([r,g,b])
#像素级别的操作，用于roi的提取以及图片叠加
face=np.ones((101,101,3))
face=img[100:200,200:300]
img[200:300,300:400]=face
#图象加法，注意numpy的加法越界之后是取模，cv2.add是数据大于255，就=255
img3=cv2.add(img,img)
#图像融合,addWeighted
img_back=cv2.imread("0.jpg")
#resize函数控制缩放，指定大小或者指定xy方向的缩放系数，最后还可以选择插值算法
img_back=cv2.resize(img_back,(800,800))
img4=cv2.addWeighted(img,0.1,img_back,0.8,0)


cv2.imshow("test",img4)
cv2.waitKey()
cv2.destroyAllWindows()
