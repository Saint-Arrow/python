## 验证是否会出现unsync的情况


### 测试请求
```
http://192.168.13.169:8081/cgi-bin/smpte2059?action=GET%20ST2110_ENC_STREAM_SYNC%2020
```
返回值:
```
RGET ST2110_ENC_STREAM_SYNC 20 1
```
返回值最后一个字段1代表sync，0代表异常情况，unsync

#### 测试异常动作
- 不再进行reboot
- 打印单前的成功循环次数

####测试成功动作
- 进行reboot，开始下一轮测试

### reboot 请求
```
http://192.168.13.169:8080/api/upgrade/reboot
``` 

#### 等待时间
reboot之后等待一段时间之后再进行测试，这个时间配置为40s

### 用户中断的动作
- 打印目前的成功循环次数