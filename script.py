import os
import re
import sys
import time
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==================== 配置 ====================
REQUEST_DELAY = 1.5         # 每次请求间隔（秒），防止触发限速
TIMEOUT = 15                # 超时时间（秒）
MAX_CONSECUTIVE_FAILS = 10  # 连续失败超过此数则暂停较长时间
LONG_PAUSE = 30             # 连续失败后的长暂停（秒）
SEARCH_DAYS_BEFORE = 30     # 向前搜索天数
SEARCH_DAYS_AFTER = 60      # 向后搜索天数（从输入日期算起）

# ==================== 工具函数 ====================

def get_env_variable(var_name, default_value, pattern):
    """读取并校验环境变量"""
    value = os.getenv(var_name, default_value)
    if not re.match(pattern, value):
        raise ValueError(f"{var_name} 格式错误: {value}")
    return value


def create_session():
    """创建带重试机制和浏览器伪装的会话"""
    session = requests.Session()

    retry_strategy = Retry(
        total=2,
        backoff_factor=3,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/126.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache',
    })
    return session


def build_url(ver, date_part):
    """构建测试用的64位下载URL"""
    if int(ver) >= 580:
        return f"https://www.win-rar.com/fileadmin/winrar-versions/sc/sc{date_part}/rrlb/winrar-x64-{ver}sc.exe"
    else:
        return f"https://www.win-rar.com/fileadmin/winrar-versions/sc{date_part}/wrr/winrar-x64-{ver}sc.exe"


def build_download_urls(ver, date_part):
    """构建最终的32位和64位下载URL"""
    if int(ver) >= 580:
        base = f"https://www.win-rar.com/fileadmin/winrar-versions/sc/sc{date_part}/rrlb"
    else:
        base = f"https://www.win-rar.com/fileadmin/winrar-versions/sc{date_part}/wrr"
    url_64 = f"{base}/winrar-x64-{ver}sc.exe"
    url_32 = f"{base}/wrar{ver}sc.exe"
    return url_32, url_64


def check_url(session, url):
    """
    检测URL是否可用
    优先使用HEAD请求（不下载文件内容）
    HEAD失败则回退到GET+stream模式（只读响应头）
    返回 (status_code, error)
    """
    # 尝试 HEAD 请求
    try:
        r = session.head(url, timeout=TIMEOUT, allow_redirects=True)
        return r.status_code, None
    except requests.RequestException:
        pass

    # HEAD 失败，尝试 GET + stream
    try:
        r = session.get(url, timeout=TIMEOUT, stream=True, allow_redirects=True)
        status = r.status_code
        r.close()
        return status, None
    except requests.RequestException as e:
        return None, e


# ==================== 核心逻辑 ====================

def test_url(ver, date, format_type, session):
    """在指定日期范围内逐日测试URL"""
    checked_days = 0
    consecutive_fails = 0
    mindate = date - timedelta(days=SEARCH_DAYS_BEFORE)
    maxdate = date + timedelta(days=SEARCH_DAYS_AFTER)

    total_days = (maxdate - mindate).days + 1
    print(f"\n{'='*60}")
    print(f"开始使用 {format_type} 格式测试 WinRAR {ver} 版本的下载地址")
    print(f"搜索范围: {mindate.strftime('%Y%m%d')} ~ {maxdate.strftime('%Y%m%d')} (共 {total_days} 天)")
    print(f"{'='*60}\n")

    current = mindate
    while current <= maxdate:
        checked_days += 1

        if format_type == 'YYYYMMDD':
            date_part = current.strftime('%Y%m%d')
        elif format_type == 'YYYYDDMM':
            date_part = current.strftime('%Y%d%m')
        else:
            raise ValueError("Unknown date format type")

        url = build_url(ver, date_part)
        progress = f"[{checked_days}/{total_days}]"
        print(f"{progress} 测试: {url}", end="  ")
        sys.stdout.flush()

        status, error = check_url(session, url)

        if status is not None:
            print(status)
            consecutive_fails = 0

            if status == 200:
                url_32, url_64 = build_download_urls(ver, date_part)
                print(f"\n{'='*60}")
                print(f"✅ 成功获取到 WinRAR {ver} 版本的下载地址！")
                print(f"")
                print(f"  32位: {url_32}")
                print(f"  64位: {url_64}")
                print(f"")
                print(f"  本次共检查了 {checked_days} 天的数据")
                print(f"{'='*60}")
                return True, session
        else:
            error_name = type(error).__name__
            print(f"失败({error_name})")
            consecutive_fails += 1

            if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                print(f"\n⚠️  连续 {consecutive_fails} 次请求失败，等待 {LONG_PAUSE} 秒后继续...")
                time.sleep(LONG_PAUSE)
                consecutive_fails = 0
                session.close()
                session = create_session()
                print("已重建连接会话\n")
                continue

        time.sleep(REQUEST_DELAY)
        current += timedelta(days=1)

    print(f"\n❌ 未找到有效的下载地址，本次共检查了 {checked_days} 天的数据")
    return False, session


# ==================== 主程序 ====================

def main():
    # 读取环境变量
    ver = get_env_variable('WINRAR_VERSION', '571', r'^\d{3}$')
    date_str = get_env_variable('WINRAR_DATE', '20190509', r'^\d{8}$')
    date = datetime.strptime(date_str, '%Y%m%d')

    print(f"WinRAR 版本: {ver}")
    print(f"参考日期: {date_str}")

    session = create_session()

    # 先查 YYYYMMDD 格式
    found, session = test_url(ver, date, 'YYYYMMDD', session)

    # 如果未找到，等待后再查 YYYYDDMM 格式
    if not found:
        print(f"\n⏳ 等待 {LONG_PAUSE} 秒后尝试 YYYYDDMM 格式...")
        time.sleep(LONG_PAUSE)
        session.close()
        session = create_session()
        found, session = test_url(ver, date, 'YYYYDDMM', session)

    session.close()

    if not found:
        print("\n❌ 两个格式都未找到有效下载链接")


if __name__ == '__main__':
    main()
