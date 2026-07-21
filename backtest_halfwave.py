# ============================================================
# 三彩 V11.3 (修复版)
# 第一部分：
# 配置 + 数据获取模块 fetch_lottery
#
# 修复说明:
# 原代码把接口返回的 lottery_data 列表(每个元素是"一个彩种")
# 误当成"每期开奖记录"去解析,导致找不到 tm/teMa 等字段,
# 数据要么为空要么错乱。
#
# 真实接口结构:
# {
#   "lottery_data": [
#       {"name":"香港彩", "expect":"2026077",
#        "numbers":[7个号码,最后一个是特码],
#        "history":["2026077 期：18,30,26,21,44,32,27", ...]},
#       {"name":"新澳门彩", ...},
#       {"name":"老澳门彩", ...},
#       ...
#   ]
# }
#
# 所以正确做法是:
# 1. 请求一次,拿到 lottery_data
# 2. 按 name 字段找到目标彩种
# 3. 解析它的 history 里的文本行 "期号 期：n1,n2,...,n7"
#    取最后一个数字作为特码
# ============================================================

import requests
import re
import datetime
import time


# ============================================================
# 基础配置
# ============================================================

VERSION = "V11.3-fixed"

# 三个彩种共用同一个接口地址,name 必须和接口里的 "name" 字段完全一致
LOTTERY_CONFIG = {

    "香港彩": {
        "url": "https://marksix6.net/index.php?api=1",
        "name": "香港彩"
    },

    "新澳门彩": {
        "url": "https://marksix6.net/index.php?api=1",
        "name": "新澳门彩"
    },

    "老澳门彩": {
        "url": "https://marksix6.net/index.php?api=1",
        "name": "老澳门彩"
    }

}


# 历史数量
HISTORY_LIMIT = 500


# ============================================================
# 请求头
# ============================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*"
}


# ============================================================
# 颜色数据库
# ============================================================

RED = {1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE = {3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
GREEN = {5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}


def get_color(num):
    num = int(num)
    if num in RED:
        return "红"
    elif num in BLUE:
        return "蓝"
    elif num in GREEN:
        return "绿"
    else:
        return "未知"


# ============================================================
# 数字属性
# ============================================================

def number_feature(num):
    num = int(num)
    return {
        "num": num,
        "tail": num % 10,
        "big": True if num >= 25 else False,
        "odd": True if num % 2 == 1 else False,
        "r3": num % 3,
        "r5": num % 5,
        "r7": num % 7,
        "color": get_color(num)
    }


# ============================================================
# 解析 history 里的单行文本
# 格式例: "2026077 期：18,30,26,21,44,32,27"
# 返回 (issue, special_num) 或 None
# ============================================================

def parse_history_line(line):

    if not line:
        return None

    try:
        # 兼容全角/半角冒号
        parts = re.split(r"期[:：]", line, maxsplit=1)

        if len(parts) != 2:
            return None

        issue = parts[0].strip()
        nums_part = parts[1].strip()

        nums = [
            n.strip()
            for n in re.split(r"[,，]", nums_part)
            if n.strip() != ""
        ]

        if len(nums) < 7:
            return None

        # 最后一个数字是特码
        special = int(nums[-1])

        if not (1 <= special <= 49):
            return None

        return issue, special

    except Exception:
        return None


# ============================================================
# 核心 fetch_lottery
# ============================================================

def fetch_lottery(name):

    print()
    print("📡 获取数据:", name)

    cfg = LOTTERY_CONFIG[name]

    try:
        r = requests.get(cfg["url"], headers=HEADERS, timeout=10)
        data = r.json()

    except Exception as e:
        print("❌接口失败:", e)
        return []

    lottery_list = data.get("lottery_data")

    if not isinstance(lottery_list, list) or len(lottery_list) == 0:
        print("❌没有找到开奖列表(lottery_data 为空)")
        return []

    # ------------------------------------------------
    # 按 name 找到目标彩种
    # ------------------------------------------------

    target = None

    for item in lottery_list:
        if isinstance(item, dict) and item.get("name") == name:
            target = item
            break

    if target is None:
        available = [
            x.get("name")
            for x in lottery_list
            if isinstance(x, dict)
        ]
        print("❌未在接口中找到彩种:", name, " 可用彩种:", available)
        return []

    records = []
    seen_issues = set()

    # ------------------------------------------------
    # 先加入最新一期(expect + numbers)
    # 防止 history 更新有延迟,漏掉最新一期
    # ------------------------------------------------

    latest_issue = target.get("expect")
    latest_numbers = target.get("numbers")

    if latest_issue and isinstance(latest_numbers, list) and len(latest_numbers) >= 7:

        try:
            special = int(latest_numbers[-1])

            if 1 <= special <= 49:
                records.append({
                    "issue": latest_issue,
                    "num": special,
                    "feature": number_feature(special)
                })
                seen_issues.add(latest_issue)

        except Exception:
            pass

    # ------------------------------------------------
    # 解析历史文本行
    # ------------------------------------------------

    history_lines = target.get("history", [])

    for line in history_lines:

        parsed = parse_history_line(line)

        if parsed is None:
            continue

        issue, special = parsed

        if issue in seen_issues:
            continue

        records.append({
            "issue": issue,
            "num": special,
            "feature": number_feature(special)
        })

        seen_issues.add(issue)

    result = records[:HISTORY_LIMIT]

    print("✅ 获取", len(result), "期")

    return result


# ============================================================
# 数据校验 (逻辑不变)
# ============================================================

def check_data(data):

    print()
    print("🔍 数据校验")

    if len(data) == 0:
        print("❌ 无数据")
        return False

    latest = data[0]

    print("最新期:", latest["issue"])
    print("最新特码:", latest["num"])
    print("颜色:", latest["feature"]["color"])

    if 1 <= latest["num"] <= 49:
        print("✅特码范围正常")
        return True
    else:
        print("❌特码异常")
        return False


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print("三彩", VERSION, "数据模块测试(修复版)")
    print("=" * 70)

    for name in LOTTERY_CONFIG:

        data = fetch_lottery(name)

        check_data(data)
