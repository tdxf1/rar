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

def test_url(ver, date, format_type):
    checked_days = 0
    mindate = date - timedelta(days=30)
    maxdate = mindate + timedelta(days=90)  # 往后查找 90 天
    
    print(f"\n开始使用 {format_type} 格式测试 WinRAR {ver} 版本的下载地址...")

    while mindate <= maxdate:
        checked_days += 1
        if format_type == 'YYYYMMDD':
            date_part = mindate.strftime('%Y%m%d')
        elif format_type == 'YYYYDDMM':
            date_part = mindate.strftime('%Y%d%m')
        else:
            raise ValueError("Unknown date format type")

        if int(ver) >= 580:
            url = f"https://www.win-rar.com/fileadmin/winrar-versions/sc/sc{date_part}/rrlb/winrar-x64-{ver}sc.exe"
        else:
            url = f"https://www.win-rar.com/fileadmin/winrar-versions/sc{date_part}/wrr/winrar-x64-{ver}sc.exe"

        print(f"测试: {url}", end="  ")
        
        try:
            r = requests.get(url, timeout=5)
            print(r.status_code)
            if r.status_code == 200:
                if int(ver) >= 580:
                    url_64 = f"https://www.win-rar.com/fileadmin/winrar-versions/sc/sc{date_part}/rrlb/winrar-x64-{ver}sc.exe"
                    url_32 = f"https://www.win-rar.com/fileadmin/winrar-versions/sc/sc{date_part}/rrlb/wrar{ver}sc.exe"
                else:
                    url_64 = f"https://www.win-rar.com/fileadmin/winrar-versions/sc{date_part}/wrr/winrar-x64-{ver}sc.exe"
                    url_32 = f"https://www.win-rar.com/fileadmin/winrar-versions/sc{date_part}/wrr/wrar{ver}sc.exe"
                
                print(f"\n成功获取到 WinRAR {ver} 版本的下载地址\n\n32位：{url_32}\n64位：{url_64}")
                print(f"\n本次共检查了 {checked_days} 天的数据")
                return True
        except requests.RequestException as e:
            print(f"请求失败: {e}")

        mindate += timedelta(days=1)

    print(f"\n未找到有效的下载地址，本次共检查了 {checked_days} 天的数据")
    return False

# 解析日期
date = datetime.strptime(date_str, '%Y%m%d')

# 先查 YYYYMMDD 格式
found = test_url(ver, date, 'YYYYMMDD')

# 如果未找到，再查 YYYYDDMM 格式
if not found:
    found = test_url(ver, date, 'YYYYDDMM')

if not found:
    print("\n两个格式都未找到有效下载链接")
