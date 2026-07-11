import telnetlib

import re

#移除颜色打印控制符
def remove_ansi_escape_codes(text):
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)



def telnet_execute_command(host, port, user, password, command):
  # 连接 Telnet 服务器
  tn = telnetlib.Telnet(host, port)
  #tn.set_debuglevel(7)
  # 输入用户名
  tn.read_until(b"login: ")
  tn.write(user.encode('ascii') + b"\n")
  #print("enter name:"+user)
  # 输入密码
  if password is not None:
    tn.read_until(b"Password: ")
    tn.write(password.encode('ascii') + b"\n")
  else:
    pass
    #print("no password ")
  
  #清除缓冲区中的用户名密码打印，防止影响命令输出回码获取
  tn.read_until(b"prompt",1)
  tn.read_eager()

  # 执行命令，例如获取当前目录下的文件列表
  tn.write(command.encode('ascii')+b"\n")
  #print("enter cmd:"+command)

  # 读取命令输出数据
  output = tn.read_until(b"prompt",1)
  output_clean=remove_ansi_escape_codes(output.decode('ascii'))
  data_output=output_clean.split("\n")

  # 关闭 Telnet 连接
  tn.close()
  return data_output


if "__main__" == __name__:
    HOST = "192.168.15.35"
    PORT = 23  # Telnet 默认端口是23
    user = "root"
    password = None
    cmd="ls"
    output_list=telnet_execute_command(HOST,PORT,user,password,cmd)
    print(output_list)