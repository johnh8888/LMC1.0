#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
三彩20期回测 - 5注策略（蓝小单+绿大单+蓝大双+红小+绿双）
支持：香港彩、新澳门彩、老澳门彩
"""

import re
import json
import urllib.request
from collections import defaultdict
from datetime import datetime
import sys

# =====================================================
# 5注策略配置
# =====================================================

BETS = [
    {"name": "蓝小单", "odds": 15.75, "numbers": [3, 9, 15, 21]},
    {"name": "绿大单", "odds": 11.80, "numbers": [27, 33, 39, 43, 49]},
    {"name": "蓝大双", "odds": 11.80, "numbers": [26, 36, 42, 47, 48]},
    {"name": "红小", "odds": 4.70, "numbers": [1, 2, 7, 8, 12, 13, 18, 19, 23, 24, 29]},
    {"name": "绿双", "odds": 6.60, "numbers": [6, 16, 22, 28, 32, 38, 44]},
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

def fetch_lottery_data(lottery_name, limit=30):
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
# 20期回测引擎
# =====================================================

def run_backtest_20(rows, lottery_name):
    if len(rows) < 20:
        print(f"⚠️ {lottery_name} 数据不足20期，仅{len(rows)}期")
        return None

    bet_per_period = len(BETS) * 100  # 500元
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

    # 取最近20期，从旧到新回测
    recent_20 = rows[:20]
    rows_chrono = list(reversed(recent_20))

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
        "recent_20": recent_20,
    }


def print_result_20(result):
    if not result:
        return

    print("\n" + "=" * 70)
    print(f"📊 {result['lottery']} 最近20期回测")
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


def print_summary_20(results):
    print("\n" + "=" * 70)
    print("📊 三彩20期汇总对比")
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

        if profitable == len(valid):
            print("🎉 所有彩种均盈利！策略20期表现稳定！")
        elif profitable >= len(valid) * 0.6:
            print("👍 大部分彩种盈利，策略基本稳定")


def main():
    print("=" * 70)
    print("🎯 三彩20期回测 - 5注策略（蓝小单+绿大单+蓝大双+红小+绿双）")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    print("\n📋 5注策略:")
    for bet in BETS:
        nums = ", ".join([f"{n:02d}" for n in bet["numbers"]])
        print(f"  {bet['name']} (赔率{bet['odds']}): {nums}")

    print(f"\n📊 覆盖号码: {len(MY_NUMBERS)}个/49个 ({len(MY_NUMBERS)/49*100:.1f}%)")
    print(f"🎯 理论命中率: {len(MY_NUMBERS)/49*100:.1f}%")

    lotteries = ["香港彩", "新澳门彩", "老澳门彩"]
    results = []

    for name in lotteries:
        rows = fetch_lottery_data(name, limit=30)
        if len(rows) < 20:
            print(f"⚠️ {name} 数据不足20期，跳过")
            results.append(None)
            continue

        result = run_backtest_20(rows, name)
        if result:
            print_result_20(result)
            results.append(result)

    print_summary_20(results)

    print("\n" + "=" * 70)
    print("📋 最终结论（20期）")
    print("=" * 70)

    valid = [r for r in results if r]
    if valid:
        all_profit = all(r["balance"] > 0 for r in valid)
        avg_hit = sum(r["hit_rate"] for r in valid) / len(valid)
        avg_roi = sum(r["roi"] for r in valid) / len(valid)

        if all_profit:
            print(f"""
✅ 5注策略在三个彩种上20期全部盈利！

关键数据:
  平均命中率: {avg_hit:.2f}%
  平均ROI: {avg_roi:.2f}%
  策略稳定性: 高 ✅

建议:
  可以在三个彩种上继续执行此策略
  每期投入: 500元 (5注×100元)
""")
        else:
            print("⚠️ 部分彩种20期表现不佳，建议继续观察")

    # 对比7期和20期
    print("\n📊 7期 vs 20期对比:")
    print("-" * 50)
    for r in valid:
        print(f"  {r['lottery']}: 7期命中率 ~80% | 20期命中率 {r['hit_rate']:.1f}% | 20期盈亏 {r['balance']:+,.0f}元")


if __name__ == "__main__":
    main()