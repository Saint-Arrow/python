import cv2
import numpy as np
import os
import re

def clean_picture():
    #clean all old picture
    dirs=os.listdir("./")
    pattern=r"\d+.jpg"
    for file in dirs:
        ma=re.match(pattern,file)
        if type(ma) == re.Match :
            os.remove(file)
    
def cut_picture():
    vc=cv2.VideoCapture("test2.mp4")
    #vc=cv2.VideoCapture("result.avi")
    c=1
    max_pic=int(255)
    if vc.isOpened():
      rval,frame=vc.read()
    else:
      rval=False

    while rval:
      rval,frame=vc.read()
      cv2.imwrite(str(c)+'.jpg',frame)
      #cv2.imwrite(str(c)+'.png',frame)
      c=c+1
      max_pic=max_pic-1
      print(max_pic)
      if max_pic == 0:
          rval = False

      #cv2.waitKey(1)
    vc.release()

if __name__=='__main__':
    clean_picture()
    cut_picture()