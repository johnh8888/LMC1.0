#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门六合彩 - 最近10期命中查看（精简版）
只拉取最新数据，显示最近10期命中情况
"""

import re
import json
import urllib.request
from datetime import datetime

# =====================================================
# 3注策略（最终版）
# =====================================================

BETS = [
    {"name": "蓝小单", "odds": 15.76, "numbers": [3, 9, 15, 21]},
    {"name": "绿大单", "odds": 11.82, "numbers": [27, 33, 39, 43, 49]},
    {"name": "蓝大双", "odds": 11.82, "numbers": [26, 36, 42, 47, 48]},
]

# 合并所有号码
MY_NUMBERS = set()
for bet in BETS:
    for n in bet["numbers"]:
        MY_NUMBERS.add(n)

# 官方号码表（用于显示半半波）
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
    """检查命中了哪个玩法"""
    for bet in BETS:
        if n in bet["numbers"]:
            return bet["name"]
    return None


def fetch_recent(limit=20):
    """获取最近N期数据"""
    rows = []
    try:
        print("📡 正在获取最新数据...")
        req = urllib.request.Request(
            "https://marksix6.net/index.php?api=1",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        data = urllib.request.urlopen(req, timeout=30).read()
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

    # 去重并排序（最新在前）
    cache = {}
    for r in rows:
        cache[r["issue"]] = r
    rows = list(cache.values())
    rows.sort(key=lambda x: x["issue"], reverse=True)
    return rows[:limit]


def main():
    print("=" * 60)
    print("🎯 新澳门六合彩 - 最近10期命中查看")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 显示策略
    print("\n📋 3注策略:")
    for bet in BETS:
        nums = ", ".join([f"{n:02d}" for n in bet["numbers"]])
        print(f"  {bet['name']} (赔率{bet['odds']}): {nums}")

    total_numbers = sum(len(bet["numbers"]) for bet in BETS)
    print(f"\n📊 覆盖号码: {total_numbers}个/49个 ({total_numbers/49*100:.1f}%)")
    print(f"🎯 理论命中率: {total_numbers/49*100:.1f}%")

    # 获取数据
    rows = fetch_recent(20)
    if len(rows) < 10:
        print("❌ 数据不足")
        return

    # 显示最近10期
    recent = rows[:10]

    print("\n" + "=" * 60)
    print(f"📊 最近10期开奖明细")
    print("=" * 60)
    print(f"{'期号':<12} {'特码':<6} {'半半波':<12} {'命中':<8} {'中奖玩法':<12}")
    print("-" * 60)

    hit_count = 0
    hit_details = []
    consecutive_miss = 0

    for r in recent:
        hit_bet = get_hit_bet(r["special"])
        is_hit = hit_bet is not None

        if is_hit:
            hit_count += 1
            hit_icon = "✅"
            hit_details.append({
                "issue": r["issue"],
                "number": r["special"],
                "bet": hit_bet,
                "halfhalf": r["halfhalf"],
            })
            consecutive_miss = 0
        else:
            hit_icon = "❌"
            consecutive_miss += 1

        print(f"{r['issue']:<12} {r['special']:<6} {r['halfhalf']:<12} {hit_icon:<8} {hit_bet or '-':<12}")

    print("-" * 60)

    # 汇总
    theoretical = total_numbers / 49 * 10

    print(f"\n📊 最近10期汇总:")
    print(f"  命中: {hit_count}/10 ({hit_count*10:.1f}%)")
    print(f"  理论预期: {theoretical:.1f}次")
    print(f"  偏差: {hit_count - theoretical:+.1f}次")

    if hit_count > theoretical:
        print(f"  ✅ 最近表现优于理论预期！")
    elif hit_count < theoretical:
        print(f"  ⚠️ 最近表现低于理论预期，属正常波动")
    else:
        print(f"  ℹ️ 与理论预期一致")

    # 命中详情
    if hit_details:
        print(f"\n🎯 命中详情:")
        for h in hit_details:
            print(f"  {h['issue']} 开{h['number']:02d} → 中{h['bet']} ({h['halfhalf']})")
    else:
        print(f"\n❌ 最近10期未命中")

    # 连续未中
    if consecutive_miss > 0:
        print(f"\n⚠️ 当前已连续 {consecutive_miss} 期未中")
        if consecutive_miss >= 10:
            print(f"  🔴 连续未中已达 {consecutive_miss} 期，请注意风险！")
    else:
        print(f"\n✅ 最近一期命中！")

    # 盈亏估算（3注，每期300元）
    total_bet = 10 * 300
    total_win = 0
    for h in hit_details:
        for bet in BETS:
            if bet["name"] == h["bet"]:
                total_win += bet["odds"] * 100
                break

    profit = total_win - total_bet
    print(f"\n💰 盈亏估算（最近10期，每期300元）:")
    print(f"  总投注: {total_bet:,.0f}元")
    print(f"  总中奖: {total_win:,.0f}元")
    print(f"  净盈亏: {profit:+,.0f}元")


if __name__ == "__main__":
    main()