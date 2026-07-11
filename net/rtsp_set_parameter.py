import socket,select,sys

ip='10.10.10.202'
sid="1"
res=360
fps=30
rate=2000

if(len(sys.argv)<=3):
    print("param:  sid res fps rate")
    exit(-1)

arg_sid = int(sys.argv[1])
arg_res = int(sys.argv[2])
arg_fps = int(sys.argv[3])
arg_rate = int(sys.argv[4])

if arg_sid >= 1 and arg_sid <= 4:
    sid = str(arg_sid)

if arg_res in (1080,720,540,360,180):
    res = arg_res

if arg_fps >= 1 and arg_fps <= 30:
    fps = arg_fps

height=res
width=0
if height ==  1080:
    width = 1920
elif height ==  720:
    width = 1280
elif height ==  540:
    width = 960
elif height ==  360:
    width = 640
elif height ==  180:
    width = 320

if arg_rate >= 10 and arg_rate <= 10000:
    rate = arg_rate

ipaddr = (ip,554)
sock = socket.socket()

try:
    sock.connect(ipaddr)
except Exception as e:
    print(e)
    exit(0)

msg = """SET_PARAMETER rtsp://__IPADDR/__SID RTSP/1.0\r
CSeq:1\r
Content-type: application/sdp\r
\r
profile: svc-t\r
width: __W\r
height: __H\r
framerate: __FPS\r
gop: 90\r
codec: h264\r
bitrate: __RATE\r
keyframe: true\r
ratecontrol: cbr\r
\r
"""

msg =msg.replace('__W',str(width)).replace('__H',str(height)) \
        .replace('__RATE',str(rate)).replace('__FPS',str(fps)) \
        .replace('__IPADDR',ip).replace('__SID',sid)

print(">" * 20)
print(msg)
# print(msg.encode())
sock.send(msg.encode())

r_inputs = [sock]

try:
    r_list, w_list, e_list = select.select(r_inputs, [], [], 3)
    if len(r_list) > 0:
        for s in r_list:
            print("<" * 20)
            data = s.recv(1024)
            # print(data)
            print(data.decode())
except Exception as e:
    print(e)

sock.close()