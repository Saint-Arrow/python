# -*- coding: UTF-8 -*-
"""
JPG 图片颜色检测工具 - 基于 RGB 欧氏距离
"""

import cv2
import numpy as np
import os
import argparse
from typing import Tuple, Dict, List, Optional


class ColorDetector:
    """颜色检测器类"""
    
    def __init__(self, image_path: str = None, show_image: bool = False):
        self.image_path = image_path
        self.show_image = show_image
        self.original_image = None
        
        if image_path is not None:
            if not os.path.exists(image_path):
                raise FileNotFoundError("Image file not found: {}".format(image_path))
            
            self.original_image = cv2.imread(image_path)
            if self.original_image is None:
                raise ValueError("Failed to read image: {}".format(image_path))
    
    def extract_roi(self, x: int, y: int, width: int, height: int) -> np.ndarray:
        h, w = self.original_image.shape[:2]
        if x < 0 or y < 0:
            raise ValueError("Coordinates cannot be negative: x={}, y={}".format(x, y))
        if x + width > w or y + height > h:
            raise ValueError("ROI exceeds image bounds")
        
        return self.original_image[y:y+height, x:x+width]
    
    def analyze_roi(self, roi: np.ndarray) -> Dict:
        flat_bgr = roi.reshape(-1, 3).astype(np.float64)
        
        stats = {
            'pixel_count': roi.size // 3,
            'shape': roi.shape,
            'avg_color': {
                'bgr': [float(np.mean(flat_bgr[:, 0])), 
                        float(np.mean(flat_bgr[:, 1])), 
                        float(np.mean(flat_bgr[:, 2]))]
            },
            'std_color': {
                'bgr': [float(np.std(flat_bgr[:, 0])), 
                        float(np.std(flat_bgr[:, 1])), 
                        float(np.std(flat_bgr[:, 2]))]
            }
        }
        
        return stats
    
    def detect_color(self, roi: np.ndarray, color_name: str, threshold: float = 0.5,
                    max_diff: int = None, rel_threshold: float = 0.1) -> Dict:
        """
        使用 RGB 相对差值检测 ROI 中是否包含指定颜色
            
        Args:
            roi: ROI 区域的 BGR 图像
            color_name: 目标颜色值 (r,g,b 格式)
            threshold: 匹配阈值（0-1），越大越严格
            max_diff: 最大允许的绝对 RGB 差值（可选）
            rel_threshold: 相对差值阈值（默认 10%，即每个通道差不超过目标值的±10%）
        """
        try:
            normalized_color = color_name.replace('，', ',').replace(',', ',')
            if normalized_color.startswith('rgb_') or normalized_color.startswith('custom_'):
                normalized_color = normalized_color.split('_')[1]
            
            rgb_values = [int(x.strip()) for x in normalized_color.split(',')]
            if len(rgb_values) != 3 or not all(0 <= v <= 255 for v in rgb_values):
                raise ValueError('RGB values must be 0-255 and provide 3 values: {}'.format(normalized_color))
            
            r, g, b = rgb_values
            rgb_target = np.array([r, g, b], dtype=np.float64)
            
            print("[INFO] Custom RGB value detected: R={}, G={}, B={}".format(r, g, b))
            print("[DEBUG] Detection method: RGB relative percentage")
            print("[DEBUG] Max diff per channel: {} or {:.0%} of target value".format(
                max_diff if max_diff is not None else 'N/A', rel_threshold))
        except Exception as e:
            raise ValueError('Custom RGB format error. Use r,g,b like: 255,0,0 or 160,160,160. Error: {}'.format(e))
        
        # 转换为 float64 用于精确计算
        flat_bgr = roi.reshape(-1, 3).astype(np.float64)
        
        # 计算相对差值百分比
        # 避免除以 0，如果目标值为 0，则要求像素值也必须接近 0
        safe_target = np.where(rgb_target == 0, 1, rgb_target)  # 用 1 代替 0 避免除零
        rel_diff = np.abs(flat_bgr - rgb_target) / safe_target
        
        # 判断哪些像素在允许范围内
        # 条件 1：相对差值小于阈值（使用 & 代替 and）
        rel_match = ((rel_diff[:, 0] <= rel_threshold) & (rel_diff[:, 1] <= rel_threshold) & (rel_diff[:, 2] <= rel_threshold))
        
        # 条件 2（可选）：绝对差值也小于阈值
        if max_diff is not None:
            abs_diff = np.abs(flat_bgr - rgb_target)
            abs_match = (abs_diff[:, 0] <= max_diff) & (abs_diff[:, 1] <= max_diff) & (abs_diff[:, 2] <= max_diff)
            match_mask = rel_match & abs_match
        else:
            match_mask = rel_match
        
        total_pixels = roi.size // 3
        match_pixels = np.sum(match_mask)
        match_ratio = match_pixels / total_pixels
        
        result = {
            'color': color_name,
            'is_custom': True,
            'match': match_ratio >= threshold,
            'ratio': match_ratio,
            'threshold': threshold,
            'rel_threshold': rel_threshold,
            'max_diff': max_diff,
            'mask': match_mask.astype(np.uint8),
            'pixel_stats': {
                'total': total_pixels,
                'matched': match_pixels,
                'distance_stats': {
                    'mean_rel': float(np.mean(rel_diff)),  # 平均相对差值
                    'max_rel': float(np.max(rel_diff)),    # 最大相对差值
                    'mean_abs': float(np.mean(abs_diff)) if max_diff is not None else None,  # 平均绝对差值
                    'max_abs': float(np.max(abs_diff)) if max_diff is not None else None     # 最大绝对差值
                }
            }
        }
        
        return result
    
    def visualize(self, x: int, y: int, width: int, height: int, 
                 analysis_stats: Dict, detection_result: Optional[Dict] = None):
        viz_image = self.original_image.copy()
        
        cv2.rectangle(viz_image, (x, y), (x + width, y + height), (0, 255, 0), 2)
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        thickness = 2
        
        roi_label = "ROI: {}x{}".format(width, height)
        text_size = cv2.getTextSize(roi_label, font, font_scale, thickness)[0]
        text_x = x
        text_y = y - 10 if y > 20 else y + height + 20
        cv2.rectangle(viz_image, 
                     (text_x - 5, text_y - text_size[1] - 5),
                     (text_x + text_size[0] + 5, text_y + 5),
                     (0, 0, 0), -1)
        cv2.putText(viz_image, roi_label, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)
        
        if detection_result and detection_result['mask'] is not None:
            overlay = viz_image.copy()
            color = (255, 0, 0) if detection_result['match'] else (0, 0, 255)
            alpha = 0.3
            cv2.addWeighted(overlay, alpha, viz_image, 1 - alpha, 0, viz_image)
            
            cv2.rectangle(viz_image, (x, y), (x + width, y + height), color, 3)
            
            status = "[X]" if detection_result['match'] else "[#]"
            status_text = "{} {} ({:.1f}%)".format(status, detection_result['color'], detection_result['ratio']*100)
            text_size = cv2.getTextSize(status_text, font, font_scale, thickness)[0]
            text_y = y + height + 25
            cv2.rectangle(viz_image,
                         (x - 5, text_y - text_size[1] - 5),
                         (x + text_size[0] + 5, text_y + 5),
                         (255, 255, 255), -1)
            cv2.putText(viz_image, status_text, (x, text_y), font, font_scale, color, thickness)
        
        if self.show_image:
            cv2.imshow("Detection Result", viz_image)
            print("Press any key to close the window...")
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        
        return viz_image
    
    def save_result(self, image: np.ndarray, output_path: str):
        cv2.imwrite(output_path, image)
        print("Result image saved: {}".format(output_path))
    
    def print_report(self, x: int, y: int, analysis_stats: Dict, detection_result: Optional[Dict] = None):
        print("\n" + "="*50)
        print("=== Image Color Analysis Report ===")
        print("="*50)
        print("Image path: {}".format(self.image_path))
        print("Image size: {}x{}".format(self.original_image.shape[1], self.original_image.shape[0]))
        print("ROI region: x={}, y={}, w={}, h={}".format(x, y, analysis_stats['shape'][1], analysis_stats['shape'][0]))
        print("")
        
        print("Color statistics:")
        print("  Pixel count: {}".format(analysis_stats['pixel_count']))
        print("  Average color (BGR): [{}, {}, {}]".format(
            int(analysis_stats['avg_color']['bgr'][2]),
            int(analysis_stats['avg_color']['bgr'][1]),
            int(analysis_stats['avg_color']['bgr'][0])))
        print("")
        
        if detection_result:
            print("Color detection (target: {}):".format(detection_result['color'].upper()))
            print("  Match ratio: {:.2f}%".format(detection_result['ratio']*100))
            print("  Detection result: {}".format('[MATCH]' if detection_result['match'] else '[NO-MATCH]'))
            
            if 'pixel_stats' in detection_result and 'distance_stats' in detection_result['pixel_stats']:
                dist_stats = detection_result['pixel_stats']['distance_stats']
                print("  Relative difference stats:")
                print("    Mean: {:.4f} ({:.2f}%)".format(
                    dist_stats['mean_rel'], dist_stats['mean_rel']*100))
                print("    Max:  {:.4f} ({:.2f}%)".format(
                    dist_stats['max_rel'], dist_stats['max_rel']*100))
                
                if dist_stats.get('mean_abs') is not None:
                    print("  Absolute difference stats (if abs-diff specified):")
                    print("    Mean: {:.2f}".format(dist_stats['mean_abs']))
                    print("    Max:  {:.2f}".format(dist_stats['max_abs']))
            
            print("")
            print("="*50)
            
            if detection_result['match']:
                print("[RESULT] SUCCESS: Detected {} region!".format(detection_result['color']))
            else:
                print("[RESULT] NOT-DETECTED: {} region".format(detection_result['color']))
            print("="*50 + "\n")


