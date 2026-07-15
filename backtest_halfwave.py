#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
三彩最近7期命中 + 高置信度判断
策略：5注（蓝小单+绿大单+蓝大双+红小+绿双）
"""

import re
import json
import urllib.request
from datetime import datetime
from collections import defaultdict

BETS = [
    {"name": "蓝小单", "odds": 15.75, "numbers": [3, 9, 15, 21]},
    {"name": "绿大单", "odds": 11.80, "numbers": [27, 33, 39, 43, 49]},
    {"name": "蓝大双", "odds": 11.80, "numbers": [26, 36, 42, 47, 48]},
    {"name": "红小", "odds": 4.70, "numbers": [1, 2, 7, 8, 12, 13, 18, 19, 23, 24, 29]},
    {"name": "绿双", "odds": 6.60, "numbers": [6, 16, 22, 28, 32, 38, 44]},
]

MY_NUMBERS = set()
for bet in BETS:
    for n in bet["numbers"]:
        MY_NUMBERS.add(n)

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


def fetch_lottery_data(lottery_name, limit=20):
    rows = []
    try:
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
    return rows[:limit]


def analyze_lottery(lottery_name):
    rows = fetch_lottery_data(lottery_name, 20)
    if len(rows) < 7:
        return None

    recent = rows[:7]
    latest = rows[0] if rows else None

    hit_count = 0
    hit_details = []
    consecutive_miss = 0
    total_win = 0
    total_bet = 7 * 500

    for r in recent:
        hit_name, odds = get_hit_bet(r["special"])
        if hit_name:
            hit_count += 1
            win_amount = odds * 100
            total_win += win_amount
            hit_details.append({
                "issue": r["issue"],
                "number": r["special"],
                "bet": hit_name,
                "halfhalf": r["halfhalf"],
                "win_amount": win_amount,
            })
            consecutive_miss = 0
        else:
            consecutive_miss += 1

    profit = total_win - total_bet
    hit_rate = hit_count / 7 * 100
    theoretical = len(MY_NUMBERS) / 49 * 100

    if hit_rate >= theoretical:
        confidence = min(95, 50 + (hit_rate - theoretical) * 2)
    else:
        confidence = max(30, 50 - (theoretical - hit_rate) * 2)

    advice = "✅ 建议下注" if confidence >= 60 else "⚠️ 谨慎下注"
    if consecutive_miss >= 3:
        advice = "🔴 连续未中3期+，建议观望"

    return {
        "lottery": lottery_name,
        "latest_issue": latest["issue"] if latest else "N/A",
        "recent": recent,
        "hit_count": hit_count,
        "hit_rate": hit_rate,
        "total_bet": total_bet,
        "total_win": total_win,
        "profit": profit,
        "consecutive_miss": consecutive_miss,
        "hit_details": hit_details,
        "confidence": confidence,
        "advice": advice,
    }


def print_result(result):
    if not result:
        return

    print("\n" + "=" * 70)
    print(f"🎯 {result['lottery']} (5注策略)")
    print("=" * 70)

    print(f"\n📊 最近7期开奖:")
    print(f"{'期号':<12} {'特码':<6} {'半半波':<12} {'命中':<8} {'中奖':<12}")
    print("-" * 55)

    for r in result["recent"]:
        hit_name, _ = get_hit_bet(r["special"])
        if hit_name:
            print(f"{r['issue']:<12} {r['special']:<6} {r['halfhalf']:<12} ✅ {'':<4} {hit_name:<12}")
        else:
            print(f"{r['issue']:<12} {r['special']:<6} {r['halfhalf']:<12} ❌ {'':<4} {'-':<12}")

    print("-" * 55)
    print(f"\n📊 汇总:")
    print(f"  命中: {result['hit_count']}/7 ({result['hit_rate']:.1f}%)")
    print(f"  总投注: {result['total_bet']:.0f}元")
    print(f"  总中奖: {result['total_win']:.0f}元")
    print(f"  净盈亏: {result['profit']:+.0f}元")
    print(f"  连续未中: {result['consecutive_miss']}期")

    if result["hit_details"]:
        print(f"\n🎯 命中详情:")
        for h in result["hit_details"]:
            print(f"  {h['issue']} 开{h['number']:02d} → 中{h['bet']} (+{h['win_amount']:.0f}元)")

    print(f"\n📊 置信度: {result['confidence']:.0f}%")
    print(f"💡 建议: {result['advice']}")


def main():
    print("=" * 70)
    print("🎯 三彩最近7期命中 + 高置信度判断 (5注策略)")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    print("\n📋 5注策略:")
    for bet in BETS:
        nums = ", ".join([f"{n:02d}" for n in bet["numbers"]])
        print(f"  {bet['name']} (赔率{bet['odds']}): {nums}")

    print(f"\n📊 覆盖号码: {len(MY_NUMBERS)}个/49个 ({len(MY_NUMBERS)/49*100:.1f}%)")

    lotteries = ["香港彩", "新澳门彩", "老澳门彩"]
    results = []

    for name in lotteries:
        result = analyze_lottery(name)
        if result:
            print_result(result)
            results.append(result)
        else:
            print(f"\n⚠️ {name} 数据不足")

    if results:
        print("\n" + "=" * 70)
        print("📊 三彩汇总")
        print("=" * 70)
        print(f"{'彩种':<12} {'最新期号':<14} {'7期命中':<12} {'盈亏':<14} {'连续未中':<10} {'置信度':<10} {'建议':<10}")
        print("-" * 80)

        for r in results:
            print(f"{r['lottery']:<12} {r['latest_issue']:<14} {r['hit_count']}/7 ({r['hit_rate']:.0f}%)  {r['profit']:+,.0f}元{'':<6} {r['consecutive_miss']}期{'':<6} {r['confidence']:.0f}%{'':<4} {r['advice']:<10}")

        print("-" * 80)

        profit_count = sum(1 for r in results if r["profit"] > 0)
        print(f"\n📊 最近7期: {profit_count}/{len(results)} 个彩种盈利")
        if profit_count == len(results):
            print("  🎉 全部盈利！可以下注！")
        elif profit_count >= 2:
            print("  👍 大部分盈利，策略有效")
        else:
            print("  ⚠️ 盈利较少，建议观望")


if __name__ == "__main__":
    main()