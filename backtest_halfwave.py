#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大/单 置信度检测工具
------------------------------------
核心思路：
  - "大"和"单"在49个号码中各占25个（含49），理论概率 = 25/49 ≈ 51.02%
  - 该理论概率已经是数学期望最优的选择（配合1:1.95赔率，EV≈99.5%）
  - 本脚本不会用历史频率去"预测"下一期，而是用统计检验(z检验)判断：
      近期实际出现率是否显著偏离理论值 51.02%
  - 只有偏离达到统计显著水平（|z| >= 1.96，对应95%置信度）时才提示关注，
    绝大多数情况下会提示"无显著偏离"——这是真实情况，不是脚本没写好。

⚠️ 重要说明：
  即使检测到"显著偏离"，也只能说明近期分布不均，不能证明未来会延续。
  真正决定长期结果的是赔率结构（EV≈99.5%，仍是负期望），不是"追热号"。
  本工具的作用是防止你把正常随机波动误判成"规律"，而不是帮你找规律。
"""

import math

THEORY_P = 25 / 49  # 大 和 单 的理论概率（含49）

def z_test(hits, n, p0=THEORY_P):
    """二项分布近似正态检验，返回 z 值和实际频率"""
    if n == 0:
        return 0.0, 0.0
    p_hat = hits / n
    se = math.sqrt(p0 * (1 - p0) / n)
    z = (p_hat - p0) / se if se > 0 else 0.0
    return z, p_hat

def judge(z):
    """根据z值给出结论，而不是无脑推荐"""
    if abs(z) >= 2.58:
        level = "高置信 (99%)"
    elif abs(z) >= 1.96:
        level = "中等置信 (95%)"
    else:
        return "无显著偏离，建议按固定策略执行，不额外加仓", None
    direction = "偏高" if z > 0 else "偏低"
    return f"{level}：实际出现率显著{direction}于理论值", level

def analyze(name, results, window_sizes=(10, 20, 30, 50, 100)):
    """
    results: 按时间顺序（旧->新）的记录列表，每条是 dict:
        {"issue": "2026/199", "is_big": True/False, "is_odd": True/False}
    """
    print(f"\n{'='*70}\n📊 {name} 大/单 置信度分析\n{'='*70}")
    print(f"理论概率（含49规则）: 大 = {THEORY_P*100:.2f}%, 单 = {THEORY_P*100:.2f}%\n")

    for key, label in (("is_big", "大"), ("is_odd", "单")):
        print(f"—— 【{label}】 ——")
        for w in window_sizes:
            if len(results) < w:
                continue
            recent = results[-w:]
            hits = sum(1 for r in recent if r[key])
            z, p_hat = z_test(hits, w)
            msg, level = judge(z)
            flag = "🔥" if level else "  "
            print(f"{flag} 近{w:>3}期: {label}出现 {hits:>3}/{w} = {p_hat*100:5.1f}%  "
                  f"z={z:+.2f}  → {msg}")
        print()

    # 最新一期实际结果
    latest = results[-1]
    print(f"最新一期: {latest['issue']}  大={'是' if latest['is_big'] else '否'}  "
          f"单={'是' if latest['is_odd'] else '否'}")


def make_recommendation(results, window=30, z_threshold=1.96):
    """
    基于最近window期数据，给出当期建议（诚实版）：
    - 若"大"或"单"任一方向出现统计显著偏离，标注为"可关注"
    - 否则给出默认建议：按大/单固定策略压注（因为这本身就是EV最优选择），
      而不是等信号才下注
    """
    recent = results[-window:] if len(results) >= window else results
    n = len(recent)
    hits_big = sum(1 for r in recent if r["is_big"])
    hits_odd = sum(1 for r in recent if r["is_odd"])

    z_big, p_big = z_test(hits_big, n)
    z_odd, p_odd = z_test(hits_odd, n)

    print(f"\n{'='*70}\n💡 当期建议（基于最近{n}期）\n{'='*70}")

    for label, z, p in (("大", z_big, p_big), ("单", z_odd, p_odd)):
        if abs(z) >= z_threshold:
            direction = "近期出现率偏高，无额外风险信号" if z > 0 else "近期出现率偏低，注意可能只是短期波动"
            print(f"【{label}】z={z:+.2f}（显著）— {direction}")
        else:
            print(f"【{label}】z={z:+.2f}（不显著）— 无统计证据支持临时调整，"
                  f"维持默认压注（{label}本身EV≈99.5%，是长期最优方向）")

    print("\n⚠️ 提醒：无论z值如何，长期期望值都低于1（负期望）。"
          "统计检验只用于识别异常，不构成盈利保证。")


if __name__ == "__main__":
    # 示例：把你实际抓取的开奖数据填进来（旧 -> 新排列）
    # 示例数据仅作演示，请替换为真实历史记录
    demo_results = [
        {"issue": "2026/190", "is_big": True,  "is_odd": True},
        {"issue": "2026/191", "is_big": True,  "is_odd": True},
        {"issue": "2026/192", "is_big": True,  "is_odd": True},
        {"issue": "2026/193", "is_big": False, "is_odd": True},
        {"issue": "2026/194", "is_big": True,  "is_odd": False},
        {"issue": "2026/195", "is_big": True,  "is_odd": True},
        {"issue": "2026/196", "is_big": True,  "is_odd": True},
        {"issue": "2026/197", "is_big": False, "is_odd": False},
        {"issue": "2026/198", "is_big": False, "is_odd": True},
        {"issue": "2026/199", "is_big": True,  "is_odd": False},
    ]

    analyze("示例数据", demo_results)
    make_recommendation(demo_results, window=10)
