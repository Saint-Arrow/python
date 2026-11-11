# -*- coding: utf-8 -*-
"""VLC 拉流采集测试(JPG 截图 + PCM 录音) —— "脚本即插件"（一份代码，两种用法）

整合 vlc_reboot.py(视频快照 JPG) 与 vlc_audio_pcm.py(音频裸 PCM) 两个脚本:
一次拉取指定摄像机 RTSP 流, 同时产出
  1) 视频快照  <ip>_snapshot_<时间戳>.jpg   (video_take_snapshot)
  2) 音频录音  <ip>_audio_<时间戳>.pcm      (s16le / 采样率 / 声道数可配)
音频优先走 VLC 音频回调(audio_set_callbacks)直取解码重采样后的数据;
老 python-vlc 不支持回调时自动 fallback 为转码 wav 再剥文件头。

用法 1：单独运行
    python vlc_capture_test.py
    python vlc_capture_test.py --ip 192.168.13.169 --record 10

用法 2：被测试平台挂载
    test_platform/platform.json 的 "plugins" 登记本文件路径,
    平台启动时自动 import 本文件, @register 的类即出现在 UI 测试项列表。

约束：平台加载本文件时只做类注册、不执行动作(顶层无副作用, 不 chdir,
     vlc 的环境变量设置与 import 延迟到 run() 内)。
"""

import ctypes
import os
import sys
import time
import wave

# ---- sys.path: 独立运行时把 test_platform 根目录加入；被平台加载时幂等 ----
_HERE = os.path.dirname(os.path.abspath(__file__))
_PLATFORM = os.path.normpath(os.path.join(_HERE, "..", "..", "test_platform"))
if os.path.isdir(_PLATFORM) and _PLATFORM not in sys.path:
    sys.path.insert(0, _PLATFORM)

from core.base import (  # noqa: E402
    Context, LogFn, ParamDef, TestCase, TestResult, TestStatus,
)
from core.registry import register  # noqa: E402


def _load_vlc(log: LogFn = None):
    """按需设置 libvlc 环境并 import vlc（延迟到运行期，顶层无副作用）。

    优先使用本目录自带的 libvlc.dll（与 vlc_reboot.py / vlc_audio_pcm.py 一致），
    不存在则回退到系统已 pip 安装的 python-vlc 默认查找逻辑。
    """
    os.environ["PYTHON_VLC_MODULE_PATH"] = _HERE
    libvlc = os.path.join(_HERE, "libvlc.dll")
    if os.path.isfile(libvlc):
        os.environ.setdefault("PYTHON_VLC_LIB_PATH", libvlc)
    import vlc  # noqa: PLC0415 运行期才导入
    if log:
        log("vlc %s, libvlc=%s" % (getattr(vlc, "__version__", "?"),
                                   os.environ.get("PYTHON_VLC_LIB_PATH", "系统默认")))
    return vlc


def _default_out_dir() -> str:
    """产物输出目录：平台 output/ 优先，回退本脚本旁 output/。"""
    d = os.path.join(_PLATFORM, "output", "vlc_capture")
    if os.path.isdir(_PLATFORM):
        os.makedirs(d, exist_ok=True)
        return d
    d = os.path.join(_HERE, "output")
    os.makedirs(d, exist_ok=True)
    return d


