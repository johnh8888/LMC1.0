#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
三彩回测 - 2注策略（绿大单+红小）
修正版：基于准确号码归属
"""

import re
import json
import urllib.request
from collections import defaultdict
from datetime import datetime
import sys

# =====================================================
# 2注策略配置（修正版）
# =====================================================

BETS = [
    {"name": "绿大单", "odds": 11.80, "numbers": [27, 33, 39, 43, 49]},
    {"name": "红小", "odds": 4.70, "numbers": [1, 2, 7, 8, 12, 13, 18, 19, 23, 24, 29]},
]

# 合并所有号码
MY_NUMBERS = set()
for bet in BETS:
    for n in bet["numbers"]:
        MY_NUMBERS.add(n)

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


def get_hit_bet(n):
    for bet in BETS:
        if n in bet["numbers"]:
            return bet["name"], bet["odds"]
    return None, None


# =====================================================
# 数据获取
# =====================================================

def fetch_lottery_data(lottery_name, limit=50):
    """获取指定彩种数据"""
    rows = []
    try:
        print(f"📡 正在获取 {lottery_name} 数据...")
        req = urllib.request.Request(
            "https://marksix6.net/index.php?api=1",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        data = urllib.request.urlopen(req, timeout=60).read()
        data = json.loads(data.decode("utf-8"))

        target = None
        for item in data.get("lottery_data", []):
            if item.get("name", "").strip() == lottery_name:
                target = item
                break

        if not target:
            print(f"❌ 未找到 {lottery_name} 数据")
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
    rows.sort(key=lambda x: x["issue"], reverse=True)
    print(f"✅ 获取 {len(rows)} 期数据")
    return rows[:limit]


# =====================================================
# 回测引擎
# =====================================================

def run_backtest(rows, lottery_name, periods=20):
    if len(rows) < periods:
        print(f"⚠️ {lottery_name} 数据不足{periods}期，仅{len(rows)}期")
        return None

    bet_per_period = len(BETS) * 100  # 200元
    total_numbers = len(MY_NUMBERS)

    results = []
    balance = 0
    hit_count = 0
    max_drawdown = 0
    max_balance = 0
    consecutive_loss = 0
    max_consecutive_loss = 0
    hit_stats = defaultdict(int)
    total_win = 0
    total_bet = 0

    recent = rows[:periods]
    rows_chrono = list(reversed(recent))

    for r in rows_chrono:
        hit_name, odds = get_hit_bet(r["special"])
        if hit_name:
            hit_count += 1
            hit_stats[hit_name] += 1
            win_amount = odds * 100
            profit = win_amount - bet_per_period
            total_win += win_amount
            balance += profit
            consecutive_loss = 0
        else:
            profit = -bet_per_period
            balance += profit
            consecutive_loss += 1
            max_consecutive_loss = max(max_consecutive_loss, consecutive_loss)

        total_bet += bet_per_period

        if balance > max_balance:
            max_balance = balance
        max_drawdown = max(max_drawdown, max_balance - balance)

        results.append({
            "issue": r["issue"],
            "number": r["special"],
            "hit": hit_name,
            "balance": balance,
        })

    total = len(results)
    hit_rate = hit_count / total * 100 if total > 0 else 0
    roi = balance / total_bet * 100 if total_bet > 0 else 0

    return {
        "lottery": lottery_name,
        "total": total,
        "hit_count": hit_count,
        "hit_rate": hit_rate,
        "balance": balance,
        "total_bet": total_bet,
        "total_win": total_win,
        "max_drawdown": max_drawdown,
        "max_consecutive_loss": max_consecutive_loss,
        "roi": roi,
        "hit_stats": hit_stats,
        "results": results,
        "recent": recent,
    }


def print_result(result):
    if not result:
        return

    print("\n" + "=" * 70)
    print(f"📊 {result['lottery']} 最近20期回测（2注策略：绿大单+红小）")
    print("=" * 70)

    print(f"\n📋 最近20期开奖明细:")
    print(f"{'期号':<12} {'特码':<6} {'半半波':<12} {'命中':<8} {'中奖玩法':<12} {'累计盈亏':<12}")
    print("-" * 70)

    for r in result["results"]:
        hit_name, _ = get_hit_bet(r["number"])
        if hit_name:
            print(f"{r['issue']:<12} {r['number']:<6} {get_halfhalf(r['number']):<12} ✅ {'':<4} {hit_name:<12} {r['balance']:<+12.0f}")
        else:
            print(f"{r['issue']:<12} {r['number']:<6} {get_halfhalf(r['number']):<12} ❌ {'':<4} {'-':<12} {r['balance']:<+12.0f}")

    print("-" * 70)

    print(f"\n📊 汇总:")
    print(f"  📅 回测期数: {result['total']}期")
    print(f"  🎯 命中次数: {result['hit_count']}次")
    print(f"  📈 命中率: {result['hit_rate']:.2f}%")
    print(f"  💰 总投注: {result['total_bet']:,.0f}元")
    print(f"  🏆 总中奖: {result['total_win']:,.0f}元")
    print(f"  📊 最终盈亏: {result['balance']:+,.0f}元")
    print(f"  📉 最大回撤: {result['max_drawdown']:,.0f}元")
    print(f"  🔥 最长连续未中: {result['max_consecutive_loss']}期")
    print(f"  📊 ROI: {result['roi']:+.2f}%")

    print(f"\n🎯 各玩法命中统计:")
    for bet in BETS:
        count = result["hit_stats"].get(bet["name"], 0)
        pct = count / result["hit_count"] * 100 if result["hit_count"] > 0 else 0
        print(f"  {bet['name']}: {count}次 ({pct:.1f}%)")


def print_summary(results):
    print("\n" + "=" * 70)
    print("📊 三彩20期汇总对比（2注策略：绿大单+红小）")
    print("=" * 70)
    print(f"{'彩种':<12} {'期数':<8} {'命中率':<12} {'盈亏':<14} {'ROI':<10} {'最大回撤':<12} {'最长连未中':<10}")
    print("-" * 80)

    for r in results:
        if r:
            print(f"{r['lottery']:<12} {r['total']:<8} {r['hit_rate']:.2f}%{'':<6} {r['balance']:+,.0f}元{'':<6} {r['roi']:+.2f}%{'':<4} {r['max_drawdown']:,.0f}元{'':<4} {r['max_consecutive_loss']}期")

    print("-" * 80)

    valid = [r for r in results if r]
    if valid:
        profitable = sum(1 for r in valid if r["balance"] > 0)
        avg_hit = sum(r["hit_rate"] for r in valid) / len(valid)
        avg_roi = sum(r["roi"] for r in valid) / len(valid)

        print(f"\n✅ {profitable}/{len(valid)} 个彩种盈利")
        print(f"📊 平均命中率: {avg_hit:.2f}%")
        print(f"📊 平均ROI: {avg_roi:.2f}%")


def main():
    print("=" * 70)
    print("🎯 三彩20期回测 - 2注策略（绿大单+红小）")
    print("   修正版：基于准确号码归属")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    print("\n📋 2注策略:")
    for bet in BETS:
        nums = ", ".join([f"{n:02d}" for n in bet["numbers"]])
        print(f"  {bet['name']} (赔率{bet['odds']}): {nums}")

    print(f"\n📊 覆盖号码: {len(MY_NUMBERS)}个/49个 ({len(MY_NUMBERS)/49*100:.1f}%)")
    print(f"🎯 理论命中率: {len(MY_NUMBERS)/49*100:.1f}%")
    print(f"💰 每期投入: {len(BETS)*100}元")

    lotteries = ["香港彩", "新澳门彩", "老澳门彩"]
    results = []

    for name in lotteries:
        rows = fetch_lottery_data(name, limit=30)
        if len(rows) < 20:
            print(f"⚠️ {name} 数据不足20期，跳过")
            results.append(None)
            continue

        result = run_backtest(rows, name, periods=20)
        if result:
            print_result(result)
            results.append(result)

    print_summary(results)

    print("\n" + "=" * 70)
    print("📋 最终结论（2注策略）")
    print("=" * 70)

    valid = [r for r in results if r]
    if valid:
        all_profit = all(r["balance"] > 0 for r in valid)
        avg_hit = sum(r["hit_rate"] for r in valid) / len(valid)
        avg_roi = sum(r["roi"] for r in valid) / len(valid)
        total_profit = sum(r["balance"] for r in valid)

        if all_profit:
            print(f"""
✅ 2注策略在三个彩种上20期全部盈利！

关键数据:
  平均命中率: {avg_hit:.2f}%
  平均ROI: {avg_roi:.2f}%
  三彩总盈利: {total_profit:+,.0f}元
  策略稳定性: 高 ✅

建议:
  每期投入: 200元 (2注×100元)
  可以继续执行此策略
""")
        else:
            print("⚠️ 部分彩种20期表现不佳")

    print("\n📊 与5注策略对比:")
    print("-" * 50)
    if valid:
        for r in valid:
            print(f"  {r['lottery']}: 2注策略命中率 {r['hit_rate']:.1f}% | 5注策略命中率约73%")
        print("\n  2注策略优势: 每期投入少300元，风险更低")
        print("  5注策略优势: 命中率更高，盈利更多")


if __name__ == "__main__":
    main()