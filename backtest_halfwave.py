#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门六合彩 - 3注半半波正期望值策略回测
验证方案：蓝小单 + 绿大单 + 蓝大双
"""

import re
import json
import urllib.request
from collections import defaultdict
from datetime import datetime
import sys

CONFIG = {
    "api_url": "https://marksix6.net/index.php?api=1",
    "history_limit": 200,
    "bet_per_note": 100,
    "bets": [
        {"name": "蓝小单", "odds": 15.76, "numbers": [3, 9, 15, 21]},
        {"name": "绿大单", "odds": 11.82, "numbers": [27, 33, 39, 43, 49]},
        {"name": "蓝大双", "odds": 11.82, "numbers": [26, 36, 42, 47, 48]},
    ]
}

# 官方号码表
RED = {1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE = {3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
GREEN = {5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}


def get_color(n):
    if n in RED: return "红"
    if n in BLUE: return "蓝"
    return "绿"


def get_size(n):
    return "大" if n >= 25 else "小"


def get_odd(n):
    return "单" if n % 2 else "双"


def get_halfhalf(n):
    return get_color(n) + get_size(n) + get_odd(n)


def fetch_data(limit=200):
    """获取历史数据"""
    rows = []
    try:
        print("📡 正在获取数据...")
        req = urllib.request.Request(
            CONFIG["api_url"],
            headers={"User-Agent": "Mozilla/5.0"}
        )
        data = urllib.request.urlopen(req, timeout=60).read()
        data = json.loads(data.decode("utf-8"))

        target = None
        for item in data.get("lottery_data", []):
            if item.get("name", "").strip() == "新澳门彩":
                target = item
                break

        if not target:
            print("❌ 未找到新澳门彩数据")
            return []

        for line in target.get("history", []):
            nums = re.findall(r"\d+", line)
            nums = [int(x) for x in nums if 1 <= int(x) <= 49]
            if len(nums) < 7:
                continue
            special = nums[-1]
            m = re.search(r"(20\d{5,8})", line)
            if not m:
                continue
            raw = m.group(1)
            issue = raw[:4] + "/" + str(int(raw[4:])).zfill(3)
            rows.append({
                "issue": issue,
                "special": special,
                "halfhalf": get_halfhalf(special)
            })

    except Exception as e:
        print(f"❌ 获取失败: {e}")
        return []

    cache = {}
    for r in rows:
        cache[r["issue"]] = r
    rows = list(cache.values())
    rows.sort(key=lambda x: x["issue"])
    return rows[-limit:]


def run_backtest(rows):
    """执行回测"""
    bets = CONFIG["bets"]
    bet_per_period = CONFIG["bet_per_note"] * len(bets)

    print("\n" + "=" * 70)
    print("📊 回测配置")
    print("=" * 70)
    print(f"  策略: 3注半半波策略")
    print(f"  每注: {CONFIG['bet_per_note']}元")
    print(f"  每期投入: {bet_per_period}元")
    print(f"  回测期数: {len(rows)}期")

    print("\n📋 下注明细:")
    total_count = 0
    for bet in bets:
        print(f"  {bet['name']}: 赔率{bet['odds']}, {len(bet['numbers'])}个号")
        total_count += len(bet['numbers'])
    print(f"\n📊 覆盖号码: {total_count}个/49个 ({total_count/49*100:.1f}%)")

    results = []
    balance = 0
    hit_count = 0
    max_drawdown = 0
    max_balance = 0
    consecutive_loss = 0
    max_consecutive_loss = 0
    hit_stats = defaultdict(int)

    for r in rows:
        hit = None
        for bet in bets:
            if r["special"] in bet["numbers"]:
                hit = bet
                break

        if hit:
            hit_count += 1
            hit_stats[hit["name"]] += 1
            balance += hit["odds"] * CONFIG["bet_per_note"] - bet_per_period
            consecutive_loss = 0
        else:
            balance -= bet_per_period
            consecutive_loss += 1
            max_consecutive_loss = max(max_consecutive_loss, consecutive_loss)

        if balance > max_balance:
            max_balance = balance
        max_drawdown = max(max_drawdown, max_balance - balance)

        results.append({
            "issue": r["issue"],
            "number": r["special"],
            "actual": r["halfhalf"],
            "hit": hit["name"] if hit else None,
            "balance": balance,
        })

    total = len(results)
    hit_rate = hit_count / total * 100 if total > 0 else 0
    roi = balance / (total * bet_per_period) * 100 if total > 0 else 0

    print("\n" + "=" * 70)
    print("📊 回测结果")
    print("=" * 70)
    print(f"  📅 回测期数: {total}期")
    print(f"  🎯 命中次数: {hit_count}次")
    print(f"  📈 命中率: {hit_rate:.2f}%")
    print(f"  💰 总投注: {total * bet_per_period:,.0f}元")
    print(f"  📊 最终盈亏: {balance:+,.0f}元")
    print(f"  📉 最大回撤: {max_drawdown:,.0f}元")
    print(f"  🔥 最长连续未中: {max_consecutive_loss}期")
    print(f"  📊 ROI: {roi:+.2f}%")

    print("\n🎯 各玩法命中统计:")
    for bet in bets:
        count = hit_stats.get(bet["name"], 0)
        pct = count / hit_count * 100 if hit_count > 0 else 0
        print(f"  {bet['name']}: {count}次 ({pct:.1f}%)")

    # 生成报告
    report = f"""# 新澳门六合彩 - 3注半半波策略回测报告

**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**数据**: 最近{total}期

## 回测结果

| 指标 | 数值 |
|------|------|
| 回测期数 | {total}期 |
| 命中次数 | {hit_count}次 |
| 命中率 | {hit_rate:.2f}% |
| 总投注 | {total * bet_per_period:,.0f}元 |
| 总盈亏 | {balance:+,.0f}元 |
| 最大回撤 | {max_drawdown:,.0f}元 |
| 最长连续未中 | {max_consecutive_loss}期 |
| ROI | {roi:+.2f}% |

## 下注明细

| 玩法 | 赔率 | 号码 | 数量 |
|------|------|------|------|
"""

    for bet in bets:
        nums = ", ".join([f"{n:02d}" for n in bet["numbers"]])
        report += f"| {bet['name']} | {bet['odds']} | {nums} | {len(bet['numbers'])}个 |\n"

    report += f"""

## 结论

{"✅ 策略可行！" if balance > 0 and roi > 0 else "❌ 策略需谨慎"}

建议启动资金: {max(10000, int(abs(max_drawdown) * 1.5)):,}元
"""

    with open("backtest_result.md", "w", encoding="utf-8") as f:
        f.write(report)

    return {
        "total": total,
        "hit_count": hit_count,
        "hit_rate": hit_rate,
        "balance": balance,
        "max_drawdown": max_drawdown,
        "max_consecutive_loss": max_consecutive_loss,
        "roi": roi,
    }


def main():
    print("=" * 70)
    print("🎯 新澳门六合彩 - 3注半半波策略回测")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    rows = fetch_data(CONFIG["history_limit"])
    if len(rows) < 30:
        print("❌ 数据不足")
        sys.exit(1)

    print(f"✅ 获取 {len(rows)} 期数据")
    print(f"📅 数据范围: {rows[0]['issue']} ~ {rows[-1]['issue']}")

    run_backtest(rows)


if __name__ == "__main__":
    main()