# -*- coding: utf-8 -*-
'''
基于 vlc_reboot.py 改写: 拉取 RTSP 流的音频数据, 保存为裸 PCM(s16le) 文件
用法:
    python vlc_audio_pcm.py [录制秒数, 默认30] [ip, 默认192.168.13.169]
输出:
    output/<ip>_audio_<时间戳>.pcm   (s16le / 48000Hz / 2ch, 可在下方配置)
试听:
    ffplay -f s16le -ar 48000 -ch_layout stereo -i xxx.pcm
原理:
    方案1: 给 libvlc 设置音频回调(audio_set_callbacks + audio_set_format),
           VLC 解码并重采样后的音频数据直接推给本脚本写入文件, 不经过声卡
    方案2(fallback): 老 python-vlc 不支持回调时, 用 VLC 转码成 wav 再剥掉文件头
'''
import os, sys, time, ctypes, wave

path = os.path.dirname(os.path.abspath(__file__))
os.chdir(path)  # 让脚本目录下的 libvlc.dll 能被找到(与 vlc_reboot.py 保持一致)
os.environ['PYTHON_VLC_MODULE_PATH'] = path
_libvlc = os.path.join(path, 'libvlc.dll')
if os.path.exists(_libvlc):
    os.environ['PYTHON_VLC_LIB_PATH'] = _libvlc

import vlc

# ---------------- 配置 ----------------
IP          = "192.168.13.169"
RTSP_URL    = "rtsp://" + IP + "/1"   # 与 vlc_reboot.py 相同的拉流地址, 按需修改
RECORD_SEC  = 30        # 录制时长(秒)
SAMPLE_RATE = 48000     # 输出 PCM 采样率
CHANNELS    = 2         # 输出 PCM 声道数: 1=mono 2=stereo
USE_TCP     = True      # RTSP 走 TCP 传输, 取数据更稳(不会 UDP 丢包)

if len(sys.argv) > 1:
    RECORD_SEC = int(sys.argv[1])
if len(sys.argv) > 2:
    RTSP_URL = "rtsp://" + sys.argv[2] + "/1"

out_dir  = os.path.join(path, "output")
os.makedirs(out_dir, exist_ok=True)
pcm_path = os.path.join(out_dir, "%s_audio_%s.pcm" % (RTSP_URL.split('/')[2],
                                                      time.strftime("%Y%m%d_%H%M%S")))

# ---------------- 音频采集回调 ----------------
pcm_file     = open(pcm_path, "wb")
total_frames = [0]      # 累计采样帧数(1帧 = 每声道各1个采样)

def _audio_play(user_data, samples, count, pts):
    # VLC 解码并重采样后的音频数据从这里推过来; count 是每声道的采样数
    try:
        if samples and count:
            nbytes = count * CHANNELS * 2    # s16 => 每采样2字节
            pcm_file.write(ctypes.string_at(samples, nbytes))
            total_frames[0] += count
    except Exception:
        pass   # C 回调里不能向上抛异常

def _audio_flush(user_data, pts):
    try: pcm_file.flush()
    except Exception: pass

def _audio_drain(user_data):
    try: pcm_file.flush()
    except Exception: pass

# 用 ctypes 包装成 C 回调; 包装后的对象必须保持引用(全局变量),
# 否则被 Python GC 回收后 VLC 再调用回调会直接崩溃
_AudioPlayCbT  = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_uint, ctypes.c_int64)
_AudioFlushCbT = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int64)
_AudioDrainCbT = ctypes.CFUNCTYPE(None, ctypes.c_void_p)
audio_play_cb  = _AudioPlayCbT(_audio_play)
audio_flush_cb = _AudioFlushCbT(_audio_flush)
audio_drain_cb = _AudioDrainCbT(_audio_drain)

def on_playing(event, user_data):
    user_data[0] = 1

