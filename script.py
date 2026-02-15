import os
import re
import sys
import time
import random
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==================== 配置 ====================
REQUEST_DELAY = 2.0
REQUEST_JITTER = 1.5
TIMEOUT = 15
MAX_CONSECUTIVE_FAILS = 5
FAIL_PAUSE = 60
SEARCH_DAYS_BEFORE = 30
SEARCH_DAYS_AFTER = 59

# ==================== 工具函数 ====================

def get_env_variable(var_name, default_value, pattern):
    value = os.getenv(var_name, default_value)
    if not re.match(pattern, value):
        raise ValueError(f"{var_name} 格式错误: {value}")
    return value


def get_env_int(var_name, default_value):
    value = os.getenv(var_name, str(default_value))
    if not value.isdigit() or int(value) <= 0:
        raise ValueError(f"{var_name} 必须为正整数: {value}")
    return int(value)


def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=1,
        backoff_factor=5,
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
        'Referer': 'https://www.win-rar.com/start.html?&L=7',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache',
    })
    return session


def build_url(ver, date_part, path_type):
    return f"https://www.win-rar.com/fileadmin/winrar-versions/sc/sc{date_part}/{path_type}/winrar-x64-{ver}sc.exe"


def smart_delay():
    delay = REQUEST_DELAY + random.uniform(0, REQUEST_JITTER)
    time.sleep(delay)


def check_url(session, url):
    try:
        r = session.head(url, timeout=TIMEOUT, allow_redirects=True)
        return r.status_code, None
    except requests.RequestException as e:
        return None, e


# ==================== 核心逻辑 ====================

def test_url(ver, date, format_type, path_type, session, batch_size, batch_pause):
    checked_days = 0
    batch_count = 0
    consecutive_fails = 0
    mindate = date - timedelta(days=SEARCH_DAYS_BEFORE)
    maxdate = date + timedelta(days=SEARCH_DAYS_AFTER)

    total_days = (maxdate - mindate).days + 1
    total_batches = (total_days + batch_size - 1) // batch_size
    current_batch = 1

    sys.stdout.write(f"\n{'='*60}\n")
    sys.stdout.write(f"使用 {format_type} 格式 + /{path_type}/ 路径\n")
    sys.stdout.write(f"测试 WinRAR {ver} 版本的下载地址\n")
    sys.stdout.write(f"搜索范围: {mindate.strftime('%Y%m%d')} ~ {maxdate.strftime('%Y%m%d')} (共 {total_days} 天)\n")
    sys.stdout.write(f"每组 {batch_size} 个请求，组间暂停 {batch_pause} 秒，预计 {total_batches} 组\n")
    sys.stdout.write(f"{'='*60}\n\n")
    sys.stdout.flush()

    current = mindate
    while current <= maxdate:
        checked_days += 1
        batch_count += 1

        if format_type == 'YYYYMMDD':
            date_part = current.strftime('%Y%m%d')
        elif format_type == 'YYYYDDMM':
            date_part = current.strftime('%Y%d%m')
        else:
            raise ValueError("Unknown date format type")

        url = build_url(ver, date_part, path_type)
        progress = f"[{checked_days}/{total_days}]"
        sys.stdout.write(f"{progress} 测试: {url}  ")
        sys.stdout.flush()

        status, error = check_url(session, url)

        if status is not None:
            sys.stdout.write(f"{status}\n")
            sys.stdout.flush()
            consecutive_fails = 0

            if status == 200:
                sys.stdout.write(f"\n{'='*60}\n")
                sys.stdout.write(f"✅ 成功获取到 WinRAR {ver} 版本的下载地址！\n")
                sys.stdout.write(f"\n")
                sys.stdout.write(f"  64位: {url}\n")
                sys.stdout.write(f"\n")
                sys.stdout.write(f"  本次共检查了 {checked_days} 天的数据\n")
                sys.stdout.write(f"{'='*60}\n")
                sys.stdout.flush()
                return True, session
        else:
            error_name = type(error).__name__
            sys.stdout.write(f"失败({error_name})\n")
            sys.stdout.flush()
            consecutive_fails += 1

            if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                sys.stdout.write(f"\n⚠️  连续 {consecutive_fails} 次超时，已被限速！"
                                 f"等待 {FAIL_PAUSE} 秒...\n")
                sys.stdout.flush()
                session.close()
                time.sleep(FAIL_PAUSE)
                session = create_session()
                consecutive_fails = 0
                batch_count = 0
                sys.stdout.write("已重建连接会话\n\n")
                sys.stdout.flush()
                continue

        # 移到下一天
        current += timedelta(days=1)

        # 后面还有请求时才需要延迟
        if current <= maxdate:
            if batch_count >= batch_size:
                current_batch += 1
                sys.stdout.write(f"\n⏸️  第 {current_batch-1} 组完成，主动暂停 {batch_pause} 秒防止被限速...\n")
                sys.stdout.flush()
                session.close()
                time.sleep(batch_pause)
                session = create_session()
                batch_count = 0
                sys.stdout.write(f"▶️  开始第 {current_batch}/{total_batches} 组\n\n")
                sys.stdout.flush()
            else:
                smart_delay()

    sys.stdout.write(f"\n❌ 未找到有效的下载地址，本次共检查了 {checked_days} 天的数据\n")
    sys.stdout.flush()
    return False, session


# ==================== 主程序 ====================

def main():
    ver = get_env_variable('WINRAR_VERSION', '571', r'^\d{3}$')
    date_str = get_env_variable('WINRAR_DATE', '20190509', r'^\d{8}$')
    path_type = get_env_variable('PATH_TYPE', 'rrlb', r'^(rrlb|wrr)$')
    batch_size = get_env_int('BATCH_SIZE', 30)
    batch_pause = get_env_int('BATCH_PAUSE', 30)
    date = datetime.strptime(date_str, '%Y%m%d')

    sys.stdout.write(f"WinRAR 版本: {ver}\n")
    sys.stdout.write(f"参考日期: {date_str}\n")
    sys.stdout.write(f"路径类型: {path_type}\n")
    sys.stdout.write(f"每组请求数: {batch_size}\n")
    sys.stdout.write(f"组间暂停: {batch_pause} 秒\n")
    sys.stdout.flush()

    session = create_session()

    found, session = test_url(ver, date, 'YYYYMMDD', path_type, session, batch_size, batch_pause)

    if not found:
        sys.stdout.write(f"\n⏳ 等待 {FAIL_PAUSE} 秒后尝试 YYYYDDMM 格式...\n")
        sys.stdout.flush()
        session.close()
        time.sleep(FAIL_PAUSE)
        session = create_session()
        found, session = test_url(ver, date, 'YYYYDDMM', path_type, session, batch_size, batch_pause)

    session.close()

    if not found:
        sys.stdout.write("\n❌ 两个格式都未找到有效下载链接\n")
        sys.stdout.flush()


if __name__ == '__main__':
    main()
