import os, time

import socket
import struct
import binascii

def udp_sendmsg(ip,port,str):
	client = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
	ip_port = (ip, port)
	str2=binascii.unhexlify(str)
	client.sendto(str2,ip_port)
	#client.sendto(b'hahaha',ip_port)
	
	#str = "B1C2FF82" #获取字符测
	#str1 = "" #初始化
	#str2 = "" #初始化
	#while str:
	#	str1 = str[0:2] #分割字符串，获取前两个字符
	#	s = int( str1, 16) #字符串转换成16进制
	#	str2 += struct.pack('B', s) #转换成字节流，“B“为格式符，代表一个unsigned char （具体请查阅struct）
	#	str = str[2:] #分割字符串，去掉字符串前两个字符
	



if "__main__" == __name__:
	t=0
	while 1==1:
		udp_sendmsg("192.168.13.159",1259,'8101040003ff')
		print("###:")
		time.sleep(5)
		udp_sendmsg("192.168.13.159",1259,'8101040002ff')
		print("##:")
		time.sleep(30)
    
	



