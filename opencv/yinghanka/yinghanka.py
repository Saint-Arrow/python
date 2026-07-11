import os
import cv2
import numpy as np

path = os.path.dirname(__file__)
os.chdir(path)
test_mode=1


#读取图片,cv2.IMREAD_GRAYSCALE可以只提取灰度信息
img = cv2.imread("yinghanka_2.jpg",cv2.IMREAD_GRAYSCALE)
img=cv2.GaussianBlur(img,(3,3),cv2.THRESH_BINARY_INV)
cv2.imshow("img",img)

#该银行卡的数字为黑色
ret, img=cv2.threshold(img,122,255,cv2.THRESH_BINARY_INV)

#开始形态学操作，弄出合适的图片，用于寻找轮廓
image=img
kernel = cv2.getStructuringElement(cv2.MORPH_RECT,(3,1))
image=cv2.dilate(image,kernel,iterations=10)
#image=cv2.erode(image,kernel,iterations=2)

kernel2 = cv2.getStructuringElement(cv2.MORPH_RECT,(1,3))
#image=cv2.dilate(image,kernel2,iterations=5)
#image=cv2.erode(image,kernel2,iterations=5)
cv2.imshow("image",image)

y_list=[]
img_cor=[]
image_rect_list=[] #用于保存数字块的图像列表

#选择合适的轮廓，该银行卡数字为4个1组,最后1组为3个，另外进行了膨胀和腐蚀 所以wh比例应该在2-5之间
contours, heirarchy=cv2.findContours(image,cv2.RETR_EXTERNAL ,cv2.CHAIN_APPROX_SIMPLE) 
#cv2.drawContours(image,contours,-1,(128,128,0),10)
#cv2.imshow("canny2",image)
for contour in reversed(contours):#倒序循环，默认的轮廓是从右往左的
    x,y,w,h = cv2.boundingRect( contour ) #外切矩形，这里暂时不考虑图片旋转的问题
    if(x > 0) and (h > 10) and (w>=2*h) and (w<=5*h):  
        #cv2.rectangle(img,(x,y),(x+w,y+h),(255,255,255),2)
        print(x,y,w,h)
        #这里我们看到出来了5+2个合适的矩形，多出来的2个是日期之类的WH也符合要求，但是我们可以看到这2类不是同一行的qq
        y_list.append(y)
        img_cor.append((x,y,w,h))
        
y_list.sort()
#这里我们直接取出列表的前5个，另外还有种做法应该也可以，就是求2阶导数，出现负的就是上升沿，代表另一个等级的数据
print("-------")
for img_c in img_cor:
    if(img_c[1]<=y_list[5]):
       x,y,w,h =img_c
       print(x,y,w,h)
       #cv2.rectangle(img,(x,y),(x+w,y+h),(255,255,255),2)
       image_digit_rect=np.zeros((w,h,1))
       image_digit_rect= img[y:y+h,x:x+w]  # 裁剪坐标为[y0:y1, x0:x1]
       image_rect_list.append(img[y:y+h,x:x+w])


def cut_img(img,digital_list):
    image=img #直接复制，为引用，会全局修改
    
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT,(2,1))
    #image=cv2.erode(image,kernel,iterations=2)
    #image=cv2.dilate(image,kernel,iterations=2)
    

    
    contours, heirarchy=cv2.findContours(image,cv2.RETR_EXTERNAL ,cv2.CHAIN_APPROX_SIMPLE) 
    #cv2.drawContours(image,contours,-1,(128,128,0),3)
    #cv2.imshow("canny2",image)
    for contour in reversed(contours):
        x,y,w,h = cv2.boundingRect( contour )
        #cv2.rectangle(image,(x,y),(x+w,y+h),(255,255,255),2)
        digital=np.zeros((w,h,1))
        digital= image[y:y+h,x:x+w]  # 裁剪坐标为[y0:y1, x0:x1]
        digital_list.append(digital)
        
    #cv2.imshow("rect",image)
    #cv2.waitKey(1000)
    #cv2.destroyWindow("rect") 


digital_list=[]
test=0
if test == 1:
    cut_img(image_rect_list[4],digital_list)
    print("111test")
else:
    for img_s in image_rect_list:
        cut_img(img_s,digital_list)
        
    cv2.waitKey(1000)
    for digital in digital_list:
        cv2.imshow("digital",digital)
        cv2.waitKey(500)
        cv2.destroyWindow("digital")
    
cv2.imshow("ori_img",img)
cv2.waitKey()
cv2.destroyAllWindows()
