# -*- coding: UTF-8 -*-
 
import numpy as np
import cv2
import matplotlib.pyplot as plt
import os
import copy
path = os.path.dirname(__file__)
os.chdir(path)


## 图片旋转
def rotate_bound(image, angle):
    #获取宽高
    (h, w) = image.shape[:2]
    (cX, cY) = (w / 2, h / 2)
    centor=(cX,cY) #旋转的中心点，设为图片的中心点
    # 提取旋转矩阵 sin cos ,该角度定义为逆时针
    M = cv2.getRotationMatrix2D(centor, angle, 1.0)
    
 
    # 计算图像的新边界尺寸，图像会变大的
    cos = np.abs(M[0, 0])
    sin = np.abs(M[0, 1])
    nW = int((h * sin) + (w * cos))
    nH = int((h * cos) + (w * sin))
  
 
    # 调整新的图像画布中心点
    M[0, 2] += (nW / 2) - cX
    M[1, 2] += (nH / 2) - cY
 
    return cv2.warpAffine(image, M, (nW, nH),flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
 
## 获取图片旋转角度
def get_minAreaRect(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    #gray = cv2.bitwise_not(gray)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    rect= cv2.minAreaRect(coords)
    cent,wh,angle_t=rect;

    box = cv2.boxPoints(rect)
    box = np.int0(box)
    cv2.drawContours(image, [box], 0, (255, 0, 0), 1)
    cv2.imshow("canny2",image)

    
    print(wh)
    print(angle_t)
    #角度定义为顺时针，且范围值为:[-90,0),为啥我测试的是个正的数值..
    #关于该角度的问题，参考如下:
    #https://blog.csdn.net/u010403272/article/details/78890410
    #https://blog.csdn.net/qq_24237837/article/details/77850496
    if(wh[0]<wh[1]):
        angle_t=(180-angle_t)
    else:
        angle_t=(90-angle_t)

    
    return angle_t 

def get_minAreaRect_2(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    image = cv2.threshold(gray, 0, 255,cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT,(3,3))
    image=cv2.dilate(image,kernel,iterations=10)
    image=cv2.erode(image,kernel,iterations=2)
    
    contours, heirarchy=cv2.findContours(image,cv2.RETR_EXTERNAL ,cv2.CHAIN_APPROX_SIMPLE) 
    cv2.drawContours(image,contours,-1,(128,128,0),3)
    #cv2.imshow("canny2",image)
    #for contour in contours:
        #x,y,w,h = cv2.boundingRect( contour ) 
        #cv2.rectangle(image,(x,y),(x+w,y+h),(255,255,255),2)
        
    
   
    
    rect= cv2.minAreaRect(contours[0])
    cent,wh,angle_t=rect;
    print(wh)
    print(angle_t)#这里获取的角度老是和上面的方法互补
    
    box = cv2.boxPoints(rect)
    box = np.int0(box)
    #cv2.drawContours(image, [box], 0, (255, 0, 0), 1)
    #cv2.imshow("canny2",image)
    
    if(wh[0]<wh[1]):
        angle_t=(90+angle_t)

  
    return angle_t;

 
image_path = "1.jpg"
image = cv2.imread(image_path)

img = cv2.imread(image_path,cv2.IMREAD_GRAYSCALE)
#直方图均衡化，重点需要理解,如下图可以看出不是万能的
img_eq=cv2.equalizeHist(img)
hist=cv2.calcHist([img_eq],[0],None,[256],[0,255])
#plt.hist(img_eq.ravel(),256)
#plt.show()
#cv2.imshow("input_eq", img_eq)


#旋转任意角度测试
image=rotate_bound(image,130)

image1=copy.deepcopy(image)
image2=copy.deepcopy(image)


angle1 = get_minAreaRect(image1)
rotated1 = rotate_bound(image1, angle1)
cv2.putText(rotated1, "angle: {:.2f} ".format(angle1),
    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
 
# show the output image
print("[INFO] angle: {:.3f}".format(angle1))
cv2.imshow("output", rotated1)

print("----------------------")
angle = get_minAreaRect_2(image)
rotated = rotate_bound(image, angle)
cv2.putText(rotated, "angle: {:.2f} ".format(angle),
    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
 
# show the output image
print("[INFO] angle: {:.3f}".format(angle))
cv2.imshow("output2", rotated)
#cv2.imwrite("output.jpg",rotated)





cv2.imshow("input", image)

cv2.waitKey(0)
cv2.destroyAllWindows()