@register
class VlcCaptureCase(TestCase):
    """拉取指定摄像机 RTSP 流：视频截 1 张 JPG + 音频录一段裸 PCM。

    通过判据：
    - 起流成功（play_timeout 秒内进入 Playing）；
    - JPG 存在、JPEG 头合法、大小 >= min_jpg_kb KB；
    - PCM 有效时长 >= min_audio_sec 秒（时长 = 文件字节数 / 采样率 / 声道数 / 2）。
    """

    id = "vlc_capture"
    name = "VLC 拉流采集(JPG+PCM)"
    category = "流媒体"
    description = ("拉取指定摄像机 RTSP 流，视频截图保存 JPG、音频录制保存裸 PCM "
                   "(s16le)，校验文件合法性后判定通过；等待期间可被平台停止")
    params = [
        ParamDef("ip", "设备 IP", "192.168.13.169", "str",
                 "支持 {device_ip} 引用 mDNS 发现结果"),
        ParamDef("rtsp_path", "RTSP 路径", "/1", "str", "拼接为 rtsp://ip+path"),
        ParamDef("use_tcp", "RTSP 走 TCP(1/0)", "1", "int", "TCP 取流更稳"),
        ParamDef("do_jpg", "视频截图(1/0)", "1", "int", "0=bypass视频: 不截图不校验"),
        ParamDef("do_pcm", "音频录音(1/0)", "1", "int", "0=bypass音频: 不录音不校验"),
        ParamDef("play_timeout", "起流等待(秒)", "15", "int"),
        ParamDef("warmup", "截图前稳定等待(秒)", "3", "int", "等画面出帧"),
        ParamDef("snapshot_w", "快照宽", "1280", "int"),
        ParamDef("snapshot_h", "快照高", "720", "int"),
        ParamDef("min_jpg_kb", "JPG 最小大小(KB,0=不校验)", "10", "int"),
        ParamDef("record_sec", "PCM 录制时长(秒)", "5", "int"),
        ParamDef("sample_rate", "PCM 采样率", "48000", "int"),
        ParamDef("channels", "PCM 声道数(1/2)", "2", "int"),
        ParamDef("min_audio_sec", "PCM 最小时长(秒)", "1", "int",
                 "低于该时长判失败；0=只要求有数据"),
        ParamDef("out_dir", "输出目录", "", "str", "留空=自动(平台 output/vlc_capture)"),
    ]

    # ---------------- 主流程 ----------------
    def run(self, ctx: Context, log: LogFn) -> TestResult:
        ip = self.p_str("ip")
        rtsp_url = "rtsp://" + ip + self.p_str("rtsp_path", "/1")
        use_tcp = self.p_int("use_tcp", 1) == 1
        do_jpg = self.p_int("do_jpg", 1) == 1
        do_pcm = self.p_int("do_pcm", 1) == 1
        if not do_jpg and not do_pcm:
            return TestResult(TestStatus.ERROR, "do_jpg 与 do_pcm 不能同时为 0")
        play_timeout = self.p_int("play_timeout", 15)
        warmup = self.p_int("warmup", 3)
        snap_w, snap_h = self.p_int("snapshot_w", 1280), self.p_int("snapshot_h", 720)
        min_jpg_kb = self.p_int("min_jpg_kb", 10)
        record_sec = self.p_int("record_sec", 30)
        self._sample_rate = self.p_int("sample_rate", 48000)
        self._channels = max(1, self.p_int("channels", 2))
        min_audio_sec = self.p_int("min_audio_sec", 1)

        out_dir = self.p_str("out_dir") or _default_out_dir()
        os.makedirs(out_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        tag = "L%d_" % ctx.current_loop if ctx.current_loop > 1 else ""
        self._jpg_path = os.path.join(out_dir, "%s_%ssnapshot_%s.jpg" % (ip, tag, stamp))
        self._pcm_path = os.path.join(out_dir, "%s_%saudio_%s.pcm" % (ip, tag, stamp))

        log("目标 %s  TCP=%s  截图=%s 录音=%s  快照=%dx%d  录音=%ds s16le/%dHz/%dch  输出=%s"
            % (rtsp_url, use_tcp, "开" if do_jpg else "bypass",
               "开" if do_pcm else "bypass", snap_w, snap_h, record_sec,
               self._sample_rate, self._channels, out_dir))

        try:
            vlc = _load_vlc(log)
        except Exception as e:  # noqa: BLE001
            return TestResult(TestStatus.ERROR, "加载 vlc 失败: %s" % e)

        self._total_frames = 0
        jpg_ok = pcm_ok = False
        msgs = []
        try:
            jpg_ok = self._capture_jpg_and_pcm(vlc, rtsp_url, use_tcp, do_jpg, do_pcm,
                                               play_timeout, warmup,
                                               snap_w, snap_h, record_sec, log)
            if self.stop_requested:
                return TestResult(TestStatus.SKIPPED, "用户停止")
            if do_pcm:
                if self._total_frames == 0:
                    # 回调不可用或流无音轨 → fallback 转码 wav 剥头(纯音频)
                    pcm_ok = self._record_pcm_sout(vlc, rtsp_url, use_tcp,
                                                   record_sec, log)
                else:
                    pcm_ok = True
        finally:
            if self._pcm_file and not self._pcm_file.closed:
                self._pcm_file.close()

        # ---------------- 判定 ----------------
        if self.stop_requested:
            return TestResult(TestStatus.SKIPPED, "用户停止")

        # 截图校验(先探测实际格式: libvlc 可能写 PNG 而非 JPG, 并按需改扩展名)
        jpg_desc = "bypass"
        if do_jpg:
            snap_fmt = self._finalize_snapshot()
            jpg_desc = "未产出"
            if jpg_ok and snap_fmt and os.path.isfile(self._jpg_path):
                size_kb = os.path.getsize(self._jpg_path) / 1024.0
                if snap_fmt not in ("jpg", "png"):
                    msgs.append("截图格式无法识别(非 JPEG/PNG)")
                elif min_jpg_kb > 0 and size_kb < min_jpg_kb:
                    msgs.append("截图过小(%.1fKB < %dKB)" % (size_kb, min_jpg_kb))
                else:
                    jpg_desc = "%.1fKB %s" % (size_kb, snap_fmt.upper())
            else:
                msgs.append("截图未生成")

        # PCM 校验
        audio_sec = self._total_frames / float(self._sample_rate)
        pcm_desc = "bypass"
        if do_pcm:
            pcm_desc = "未产出"
            if pcm_ok and os.path.isfile(self._pcm_path) and os.path.getsize(self._pcm_path) > 0:
                if audio_sec <= 0:  # sout 模式没累计帧数，从文件大小反推
                    audio_sec = os.path.getsize(self._pcm_path) / \
                        float(self._sample_rate * self._channels * 2)
                if min_audio_sec > 0 and audio_sec < min_audio_sec:
                    msgs.append("PCM 时长不足(%.2fs < %ds)" % (audio_sec, min_audio_sec))
                else:
                    pcm_desc = "%.2fs/%dKB" % (audio_sec, os.path.getsize(self._pcm_path) // 1024)
            else:
                msgs.append("PCM 无数据(流可能无音轨)")

        data = {"jpg_path": self._jpg_path, "pcm_path": self._pcm_path,
                "audio_seconds": round(audio_sec, 2)}
        ctx.set("vlc_jpg_path", self._jpg_path)
        ctx.set("vlc_pcm_path", self._pcm_path)

        if msgs:
            return TestResult(TestStatus.FAILED,
                              "截图:%s PCM:%s -> %s" % (jpg_desc, pcm_desc, "; ".join(msgs)),
                              data=data)
        msg = "截图:%s PCM:%s" % (jpg_desc, pcm_desc)
        if do_pcm:
            msg += (" (试听: ffplay -f s16le -ar %d -ch_layout %s -i \"%s\")"
                    % (self._sample_rate, "stereo" if self._channels == 2 else "mono",
                       self._pcm_path))
        return TestResult(TestStatus.PASSED, msg, data=data)

    # ---------------- 方案1: 一次拉流, 快照 + 音频回调直取 PCM ----------------
    def _capture_jpg_and_pcm(self, vlc, rtsp_url, use_tcp, do_jpg, do_pcm,
                             play_timeout, warmup, snap_w, snap_h, record_sec,
                             log) -> bool:
        if do_pcm:
            self._pcm_file = open(self._pcm_path, "wb")

        # ctypes 回调包装；保持引用(局部变量)防 GC, 否则 VLC 回调时崩溃
        play_t = flush_t = drain_t = None
        if do_pcm:
            play_t = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p,
                                      ctypes.c_uint, ctypes.c_int64)(self._on_audio)
            flush_t = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int64)(self._on_flush)
            drain_t = ctypes.CFUNCTYPE(None, ctypes.c_void_p)(self._on_drain)

        instance = vlc.Instance("--no-video-title-show", "--no-xlib")
        player = instance.media_player_new()
        media = instance.media_new(rtsp_url)
        if use_tcp:
            media.add_option(":rtsp-tcp")
        if not do_jpg:
            media.add_option(":no-video")   # bypass 视频: 不解码视频, 只取音频
        player.set_media(media)

        use_cb = do_pcm and hasattr(player, "audio_set_callbacks")
        if use_cb:
            # 必须在 play() 之前; S16N = 16bit 本机字节序(Windows 小端 = s16le)
            player.audio_set_callbacks(play_t, None, None, flush_t, drain_t, None)
            player.audio_set_format("S16N", self._sample_rate, self._channels)
        elif do_pcm:
            log("当前 python-vlc 不支持音频回调; PCM 走 fallback 转码")

        status = [0]

        def on_playing(event, user_data):
            user_data[0] = 1

        player.event_manager().event_attach(vlc.EventType.MediaPlayerPlaying,
                                            on_playing, status)

        log("try to get rtsp: " + rtsp_url)
        player.play()
        for _ in range(play_timeout):
            if not self.sleep_interruptible(1, None):
                self._stop(player)
                return False
            if status[0]:
                break
        if not status[0]:
            log("ERROR: rtsp 流 %ds 内未起播" % play_timeout)
            self._stop(player)
            return False

        if do_jpg:
            log("vlc stream ok, warmup %ds ..." % warmup)
            if not self.sleep_interruptible(warmup, log):
                self._stop(player)
                return False
            if self.stop_requested:
                self._stop(player)
                return False
            log("take snapshot -> %s" % os.path.basename(self._jpg_path))
            player.video_take_snapshot(0, self._jpg_path, snap_w, snap_h)
        else:
            log("vlc stream ok (bypass video)")

        if not do_pcm:               # 纯截图模式: 快照异步落盘后即可停流
            self.sleep_interruptible(2, log)
            self._stop(player)
            return self._wait_jpg_written()

        log("recording %ds ..." % record_sec)
        t0 = time.time()
        while time.time() - t0 < record_sec:
            if player.get_state() == vlc.State.Ended:
                log("stream ended early")
                break
            if not self.sleep_interruptible(1, None):
                self._stop(player)
                return False
            if int(time.time() - t0) % 5 == 0:
                log("  %3ds/%ds  audio %.2fs"
                    % (time.time() - t0, record_sec,
                       self._total_frames / float(self._sample_rate)))

        self._stop(player)
        return self._wait_jpg_written() if do_jpg else True

    def _wait_jpg_written(self, timeout_s: float = 3.0) -> bool:
        """take_snapshot 异步落盘, 轮询等文件写完。"""
        for _ in range(int(timeout_s / 0.5)):
            if os.path.isfile(self._jpg_path) and os.path.getsize(self._jpg_path) > 0:
                return True
            time.sleep(0.5)
        return os.path.isfile(self._jpg_path) and os.path.getsize(self._jpg_path) > 0

    def _finalize_snapshot(self) -> str:
        """探测快照实际编码并统一扩展名。

        libvlc 3.0 在 D3D11 硬解输出下 take_snapshot 实测写 PNG(忽略 .jpg
        扩展名), 故按魔数识别: 返回 'jpg'/'png'/'raw'(无法识别)/''(无文件);
        PNG 时把产物重命名为 .png, self._jpg_path 同步更新。
        """
        if not os.path.isfile(self._jpg_path):
            return ""
        try:
            with open(self._jpg_path, "rb") as f:
                head = f.read(8)
        except OSError:
            return ""
        if head.startswith(b"\x89PNG"):
            if self._jpg_path.lower().endswith(".jpg"):
                try:
                    new_path = self._jpg_path[:-4] + ".png"
                    os.replace(self._jpg_path, new_path)
                    self._jpg_path = new_path
                except OSError:
                    pass
            return "png"
        if head.startswith(b"\xff\xd8"):
            return "jpg"
        return "raw"

    # ---------------- 方案2(fallback): 转码 wav 再剥头 ----------------
    def _record_pcm_sout(self, vlc, rtsp_url, use_tcp, record_sec, log) -> bool:
        log("fallback: transcode to wav then strip header")
        wav_path = self._pcm_path + ".tmp.wav"
        dst = wav_path.replace("\\", "/")
        instance = vlc.Instance("--no-video-title-show", "--no-xlib")
        media = instance.media_new(rtsp_url)
        if use_tcp:
            media.add_option(":rtsp-tcp")
        media.add_option(":no-sout-video")
        media.add_option(":sout=#transcode{acodec=s16l,channels=%d,samplerate=%d}"
                         ":standard{access=file,mux=wav,dst=\"%s\"}"
                         % (self._channels, self._sample_rate, dst))
        player = instance.media_player_new()
        player.set_media(media)
        player.play()
        if not self.sleep_interruptible(3 + record_sec, log):
            self._stop(player)
            return False
        self._stop(player)
        time.sleep(1)
        try:
            with open(self._pcm_path, "wb") as f:   # wav 去头 -> 裸 pcm
                w = wave.open(wav_path, "rb")
                f.write(w.readframes(w.getnframes()))
                w.close()
            os.remove(wav_path)
        except OSError as e:
            log("fallback 剥头失败: %s" % e)
            return False
        return os.path.getsize(self._pcm_path) > 0

    # ---------------- 音频回调(C 回调内不可抛异常) ----------------
    def _on_audio(self, user_data, samples, count, pts):
        try:
            if samples and count:
                nbytes = count * self._channels * 2   # s16 => 每采样2字节
                self._pcm_file.write(ctypes.string_at(samples, nbytes))
                self._total_frames += count
        except Exception:  # noqa: BLE001
            pass

    def _on_flush(self, user_data, pts):
        try:
            self._pcm_file.flush()
        except Exception:  # noqa: BLE001
            pass

    def _on_drain(self, user_data):
        try:
            self._pcm_file.flush()
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _stop(player):
        try:
            player.stop()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)   # 等 flush/drain 回调收尾

    _pcm_file = None


