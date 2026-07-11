import os, time

#方法1：直接指定库
#os.environ['PYTHON_VLC_LIB_PATH']='C:\\Users\Acer\Desktop\python_vlc_test\libvlc.dll'
#方法2：指定模块路径
#os.environ['PYTHON_VLC_MODULE_PATH']='C:\\Users\\Acer\\Desktop\\test\python_vlc_test'
#os.environ['PATHON_VLC_MODULE_PATH']="D:\\WORK\\VHD_CWJ_File\\tool\\python\\python_vlc_test"
#trust_path = os.environ.get('PYTHON_VLC_MODULE_PATH', None)
#os.add_dll_directory(trust_path);

import vlc
ip_list=[
"192.168.12.108",
"192.168.12.134",
"192.168.12.133",
]
ip_res=[]
import time

class Player:
    '''
        args:设置 options
    '''
    def __init__(self, *args):
        if args:
            instance = vlc.Instance(*args)
            self.media = instance.media_player_new()
        else:
            self.media = vlc.MediaPlayer()

    # 设置待播放的url地址或本地文件路径，每次调用都会重新加载资源
    def set_uri(self, uri):
        self.media_option=self.media.set_mrl(uri)

    # 播放 成功返回0，失败返回-1
    def play(self, path=None):
        if path:
            self.set_uri(path)
            #self.media_option.add_option(":rtsp-tcp")
            return self.media.play()
        else:
            return self.media.play()

    # 暂停
    def pause(self):
        self.media.pause()

    # 恢复
    def resume(self):
        self.media.set_pause(0)

    # 停止
    def stop(self):
        self.media.stop()

    # 释放资源
    def release(self):
        return self.media.release()

    # 是否正在播放
    def is_playing(self):
        return self.media.is_playing()
		


    # 已播放时间，返回毫秒值
    def get_time(self):
        return self.media.get_time()

    # 拖动指定的毫秒值处播放。成功返回0，失败返回-1 (需要注意，只有当前多媒体格式或流媒体协议支持才会生效)
    def set_time(self, ms):
        return self.media.get_time()

    # 音视频总长度，返回毫秒值
    def get_length(self):
        return self.media.get_length()

    # 获取当前音量（0~100）
    def get_volume(self):
        return self.media.audio_get_volume()

    # 设置音量（0~100）
    def set_volume(self, volume):
        return self.media.audio_set_volume(volume)

    # 返回当前状态：正在播放；暂停中；其他
    def get_state(self):
        state = self.media.get_state()
        if state == vlc.State.Playing:
            return 1
        elif state == vlc.State.Paused:
            return 0
        else:
            return -1

    # 当前播放进度情况。返回0.0~1.0之间的浮点数
    def get_position(self):
        return self.media.get_position()

    # 拖动当前进度，传入0.0~1.0之间的浮点数(需要注意，只有当前多媒体格式或流媒体协议支持才会生效)
    def set_position(self, float_val):
        return self.media.set_position(float_val)

    # 获取当前文件播放速率
    def get_rate(self):
        return self.media.get_rate()

    # 设置播放速率（如：1.2，表示加速1.2倍播放）
    def set_rate(self, rate):
        return self.media.set_rate(rate)

    # 设置宽高比率（如"16:9","4:3"）
    def set_ratio(self, ratio):
        self.media.video_set_scale(0)  # 必须设置为0，否则无法修改屏幕宽高
        self.media.video_set_aspect_ratio(ratio)

    # 注册监听器
    def add_callback(self, event_type, callback,user_data):
        self.media.event_manager().event_attach(event_type, callback,user_data)

    # 移除监听器
    def remove_callback(self, event_type, callback,user_data):
        self.media.event_manager().event_detach(event_type, callback,user_data)

    def take_snapshot(self, *args):
        self.media.video_take_snapshot(*args)
    def audio_get_delay(self):
        return self.media.audio_get_delay()
    def video_get_width(self):
        return self.media.video_get_width()
    def video_get_height(self):
        return self.media.video_get_height()

def my_call_back1(event,user_data):
    user_data.append(True)
    print("###:111 "+ str(user_data)+str(id(user_data)))

	
def my_call_back2(event,user_data):
    end=time.perf_counter()
    print("###:222 "+ str(end-start))
	
def my_call_back3(event,user_data):
    end=time.perf_counter()
    print("###:333 "+ str(end-start))
	
def mkdir(path):
    # 引入模块
    import os
 
    # 去除首位空格
    path=path.strip()
    # 去除尾部 \ 符号
    path=path.rstrip("\\")
 
    # 判断路径是否存在
    # 存在     True
    # 不存在   False
    isExists=os.path.exists(path)
 
    # 判断结果
    if not isExists:
        # 如果不存在则创建目录
        # 创建目录操作函数
        os.makedirs(path) 
 
        print (path+' 创建成功')
        return True
    else:
        # 如果目录存在则不创建，并提示目录已存在
        print (path+' 目录已存在')
        return False


	
if "__main__" == __name__:
    
    t=0
	
    mkdir(".\\output")
    player = Player()  
    for ip in ip_list:
        print ("vlc loop test ip:"+ip)
        start=time.perf_counter()
        status_list=[]
		
        player.add_callback(vlc.EventType.MediaPlayerPlaying, my_call_back1,status_list)
        player.add_callback(vlc.EventType.MediaPlayerEncounteredError, my_call_back2,1)
        player.play("rtsp://"+ip+"/1")

        time.sleep(3)
        player.take_snapshot(0,os.getcwd()+"\\output\\"+ip+".jpg",1280,720)
        time.sleep(1)
        player.stop()
        

        if True in status_list:
            ip_res.append(True)
        else:
            ip_res.append(False)
			
			
			
    player.release()
    print ("vlc loop test finish")
    for index in range(len(ip_list)):
        print (ip_list[index],end=' ') 
        print (ip_res[index])


