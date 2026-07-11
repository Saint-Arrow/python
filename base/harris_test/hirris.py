import cv2
import numpy as np

import os
path = os.path.dirname(__file__)
os.chdir(path)

# 读入图像并转化为float类型，用于传递给harris函数
img = cv2.imread("finger.jpeg")
gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
gray_img = np.float32(gray_img)
# 对图像执行harris
blockSize = 2     # 邻域半径
apertureSize = 3  # 邻域大小
Harris_detector = cv2.cornerHarris(gray_img, blockSize, apertureSize, 0.04)

cv2.imshow('Harris', Harris_detector)

# 腐蚀harris结果
dst = cv2.dilate(Harris_detector, None)
# 设置阈值
thres = 0.01 * dst.max()
img[dst > thres] = [255, 0, 0]


cv2.imshow('show', img)
cv2.waitKey()


