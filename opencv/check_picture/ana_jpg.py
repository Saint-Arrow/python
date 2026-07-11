import cv2
import numpy as np
import os
import sys
import math
import matplotlib.pyplot as plt
from numpy import *

def get_contour(file_name,test_mode):
    if test_mode == 1:
        print(file_name)
    try:
        image = cv2.imread(file_name,cv2.IMREAD_GRAYSCALE)
        ###################图像处理######################################
        #img = cv2.GaussianBlur(img,(3,3),0)
        mp=np.array(image)
        ret, image=cv2.threshold(image,mp.max()-20,255,0)
        image = image[0:200, 20:1900]  # 裁剪坐标为[y0:y1, x0:x1]
    except Exception as ret:
        print(ret)
        return False

    ###################边缘检测#######################################
    #第2个参数代表准确度阀值，只有高于第2个参数的直线的点才会被留下
    #第1个参数用于连接断断续续的线条
    canny=cv2.Canny(image,40,50)
    if test_mode == 1:
        cv2.imshow("canny",canny)

    ###################轮廓检测#######################################
    #ret, image = cv2.threshold(image, 127, 255, 0)
    contours, heirarchy=cv2.findContours(image,cv2.RETR_EXTERNAL ,cv2.CHAIN_APPROX_SIMPLE)
    if test_mode == 1:
        cv2.drawContours(image,contours,-1,(128,128,0),10)
        cv2.imshow("canny2",image)

    for contour in contours:
        min_x=1920
        max_x=0
        min_y=1080
        max_y=0
        for i,point in enumerate(contour):
            if point[0][0] < min_x:
                min_x=point[0][0]
            if point[0][0] > max_x:
                max_x=point[0][0]
            if point[0][1] < min_y:
                min_y=point[0][1]
            if point[0][1] > max_y:
                max_y=point[0][1]
        if (max_x-min_x) > 10 and  (max_y-min_y) > 10 :
            return min_x
        #print("%d----%d,%d,%d,%d" %(i,min_x,max_x,min_y,max_y))
            
    cv2.drawContours(image,contours,-1,(128,128,0),10)
    cv2.imshow("canny2",image)
    print(contours)
    
    return False

test_mode=0
file_start=1
file_list=file_start
ret = True
fig = plt.figure()
ax = fig.add_subplot(1,1,1)
x_point_list=[]
y_point_list=[]
while ret == True:
    file_name=str(file_list)+".jpg"
    res=get_contour(file_name,test_mode)
    if(type(res) == bool):
        ret = False
    else:
        print(res)
        y_point_list.append(res)
        x_point_list.append(file_list)
        file_list=file_list+1
        if test_mode == 1:
            ret = False
ax.plot(x_point_list,y_point_list)
plt.show()