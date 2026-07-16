#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
方案B：新澳门加蓝波（4注优化版）
香港彩: 3注（绿大单+绿单+绿双）
新澳门彩: 4注（绿大单+绿单+绿双+蓝波）
老澳门彩: 3注（绿大单+绿单+绿双）
"""

import re
import json
import urllib.request
from collections import defaultdict
from datetime import datetime
import sys

# =====================================================
# 策略配置
# =====================================================

# 香港彩、老澳门彩：3注
BETS_3 = [
    {"name": "绿大单", "odds": 11.82, "numbers": [27, 33, 39, 43, 49]},
    {"name": "绿单", "odds": 5.82, "numbers": [5, 11, 17, 21, 27, 33, 39, 43, 49]},
    {"name": "绿双", "odds": 6.60, "numbers": [6, 16, 22, 28, 32, 38, 44]},
]

# 新澳门彩：4注（加蓝波）
BETS_4 = [
    {"name": "绿大单", "odds": 11.82, "numbers": [27, 33, 39, 43, 49]},
    {"name": "绿单", "odds": 5.82, "numbers": [5, 11, 17, 21, 27, 33, 39, 43, 49]},
    {"name": "绿双", "odds": 6.60, "numbers": [6, 16, 22, 28, 32, 38, 44]},
    {"name": "蓝波", "odds": 2.80, "numbers": [3, 4, 9, 10, 14, 15, 20, 25, 26, 31, 36, 37, 41, 42, 47, 48]},
]

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


def get_hit_bet(n, bets):
    sorted_bets = sorted(bets, key=lambda x: x["odds"], reverse=True)
    for bet in sorted_bets:
        if n in bet["numbers"]:
            return bet["name"], bet["odds"]
    return None, None


def fetch_lottery_data(lottery_name, limit=30):
    rows = []
    try:
        print(f"📡 正在获取 {lottery_name} 数据...")
        req = urllib.request.Request(
            "https://marksix6.net/index.php?api=1",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        data = urllib.request.urlopen(req, timeout=30).read()
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


def run_backtest(rows, lottery_name, bets, periods=20):
    if len(rows) < periods:
        print(f"⚠️ {lottery_name} 数据不足{periods}期")
        return None

    bet_per_period = len(bets) * 100

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
        hit_name, odds = get_hit_bet(r["special"], bets)
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
            "profit": profit,
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
    }


def print_result(result, bets):
    if not result:
        return

    bets_count = len(bets)

    print("\n" + "=" * 70)
    print(f"📊 {result['lottery']} 最近{result['total']}期回测")
    print(f"   注数: {bets_count}注 | 每期投入: {bets_count*100}元")
    print("=" * 70)

    print(f"\n📋 最近{result['total']}期开奖明细:")
    print(f"{'期号':<12} {'特码':<6} {'半半波':<12} {'命中':<8} {'中奖玩法':<14} {'单期盈亏':<12} {'累计盈亏':<12}")
    print("-" * 80)

    for r in result["results"]:
        hit_name, _ = get_hit_bet(r["number"], bets)
        if hit_name:
            print(f"{r['issue']:<12} {r['number']:<6} {get_halfhalf(r['number']):<12} ✅ {'':<4} {hit_name:<14} {r['profit']:<+12.0f} {r['balance']:<+12.0f}")
        else:
            print(f"{r['issue']:<12} {r['number']:<6} {get_halfhalf(r['number']):<12} ❌ {'':<4} {'-':<14} {r['profit']:<+12.0f} {r['balance']:<+12.0f}")

    print("-" * 80)

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
    for bet in bets:
        count = result["hit_stats"].get(bet["name"], 0)
        pct = count / result["hit_count"] * 100 if result["hit_count"] > 0 else 0
        print(f"  {bet['name']}: {count}次 ({pct:.1f}%)")


def print_summary(results, configs):
    print("\n" + "=" * 70)
    print("📊 方案B汇总对比（新澳门加蓝波）")
    print("=" * 70)
    print(f"{'彩种':<12} {'注数':<8} {'命中率':<12} {'盈亏':<14} {'ROI':<10} {'最大回撤':<12} {'最长连未中':<10}")
    print("-" * 80)

    total_profit = 0
    total_bet = 0

    for r, config in zip(results, configs):
        if r:
            bets_count = config["count"]
            print(f"{r['lottery']:<12} {bets_count}注{'':<4} {r['hit_rate']:.2f}%{'':<6} {r['balance']:+,.0f}元{'':<6} {r['roi']:+.2f}%{'':<4} {r['max_drawdown']:,.0f}元{'':<4} {r['max_consecutive_loss']}期")
            total_profit += r["balance"]
            total_bet += r["total_bet"]

    print("-" * 80)

    valid = [r for r in results if r]
    if valid:
        profitable = sum(1 for r in valid if r["balance"] > 0)
        avg_hit = sum(r["hit_rate"] for r in valid) / len(valid)
        avg_roi = sum(r["roi"] for r in valid) / len(valid)

        print(f"\n✅ {profitable}/{len(valid)} 个彩种盈利")
        print(f"📊 平均命中率: {avg_hit:.2f}%")
        print(f"📊 平均ROI: {avg_roi:.2f}%")
        print(f"💰 三彩总盈利: {total_profit:+,.0f}元")
        print(f"💰 三彩总投注: {total_bet:,.0f}元")

    return total_profit, total_bet


def main():
    print("=" * 70)
    print("🎯 方案B：新澳门加蓝波（4注优化版）")
    print("   香港彩: 3注（绿大单+绿单+绿双）")
    print("   新澳门彩: 4注（绿大单+绿单+绿双+蓝波）")
    print("   老澳门彩: 3注（绿大单+绿单+绿双）")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    results = []
    configs = []

    # 香港彩 - 3注
    rows_hk = fetch_lottery_data("香港彩", limit=25)
    if len(rows_hk) >= 20:
        result_hk = run_backtest(rows_hk, "香港彩", BETS_3, periods=20)
        if result_hk:
            print_result(result_hk, BETS_3)
            results.append(result_hk)
            configs.append({"count": 3})

    # 新澳门彩 - 4注（加蓝波）
    rows_mo = fetch_lottery_data("新澳门彩", limit=25)
    if len(rows_mo) >= 20:
        result_mo = run_backtest(rows_mo, "新澳门彩", BETS_4, periods=20)
        if result_mo:
            print_result(result_mo, BETS_4)
            results.append(result_mo)
            configs.append({"count": 4})

    # 老澳门彩 - 3注
    rows_old = fetch_lottery_data("老澳门彩", limit=25)
    if len(rows_old) >= 20:
        result_old = run_backtest(rows_old, "老澳门彩", BETS_3, periods=20)
        if result_old:
            print_result(result_old, BETS_3)
            results.append(result_old)
            configs.append({"count": 3})

    # 汇总
    if results:
        total_profit, total_bet = print_summary(results, configs)

        print("\n" + "=" * 70)
        print("📋 最终结论（20期）")
        print("=" * 70)

        if all(r["balance"] > 0 for r in results):
            avg_hit = sum(r["hit_rate"] for r in results) / len(results)
            avg_roi = sum(r["roi"] for r in results) / len(results)

            print(f"""
✅ 方案B全部盈利！

策略配置:
  香港彩: 3注 (300元/期) → 绿大单+绿单+绿双
  新澳门彩: 4注 (400元/期) → 绿大单+绿单+绿双+蓝波
  老澳门彩: 3注 (300元/期) → 绿大单+绿单+绿双

关键数据:
  三彩总盈利: {total_profit:+,.0f}元
  平均命中率: {avg_hit:.2f}%
  平均ROI: {avg_roi:.2f}%

每周预期:
  单期总投入: 1,000元
  每周总投入: 7,000元
  每周预期盈利: ~{total_profit/20*7:.0f}元

🎯 策略验证通过！可以执行！
""")
        else:
            print("⚠️ 部分彩种表现不佳，建议继续优化")


if __name__ == "__main__":
    main()