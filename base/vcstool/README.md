# vcstool - Windows 使用说明

> 项目主页: https://github.com/dirk-thomas/vcstool
>
> vcstool 是一个命令行工具，用于批量管理多个版本控制仓库（git/hg/svn/bzr），
> 常用于 ROS 工作空间的多仓库导入/导出/批量 pull。

## 一、安装

### Windows（实测可用）

```powershell
pip install vcstool
```

- 纯 Python 包，仅依赖 PyYAML，安装后自动注册 `vcs` / `vcs-import` / `vcs-export` 等 17 个命令
- 前提：已安装 Python（≥3.5）和 git，且都在 PATH 中

### Linux（官方方式，作为对照）

```bash
curl -s https://packagecloud.io/install/repositories/dirk-thomas/vcstool/script.deb.sh | sudo bash
sudo apt-get update
sudo apt-get install python3-vcstool
```

## 二、Windows 实测结论

实测环境：Windows 10 (19044) + Python 3.8.4 + git 2.29.2 + vcstool 0.3.0

| 命令 | Windows 可用性 | 说明 |
|------|---------------|------|
| `vcs import --input my.repos` | ✅ | 推荐，跨平台通用 |
| `vcs export` | ✅ | 输出到 stdout，重定向见下方注意点 |
| `vcs status` | ✅ | |
| `vcs pull` | ✅ | |
| `vcs log -l N` | ✅ | 输出带 `b'...'` 前缀，纯显示瑕疵 |
| `vcs validate --input my.repos` | ✅ | 校验 .repos 文件 |
| `vcs import < my.repos` | ❌ | **PowerShell 不支持 `<` 输入重定向**（cmd 下可用） |
| `Get-Content my.repos \| vcs import` | ❌ | PowerShell 管道编码问题导致 YAML 解析失败 |

## 三、Windows 使用的坑与正确写法

### 1. `<` 重定向：PowerShell 不支持

PowerShell 中 `<` 是保留运算符，直接报错。替代写法：

```powershell
vcs import --input my.repos          # 推荐：vcstool 自带参数，跨平台一致，还支持 URL
cmd /c "vcs import < my.repos"       # 或者借助 cmd 子shell
```

### 2. `vcs export` 没有 `--output` 参数

export 只能输出到 stdout（仅有 `--exact` / `--exact-with-tags` 两个参数）。
**PowerShell 5.1 直接 `>` 重定向会生成 UTF-16 LE 文件（FF FE 头），vcstool 读回报
`gbk codec can't decode` 错误**。正确写法：

```powershell
cmd /c "vcs export > my.repos"                    # ✅ cmd 字节直通，实测可正常读回
vcs export | Out-File my.repos -Encoding ascii    # ✅ 实测可正常读回
vcs export > my.repos                             # ❌ PS 5.1 下生成 UTF-16，读回失败
```

原因：cmd 的 `>` 只是把文件句柄接到子进程 stdout，字节原样落盘；
PowerShell 的 `>` 本质是 `Out-File`，会把输出解码成字符串再用默认编码（PS 5.1 = UTF-16）重写。
注：PowerShell 7.4+ 已改为默认 UTF-8 无 BOM，此坑自动消失。

### 3. bash 自动补全不可用

`source /usr/share/vcstool-completion/vcs.bash` 是 Linux 专属，Windows 跳过即可，不影响功能。

## 四、.repos 文件示例

本目录下的 `test.repos` 即为示例（测试遗留，可删）：

```yaml
repositories:
  vcstool-src:
    type: git
    url: https://github.com/dirk-thomas/vcstool.git
    version: master
```

## 五、常用命令速查（Windows 推荐）

```powershell
vcs import --input my.repos          # 按 .repos 批量克隆
vcs export                           # 导出当前目录下所有仓库为 YAML
cmd /c "vcs export > my.repos"       # 导出并保存到文件
vcs status                           # 批量查看状态
vcs pull                             # 批量拉取更新
vcs log -l 5                         # 批量查看最近 5 条日志
vcs validate --input my.repos        # 校验 .repos 格式
```
