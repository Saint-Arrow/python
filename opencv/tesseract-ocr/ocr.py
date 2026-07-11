import cv2
import numpy as np
import os
from PIL import Image
import pytesseract


path = os.path.dirname(__file__)
os.chdir(path)

#img=cv2.imread("en.jpg")
text = pytesseract.image_to_string(Image.open("en.jpg"))
print(text)

