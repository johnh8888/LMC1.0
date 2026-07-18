#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三彩（香港彩 / 新澳门彩 / 老澳门彩）大/单 置信度下注建议
------------------------------------------------------
逻辑：
  - "大"(>=25，含49) 和 "单"(奇数，含49) 理论概率均为 25/49 ≈ 51.02%
  - 本脚本用 z 检验，判断近期实际出现率是否显著偏离理论值。
  - 支持多窗口综合判断，只有当多数窗口都显示信号时才建议下注。
  
版本：v2.0 - 多窗口综合判断
"""

import re
import json
import math
import urllib.request
from collections import defaultdict

API_URL = "https://marksix6.net/index.php?api=1"

# 三彩配置
LOTTERIES = [
    {"key": "hk",   "name": "香港彩", "label": "香港彩"},
    {"key": "xam",  "name": "新澳门彩", "label": "新澳门彩"},
    {"key": "lam",  "name": "老澳门彩", "label": "老澳门彩"},
]

THEORY_P = 25 / 49  # 大 / 单 理论概率


def parse_numbers(text):
    nums = re.findall(r"\d+", text)
    return [int(x) for x in nums if 1 <= int(x) <= 49]


def fetch_lottery(lottery_name, limit=200):
    """抓取指定彩种最近 limit 期特码数据"""
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

        # 去重
        unique_rows = {}
        for r in rows:
            unique_rows[r["issue"]] = r
        rows = list(unique_rows.values())
        
        # 按从新到旧排序，取前limit期，再转回升序
        rows.sort(key=lambda x: x["issue"], reverse=True)
        rows = rows[:limit]
        rows.sort(key=lambda x: x["issue"])
        
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


def bet_decision(rows, window=50, z_threshold=1.96):
    """单窗口判断"""
    if len(rows) < window:
        return None
    
    recent = rows[-window:]
    n = len(recent)
    hits_big = sum(1 for r in recent if r["is_big"])
    hits_odd = sum(1 for r in recent if r["is_odd"])

    z_big, p_big = z_test(hits_big, n)
    z_odd, p_odd = z_test(hits_odd, n)

    return {
        "大": {
            "action": "下注" if z_big >= z_threshold else "观望",
            "z": z_big,
            "p": p_big,
            "hits": hits_big,
            "n": n
        },
        "单": {
            "action": "下注" if z_odd >= z_threshold else "观望",
            "z": z_odd,
            "p": p_odd,
            "hits": hits_odd,
            "n": n
        },
    }


def multi_window_decision(rows, windows=[30, 50, 100], z_threshold=1.96):
    """
    多窗口综合判断
    只有超过半数窗口显示"下注"时才建议下注
    """
    if not rows:
        return None
    
    results = {}
    
    for w in windows:
        if len(rows) >= w:
            d = bet_decision(rows, window=w, z_threshold=z_threshold)
            if d:
                results[w] = d
    
    if not results:
        return None
    
    # 统计各方向投票
    big_votes = []
    odd_votes = []
    
    for w, d in results.items():
        big_votes.append(1 if d["大"]["action"] == "下注" else 0)
        odd_votes.append(1 if d["单"]["action"] == "下注" else 0)
    
    # 超过半数窗口同意才下注
    threshold = len(results) / 2
    
    final_big = sum(big_votes) > threshold
    final_odd = sum(odd_votes) > threshold
    
    # 获取最新窗口的数据用于显示
    latest_w = max(results.keys())
    latest_d = results[latest_w]
    
    return {
        "big": {
            "action": "下注" if final_big else "观望",
            "votes": sum(big_votes),
            "total_windows": len(results),
            "detail": {w: results[w]["大"] for w in results.keys()}
        },
        "odd": {
            "action": "下注" if final_odd else "观望",
            "votes": sum(odd_votes),
            "total_windows": len(results),
            "detail": {w: results[w]["单"] for w in results.keys()}
        },
        "latest_window": latest_w,
        "latest_detail": latest_d
    }


def backtest_signal_accuracy(rows, window=50, z_threshold=1.96):
    """历史准确率回测"""
    stats = {"大": {"bet_count": 0, "hit_count": 0},
             "单": {"bet_count": 0, "hit_count": 0}}

    if len(rows) < window + 1:
        print(f"\n⚠️ 数据不足 {window+1} 期，无法进行历史准确率回测")
        return stats

    for i in range(window, len(rows)):
        history = rows[:i]
        actual_next = rows[i]

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

    print(f"\n{'='*70}")
    print(f"📈 信号历史准确率回测（窗口={window}期，基于{len(rows)}期数据）")
    print("="*70)
    
    for label, s in stats.items():
        bc, hc = s["bet_count"], s["hit_count"]
        if bc == 0:
            print(f"【{label}】 历史从未触发下注信号")
            continue
        acc = hc / bc * 100
        z_acc, _ = z_test(hc, bc)
        
        # 评估信号质量
        if bc >= 50 and abs(z_acc) >= 1.96:
            verdict = "✅ 显著高于理论值" if z_acc > 0 else "⚠️ 显著低于理论值"
        elif bc >= 30:
            verdict = "📊 有一定参考价值（需继续观察）"
        else:
            verdict = "⚠️ 样本太少，结论不可靠"
            
        print(f"【{label}】 信号触发 {bc} 次，命中 {hc} 次 = {acc:.1f}%  "
              f"(理论基准 {THEORY_P*100:.1f}%)  → {verdict}")
        
        # 显示置信区间
        if bc > 0:
            se = math.sqrt(acc/100 * (1 - acc/100) / bc)
            ci_low = max(0, acc/100 - 1.96*se) * 100
            ci_high = min(1, acc/100 + 1.96*se) * 100
            print(f"   95%置信区间: {ci_low:.1f}% ~ {ci_high:.1f}%")
    
    return stats


def run_all(windows=[30, 50, 100], z_threshold=1.96, fetch_limit=200):
    print("=" * 70)
    print(f"🎯 三彩大/单置信度下注建议（多窗口综合判断）")
    print(f"   窗口: {windows}期 | 阈值: z>={z_threshold}")
    print(f"   数据: 最近{fetch_limit}期")
    print("=" * 70)

    summary = []
    
    for lot in LOTTERIES:
        rows = fetch_lottery(lot["name"], limit=fetch_limit)
        if len(rows) < max(windows):
            print(f"⚠️ {lot['label']} 数据不足 {max(windows)} 期，跳过\n")
            continue

        latest = rows[-1]
        
        # 多窗口综合判断
        decision = multi_window_decision(rows, windows=windows, z_threshold=z_threshold)
        
        print(f"\n—— {lot['label']} ——")
        print(f"最新期号: {latest['issue']}  特码: {latest['special']}  "
              f"大={'是' if latest['is_big'] else '否'}  单={'是' if latest['is_odd'] else '否'}")
        
        # 显示各窗口详情
        print(f"\n📊 各窗口判断详情:")
        print(f"{'窗口':<8} {'大-z值':<10} {'大出现率':<10} {'大判断':<8} {'单-z值':<10} {'单出现率':<10} {'单判断':<8}")
        print("-" * 75)
        
        for w in sorted(windows):
            if w in decision["big"]["detail"]:
                big_d = decision["big"]["detail"][w]
                odd_d = decision["odd"]["detail"][w]
                print(f"{w}期{'':<4} {big_d['z']:+.2f}     {big_d['p']*100:.1f}%    "
                      f"{'✅下注' if big_d['action']=='下注' else '⏸️观望':<8} "
                      f"{odd_d['z']:+.2f}     {odd_d['p']*100:.1f}%    "
                      f"{'✅下注' if odd_d['action']=='下注' else '⏸️观望':<8}")
        
        # 综合结论
        print(f"\n📋 综合判断（{decision['big']['total_windows']}个窗口，超过半数同意才下注）:")
        for label in ["big", "odd"]:
            d = decision[label]
            if d["action"] == "下注":
                print(f"  【{'大' if label=='big' else '单'}】 ✅ 建议下注 ({d['votes']}/{d['total_windows']}个窗口同意)")
            else:
                print(f"  【{'大' if label=='big' else '单'}】 ⏸️ 观望 ({d['votes']}/{d['total_windows']}个窗口同意)")
            
            # 显示各窗口详细
            for w in sorted(d['detail'].keys()):
                detail = d['detail'][w]
                status = "✅" if detail['action'] == '下注' else "⏸️"
                print(f"      {w}期窗口: {status} z={detail['z']:+.2f} 出现率={detail['p']*100:.1f}%")
        
        # 历史准确率回测（使用中间窗口）
        mid_window = windows[len(windows)//2]
        backtest_signal_accuracy(rows, window=mid_window, z_threshold=z_threshold)
        
        # 记录汇总
        summary.append({
            "lottery": lot["label"],
            "big": decision["big"]["action"],
            "odd": decision["odd"]["action"],
            "big_votes": decision["big"]["votes"],
            "odd_votes": decision["odd"]["votes"],
            "total_windows": decision["big"]["total_windows"]
        })
        print()

    # 最终汇总
    print("=" * 70)
    print("📋 本期汇总（综合判断）")
    print("=" * 70)
    
    bets = [s for s in summary if s["big"] == "下注" or s["odd"] == "下注"]
    if not bets:
        print("本期无任何彩种/方向达到综合下注标准，建议全部观望。")
    else:
        for s in bets:
            if s["big"] == "下注":
                print(f"  {s['lottery']} - 大号 ({s['big_votes']}/{s['total_windows']}个窗口同意)")
            if s["odd"] == "下注":
                print(f"  {s['lottery']} - 单号 ({s['odd_votes']}/{s['total_windows']}个窗口同意)")
    
    print("\n" + "=" * 70)
    print("📊 信号质量评估")
    print("=" * 70)
    print("""
✅ 高可信度信号：窗口≥50期 + 历史触发≥50次 + 准确率显著高于理论值
📊 中等可信度信号：窗口≥30期 + 历史触发≥30次
⚠️ 低可信度信号：窗口<30期 或 历史触发<20次（建议观望）
    """)
    print("\n⚠️ 提醒：本工具用于减少下注频率，不构成盈利保证。")


if __name__ == "__main__":
    # 推荐配置：多窗口综合判断
    run_all(
        windows=[30, 50, 100],  # 多个窗口
        z_threshold=1.96,       # 95%置信度
        fetch_limit=200         # 获取200期数据
    )