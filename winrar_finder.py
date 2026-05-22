import requests
import re
import time
import sys
import os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

# ─────────────────────────────────────────────────────────────
# Read parameters from environment variables
# ─────────────────────────────────────────────────────────────
DAYS_BEFORE      = int(os.environ.get("DAYS_BEFORE",      "10"))   # Days to search before release date
BATCH_SIZE       = int(os.environ.get("BATCH_SIZE",       "30"))   # Requests per batch before pausing
BATCH_INTERVAL   = int(os.environ.get("BATCH_INTERVAL",   "60"))   # Pause duration between batches (seconds)
REQUEST_INTERVAL = float(os.environ.get("REQUEST_INTERVAL", "1.0")) # Delay between individual requests (seconds)
SUBDIR_FILTER    = os.environ.get("SUBDIR", "").strip().lower()     # Limit to "wrr", "rrlb", or "" (both)

BASE_URL = "https://www.win-rar.com/fileadmin/winrar-versions/sc"
NEWS_URL = "https://www.win-rar.com/latestnews.html?&L=0"

def log(msg: str):
    print(msg, flush=True)

# ─────────────────────────────────────────────────────────────
# 1. Fetch the latest stable release information
# ─────────────────────────────────────────────────────────────
log("=" * 60)
log("Fetching latest WinRAR stable release info...")
log(f"   News page: {NEWS_URL}")
log("=" * 60)

try:
    resp = requests.get(NEWS_URL, timeout=15)
    resp.raise_for_status()
    log(f"Page fetched successfully. HTTP {resp.status_code}, size {len(resp.content)} bytes")
except requests.RequestException as e:
    log(f"ERROR: Could not access news page: {e}")
    sys.exit(1)

soup = BeautifulSoup(resp.text, "html.parser")

release_date       = None
version            = None
version_nodot      = None
latest_final_title = None

log("\nParsing news items...")
item_count = 0
for item in soup.find_all("div", class_="news-list-item"):
    item_count += 1
    date_tag  = item.find("span", class_="news-list-date")
    h2        = item.find("h2")
    title_tag = h2.find("a") if h2 else None

    if not date_tag or not title_tag:
        continue

    title_text = title_tag.text.strip()
    date_text  = date_tag.text.strip()
    log(f"   [{item_count:02d}] {date_text} | {title_text}")

    if "Final released" not in title_text:
        log("        Skipping (not a stable release)")
        continue

    date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', date_text)
    if date_match:
        day, month, year = date_match.groups()
        release_date = f"{year}-{month}-{day}"
        log(f"        Parsed date: {date_text} -> {release_date}")
    else:
        log(f"        WARNING: Failed to parse date: {date_text}")

    ver_match = re.search(r'WinRAR\s+(\d+\.\d+)', title_text)
    if ver_match:
        version            = ver_match.group(1)
        version_nodot      = version.replace('.', '')
        latest_final_title = title_text
        log(f"        Parsed version: {version} (no-dot: {version_nodot})")
        break
    else:
        log(f"        WARNING: Failed to parse version from: {title_text}")

log(f"\nScanned {item_count} news items total")

if not release_date or not version:
    log("ERROR: Could not find a stable release entry or version number")
    sys.exit(1)

log("")
log("=" * 60)
log(f"Latest stable release : {latest_final_title}")
log(f"Release date          : {release_date}")
log(f"Version               : {version}  (filename variant: {version_nodot})")

file_name  = f"winrar-x64-{version_nodot}sc.exe"
public_url = (f"https://www.win-rar.com/fileadmin/winrar-versions/"
              f"partners/hua/{file_name}")
log(f"Target filename       : {file_name}")
log(f"Public commercial URL : {public_url}")
log("=" * 60)

# ─────────────────────────────────────────────────────────────
# 2. Build the search date range
#    Order: release day first -> forward to today -> backward N days
# ─────────────────────────────────────────────────────────────
base_date = datetime.strptime(release_date, "%Y-%m-%d")
today     = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=None)

start_date = base_date - timedelta(days=DAYS_BEFORE)
end_date   = today

forward_dates, backward_dates = [], []
d = base_date
while d <= end_date:
    forward_dates.append(d)
    d += timedelta(days=1)

d = base_date - timedelta(days=1)
while d >= start_date:
    backward_dates.append(d)
    d -= timedelta(days=1)

all_dates  = forward_dates + backward_dates
total_days = len(all_dates)

log(f"\nSearch date range:")
log(f"   Base    : {base_date.date()} (release day, highest priority)")
log(f"   Forward : up to {end_date.date()} (today)")
log(f"   Backward: down to {start_date.date()} ({DAYS_BEFORE} days before release)")
log(f"   Total   : {total_days} dates")

# ─────────────────────────────────────────────────────────────
# 3. Build 4 scan rounds
#    Each round = one (subdirectory + date-format) combination
#    covering all dates in the list.
#
#    Round 1: wrr  + YYYYMMDD
#    Round 2: wrr  + YYYYDDMM
#    Round 3: rrlb + YYYYMMDD
#    Round 4: rrlb + YYYYDDMM
# ─────────────────────────────────────────────────────────────
ALL_ROUNDS = [
    ("wrr",  "YYYYMMDD", lambda d: d.strftime('%Y%m%d')),
    ("wrr",  "YYYYDDMM", lambda d: d.strftime('%Y%d%m')),
    ("rrlb", "YYYYMMDD", lambda d: d.strftime('%Y%m%d')),
    ("rrlb", "YYYYDDMM", lambda d: d.strftime('%Y%d%m')),
]

