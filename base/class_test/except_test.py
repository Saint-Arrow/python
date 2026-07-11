try:
    open("testfile", "r")
#except FileNotFoundError:
#except (ConnectionError, FileNotFoundError):
except Exception as ret:
    print ("Error: 没有找到文件或读取文件失败")
    print (ret)
else:
    print ("内容写入文件成功")