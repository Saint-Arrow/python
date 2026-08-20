# -*- coding: UTF-8 -*-
"""
实时屏幕颜色和 ROI 监控工具
功能：连续截屏并检测指定区域的 RGB 颜色匹配情况
"""

import cv2
import numpy as np
import os
import time
import argparse
from datetime import datetime
from color_detect import ColorDetector


class LiveMonitor:
    """实时屏幕监控类"""
    
    def __init__(self, roi_coords=None, show_image=False):
        """
        Args:
            roi_coords: (x, y, width, height) - 要检测的区域坐标
            show_image: 是否显示监控窗口（调试用）
        """
        self.roi_coords = roi_coords or (0, 0, 1920, 1080)  # 默认全屏
        self.show_image = show_image
        self.is_running = False
        
        # 准备保存目录
        self.output_dir = "live_monitor_output"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def capture_screen(self, crop_area=None):
        """
        使用 PIL 捕获屏幕
        Args:
            crop_area: (width, height, x_offset, y_offset) 可选裁剪区域
        Returns:
            BGR 格式的图像数组
        """
        try:
            from PIL import ImageGrab
            
            # 获取整个屏幕
            full_screenshot = ImageGrab.grab()
            screenshot_array = np.array(full_screenshot)
            
            # 转换 RGB -> BGR（注意：PIL 返回的是 RGB，OpenCV 需要 BGR）
            if len(screenshot_array.shape) == 3 and screenshot_array.shape[2] == 3:
                screenshot_bgr = cv2.cvtColor(screenshot_array, cv2.COLOR_RGB2BGR)
            else:
                # 如果是灰度图或其他格式，直接返回
                screenshot_bgr = screenshot_array
            
            return screenshot_bgr
        
        except Exception as e:
            print("[ERROR] Screen capture failed: {}".format(e))
            return None
    
    def process_frame(self, frame, detector, rel_threshold, threshold, max_diff=None):
        """
        处理单帧图像
        Args:
            frame: BGR 图像
            detector: ColorDetector 实例
            rel_threshold: 相对差值阈值（如 0.1 表示 10%）
            threshold: 匹配阈值
            max_diff: 绝对差值阈值（可选）
        Returns:
            detection_result: 检测结果
            viz_image: 带标注的图片
        """
        x, y, width, height = self.roi_coords
        
        # 提取 ROI
        roi = frame[y:y+height, x:x+width]
        
        # 分析统计
        stats = detector.analyze_roi(roi)
        
        # 检测颜色（使用目标平均色作为参考）
        target_color = "{},{},{}".format(
            int(stats['avg_color']['bgr'][2]),
            int(stats['avg_color']['bgr'][1]),
            int(stats['avg_color']['bgr'][0])
        )
        
        result = detector.detect_color(roi, target_color, threshold=threshold, rel_threshold=rel_threshold, max_diff=max_diff)
        
        # 可视化
        viz_image = detector.visualize(x, y, width, height, stats, result)
        
        return result, viz_image
    
    def run_continuous(self, target_color, rel_threshold=0.1,
                      max_diff=None, threshold=0.5, 
                      interval=2.0, duration=None, output_pattern=None, 
                      stop_on_nofit=False, save_all_failures=True, max_success=10, max_failure=100):
        """
        连续运行监控
        Args:
            target_color: 目标颜色 r,g,b
            rel_threshold: 相对差值阈值（默认 10%，即±0.1）
            max_diff: 绝对差值阈值（可选，更严格的控制）
            threshold: 匹配阈值
            interval: 每秒间隔（秒）
            duration: 总时长（秒），None 表示无限
            output_pattern: 输出文件名模式 'frame_{num}.jpg'
            stop_on_nofit: 检测到不匹配后立即停止 (默认 False)
            save_all_failures: 是否保存所有失败帧 (默认 True，最多保存 max_failure 张)
            max_success: 保留的最新成功帧数量 (默认 10)
            max_failure: 保存的失败帧最大数量 (默认 100)
        """
        print("="*60)
        print("=== Live Color Monitoring Started ===")
        print("="*60)
        print("Target color: {}".format(target_color))
        print("ROI: {}x{}@({},{})".format(*self.roi_coords))
        print("Max diff per channel: {}".format(max_diff))
        print("Match threshold: {:.2%}".format(threshold))
        print("Interval: {:.1f}s".format(interval))
        print("Output directory: {}".format(self.output_dir))
        print("Stop on mismatch: {}".format(stop_on_nofit))
        if not stop_on_nofit:
            print("Do not stop immediately on mismatch")
        print("Save all failures: {}".format(save_all_failures))
        print("Keep latest success frames: {}".format(max_success))
        if save_all_failures:
            print("Keep failure frames (up to): {}".format(max_failure))
        print("Relative difference threshold: {:.0%}".format(rel_threshold))
        if max_diff is not None:
            print("Absolute difference threshold: {} (stricter mode)".format(max_diff))
        print("-"*60)
        print("Press Ctrl+C to stop...")
        print("="*60)
        
        self.is_running = True
        start_time = time.time()
        frame_count = 0
        match_count = 0
        success_frames = []  # 保存的成功帧列表
        failure_frames = []  # 保存的失败帧列表
        
        try:
            while self.is_running:
                current_time = time.time()
                elapsed = current_time - start_time
                
                # 检查是否超时
                if duration and elapsed >= duration:
                    print("\n[INFO] Duration reached, stopping...")
                    break
                
                # 捕获屏幕
                frame = self.capture_screen(self.roi_coords)
                if frame is None:
                    print("[ERROR] Failed to capture screen")
                    time.sleep(interval)
                    continue
                
                # 创建检测器
                detector = ColorDetector(None)
                detector.original_image = frame
                
                # 处理帧
                result, viz_image = self.process_frame(frame, detector, rel_threshold, threshold, max_diff)
                
                # 更新计数
                frame_count += 1
                if result['match']:
                    match_count += 1
                
                # 打印状态
                status = "[X] MATCH" if result['match'] else "[#] NO-MATCH"
                print("[{:04d}] {:6s} Ratio:{:.2f}% | MaxDiff:{:.2f} Mean:{:.2f}"
                     .format(frame_count, status, result['ratio']*100, 
                            result.get('pixel_stats', {}).get('distance_stats', {}).get('max', 0),
                            result.get('pixel_stats', {}).get('distance_stats', {}).get('mean', 0)))
                                
                # 保存图片（先保存，再判断是否停止）
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:26]
                if output_pattern:
                    filename = output_pattern.format(timestamp=timestamp, count=frame_count)
                else:
                    if result['match']:
                        filename = "success_{}_{}.jpg".format(timestamp, frame_count)
                    else:
                        filename = "failure_{}_{}.jpg".format(timestamp, frame_count)
                                
                filepath = os.path.join(self.output_dir, filename)
                cv2.imwrite(filepath, viz_image)
                                
                # 根据检测结果分类保存
                if result['match']:
                    success_frames.append(filepath)
                    # 如果超过限制，删除最早的成功帧
                    if len(success_frames) > max_success:
                        oldest = success_frames.pop(0)
                        self._delete_file_safe(oldest)
                else:
                    # 失败帧：保存到另一个列表，直到达到限制
                    failure_frames.append(filepath)
                    # 如果超过限制，删除最早的失败帧
                    if len(failure_frames) > max_failure:
                        oldest = failure_frames.pop(0)
                        self._delete_file_safe(oldest)
                                
                # 显示窗口
                if self.show_image:
                    cv2.imshow("Live Monitor - Frame {}: {}".format(frame_count, 
                        "MATCH" if result['match'] else "FAIL"), viz_image)
                                    
                    # 按 ESC 退出
                    key = cv2.waitKey(1) & 0xFF
                    if key == 27:  # ESC
                        print("\n[INFO] User pressed ESC, stopping...")
                        break
                                
                # 检测到不匹配时立即停止（可选功能）
                if stop_on_nofit and not result['match']:
                    print("\n[INFO] Detection failed - stopping automatically")
                    break
                
                # 等待下一帧
                next_frame_time = start_time + frame_count * interval
                sleep_time = next_frame_time - time.time()
                if sleep_time > 0:
                    time.sleep(sleep_time)
        
        except KeyboardInterrupt:
            print("\n[INFO] User interrupted, stopping...")
        
        finally:
            self.is_running = False
            
            # 打印统计报告
            print("\n" + "="*60)
            print("=== Final Statistics ===")
            print("Total frames captured: {}".format(frame_count))
            print("Frames matching criteria: {}".format(match_count))
            if frame_count > 0:
                match_rate = match_count / frame_count * 100
                print("Overall match rate: {:.2f}%".format(match_rate))
            print("Duration: {:.1f}s".format(time.time() - start_time))
            print("Output files saved to: {}".format(self.output_dir))
            print("="*60 + "\n")
            
            # 关闭所有窗口
            if self.show_image:
                cv2.destroyAllWindows()
    
    def _cleanup_old_images(self, frames_saved, max_history):
        """
        清理旧的截图文件，只保留最近的 max_history 张
        Args:
            frames_saved: 已保存文件路径列表（按时间顺序）
            max_history: 要保留的最大数量
        """
        if len(frames_saved) <= max_history:
            return
        
        # 删除最老的帧，直到只剩 max_history 个
        files_to_delete = frames_saved[:-max_history]
        for filepath in files_to_delete:
            self._delete_file_safe(filepath)
            if filepath in frames_saved:
                frames_saved.remove(filepath)
    
    def _delete_file_safe(self, filepath):
        """
        安全删除文件
        Args:
            filepath: 文件路径
        """
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                print("[CLEANUP] Deleted old file: {}".format(os.path.basename(filepath)))
        except Exception as e:
            print("[CLEANUP ERROR] Failed to delete {}: {}".format(filepath, e))
    
    def snapshot_mode(self, output_filename="snapshot.jpg", save_result=True, show_image=False):
        """
        单次快照模式
        Args:
            output_filename: 输出文件名
            save_result: 是否保存到文件
            show_image: 是否显示图片窗口
        """
        frame = self.capture_screen(self.roi_coords)
        if frame is None:
            return
        
        detector = ColorDetector(None)
        detector.original_image = frame
        
        x, y, width, height = self.roi_coords
        roi = frame[y:y+height, x:x+width]
        stats = detector.analyze_roi(roi)
        
        print("\n=== Snapshot Analysis ===")
        print("Frame size: {}x{}".format(width, height))
        print("Average color (BGR): [{}, {}, {}]"
             .format(int(stats['avg_color']['bgr'][2]),
                    int(stats['avg_color']['bgr'][1]),
                    int(stats['avg_color']['bgr'][0])))
        print("Standard deviation: [{:.2f}, {:.2f}, {:.2f}]"
             .format(stats['std_color']['bgr'][0],
                    stats['std_color']['bgr'][1],
                    stats['std_color']['bgr'][2]))
        
        if save_result:
            viz_image = detector.visualize(x, y, width, height, stats, None)
            cv2.imwrite(output_filename, viz_image)
            print("Snapshot saved to: {}".format(output_filename))
        else:
            viz_image = None
        
        if show_image and viz_image is not None:
            cv2.imshow("Snapshot", viz_image)
            print("Press any key to close the window...")
            cv2.waitKey(0)
            cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(
        description='Real-time screen color monitoring and analysis tool')
    
    subparsers = parser.add_subparsers(dest='mode', help='Operation mode')
    
    # 连续监控模式
    parser_live = subparsers.add_parser('live', help='Continuous monitoring mode')
    parser_live.add_argument('--color', default='128,128,128',
                            help='Target color r,g,b for analysis (default: 128,128,128)')
    parser_live.add_argument('--rel-threshold', type=float, default=0.1, dest='rel_threshold',
                            help='Relative difference threshold as decimal (e.g., 0.1 for 10%%, default: 0.1)')
    parser_live.add_argument('--abs-diff', type=int, default=None, dest='abs_diff',
                            help='Max absolute single-channel difference (optional, for stricter control)')
    parser_live.add_argument('--threshold', type=float, default=0.5,
                            help='Match threshold 0-1 (default: 0.5)')
    parser_live.add_argument('--interval', type=float, default=2.0,
                            help='Capture interval in seconds (default: 2.0)')
    parser_live.add_argument('--duration', type=float, default=None,
                            help='Run duration in seconds, None for unlimited')
    parser_live.add_argument('--roi', dest='roi', default='0,0,1920,1080',
                            help='ROI coordinates: x,y,width,height (default: 0,0,1920,1080)')
    parser_live.add_argument('--show-image', action='store_true',
                            help='Show live preview window')
    parser_live.add_argument('--output-pattern', dest='output_pattern', default=None,
                            help='Output filename pattern, e.g., "monitor_{timestamp}.jpg"')
    parser_live.add_argument('--stop-on-nofit', dest='stop_on_nofit', action='store_true', default=False,
                            help='Stop immediately on mismatch (default: do not stop)')
    parser_live.add_argument('--max-history', type=int, default=10, dest='max_history',
                            help='Max frames to keep in output directory (default: 10)')
    
    # 快照模式
    parser_snap = subparsers.add_parser('snap', help='Single snapshot mode')
    parser_snap.add_argument('--output', '-o', default='snapshot.jpg',
                            help='Output filename (default: snapshot.jpg)')
    parser_snap.add_argument('--roi', dest='roi', default='0,0,1920,1080',
                            help='ROI coordinates: x,y,width,height')
    parser_snap.add_argument('--show-image', action='store_true',
                            help='Show image window after capture')
    
    args = parser.parse_args()
    
    if not args.mode:
        parser.print_help()
        return
    
    # 解析 ROI
    try:
        x, y, width, height = map(int, args.roi.split(','))
        roi_coords = (x, y, width, height)
    except ValueError:
        print("[ERROR] Invalid ROI format. Use: x,y,width,height")
        return
    
    try:
        monitor = LiveMonitor(roi_coords=roi_coords, show_image=args.show_image)
        
        if args.mode == 'live':
            monitor.run_continuous(
                target_color=args.color,
                rel_threshold=args.rel_threshold,
                max_diff=args.abs_diff,
                threshold=args.threshold,
                interval=args.interval,
                duration=args.duration,
                output_pattern=args.output_pattern,
                stop_on_nofit=args.stop_on_nofit
                # save_all_failures=True, max_success=10, max_failure=100 (默认值)
            )
        
        elif args.mode == 'snap':
            monitor.snapshot_mode(output_filename=args.output, 
                                 show_image=getattr(args, 'show_image', False))
    
    except Exception as e:
        print("\n[ERROR]: {}".format(e))
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
