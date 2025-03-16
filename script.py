import os
import re
from datetime import datetime, timedelta
import requests

# 获取 GitHub Actions 传递的参数
def get_env_variable(var_name, default_value, pattern):
    value = os.getenv(var_name, default_value)
    if not re.match(pattern, value):
        raise ValueError(f"{var_name} 格式错误: {value}")
    return value

# 读取环境变量
ver = get_env_variable('WINRAR_VERSION', '571', r'^\d{3}$')
date_str = get_env_variable('WINRAR_DATE', '20190509', r'^\d{8}$')

# 解析日期
date = datetime.strptime(date_str, '%Y%m%d')
maxdate = date + timedelta(days=365)  # 结束日期 = 输入日期 + 365 天
mindate = date  # 起始日期 = 输入日期
checked_days = 0  # 统计检查的天数

print(f"开始测试 WinRAR {ver} 版本的下载地址...")

while maxdate >= mindate:
    checked_days += 1  # 统计检查的日期数
    if int(ver) >= 580:
        url = f"https://www.win-rar.com/fileadmin/winrar-versions/sc/sc{maxdate.strftime('%Y%m%d')}/rrlb/winrar-x64-{ver}sc.exe"
    else:
        url = f"https://www.win-rar.com/fileadmin/winrar-versions/sc{maxdate.strftime('%Y%m%d')}/wrr/winrar-x64-{ver}sc.exe"

    print(f"测试: {url}", end="  ")
    
    try:
        r = requests.get(url, timeout=5)
        print(r.status_code)
        if r.status_code == 200:
            if int(ver) >= 580:
                url_64 = f"https://www.win-rar.com/fileadmin/winrar-versions/sc/sc{maxdate.strftime('%Y%m%d')}/rrlb/winrar-x64-{ver}sc.exe"
                url_32 = f"https://www.win-rar.com/fileadmin/winrar-versions/sc/sc{maxdate.strftime('%Y%m%d')}/rrlb/wrar{ver}sc.exe"
            else:
                url_64 = f"https://www.win-rar.com/fileadmin/winrar-versions/sc{maxdate.strftime('%Y%m%d')}/wrr/winrar-x64-{ver}sc.exe"
                url_32 = f"https://www.win-rar.com/fileadmin/winrar-versions/sc{maxdate.strftime('%Y%m%d')}/wrr/wrar{ver}sc.exe"
            
            print(f"\n成功获取到 WinRAR {ver} 版本的下载地址\n\n32位：{url_32}\n64位：{url_64}")
            print(f"\n本次共检查了 {checked_days} 天的数据")
            break
    except requests.RequestException as e:
        print(f"请求失败: {e}")

    maxdate -= timedelta(days=1)
    
    if maxdate < mindate:
        print(f"\n未找到有效的下载地址，本次共检查了 {checked_days} 天的数据")
        break
