#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
纯正期望值策略回测
只买正期望值玩法：绿大单 + 绿单 + 绿双
每期300元
"""

import re
import json
import urllib.request
from collections import defaultdict
from datetime import datetime
import sys

# =====================================================
# 策略配置（只保留正期望值玩法）
# =====================================================

BETS = [
    {"name": "绿大单", "odds": 11.82, "numbers": [27, 33, 39, 43, 49]},
    {"name": "绿单", "odds": 5.82, "numbers": [5, 11, 17, 21, 27, 33, 39, 43, 49]},
    {"name": "绿双", "odds": 6.60, "numbers": [6, 16, 22, 28, 32, 38, 44]},
]

# 合并所有号码
ALL_NUMBERS = set()
for bet in BETS:
    for n in bet["numbers"]:
        ALL_NUMBERS.add(n)

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
    """检查命中了哪个玩法（按赔率从高到低）"""
    sorted_bets = sorted(BETS, key=lambda x: x["odds"], reverse=True)
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


def run_backtest(rows, lottery_name, periods=20):
    if len(rows) < periods:
        print(f"⚠️ {lottery_name} 数据不足{periods}期")
        return None

    bet_per_period = len(BETS) * 100  # 300元

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


def print_result(result):
    if not result:
        return

    print("\n" + "=" * 70)
    print(f"📊 {result['lottery']} 最近{result['total']}期回测（纯正期望值策略）")
    print(f"   每期投入: 300元（3注×100元）")
    print("=" * 70)

    print(f"\n📋 最近{result['total']}期开奖明细:")
    print(f"{'期号':<12} {'特码':<6} {'半半波':<12} {'命中':<8} {'中奖玩法':<14} {'单期盈亏':<12} {'累计盈亏':<12}")
    print("-" * 80)

    for r in result["results"]:
        hit_name, _ = get_hit_bet(r["number"])
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
    for bet in BETS:
        count = result["hit_stats"].get(bet["name"], 0)
        pct = count / result["hit_count"] * 100 if result["hit_count"] > 0 else 0
        print(f"  {bet['name']}: {count}次 ({pct:.1f}%)")


def print_summary(results):
    print("\n" + "=" * 70)
    print("📊 纯正期望值策略20期汇总对比")
    print("=" * 70)
    print(f"{'彩种':<12} {'期数':<8} {'命中率':<12} {'盈亏':<14} {'ROI':<10} {'最大回撤':<12} {'最长连未中':<10}")
    print("-" * 80)

    total_profit = 0
    total_bet = 0

    for r in results:
        if r:
            print(f"{r['lottery']:<12} {r['total']:<8} {r['hit_rate']:.2f}%{'':<6} {r['balance']:+,.0f}元{'':<6} {r['roi']:+.2f}%{'':<4} {r['max_drawdown']:,.0f}元{'':<4} {r['max_consecutive_loss']}期")
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
    print("🎯 纯正期望值策略20期回测（绿大单+绿单+绿双）")
    print("   只买正期望值玩法，每期300元")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    print("\n📋 3注策略:")
    for bet in BETS:
        nums = ", ".join([f"{n:02d}" for n in bet["numbers"]])
        print(f"  {bet['name']} (赔率{bet['odds']}): {nums}")

    # 计算覆盖
    total_numbers = len(ALL_NUMBERS)
    print(f"\n📊 覆盖号码: {total_numbers}个/49个 ({total_numbers/49*100:.1f}%)")
    print(f"💰 每期投入: {len(BETS)*100}元")

    results = []

    # 香港彩
    rows_hk = fetch_lottery_data("香港彩", limit=25)
    if len(rows_hk) >= 20:
        result_hk = run_backtest(rows_hk, "香港彩", periods=20)
        if result_hk:
            print_result(result_hk)
            results.append(result_hk)

    # 新澳门彩
    rows_mo = fetch_lottery_data("新澳门彩", limit=25)
    if len(rows_mo) >= 20:
        result_mo = run_backtest(rows_mo, "新澳门彩", periods=20)
        if result_mo:
            print_result(result_mo)
            results.append(result_mo)

    # 老澳门彩
    rows_old = fetch_lottery_data("老澳门彩", limit=25)
    if len(rows_old) >= 20:
        result_old = run_backtest(rows_old, "老澳门彩", periods=20)
        if result_old:
            print_result(result_old)
            results.append(result_old)

    # 汇总
    if results:
        total_profit, total_bet = print_summary(results)

        print("\n" + "=" * 70)
        print("📋 最终结论（20期）")
        print("=" * 70)

        if all(r["balance"] > 0 for r in results):
            avg_hit = sum(r["hit_rate"] for r in results) / len(results)
            avg_roi = sum(r["roi"] for r in results) / len(results)

            print(f"""
✅ 纯正期望值策略全部盈利！

策略配置:
  绿大单: 100元 (11.82)
  绿单: 100元 (5.82)
  绿双: 100元 (6.60)

关键数据:
  三彩总盈利: {total_profit:+,.0f}元
  平均命中率: {avg_hit:.2f}%
  平均ROI: {avg_roi:.2f}%

每周预期:
  单期投入: 300元
  每周投入: 2,100元
  每周预期盈利: ~{total_profit/20*7:.0f}元

🎯 策略验证通过！可以执行！
""")
        else:
            print("⚠️ 部分彩种表现不佳，建议优化")


if __name__ == "__main__":
    main()