# ---------------- 单独运行入口 ----------------
def _main() -> None:
    import argparse
    ap = argparse.ArgumentParser(
        description="VLC 拉流采集测试: RTSP -> JPG 快照 + PCM 录音"
                    "（可独立运行，亦可被 test_platform 挂载）")
    ap.add_argument("--ip", default="192.168.13.169", help="设备 IP")
    ap.add_argument("--path", default="/1", help="RTSP 路径(默认 /1)")
    ap.add_argument("--record", type=int, default=30, help="PCM 录制秒数(默认 30)")
    ap.add_argument("--udp", action="store_true", help="RTSP 走 UDP(默认 TCP)")
    ap.add_argument("--no-jpg", action="store_true", help="bypass 视频截图(纯音频)")
    ap.add_argument("--no-pcm", action="store_true", help="bypass 音频录音(纯视频)")
    args = ap.parse_args()

    case = VlcCaptureCase({"ip": args.ip, "rtsp_path": args.path,
                           "record_sec": str(args.record),
                           "use_tcp": "0" if args.udp else "1",
                           "do_jpg": "0" if args.no_jpg else "1",
                           "do_pcm": "0" if args.no_pcm else "1"})
    print("[单独运行] %s -> rtsp://%s%s" % (case.name, args.ip, args.path))
    result = case.run(Context(), log=print)
    print("[结果] %s  %s" % (result.status.value, result.message))


if __name__ == "__main__":
    _main()
