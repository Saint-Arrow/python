from selenium import webdriver
import time
import os


Name = "admin"
Password = "admin"
ip="192.168.13.159"
url = 'http://admin:admin@'+ip+'/#view'
output_dir=".\\output_"+ip

def OpenUrl():
    # 访问网址
    driver.get(url)
    time.sleep(5)

def Login():
    # 查询登录按钮
    driver.find_element_by_link_text("登录").click()
    time.sleep(1)
    # 输入账号
    driver.find_element_by_id("LoginName").send_keys(Name)
    # 输入密码
    driver.find_element_by_id("Password").send_keys(Password)
    time.sleep(2)
    # 点击登录按钮
    driver.find_element_by_id("submitBtn").click()
    time.sleep(2)
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


if __name__ == "__main__":
    t=0
    mkdir(output_dir)
    option = webdriver.ChromeOptions()
    option.add_argument('headless') # 设置option
    driver = webdriver.Chrome(chrome_options=option)
    OpenUrl()


    while 1==1:
        driver.get_screenshot_as_file(os.getcwd()+"\\"+output_dir+"\\"+str(t)+".png")
        # 刷新方法 refresh
        driver.refresh() 
        time.sleep(0.5)
        driver.refresh() 
        
        print ('%s test %d pass: refresh successful' % (ip ,t))
        t=t+1
        time.sleep(5)
        
