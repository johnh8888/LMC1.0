#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新澳门六合彩 - 3注半半波策略每日预测
功能：
1. 获取新澳门彩历史开奖数据
2. 自动处理 SSL 证书过期问题
3. 网络失败自动重试
4. 解析特码
5. 计算半半波：颜色 + 大小 + 单双
6. 输出最近开奖数据
7. 输出固定3注策略
8. 自动生成 result.md
Python:
    3.10+
依赖：
    仅使用 Python 标准库
"""
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
# ============================================================
# 配置
# ============================================================
CONFIG = {
    # API 地址
    "api_url": "https://marksix6.net/index.php?api=1",
    # 获取历史期数
    "history_limit": 30,
    # 每注金额
    "bet_per_note": 100,
    # 网络设置
    "timeout": 60,
    "retry_times": 3,
    "retry_delay": 3,
    # 3注策略
    "bets": [
        {
            "name": "蓝小单",
            "odds": 15.76,
            "numbers": [3, 9, 15, 21],
        },
        {
            "name": "绿大单",
            "odds": 11.82,
            "numbers": [27, 33, 39, 43, 49],
        },
        {
            "name": "蓝大双",
            "odds": 11.82,
            "numbers": [26, 36, 42, 47, 48],
        },
    ],
}
# ============================================================
# 香港/澳门六合彩波色
# ============================================================
RED = {
    1, 2, 7, 8, 12, 13, 18, 19,
    23, 24, 29, 30, 34, 35, 40,
    45, 46,
}
BLUE = {
    3, 4, 9, 10, 14, 15, 20, 25,
    26, 31, 36, 37, 41, 42, 47,
    48,
}
GREEN = {
    5, 6, 11, 16, 17, 21, 22, 27,
    28, 32, 33, 38, 39, 43, 44,
    49,
}
# ============================================================
# 基础属性
# ============================================================
def get_color(number):
    """获取波色"""
    if number in RED:
        return "红"
    if number in BLUE:
        return "蓝"
    if number in GREEN:
        return "绿"
    return "未知"
def get_size(number):
    """获取大小"""
    if number >= 25:
        return "大"
    return "小"
def get_odd(number):
    """获取单双"""
    if number % 2 == 0:
        return "双"
    return "单"
def get_halfhalf(number):
    """
    半半波：
    波色 + 大小 + 单双
    例如：
    03 = 蓝小单
    26 = 蓝大双
    27 = 绿大单
    """
    return (
        get_color(number)
        + get_size(number)
        + get_odd(number)
    )
# ============================================================
# SSL 上下文
# ============================================================
def create_ssl_context(verify=True):
    """
    创建 SSL Context。
    verify=True：
        正常验证服务器证书。
    verify=False：
        不验证服务器证书。
        用于服务器 SSL 证书过期的情况。
    """
    if verify:
        return ssl.create_default_context()
    return ssl._create_unverified_context()
# ============================================================
# HTTP 请求
# ============================================================
def request_api(verify_ssl=True):
    """
    请求 API。
    verify_ssl=True：
        正常 HTTPS 验证。
    verify_ssl=False：
        忽略 SSL 证书验证。
    """
    context = create_ssl_context(
        verify=verify_ssl
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),
        "Accept": (
            "application/json,"
            "text/plain,"
            "*/*"
        ),
        "Connection": "close",
    }
    request = urllib.request.Request(
        CONFIG["api_url"],
        headers=headers,
        method="GET",
    )
    with urllib.request.urlopen(
        request,
        timeout=CONFIG["timeout"],
        context=context,
    ) as response:
        return response.read()
# ============================================================
# 获取 API 数据
# ============================================================
def download_api_data():
    """
    获取 API 数据。
    第一步：
        正常验证 SSL。
    如果 SSL 证书过期：
        自动使用不验证证书模式。
    每种模式都会进行多次重试。
    """
    retry_times = CONFIG["retry_times"]
    retry_delay = CONFIG["retry_delay"]
    # --------------------------------------------------------
    # 第一阶段：正常 SSL
    # --------------------------------------------------------
    print("🌐 正在连接 API...")
    print(f"🔗 {CONFIG['api_url']}")
    print("🔐 尝试正常 SSL 证书验证...")
    for attempt in range(
        1,
        retry_times + 1,
    ):
        try:
            data = request_api(
                verify_ssl=True
            )
            print(
                f"✅ 正常 SSL 连接成功 "
                f"(第 {attempt} 次)"
            )
            return data
        except ssl.SSLCertVerificationError as error:
            print(
                "⚠️ SSL 证书验证失败："
            )
            print(error)
            print(
                "➡️ 自动切换到兼容模式..."
            )
            break
        except ssl.SSLError as error:
            print(
                f"⚠️ SSL 错误 "
                f"(第 {attempt}/{retry_times} 次)："
            )
            print(error)
        except urllib.error.URLError as error:
            print(
                f"⚠️ 网络错误 "
                f"(第 {attempt}/{retry_times} 次)："
            )
            print(error)
        except Exception as error:
            print(
                f"⚠️ 请求失败 "
                f"(第 {attempt}/{retry_times} 次)："
            )
            print(error)
        if attempt < retry_times:
            print(
                f"⏳ {retry_delay} 秒后重试..."
            )
            time.sleep(retry_delay)
    # --------------------------------------------------------
    # 第二阶段：忽略 SSL 证书
    # --------------------------------------------------------
    print("")
    print("=" * 60)
    print("🔓 SSL 兼容模式")
    print("   忽略服务器证书验证")
    print("=" * 60)
    for attempt in range(
        1,
        retry_times + 1,
    ):
        try:
            data = request_api(
                verify_ssl=False
            )
            print(
                f"✅ SSL 兼容模式连接成功 "
                f"(第 {attempt} 次)"
            )
            return data
        except Exception as error:
            print(
                f"⚠️ 兼容模式失败 "
                f"(第 {attempt}/{retry_times} 次)："
            )
            print(error)
        if attempt < retry_times:
            print(
                f"⏳ {retry_delay} 秒后重试..."
            )
            time.sleep(retry_delay)
    raise RuntimeError(
        "API 无法连接，请检查网站是否正常运行。"
    )
# ============================================================
# 解析 API JSON
# ============================================================
def parse_api_json(raw_data):
    """
    将 API 返回的数据转换成 Python 字典。
    """
    if not raw_data:
        raise ValueError(
            "API 返回为空"
        )
    try:
        text = raw_data.decode(
            "utf-8",
            errors="replace",
        )
    except Exception:
        text = str(raw_data)
    text = text.strip()
    if not text:
        raise ValueError(
            "API 返回内容为空"
        )
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        print("")
        print("❌ API 返回内容不是有效 JSON")
        print(
            f"JSON 错误：{error}"
        )
        print("")
        print("API 返回前500字符：")
        print(text[:500])
        raise
# ============================================================
# 解析期号
# ============================================================
def parse_issue(line):
    """
    从开奖记录中提取期号。
    支持：
        2026123
        20261234
        202612345
    """
    if not line:
        return None
    text = str(line)
    matches = re.findall(
        r"20\d{5,8}",
        text,
    )
    if not matches:
        return None
    raw = matches[0]
    try:
        year = raw[:4]
        number = int(raw[4:])
        return (
            year
            + "/"
            + str(number).zfill(3)
        )
    except Exception:
        return None
# ============================================================
# 解析号码
# ============================================================
def parse_numbers(line):
    """
    从开奖记录中提取 1~49 的号码。
    返回：
        [n1, n2, n3, n4, n5, n6, special]
    """
    if not line:
        return []
    text = str(line)
    numbers = re.findall(
        r"\d+",
        text,
    )
    result = []
    for item in numbers:
        try:
            number = int(item)
        except ValueError:
            continue
        if 1 <= number <= 49:
            result.append(number)
    return result
# ============================================================
# 获取历史数据
# ============================================================
def fetch_data(limit=30):
    rows = []
    try:
        raw_data = download_api_data()
        data = parse_api_json(
            raw_data
        )
    except Exception as error:
        print("")
        print("❌ 获取 API 数据失败：")
        print(error)
        return []
    # --------------------------------------------------------
    # 查找新澳门彩
    # --------------------------------------------------------
    target = None
    lottery_data = data.get(
        "lottery_data",
        [],
    )
    if not isinstance(
        lottery_data,
        list,
    ):
        print(
            "❌ lottery_data 数据格式错误"
        )
        return []
    for item in lottery_data:
        if not isinstance(
            item,
            dict,
        ):
            continue
        name = str(
            item.get("name", "")
        ).strip()
        if name == "新澳门彩":
            target = item
            break
    if target is None:
        print(
            "❌ API 中没有找到：新澳门彩"
        )
        available = []
        for item in lottery_data:
            if isinstance(
                item,
                dict,
            ):
                name = item.get(
                    "name"
                )
                if name:
                    available.append(
                        str(name)
                    )
        if available:
            print(
                "📋 当前 API 彩票名称："
            )
            for name in available:
                print(
                    f"   - {name}"
                )
        return []
    history = target.get(
        "history",
        [],
    )
    if not isinstance(
        history,
        list,
    ):
        print(
            "❌ 新澳门彩 history 数据格式错误"
        )
        return []
    print(
        f"📥 API 返回历史记录："
        f"{len(history)} 条"
    )
    # --------------------------------------------------------
    # 逐条解析
    # --------------------------------------------------------
    for line in history:
        issue = parse_issue(line)
        if issue is None:
            continue
        numbers = parse_numbers(line)
        if len(numbers) < 7:
            continue
        # 最后一个号码作为特码
        special = numbers[-1]
        if not 1 <= special <= 49:
            continue
        row = {
            "issue": issue,
            "special": special,
            "color": get_color(special),
            "size": get_size(special),
            "odd": get_odd(special),
            "halfhalf": get_halfhalf(
                special
            ),
        }
        rows.append(row)
    # --------------------------------------------------------
    # 按期号去重
    # --------------------------------------------------------
    cache = {}
    for row in rows:
        cache[row["issue"]] = row
    rows = list(
        cache.values()
    )
    # --------------------------------------------------------
    # 最新期在前
    # --------------------------------------------------------
    rows.sort(
        key=lambda x: x["issue"],
        reverse=True,
    )
    return rows[:limit]
# ============================================================
# 生成最近开奖表
# ============================================================
def build_history_table(rows):
    result = ""
    for row in rows[:10]:
        result += (
            f"| {row['issue']} "
            f"| {row['special']:02d} "
            f"| {row['color']} "
            f"| {row['size']} "
            f"| {row['odd']} "
            f"| {row['halfhalf']} |\n"
        )
    return result
# ============================================================
# 生成下注建议表
# ============================================================
def build_bet_table(bets):
    result = ""
    for index, bet in enumerate(
        bets,
        start=1,
    ):
        numbers = ", ".join(
            f"{number:02d}"
            for number in bet["numbers"]
        )
        result += (
            f"| {index} "
            f"| **{bet['name']}** "
            f"| {bet['odds']} "
            f"| {numbers} |\n"
        )
    return result
# ============================================================
# 生成 Markdown 报告
# ============================================================
def generate_report(rows):
    bets = CONFIG["bets"]
    bet_per_note = CONFIG[
        "bet_per_note"
    ]
    bet_per_period = (
        bet_per_note
        * len(bets)
    )
    total_numbers = sum(
        len(bet["numbers"])
        for bet in bets
    )
    coverage = (
        total_numbers
        / 49
        * 100
    )
    now = datetime.now()
    history_table = (
        build_history_table(rows)
    )
    bet_table = (
        build_bet_table(bets)
    )
    latest = rows[0]
    report = f"""# 🎯 新澳门六合彩 - 3注半半波策略