if SUBDIR_FILTER in ("wrr", "rrlb"):
    ROUNDS = [(s, f, fn) for s, f, fn in ALL_ROUNDS if s == SUBDIR_FILTER]
    log(f"SUBDIR filter active: only scanning [{SUBDIR_FILTER}]")
else:
    ROUNDS = ALL_ROUNDS
    log("SUBDIR filter: none (scanning both wrr and rrlb)")

total_rounds = len(ROUNDS)
log(f"\nScan rounds   : {total_rounds} rounds x {total_days} dates each")
log(f"Batch settings: pause every {BATCH_SIZE} requests for {BATCH_INTERVAL}s")
log(f"Request delay : {REQUEST_INTERVAL}s between each individual request")
log(f"\nRound preview:")
for i, (sub, fmt, _) in enumerate(ROUNDS, 1):
    log(f"   Round {i}: [{sub:4s}] + {fmt}")

# ─────────────────────────────────────────────────────────────
# 4. Main scan loop
# ─────────────────────────────────────────────────────────────
found_url    = None
found_sub    = None
found_fmt    = None
total_probed = 0
probe_start  = time.time()

log("\n" + "=" * 60)
log("Starting scan...")
log("=" * 60)

outer_break = False

for round_idx, (sub, fmt_name, fmt_func) in enumerate(ROUNDS, 1):
    if outer_break:
        break

    log(f"\n{'─' * 60}")
    log(f"Round {round_idx}/{total_rounds}: [{sub:4s}] + {fmt_name}  ({total_days} dates)")
    log(f"{'─' * 60}")

    round_probed = 0

    for date_idx, test_date in enumerate(all_dates, 1):
        if outer_break:
            break

        date_str = fmt_func(test_date)

        # Skip duplicate dates where YYYYMMDD == YYYYDDMM (e.g. 2025-01-01)
        ymd = test_date.strftime('%Y%m%d')
        ydm = test_date.strftime('%Y%d%m')
        if fmt_name == "YYYYDDMM" and ymd == ydm:
            log(f"   [{date_idx:04d}/{total_days}] {test_date.strftime('%Y-%m-%d')} "
                f"sc{date_str} -- Both formats identical, skipping")
            continue

        url = f"{BASE_URL}/sc{date_str}/{sub}/{file_name}"
        total_probed += 1
        round_probed += 1
        elapsed       = time.time() - probe_start

        log(f"   [{date_idx:04d}/{total_days}] "
            f"{test_date.strftime('%Y-%m-%d')} sc{date_str} "
            f"[{sub:4s}] "
            f"total={total_probed} round={round_probed} elapsed={elapsed:.1f}s")
        log(f"            -> {url}")

        # ── HEAD request ───────────────────────────────────────
        try:
            r      = requests.head(url, timeout=10, allow_redirects=True)
            status = r.status_code
        except requests.RequestException as e:
            log(f"            WARNING: Request error: {e}")
            status = -1

        if status == 200:
            found_url = url
            found_sub = sub
            found_fmt = date_str
            tag = "[rrlb]" if sub == "rrlb" else "[wrr ]"
            log(f"            SUCCESS: HTTP 200 {tag} - Match found! Stopping all scans.")
            outer_break = True
            break
        else:
            log(f"            HTTP {status}")

        # ── Per-request delay ──────────────────────────────────
        time.sleep(REQUEST_INTERVAL)

        # ── Batch pause ────────────────────────────────────────
        if total_probed % BATCH_SIZE == 0:
            log(f"\n   Batch pause: {total_probed} requests completed "
                f"({round_probed} this round). Sleeping {BATCH_INTERVAL}s...\n")
            time.sleep(BATCH_INTERVAL)

    if not outer_break:
        log(f"\n   Round {round_idx} complete. {round_probed} requests, no match found.")

log("\n" + "=" * 60)
total_elapsed = time.time() - probe_start
log(f"Scan complete: {total_probed} requests, {total_elapsed:.1f}s elapsed")

# ─────────────────────────────────────────────────────────────
# 5. Print results
# ─────────────────────────────────────────────────────────────
log("")
log("=" * 60)
log("Final Results")
log("=" * 60)
log(f"  Version          : {version}")
log(f"  Release date     : {release_date}")
log(f"  Filename         : {file_name}")
log(f"  Public URL       : {public_url}")
log("")

if found_url:
    tag = "[rrlb]" if found_sub == "rrlb" else "[wrr ]"
    log(f"  {tag} Hidden URL : {found_url}")
    log(f"  Subdirectory   : {found_sub}")
    log(f"  Date segment   : sc{found_fmt}")
else:
    log("  No hidden URL found.")
    log(f"  Fallback public URL: {public_url}")

# ─────────────────────────────────────────────────────────────
# 6. Write outputs for GitHub Actions
# ─────────────────────────────────────────────────────────────
github_output = os.environ.get("GITHUB_OUTPUT", "")
if github_output:
    with open(github_output, "a", encoding="utf-8") as f:
        f.write(f"version={version}\n")
        f.write(f"version_nodot={version_nodot}\n")
        f.write(f"release_date={release_date}\n")
        f.write(f"file_name={file_name}\n")
        f.write(f"public_url={public_url}\n")
        f.write(f"found_url={found_url or ''}\n")
        f.write(f"found_sub={found_sub or ''}\n")
    log("\nResults written to GITHUB_OUTPUT")

log("=" * 60)
log("Script finished.")
log("=" * 60)
