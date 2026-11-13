$py = 'C:\Users\chen.wenjun\AppData\Local\Programs\Python\Python38\python.exe'
$srv = 'F:\WORK\VHD_CWJ_File\tool\python\python\net\nmos_demo\nmos_server.py'
$dir = 'F:\WORK\VHD_CWJ_File\tool\python\python\net\nmos_demo'

# 杀掉所有现存 nmos_server 进程
Get-CimInstance Win32_Process -Filter "CommandLine like '%nmos_server%'" | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep 1

# 用新代码（带 access.log）后台启动
Start-Process -WindowStyle Hidden $py -ArgumentList $srv, '8090' `
    -RedirectStandardOutput "$dir\server_out.txt" `
    -RedirectStandardError "$dir\server_err.txt"
Start-Sleep 3

"== STDERR (应为空) =="
Get-Content "$dir\server_err.txt" -ErrorAction SilentlyContinue | Select-Object -Last 10

"== test GET /self/ =="
try { (Invoke-RestMethod 'http://192.168.17.166:8090/x-nmos/node/v1.3/self/').label } catch { "ERR" }

Start-Sleep 1
"== access.log tail =="
Get-Content "$dir\access.log" -Tail 4 -ErrorAction SilentlyContinue