**生成时间**：{now.strftime('%Y-%m-%d %H:%M:%S')}
**数据源**：marksix6.net
**最新期号**：{latest['issue']}
**最新特码**：{latest['special']:02d}
**最新半半波**：{latest['halfhalf']}
---
## 📊 最近开奖
| 期号 | 特码 | 波色 | 大小 | 单双 | 半半波 |
|------|------|------|------|------|--------|
{history_table}
---
## 🎯 今日策略
| 注数 | 玩法 | 赔率 | 号码 |
|------|------|------|------|
{bet_table}
---
## 📈 统计信息
| 项目 | 数值 |
|------|------|
| 策略注数 | {len(bets)} 注 |
| 每注金额 | {bet_per_note} 元 |
| 每期投入 | {bet_per_period} 元 |
| 覆盖号码 | {total_numbers} 个 |
| 理论号码覆盖率 | {coverage:.1f}% |
> 注：这里的“号码覆盖率”只是这3组号码占49个号码的比例，
> 不等于实际开奖命中率，也不代表盈利概率。
---
## 📋 当前策略
### 第1注：蓝小单
号码：
**03、09、15、21**
赔率：
**15.76**
### 第2注：绿大单
号码：
**27、33、39、43、49**
赔率：
**11.82**
### 第3注：蓝大双
号码：
**26、36、42、47、48**
赔率：
**11.82**
---
## ⚠️ 风险说明
彩票开奖结果具有随机性。
历史数据、颜色、大小、单双和半半波统计，
都不能保证下一期结果。
本程序仅用于自动化数据整理和策略记录，
不构成盈利保证或投资建议。
请勿借贷或使用影响正常生活的资金参与。
---
*本报告由 macau_predict.py 自动生成。*
"""
    return report
# ============================================================
# 保存报告
# ============================================================
def save_report(report):
    filename = "result.md"
    try:
        with open(
            filename,
            "w",
            encoding="utf-8",
        ) as file:
            file.write(report)
        print("")
        print(
            f"✅ 报告已生成：{filename}"
        )
        return True
    except Exception as error:
        print("")
        print(
            "❌ 保存报告失败："
        )
        print(error)
        return False
# ============================================================
# 主程序
# ============================================================
def main():
    print("=" * 60)
    print(
        "🎯 新澳门六合彩 - "
        "3注半半波策略"
    )
    print("=" * 60)
    print(
        f"🕐 运行时间："
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print(
        f"🐍 Python："
        f"{sys.version.split()[0]}"
    )
    print("=" * 60)
    # --------------------------------------------------------
    # 获取历史数据
    # --------------------------------------------------------
    rows = fetch_data(
        CONFIG["history_limit"]
    )
    if len(rows) < 10:
        print("")
        print(
            f"❌ 有效数据不足："
            f"{len(rows)} 期"
        )
        print(
            "至少需要10期有效数据。"
        )
        sys.exit(1)
    # --------------------------------------------------------
    # 基本信息
    # --------------------------------------------------------
    print("")
    print(
        f"✅ 成功获取："
        f"{len(rows)} 期数据"
    )
    print(
        f"📅 最新期号："
        f"{rows[0]['issue']}"
    )
    print(
        f"🎯 最新特码："
        f"{rows[0]['special']:02d}"
    )
    print(
        f"🎨 最新波色："
        f"{rows[0]['color']}"
    )
    print(
        f"📏 最新大小："
        f"{rows[0]['size']}"
    )
    print(
        f"🔢 最新单双："
        f"{rows[0]['odd']}"
    )
    print(
        f"🎯 最新半半波："
        f"{rows[0]['halfhalf']}"
    )
    # --------------------------------------------------------
    # 今日下注建议
    # --------------------------------------------------------
    print("")
    print("=" * 60)
    print("🎯 今日下注建议")
    print("=" * 60)
    bets = CONFIG["bets"]
    for index, bet in enumerate(
        bets,
        start=1,
    ):
        numbers = ", ".join(
            f"{number:02d}"
            for number in bet["numbers"]
        )
        print(
            f"{index}. "
            f"{bet['name']} "
            f"| 赔率 {bet['odds']} "
            f"| {numbers}"
        )
    bet_per_period = (
        CONFIG["bet_per_note"]
        * len(bets)
    )
    print("")
    print(
        f"💰 每期投入："
        f"{bet_per_period} 元"
    )
    # --------------------------------------------------------
    # 生成报告
    # --------------------------------------------------------
    report = generate_report(
        rows
    )
    if not save_report(report):
        sys.exit(1)
    print("")
    print("=" * 60)
    print("✅ 程序执行完成")
    print("=" * 60)
# ============================================================
# 程序入口
# ============================================================
if __name__ == "__main__":
    main