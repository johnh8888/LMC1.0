#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三彩（香港彩 / 新澳门彩 / 老澳门彩）大/单 置信度下注建议
------------------------------------------------------
逻辑：
  - "大"(>=25，含49) 和 "单"(奇数，含49) 理论概率均为 25/49 ≈ 51.02%
    这已经是数学期望最优方向（配合1:1.95赔率，EV≈99.5%），本身不需要"预测"。
  - 本脚本用 z 检验，判断近期(默认30期)实际出现率是否显著偏离理论值。
  - 只有 z >= 1.96（95%置信度，显著偏高）才建议"下注"，否则一律"观望"。
  - 显著偏低(z <= -1.96)也不下注（没道理去押偏低的方向）。

⚠️ 重要说明：
  - 95%置信度意味着即使数据完全随机，约每20次判断也会有1次"假显著"。
  - 多彩种、多窗口同时检验会放大总体误报率，建议固定窗口（如30期），
    不要因为哪个窗口显示"下注"就采信哪个。
  - 即使某次真的显著，也只说明"近期分布不均"，不代表下一期会延续。
    这不是盈利保证，只是风险控制工具。
"""

import re
import json
import math
import urllib.request

API_URL = "https://marksix6.net/index.php?api=1"

# 三彩配置：name 对应 API 返回数据里的 "name" 字段
LOTTERIES = [
    {"key": "hk",   "name": "香港彩", "label": "香港彩"},
    {"key": "xam",  "name": "新澳门彩",   "label": "新澳门彩"},
    {"key": "lam",  "name": "老澳门彩",   "label": "老澳门彩"},
]

THEORY_P = 25 / 49  # 大 / 单 理论概率（49参与判定，不退款）


def parse_numbers(text):
    nums = re.findall(r"\d+", text)
    return [int(x) for x in nums if 1 <= int(x) <= 49]


def fetch_lottery(lottery_name, limit=100):
    """抓取指定彩种最近 limit 期特码数据，返回按期号升序(旧->新)的列表"""
    print(f"📡 正在获取 {lottery_name} 最近{limit}期数据...")
    try:
        req = urllib.request.Request(API_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        rows = []
        for item in data.get("lottery_data", []):
            if item.get("name", "").strip() == lottery_name:
                for line in item.get("history", []):
                    nums = parse_numbers(line)
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
                        "is_big": special >= 25,
                        "is_odd": special % 2 == 1,
                    })
                break

        # 去重（按期号）
        unique_rows = {}
        for r in rows:
            unique_rows[r["issue"]] = r
        rows = list(unique_rows.values())
        
        # 按从新到旧排序，取前limit期，再转回升序
        rows.sort(key=lambda x: x["issue"], reverse=True)
        rows = rows[:limit]  # 只取最近limit期
        rows.sort(key=lambda x: x["issue"])  # 升序：旧 -> 新
        
        print(f"✅ 获取 {len(rows)} 期数据（最近{limit}期）")
        
        if rows:
            print(f"📅 数据范围: {rows[0]['issue']} ~ {rows[-1]['issue']} (共{len(rows)}期)")
        
        return rows
    except Exception as e:
        print(f"❌ 获取失败: {e}")
        return []


def z_test(hits, n, p0=THEORY_P):
    if n == 0:
        return 0.0, 0.0
    p_hat = hits / n
    se = math.sqrt(p0 * (1 - p0) / n)
    z = (p_hat - p0) / se if se > 0 else 0.0
    return z, p_hat


def bet_decision(results, window=30, z_threshold=1.96):
    """只有显著偏高(z>=阈值)才建议下注，否则观望"""
    recent = results[-window:] if len(results) >= window else results
    n = len(recent)
    if n == 0:
        return {}
    hits_big = sum(1 for r in recent if r["is_big"])
    hits_odd = sum(1 for r in recent if r["is_odd"])

    z_big, p_big = z_test(hits_big, n)
    z_odd, p_odd = z_test(hits_odd, n)

    return {
        "大": ("下注" if z_big >= z_threshold else "观望", z_big, p_big),
        "单": ("下注" if z_odd >= z_threshold else "观望", z_odd, p_odd),
        "n": n,
    }


def backtest_signal_accuracy(results, window=30, z_threshold=1.96):
    """
    历史回测：走位验证(walk-forward)信号准确率。
    对每一期，只用它之前的数据算z值判断是否"下注"，
    若触发下注，则检查下一期实际是否真的开出该方向，统计命中率。

    这个命中率如果显著高于理论值51.02%，才说明信号真的有效；
    如果命中率接近51%甚至更低，说明信号只是噪音，不具备预测力。
    """
    stats = {"大": {"bet_count": 0, "hit_count": 0},
             "单": {"bet_count": 0, "hit_count": 0}}

    # 需要至少window期数据才能开始回测
    if len(results) < window + 1:
        print(f"\n⚠️ 数据不足 {window+1} 期，无法进行历史准确率回测")
        return stats

    for i in range(window, len(results)):
        history = results[:i]          # 只用当前期之前的数据
        actual_next = results[i]       # 实际发生的下一期结果

        recent = history[-window:]
        n = len(recent)
        hits_big = sum(1 for r in recent if r["is_big"])
        hits_odd = sum(1 for r in recent if r["is_odd"])
        z_big, _ = z_test(hits_big, n)
        z_odd, _ = z_test(hits_odd, n)

        if z_big >= z_threshold:
            stats["大"]["bet_count"] += 1
            if actual_next["is_big"]:
                stats["大"]["hit_count"] += 1

        if z_odd >= z_threshold:
            stats["单"]["bet_count"] += 1
            if actual_next["is_odd"]:
                stats["单"]["hit_count"] += 1

    print(f"\n{'='*70}\n📈 信号历史准确率回测（走位验证，窗口={window}期，基于最近{len(results)}期数据）\n{'='*70}")
    for label, s in stats.items():
        bc, hc = s["bet_count"], s["hit_count"]
        if bc == 0:
            print(f"【{label}】 历史从未触发下注信号（数据不足或长期无显著偏离）")
            continue
        acc = hc / bc * 100
        # 用二项检验判断这个命中率本身是否显著高于理论值
        z_acc, _ = z_test(hc, bc)
        verdict = "⚠️ 与理论值无显著差异，信号可能只是噪音" if abs(z_acc) < 1.96 else \
                  ("✅ 显著高于理论值" if z_acc > 0 else "⚠️ 显著低于理论值，信号方向可能反了")
        print(f"【{label}】 信号触发 {bc} 次，命中 {hc} 次 = {acc:.1f}%  "
              f"(理论基准 {THEORY_P*100:.1f}%)  → {verdict}")

    print("\n⚠️ 提醒：触发次数(bet_count)太少时（比如<20次），这个准确率本身的")
    print("   置信区间会很宽，不能当作可靠结论；触发次数越多，结果才越可信。")
    return stats


def run_all(window=30, z_threshold=1.96, fetch_limit=100):
    print("=" * 70)
    print(f"🎯 三彩大/单置信度下注建议（窗口={window}期，阈值z>={z_threshold}）")
    print(f"   基于最近{fetch_limit}期数据")
    print("=" * 70)

    summary = []
    for lot in LOTTERIES:
        rows = fetch_lottery(lot["name"], limit=fetch_limit)
        if len(rows) < 10:
            print(f"⚠️ {lot['label']} 数据不足，跳过\n")
            continue

        latest = rows[-1]
        d = bet_decision(rows, window=window, z_threshold=z_threshold)

        print(f"\n—— {lot['label']} ——")
        print(f"最新期号: {latest['issue']}  特码: {latest['special']}  "
              f"大={'是' if latest['is_big'] else '否'}  单={'是' if latest['is_odd'] else '否'}")

        for label in ("大", "单"):
            action, z, p = d[label]
            mark = "✅ 下注" if action == "下注" else "⏸️ 观望"
            print(f"  【{label}】 z={z:+.2f}  近{d['n']}期出现率={p*100:.1f}%  → {mark}")
            summary.append({"lottery": lot["label"], "type": label, "action": action, "z": z})

        # 历史准确率回测：这个信号过去触发时到底准不准
        backtest_signal_accuracy(rows, window=window, z_threshold=z_threshold)
        print()

    print("=" * 70)
    print("📋 本期汇总（只列出建议下注的项，其余均为观望）")
    print("=" * 70)
    bets = [s for s in summary if s["action"] == "下注"]
    if not bets:
        print("本期无任何彩种/方向达到显著阈值，建议全部观望。")
    else:
        for b in bets:
            print(f"  {b['lottery']} - {b['type']}  (z={b['z']:+.2f})")

    print("\n⚠️ 提醒：下注信号基于统计显著性，仍可能是随机波动的误报（约5%概率）。")
    print("   长期期望值约99.5%（负期望），本工具用于减少下注频率，不构成盈利保证。")


if __name__ == "__main__":
    run_all(window=30, z_threshold=1.96, fetch_limit=100)