#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新澳门六合彩 - 3注半半波策略每日预测
修复：API SSL 证书过期 / CERTIFICATE_VERIFY_FAILED
"""
import re
import json
import urllib.request
import ssl
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
RED = {
    1, 2, 7, 8, 12, 13, 18, 19, 23, 24,
    29, 30, 34, 35, 40, 45, 46
}
BLUE = {
    3, 4, 9, 10, 14, 15, 20, 25, 26, 31,
    36, 37, 41, 42, 47, 48
}
GREEN = {
    5, 6, 11, 16, 17, 21, 22, 27, 28, 32,
    33, 38, 39, 43, 44, 49
}
def get_color(n):
    if n in RED:
        return "红"
    if n in BLUE:
        return "蓝"
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
        # ==========================================================
        # SSL证书兼容处理
        # 如果 marksix6.net 证书过期，则跳过证书验证
        # ==========================================================
        ssl_context = ssl._create_unverified_context()
        req = urllib.request.Request(
            CONFIG["api_url"],
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                ),
                "Accept": "application/json,text/plain,*/*",
                "Connection": "close"
            }
        )
        print("🌐 正在获取新澳门彩历史数据...")
        print(f"🔗 API: {CONFIG['api_url']}")
        # 关键：
        # context=ssl_context
        # 绕过服务器过期SSL证书检查
        with urllib.request.urlopen(
            req,
            timeout=60,
            context=ssl_context
        ) as response:
            raw_data = response.read()
        data = json.loads(raw_data.decode("utf-8"))
        target = None
        for item in data.get("lottery_data", []):
            if item.get("name", "").strip() == "新澳门彩":
                target = item
                break
        if not target:
            print("❌ API中没有找到“新澳门彩”")
            return []
        history = target.get("history", [])
        print(f"📥 API返回历史记录: {len(history)} 条")
        for line in history:
            nums = re.findall(r"\d+", str(line))
            nums = [
                int(x)
                for x in nums
                if 1 <= int(x) <= 49
            ]
            # 必须至少有7个号码
            if len(nums) < 7:
                continue
            # 最后一个号码作为特码
            special = nums[-1]
            # 提取期号
            m = re.search(
                r"(20\d{5,8})",
                str(line)
            )
            if not m:
                continue
            raw = m.group(1)
            try:
                issue = (
                    raw[:4]
                    + "/"
                    + str(int(raw[4:])).zfill(3)
                )
            except Exception:
                continue
            rows.append({
                "issue": issue,
                "special": special,
                "halfhalf": get_halfhalf(special)
            })
    except ssl.SSLError as e:
        print("❌ SSL错误:")
        print(e)
        print("\n⚠️ 即使已经关闭证书验证，仍然无法连接。")
        print("可能是服务器TLS协议或网站本身无法访问。")
        return []
    except urllib.error.URLError as e:
        print("❌ 网络连接失败:")
        print(e)
        return []
    except json.JSONDecodeError as e:
        print("❌ API返回的数据不是有效JSON:")
        print(e)
        return []
    except Exception as e:
        print(f"❌ 获取失败: {e}")
        return []
    # ==========================================================
    # 去重
    # ==========================================================
    cache = {}
    for r in rows:
        cache[r["issue"]] = r
    rows = list(cache.values())
    # 最新期在前
    rows.sort(
        key=lambda x: x["issue"],
        reverse=True
    )
    return rows[:limit]
def main():
    print("=" * 60)
    print("🎯 新澳门六合彩 - 3注半半波策略")
    print(
        f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print("=" * 60)
    rows = fetch_data(30)
    if len(rows) < 10:
        print("❌ 数据不足")
        sys.exit(1)
    print(f"✅ 获取 {len(rows)} 期数据")
    print(f"📅 最新期号: {rows[0]['issue']}")
    bets = CONFIG["bets"]
    bet_per_period = (
        CONFIG["bet_per_note"]
        * len(bets)
    )
    total_numbers = sum(
        len(bet["numbers"])
        for bet in bets
    )
    report = f"""# 🎯 新澳门六合彩 - 3注半半波策略
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**策略**: 3注半半波策略
**每期投入**: {bet_per_period}元
---
## 📊 最近开奖
| 期号 | 特码 | 半半波 |
|------|------|--------|
"""
    for r in rows[:10]:
        report += (
            f"| {r['issue']} "
            f"| {r['special']:2d} "
            f"| {r['halfhalf']} |\n"
        )
    report += f"""
---
## 🎯 今日下注建议
| 注数 | 玩法 | 赔率 | 号码 |
|------|------|------|------|
"""
    for i, bet in enumerate(bets, 1):
        nums = ", ".join(
            f"{n:02d}"
            for n in bet["numbers"]
        )
        report += (
            f"| {i} "
            f"| **{bet['name']}** "
            f"| {bet['odds']} "
            f"| {nums} |\n"
        )
    report += f"""
---
## 📈 统计信息
| 项目 | 数值 |
|------|------|
| 每期投入 | {bet_per_period}元 |
| 覆盖号码 | {total_numbers}个/49个 |
| 号码覆盖率 | {total_numbers / 49 * 100:.1f}% |
---
## ⚠️ 风险提示
1. 彩票结果具有随机性，历史数据不能保证未来结果。
2. 不要借贷或使用影响正常生活的资金参与。
3. 本程序只负责数据分析和报告生成。
4. 不构成任何盈利保证。
---
*本报告由自动化系统生成，仅供参考*
"""
    with open(
        "result.md",
        "w",
        encoding="utf-8"
    ) as f:
        f.write(report)
    print("\n📋 下注建议:")
    for bet in bets:
        nums = ", ".join(
            f"{n:02d}"
            for n in bet["numbers"]
        )
        print(
            f"  {bet['name']}: {nums}"
        )
    print(
        f"\n💰 每期投入: {bet_per_period}元"
    )
    print("✅ 报告已生成: result.md")
if __name__ == "__main__":
    main()
``