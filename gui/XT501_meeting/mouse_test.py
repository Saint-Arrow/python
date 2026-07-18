import os, time
import pyautogui

time.sleep(10)

if "__main__" == __name__:
	t=0
	while 1==1:
        #本端挂断以及其他提示
		pyautogui.click(1136, 164,button='left')
        #上会
		time.sleep(1)
		pyautogui.click(1256, 246,button='left')
		time.sleep(10)
        
        
		#挂断
		time.sleep(1)
		pyautogui.click(1386, 448,button='left')
		time.sleep(1)
		pyautogui.click(1062, 166,button='left')
		time.sleep(3)
        #本端挂断以及其他提示
		pyautogui.click(1136, 164,button='left')
        #挂断
		time.sleep(1)
		pyautogui.click(1386, 448,button='left')
		time.sleep(1)
		pyautogui.click(1062, 166,button='left')
		time.sleep(3)
        #本端挂断以及其他提示
		pyautogui.click(1136, 164,button='left')
	


