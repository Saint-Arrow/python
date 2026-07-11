import os,time
devname="QAAMZ"
	
import winreg,string,os,time
from time import sleep

key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r"SYSTEM\CurrentControlSet\Services\usbccgp\Enum")

count =0
times=1
#获取该键的所有键值，因为没有方法可以获取键值的个数，所以只能用这种方法进行遍历
while 1:
	str1=""
	try:
		for i in range(0,100):
			#EnumValue方法用来枚举键值，EnumKey用来枚举子键
			name, value, type = winreg.EnumValue(key, i)
			str1=str1+"\r\n"+str(value)
	except WindowsError:
		i=0
	sleep(1)
	
	checkstr="VID_2E7E&PID_0201"
	count+=1
	print(str1)
	if  count==3 and str1.find(checkstr)>=0:
		main = "CommandApp_USBRelay.exe "+devname+" close 01"
		print(os.system(main))
		
	if  count==3 and str1.find(checkstr)<0:
		main = "CommandApp_USBRelay.exe "+devname+" open 01"
		print(os.system(main))
	if count==6 and str1.find(checkstr)<0:
		main = "CommandApp_USBRelay.exe "+devname+" open 01"
		print(os.system(main))
	# if count==20 and str1.find(checkstr)>=0:
	t = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime())
	if  count==20 and str1.find(checkstr)>=0:
		count=0
		main = "CommandApp_USBRelay.exe "+devname+" close 01"
		print(os.system(main))
		times+=1		
		file_handle=open('test.txt',mode='a+')
		file_handle.write("\n"+t+str.replace(str1,"\n","")+"----------------total times:"+str(times)+" "+str(count)+"----------------\n")
		file_handle.close()
	if  count>20 and str1.find(checkstr)<0:
		count=0
#		main = "CommandApp_USBRelay.exe "+devname+" close 01"
		print(os.system(main))
		times+=1		
		file_handle=open('error.txt',mode='a+')
		file_handle.write("\n"+t+str.replace(str1,"\n","")+"----------------total times:"+str(times)+" "+str(count)+"----------------\n")
		file_handle.close()
		break
	print("\ntotal times:",t,"\n",times,str(count)+"----------\n")
	
