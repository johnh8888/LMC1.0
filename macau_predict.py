#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门六合彩 - 4注半半波策略预测
每天自动运行，生成下注建议
"""

import re
import json
import urllib.request
from datetime import datetime
import sys

CONFIG = {
    "api_url": "https://marksix6.net/index.php?api=1",
    "history_limit": 50,
    "bet_per_note": 100,
    "bets": [
        {"name": "蓝小单", "odds": 15.76, "numbers": [3, 9, 15, 21]},
        {"name": "蓝大双", "odds": 11.82, "numbers": [26, 36, 42, 47, 48]},
        {"name": "绿大双", "odds": 11.82, "numbers": [28, 32, 38, 44, 49]},
        {"name": "红小双", "odds": 9.45, "numbers": [2, 8, 12, 18, 24]},
    ]
}

RED = {1, 2, 7, 8, 12, 13, 18, 19, 23, 24, 29, 30, 34, 35, 40, 45, 46}
BLUE = {3, 4, 9, 10, 14, 15, 20, 25, 26, 31, 36, 37, 41, 42, 47, 48}
GREEN = {5, 6, 11, 16, 17, 21, 22, 27, 28, 32, 33, 38, 39, 43, 44, 49}


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


def fetch_data(limit=50):
    rows = []
    try:
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
                "color": get_color(special),
                "size": get_size(special),
                "odd": get_odd(special),
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


def generate_report(rows):
    bets = CONFIG["bets"]
    bet_per_period = CONFIG["bet_per_note"] * len(bets)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    latest = rows[0] if rows else None

    report = f"""# 🎯 新澳门六合彩 - 半半波策略预测报告

**生成时间**: {now}
**策略**: 4注半半波正期望值策略
**每期投入**: {bet_per_period}元 ({len(bets)}注×{CONFIG['bet_per_note']}元)

---

## 📊 最近开奖

| 期号 | 特码 | 颜色 | 大小 | 单双 | 半半波 |
|------|------|------|------|------|--------|
"""

    for r in rows[:10]:
        report += f"| {r['issue']} | {r['special']} | {r['color']} | {r['size']} | {r['odd']} | {r['halfhalf']} |\n"

    report += f"""

---

## 🎯 今日下注建议

| 注数 | 玩法 | 赔率 | 号码 |
|------|------|------|------|
"""

    for i, bet in enumerate(bets, 1):
        numbers_str = ", ".join([f"{n:02d}" for n in bet["numbers"]])
        report += f"| {i} | **{bet['name']}** | {bet['odds']} | {numbers_str} |\n"

    total_numbers = sum(len(bet["numbers"]) for bet in bets)
    report += f"""

**命中率**: {total_numbers/49*100:.1f}% (覆盖{total_numbers}个号码)

---

## 📈 统计信息

| 项目 | 数值 |
|------|------|
| 最近30期命中率 | 待更新 |
| 最长连续未中 | 待更新 |

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

    print("✅ 报告已生成: result.md")
    return report


def main():
    print("=" * 60)
    print("🎯 新澳门六合彩 - 半半波策略预测")
    print("=" * 60)

    rows = fetch_data(50)
    if len(rows) < 10:
        print("❌ 数据不足")
        sys.exit(1)

    print(f"✅ 获取 {len(rows)} 期数据")
    print(f"📅 最新期号: {rows[0]['issue']}")

    generate_report(rows)

    # 保存参数缓存
    params = {
        "last_run": datetime.now().isoformat(),
        "latest_issue": rows[0]["issue"],
        "total_periods": len(rows),
    }
    with open("macau_best_params.json", "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)

    print("✅ 参数缓存已保存")


if __name__ == "__main__":
    main()