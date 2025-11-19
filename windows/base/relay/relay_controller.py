#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
继电器控制程序
功能：
1. 打开继电器串口1，波特率为9600
2. 发送打开命令 0xa00101a2
3. 延时30s之后使用ping命令测试，如果能ping通，就发送关闭命令(0xa10102a3)，再延时3秒之后回到第2步继续执行
4. 如果ping不通，就退出程序循环
"""

import serial
import time
import subprocess
import sys
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('relay_controller.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

class RelayController:
    def __init__(self, port='COM1', baudrate=9600):
        """
        初始化继电器控制器
        
        Args:
            port: 串口号，默认为COM1
            baudrate: 波特率，默认为9600
        """
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        
        # 继电器命令
        self.OPEN_COMMAND = bytes([0xa0, 0x01, 0x00, 0xa1])  # 打开命令
        self.CLOSE_COMMAND = bytes([0xa0, 0x01, 0x01, 0xa2])  # 关闭命令
        
        # ping测试目标（可根据实际情况修改）
        self.ping_target = "8.8.8.8"  # Google DNS，可根据需要修改为实际目标IP
        self.time_wait_to_ping = 50
        self.ping_timeout = 3  # ping超时时间（秒）
        
    def connect_serial(self):
        """连接串口"""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            logging.info(f"成功连接串口 {self.port}，波特率 {self.baudrate}")
            return True
        except Exception as e:
            logging.error(f"连接串口失败: {e}")
            return False
    
    def send_command(self, command):
        """发送命令到继电器"""
        try:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.write(command)
                logging.info(f"发送命令: {command.hex(' ')}")
                
                # 等待并读取响应（可选）
                time.sleep(0.1)
                if self.serial_conn.in_waiting > 0:
                    response = self.serial_conn.read(self.serial_conn.in_waiting)
                    logging.info(f"收到响应: {response.hex(' ')}")
                return True
            else:
                logging.error("串口未连接或已关闭")
                return False
        except Exception as e:
            logging.error(f"发送命令失败: {e}")
            return False
    
    def open_relay(self):
        """打开继电器"""
        logging.info("发送打开继电器命令...")
        return self.send_command(self.OPEN_COMMAND)
    
    def close_relay(self):
        """关闭继电器"""
        logging.info("发送关闭继电器命令...")
        return self.send_command(self.CLOSE_COMMAND)
    
    def ping_test(self):
        """执行ping测试"""
        try:
            # 根据操作系统选择ping命令参数
            if sys.platform.startswith('win'):
                cmd = ['ping', '-n', '1', '-w', str(self.ping_timeout * 1000), self.ping_target]
            else:
                cmd = ['ping', '-c', '1', '-W', str(self.ping_timeout), self.ping_target]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.ping_timeout + 2
            )
            
            if result.returncode == 0:
                logging.info(f"Ping测试成功: {self.ping_target} 可达")
                return True
            else:
                logging.warning(f"Ping测试失败: {self.ping_target} 不可达")
                return False
                
        except subprocess.TimeoutExpired:
            logging.warning(f"Ping测试超时: {self.ping_target}")
            return False
        except Exception as e:
            logging.error(f"Ping测试异常: {e}")
            return False
    
    def disconnect_serial(self):
        """断开串口连接"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logging.info("串口连接已断开")
    
    def run_control_loop(self):
        """运行继电器控制主循环"""
        logging.info("启动继电器控制程序...")
        logging.info(f"配置信息: 串口={self.port}, 波特率={self.baudrate}, ping目标={self.ping_target}")
        
        # 连接串口
        if not self.connect_serial():
            logging.error("无法连接串口，程序退出")
            return False
        
        try:
            loop_count = 0
            while True:
                loop_count += 1
                logging.info(f"\n=== 开始第 {loop_count} 次循环 ===")
                
                # 步骤2: 发送打开命令
                if not self.open_relay():
                    logging.error("发送打开命令失败，继续尝试...")
                    time.sleep(1)
                    continue
                
                # 步骤3: 延时50秒
                logging.info("等待后进行ping测试...")
                for i in range(self.time_wait_to_ping, 0, -1):
                    time.sleep(1)
                    if i % 5 == 0 or i <= 5:
                        logging.info(f"倒计时: {i}秒")
                
                # 执行ping测试
                ping_success = self.ping_test()
                
                if ping_success:
                    # ping通，发送关闭命令
                    if not self.close_relay():
                        logging.error("发送关闭命令失败")
                    
                    # 延时3秒后继续循环
                    logging.info("等待3秒后继续下一次循环...")
                    time.sleep(3)
                else:
                    # ping不通，退出程序
                    logging.warning("Ping测试失败，退出程序循环")
                    break
                    
        except KeyboardInterrupt:
            logging.info("收到中断信号，程序退出")
        except Exception as e:
            logging.error(f"程序运行异常: {e}")
        finally:
            self.disconnect_serial()
            logging.info("继电器控制程序结束")
        
        return True

def control_instance(port='COM1', time_wait_to_ping=50, ping_target='8.8.8.8'):
    """主函数
    Args:
        port (str): 串口号 (默认: COM1)
        time_wait_to_ping (int): 延时 (默认: 50s)
        ping_target (str): ping测试目标IP (默认: 8.8.8.8)
    """
    # 创建控制器实例
    controller = RelayController(port=port, baudrate=9600)
    controller.ping_target = ping_target
    controller.time_wait_to_ping = time_wait_to_ping
    
    # 运行控制循环
    controller.run_control_loop()

if __name__ == "__main__":
    control_instance(port='COM24', time_wait_to_ping=50, ping_target='192.168.13.169')