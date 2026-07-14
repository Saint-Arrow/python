#!/bin/sh

# 网络接口名称（需要根据实际情况修改，如eth0、ens33、enp0s3等）
INTERFACE="eth0"
# 目标ping服务器
TARGET_IP="192.168.13.166"
# 日志文件路径
LOG_FILE="/data/ifconfig_loop.log"
# ping测试次数
PING_COUNT=3
# 初始成功计数
SUCCESS_COUNT=0

echo "$(date '+%Y-%m-%d %H:%M:%S') - 脚本启动" >> "$LOG_FILE"

while true; do
    # 使用 ip link 替代 ifconfig down/up
    # ip link down 只关闭接口，不会清除IP和路由配置，重新 up 后自动恢复
    # 但是网关是不会恢复的
    
    # ifconfig down (使用ip命令)
    echo "$(date '+%Y-%m-%d %H:%M:%S') - 执行: ip link set $INTERFACE down" >> "$LOG_FILE"
    ip link set "$INTERFACE" down
    
    # # 等待100ms
    # sleep 0.1
    
    # # ifconfig up (使用ip命令)
    # echo "$(date '+%Y-%m-%d %H:%M:%S') - 执行: ip link set $INTERFACE up" >> "$LOG_FILE"
    ip link set "$INTERFACE" up
    
    # 等待100ms让网络稳定
    sleep 0.1
    
    # ping测试
    #echo "$(date '+%Y-%m-%d %H:%M:%S') - 执行: ping -c $PING_COUNT $TARGET_IP" >> "$LOG_FILE"
    if ping -c "$PING_COUNT" "$TARGET_IP" > /dev/null 2>&1; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 20))
        echo "$(date '+%Y-%m-%d %H:%M:%S') - ping total: $SUCCESS_COUNT" >> "$LOG_FILE"
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') - ping fail" >> "$LOG_FILE"
        exit 1
    fi
    
    # 显示当前统计
    echo "total: $SUCCESS_COUNT"
    
    # 等待1秒再进行下一次测试
    sleep 0.5
done
