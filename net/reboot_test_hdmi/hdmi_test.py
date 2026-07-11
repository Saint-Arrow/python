import os, time

ip="192.168.13.168"
t=0
output_dir=".\\output_"+ip

import socket
import binascii

def udp_sendmsg(ip, port, msg):
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ip_port = (ip, port)
    data = binascii.unhexlify(msg)
    client.sendto(data, ip_port)
    client.close()

def time_wait(timeout):
    for i in range(timeout, 0, -1):
        time.sleep(1)
        print(i, "s...")

#os.system(r'start /d"D:\upgrade v2.8" upgrade.exe')
path = os.path.dirname(__file__)
os.chdir(path)
os.makedirs(output_dir, exist_ok=True)



while True:
    os.system(r'ffmpeg -f gdigrab -framerate 10 -i desktop -frames:v 1 -y ' + os.path.join(output_dir, f"{t:04d}.jpg"))
    t = t + 1
    time.sleep(2)

    udp_sendmsg(ip, 1259, '8101040003ff')
    time_wait(2)
    udp_sendmsg(ip, 1259, '8101040002ff')
    time_wait(80)
