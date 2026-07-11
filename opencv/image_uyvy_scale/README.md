## 需求
输入文件为一张图片，数据格式如下:
```
U Y V Y U Y V Y U Y V Y 
U Y V Y U Y V Y U Y V Y 
```

要求输出为一张缩小后的图片，数据格式如下:
```
U Y V Y U Y V Y U Y V Y 
U Y V Y U Y V Y U Y V Y 
```
但是分辨率为原来的一半。

## 实现
- Y分量采用奇数行和偶数行的4个Y的平均值
- U分量采用奇数行和偶数行的2个U的平均值
- V分量采用奇数行和偶数行的2个V的平均值

## 输入参数
- 指定输入文件的文件名
- 解析输入的分辨率，如3840x2160的格式 
- 输出文件为out_uyvy.bin

## 使用方法

### 缩放（W/2, H/2）
```bash
python uyvy_scale.py -i in_uyvy.bin -s 3840x2160 -o out_uyvy.bin
```

### 调试打印（不缩放）
```bash
python uyvy_scale.py -i in_uyvy.bin -s 3840x2160 -d 0x0
```