# ---------------- 方案1: 音频回调直取 PCM ----------------
def record_with_callbacks():
    instance = vlc.Instance("--no-video-title-show", "--no-xlib")
    player   = instance.media_player_new()
    media    = instance.media_new(RTSP_URL)
    if USE_TCP:
        media.add_option(":rtsp-tcp")
    media.add_option(":no-video")          # 只取音频, 不解码视频
    player.set_media(media)

    # 必须在 play() 之前设置; S16N = 16bit 本机字节序(Windows 小端 = s16le)
    player.audio_set_callbacks(audio_play_cb, None, None,
                               audio_flush_cb, audio_drain_cb, None)
    player.audio_set_format("S16N", SAMPLE_RATE, CHANNELS)

    status = [0]
    player.event_manager().event_attach(vlc.EventType.MediaPlayerPlaying,
                                        on_playing, status)

    print("try to get rtsp audio: " + RTSP_URL)
    player.play()

    for _ in range(15):                    # 最多等 15 秒起流
        time.sleep(1)
        if status[0]:
            break
    if not status[0]:
        print("ERROR: rtsp stream not playing in 15s")
        player.stop()
        pcm_file.close()
        return False

    print("vlc stream ok, recording %ds ..." % RECORD_SEC)
    t0 = time.time()
    while time.time() - t0 < RECORD_SEC:
        if player.get_state() == vlc.State.Ended:
            print("stream ended early")
            break
        time.sleep(1)
        print("  %4ds/%ds  got %.2fs audio" % (time.time() - t0, RECORD_SEC,
                                                total_frames[0] / float(SAMPLE_RATE)))

    player.stop()
    time.sleep(0.5)                        # 等 flush/drain 回调收尾
    pcm_file.close()
    return True

# ---------------- 方案2(fallback): VLC 转码成 wav 再剥头 ----------------
def record_with_sout():
    print("fallback: transcode to wav then strip header")
    wav_path = pcm_path + ".tmp.wav"
    dst      = wav_path.replace("\\", "/")
    instance = vlc.Instance("--no-video-title-show", "--no-xlib")
    media    = instance.media_new(RTSP_URL)
    if USE_TCP:
        media.add_option(":rtsp-tcp")
    media.add_option(":no-sout-video")
    media.add_option(":sout=#transcode{acodec=s16l,channels=%d,samplerate=%d}"
                     ":standard{access=file,mux=wav,dst=\"%s\"}"
                     % (CHANNELS, SAMPLE_RATE, dst))
    player = instance.media_player_new()
    player.set_media(media)
    player.play()
    time.sleep(3 + RECORD_SEC)
    player.stop()
    time.sleep(1)

    with open(pcm_path, "wb") as f:        # wav 去头 -> 裸 pcm
        w = wave.open(wav_path, "rb")
        f.write(w.readframes(w.getnframes()))
        w.close()
    os.remove(wav_path)
    total_frames[0] = os.path.getsize(pcm_path) // (CHANNELS * 2)
    return True

if __name__ == "__main__":
    ok = False
    try:
        ok = record_with_callbacks()
    except Exception as e:
        print("callback mode failed: " + str(e))
    if not ok:
        try:
            ok = record_with_sout()
        except Exception as e:
            print("sout mode failed: " + str(e))

    if ok and total_frames[0] > 0:
        print("=" * 60)
        print("pcm file : " + pcm_path)
        print("format   : s16le, %d Hz, %d ch" % (SAMPLE_RATE, CHANNELS))
        print("duration : %.2f s (%d frames)" % (total_frames[0] / float(SAMPLE_RATE),
                                                  total_frames[0]))
        print("size     : %d bytes" % os.path.getsize(pcm_path))
        print("check    : ffplay -f s16le -ar %d -ch_layout %s -i \"%s\""
              % (SAMPLE_RATE, "stereo" if CHANNELS == 2 else "mono", pcm_path))
    else:
        print("no audio data captured (stream has no audio track?)")
