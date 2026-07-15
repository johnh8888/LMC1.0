#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门六合彩 - 3注半半波策略每日预测
"""

import re
import json
import urllib.request
from datetime import datetime
import sys

CONFIG = {
    "api_url": "https://marksix6.net/index.php?api=1",
    "history_limit": 30,
    "bet_per_note": 100,
    "bets": [
        {"name": "蓝小单", "odds": 15.76, "numbers": [3, 9, 15, 21]},
        {"name": "绿大单", "odds": 11.82, "numbers": [27, 33, 39, 43, 49]},
        {"name": "蓝大双", "odds": 11.82, "numbers": [26, 36, 42, 47, 48]},
    ]
}

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

def fetch_data(limit=30):
    rows = []
    try:
        req = urllib.request.Request(CONFIG["api_url"], headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=60).read()
        data = json.loads(data.decode("utf-8"))

        target = None
        for item in data.get("lottery_data", []):
            if item.get("name", "").strip() == "新澳门彩":
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

def main():
    print("=" * 60)
    print("🎯 新澳门六合彩 - 3注半半波策略")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    rows = fetch_data(30)
    if len(rows) < 10:
        print("❌ 数据不足")
        sys.exit(1)

    print(f"✅ 获取 {len(rows)} 期数据")
    print(f"📅 最新期号: {rows[0]['issue']}")

    bets = CONFIG["bets"]
    bet_per_period = CONFIG["bet_per_note"] * len(bets)
    total_numbers = sum(len(bet["numbers"]) for bet in bets)

    report = f"""# 🎯 新澳门六合彩 - 3注半半波策略

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**策略**: 3注正期望值策略
**每期投入**: {bet_per_period}元 (3注×{CONFIG['bet_per_note']}元)

---

## 📊 最近开奖

| 期号 | 特码 | 半半波 |
|------|------|--------|
"""

    for r in rows[:10]:
        report += f"| {r['issue']} | {r['special']:2d} | {r['halfhalf']} |\n"

    report += f"""

---

## 🎯 今日下注建议

| 注数 | 玩法 | 赔率 | 号码 |
|------|------|------|------|
"""

    for i, bet in enumerate(bets, 1):
        nums = ", ".join([f"{n:02d}" for n in bet["numbers"]])
        report += f"| {i} | **{bet['name']}** | {bet['odds']} | {nums} |\n"

    report += f"""

**命中率**: {total_numbers/49*100:.1f}% (覆盖{total_numbers}个号码)

---

## 📈 统计信息

| 项目 | 数值 |
|------|------|
| 每期投入 | {bet_per_period}元 |
| 覆盖号码 | {total_numbers}个/49个 |
| 命中率 | {total_numbers/49*100:.1f}% |

---

## ⚠️ 风险提示

1. 彩票是随机游戏，任何策略都无法保证盈利
2. 请用闲钱参与，不要借贷
3. 严格按策略执行，不临时改变
4. 建议止损线: -10,000元
5. 建议止盈线: +30,000元

---

*本报告由自动化系统生成，仅供参考*
"""

    with open("result.md", "w", encoding="utf-8") as f:
        f.write(report)

    print("\n📋 下注建议:")
    for bet in bets:
        nums = ", ".join([f"{n:02d}" for n in bet["numbers"]])
        print(f"  {bet['name']}: {nums}")

    print(f"\n💰 每期投入: {bet_per_period}元")
    print("✅ 报告已生成: result.md")


if __name__ == "__main__":
    main()