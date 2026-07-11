import os,time,vlc
import serial
#from VideoCapture import Device
devname="QAAMZ"
host="192.168.12.98"
count =0
times=1
def CaptureImg1(filename="1.jpg",devnum=0):
	cam = Device(devnum,1)
	flagsuc=False
	for i in range(0,100):
		print(i)
		try:
			cam.saveSnapshot(filename, quality=100, timestamp=0)
			k = os.path.getsize(t+'A.jpg')
			print(k)
			if k==33272:#or k == 97848:
				cam.saveSnapshot(filename, quality=100, timestamp=0)
			else:
				flagsuc=True
		except:
			print("error!")
		if flagsuc==True:
			break
		if i==99:
			while(1):
				print("截图失败")
				time.sleep(10)
def CaptureImg2(filename="2.jpg",devnum=1):
	cam = Device(devnum,1)
	flagsuc=False
	for i in range(0,100):
		print(i)
		try:
			cam.saveSnapshot(filename, quality=100, timestamp=0)
			k = os.path.getsize(t+'B.jpg')
			print(k)
			if k==33272:#or k == 97848:
				cam.saveSnapshot(filename, quality=100, timestamp=0)
			else:
				flagsuc=True
		except:
			print("error!")
		if flagsuc==True:
			break
		if i==99:
			while(1):
				print("截图失败")
				time.sleep(10)
def VLCCapImg(ip):
	flagsuc=False
	player=vlc.MediaPlayer('rtsp://'+str(ip))
	player.play()
	time.sleep(3)
	for i in range(0,100):
		print(i)
		print(os.getcwd()+"\\"+ip+t+'.jpg')
		player.video_take_snapshot(0, os.getcwd()+"\\"+ip+t+'.jpg', 0, 0)
		k = os.path.getsize(ip+t+'.jpg')
		print(k)
		if k<300000:
			player.stop()
			player=vlc.MediaPlayer('rtsp://'+str(ip))
			player.play()
			time.sleep(3)
			print(os.getcwd()+"\\"+ip+t+'.jpg')
			player.video_take_snapshot(0, os.getcwd()+"\\"+ip+t+'.jpg', 0, 0)
			k = os.path.getsize(ip+t+'.jpg')
		else:
			flagsuc=True
		time.sleep(3)
		player.stop()
		if flagsuc==True:
			break
		if i==99:
			while(1):
				print("截图失败")
				time.sleep(120000)
def potplayerimg(ip):
	autoit.run(r"C:\Program Files\DAUM\PotPlayer\PotPlayerMini.exe")
	time.sleep(3)
	autoit.win_activate('PotPlayer')
	autoit.send('^u',mode=0)
	time.sleep(2)
	autoit.win_activate('请输入地址。')
	autoit.send('rtsp://'+str(ip)+'/1')
	time.sleep(2)
	autoit.win_activate('请输入地址。')
	autoit.send('{ENTER}')
	time.sleep(12)
	autoit.win_activate('1 - PotPlayer')
	autoit.send('^e',mode=0)
	time.sleep(2)
	autoit.win_close('1 - PotPlayer')


flagsuc=True
while 1:
	time.sleep(1)
	count+=1
	t = time.strftime('%Y-%m-%d_%H%M%S',time.localtime())
	if count==2:
		main = ".\CommandApp_USBRelay.exe "+devname+" close 01"
		print(os.system(main))
		main = ".\CommandApp_USBRelay.exe "+devname+" close 02"
		print(os.system(main))
		time.sleep(1)
		main = ".\CommandApp_USBRelay.exe "+devname+" open 01"
		print(os.system(main))
		main = ".\CommandApp_USBRelay.exe "+devname+" open 02"
		print(os.system(main))
	if count==18:
		#VLCCapImg(t+"A.jpg")
		#potplayerimg("192.168.12.98")
		p = os.popen("ping "+ host + " -n 2")
		line = p.read()
		if "无法访问目标主机" in line:
			print("ping fail")
		elif "请求超时" in line:
			print("ping fail11")
		elif "一般故障" in line:
			print("ping fail22")
		else:
			print("ping ok")
			count=0
			times+=1
	print("\ntotal times:",t,"\n",times,str(count)+"----------\n")