def main():
    parser = argparse.ArgumentParser(description='JPG Image Color Analysis Tool - RGB Relative Percentage Method')
    parser.add_argument('image', help='Image file path')
    parser.add_argument('--roi', required=True, help='ROI coordinates: x,y,width,height')
    parser.add_argument('--color', default='128,128,128', help='Target color: r,g,b (default: 128,128,128)')
    parser.add_argument('--threshold', type=float, default=0.5, help='Match threshold 0-1 (default: 0.5)')
    parser.add_argument('--rel-threshold', type=float, default=0.1, dest='rel_threshold',
                       help='Relative difference threshold as decimal (e.g., 0.1 for 10%%, default: 0.1)')
    parser.add_argument('--abs-diff', type=int, default=None, dest='abs_diff',
                       help='Max absolute single-channel difference (optional, for stricter control)')
    parser.add_argument('--output', default=None, help='Output image filename')
    parser.add_argument('--show-image', action='store_true', help='Show debug windows')
    
    args = parser.parse_args()
    
    try:
        x, y, width, height = map(int, args.roi.split(','))
        
        detector = ColorDetector(args.image, show_image=args.show_image)
        roi = detector.extract_roi(x, y, width, height)
        stats = detector.analyze_roi(roi)
        
        result = None
        if args.color:
            result = detector.detect_color(
                roi, args.color, 
                threshold=args.threshold,
                rel_threshold=args.rel_threshold,
                max_diff=args.abs_diff
            )
        
        viz_image = detector.visualize(x, y, width, height, stats, result)
        
        if args.output:
            detector.save_result(viz_image, args.output)
        elif args.show_image and not args.output:
            base_name = os.path.splitext(os.path.basename(args.image))[0]
            auto_output = "{}_result.jpg".format(base_name)
            detector.save_result(viz_image, auto_output)
        
        detector.print_report(x, y, stats, result)
        
        return stats, result
        
    except Exception as e:
        print("\n[ERROR] Error: {}".format(e))
        import traceback
        traceback.print_exc()
        return None, None


if __name__ == "__main__":
    stats, result = main()
