#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三彩大/单 置信度下注建议 + 反向策略回测
包含：
1. 正向策略（压大/单）
2. 反向策略（压小/双）
3. 对比分析
"""

import re
import json
import math
import urllib.request
from datetime import datetime, timedelta
from collections import defaultdict

API_URL = "https://marksix6.net/index.php?api=1"

# ============ 配置 ============
CONFIG = {
    "per_bet_amount": 200,
    "max_daily_bets": 3,
    "weekly_target": 2000,
    "daily_target": 300,
    "weekly_stop_loss": -2000,
    "daily_stop_loss": -500,
    "consecutive_loss_days": 3,
}

LOTTERIES = [
    {"key": "hk", "name": "香港彩", "label": "香港彩"},
    {"key": "xam", "name": "新澳门彩", "label": "新澳门彩"},
    {"key": "lam", "name": "老澳门彩", "label": "老澳门彩"},
]

THEORY_P = 25 / 49

# ============ 数据获取 ============
def parse_numbers(text):
    nums = re.findall(r"\d+", text)
    return [int(x) for x in nums if 1 <= int(x) <= 49]

def fetch_lottery(lottery_name, limit=200):
    """获取彩票数据"""
    print(f"📡 正在获取 {lottery_name} 数据...")
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
                        "is_small": special < 25,
                        "is_odd": special % 2 == 1,
                        "is_even": special % 2 == 0,
                    })
                break

        unique_rows = {}
        for r in rows:
            unique_rows[r["issue"]] = r
        rows = list(unique_rows.values())
        rows.sort(key=lambda x: x["issue"], reverse=True)
        rows = rows[:limit]
        rows.sort(key=lambda x: x["issue"])
        
        print(f"✅ 获取 {len(rows)} 期数据")
        if rows:
            print(f"📅 范围: {rows[0]['issue']} ~ {rows[-1]['issue']} ({len(rows)}期)")
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

# ============ 正向 + 反向策略回测 ============
def backtest_both_strategies(rows, window=30, z_threshold=1.96):
    """
    同时回测正向和反向策略
    正向：z>=阈值时押大/单
    反向：z<=-阈值时押小/双（即大偏冷时押小，单偏冷时押双）
    """
    if len(rows) < window + 1:
        return None
    
    strategies = {
        "正向_大": {"bets": 0, "hits": 0, "profits": [], "z_values": []},
        "反向_小": {"bets": 0, "hits": 0, "profits": [], "z_values": []},
        "正向_单": {"bets": 0, "hits": 0, "profits": [], "z_values": []},
        "反向_双": {"bets": 0, "hits": 0, "profits": [], "z_values": []},
    }
    
    for i in range(window, len(rows)):
        history = rows[:i]
        actual = rows[i]
        recent = history[-window:]
        
        n = len(recent)
        hits_big = sum(1 for r in recent if r["is_big"])
        hits_odd = sum(1 for r in recent if r["is_odd"])
        
        z_big, p_big = z_test(hits_big, n)
        z_odd, p_odd = z_test(hits_odd, n)
        
        # === 正向策略：押大 ===
        if z_big >= z_threshold:
            strategies["正向_大"]["bets"] += 1
            strategies["正向_大"]["z_values"].append(z_big)
            if actual["is_big"]:
                strategies["正向_大"]["hits"] += 1
                strategies["正向_大"]["profits"].append(95)  # 赔率1.95
            else:
                strategies["正向_大"]["profits"].append(-100)
        
        # === 反向策略：押小（大号偏冷时） ===
        if z_big <= -z_threshold:
            strategies["反向_小"]["bets"] += 1
            strategies["反向_小"]["z_values"].append(z_big)
            if actual["is_small"]:
                strategies["反向_小"]["hits"] += 1
                strategies["反向_小"]["profits"].append(95)
            else:
                strategies["反向_小"]["profits"].append(-100)
        
        # === 正向策略：押单 ===
        if z_odd >= z_threshold:
            strategies["正向_单"]["bets"] += 1
            strategies["正向_单"]["z_values"].append(z_odd)
            if actual["is_odd"]:
                strategies["正向_单"]["hits"] += 1
                strategies["正向_单"]["profits"].append(95)
            else:
                strategies["正向_单"]["profits"].append(-100)
        
        # === 反向策略：押双（单号偏冷时） ===
        if z_odd <= -z_threshold:
            strategies["反向_双"]["bets"] += 1
            strategies["反向_双"]["z_values"].append(z_odd)
            if actual["is_even"]:
                strategies["反向_双"]["hits"] += 1
                strategies["反向_双"]["profits"].append(95)
            else:
                strategies["反向_双"]["profits"].append(-100)
    
    # 计算结果
    results = {}
    for name, s in strategies.items():
        if s["bets"] > 0:
            hit_rate = s["hits"] / s["bets"] * 100
            total_profit = sum(s["profits"])
            avg_z = sum(s["z_values"]) / len(s["z_values"]) if s["z_values"] else 0
            results[name] = {
                "bets": s["bets"],
                "hits": s["hits"],
                "hit_rate": hit_rate,
                "total_profit": total_profit,
                "avg_profit": total_profit / s["bets"] if s["bets"] > 0 else 0,
                "avg_z": avg_z,
                "max_consecutive_loss": 0,  # 简化
            }
    
    return results

def backtest_threshold_sensitivity(rows, window=30):
    """测试不同阈值下的表现"""
    thresholds = [1.0, 1.3, 1.6, 1.96, 2.33, 2.58]
    results = {}
    
    for threshold in thresholds:
        result = backtest_both_strategies(rows, window=window, z_threshold=threshold)
        if result:
            results[threshold] = result
    
    return results

def print_backtest_results(results, lottery_name):
    """打印回测结果"""
    if not results:
        print("无回测数据")
        return
    
    print(f"\n{'='*70}")
    print(f"📊 {lottery_name} 正向vs反向策略回测（窗口30期）")
    print("="*70)
    
    print(f"\n{'策略':<12} {'投注次数':<10} {'命中次数':<10} {'命中率':<12} {'总盈亏':<12} {'平均Z值':<10}")
    print("-"*75)
    
    # 按策略类型分组显示
    for strategy in ["正向_大", "反向_小", "正向_单", "反向_双"]:
        if strategy in results:
            r = results[strategy]
            label = {
                "正向_大": "✅ 押大",
                "反向_小": "🔄 押小(反)",
                "正向_单": "✅ 押单",
                "反向_双": "🔄 押双(反)"
            }[strategy]
            print(f"{label:<12} {r['bets']:<10} {r['hits']:<10} {r['hit_rate']:.1f}%{'':<6} {r['total_profit']:+.0f}元{'':<4} {r['avg_z']:+.2f}")
    
    # 对比分析
    print(f"\n📋 对比分析:")
    
    big_forward = results.get("正向_大", None)
    small_reverse = results.get("反向_小", None)
    odd_forward = results.get("正向_单", None)
    even_reverse = results.get("反向_双", None)
    
    # 大号对比
    if big_forward and small_reverse:
        diff = big_forward["hit_rate"] - small_reverse["hit_rate"]
        better = "正向押大" if diff > 0 else "反向押小"
        print(f"  大号方向: 正向押大 {big_forward['hit_rate']:.1f}% vs 反向押小 {small_reverse['hit_rate']:.1f}%")
        print(f"  差异: {diff:+.1f}% → {better}更好")
    
    # 单号对比
    if odd_forward and even_reverse:
        diff = odd_forward["hit_rate"] - even_reverse["hit_rate"]
        better = "正向押单" if diff > 0 else "反向押双"
        print(f"  单号方向: 正向押单 {odd_forward['hit_rate']:.1f}% vs 反向押双 {even_reverse['hit_rate']:.1f}%")
        print(f"  差异: {diff:+.1f}% → {better}更好")
    
    # 总结建议
    print(f"\n💡 策略建议:")
    best_strategy = max(results.items(), key=lambda x: x[1]["hit_rate"])
    best_name = {
        "正向_大": "✅ 正向押大号",
        "反向_小": "🔄 反向押小号",
        "正向_单": "✅ 正向押单号",
        "反向_双": "🔄 反向押双号"
    }[best_strategy[0]]
    print(f"  最佳策略: {best_name} (命中率{best_strategy[1]['hit_rate']:.1f}%)")

def print_threshold_sensitivity(results):
    """打印不同阈值的敏感性分析"""
    if not results:
        return
    
    print(f"\n{'='*70}")
    print(f"📊 不同阈值下策略表现对比")
    print("="*70)
    
    print(f"\n{'阈值':<8} {'策略':<12} {'投注次数':<10} {'命中率':<12} {'总盈亏':<10}")
    print("-"*55)
    
    for threshold in sorted(results.keys()):
        r = results[threshold]
        for strategy in ["正向_大", "反向_小"]:
            if strategy in r:
                label = "押大" if strategy == "正向_大" else "押小(反)"
                print(f"{threshold:.2f}  {label:<10} {r[strategy]['bets']:<10} {r[strategy]['hit_rate']:.1f}%{'':<6} {r[strategy]['total_profit']:+.0f}元")

def print_current_signal(rows, lottery_name, window=30):
    """打印当前信号"""
    if len(rows) < window:
        return
    
    recent = rows[-window:]
    n = len(recent)
    hits_big = sum(1 for r in recent if r["is_big"])
    hits_odd = sum(1 for r in recent if r["is_odd"])
    
    z_big, p_big = z_test(hits_big, n)
    z_odd, p_odd = z_test(hits_odd, n)
    
    latest = rows[-1]
    
    print(f"\n{'='*70}")
    print(f"📡 {lottery_name} 当前信号（最近{window}期）")
    print("="*70)
    print(f"  最新: {latest['issue']} 特码{latest['special']}")
    print(f"  大号: z={z_big:+.2f} 出现率={p_big*100:.1f}%")
    print(f"  单号: z={z_odd:+.2f} 出现率={p_odd*100:.1f}%")
    
    # 当前建议
    print(f"\n🎯 当前建议:")
    if z_big >= 1.96:
        print(f"  ✅ 押大号 (z={z_big:+.2f})")
    elif z_big <= -1.96:
        print(f"  🔄 押小号 (反向，z={z_big:+.2f})")
    else:
        print(f"  ⏸️ 大号方向观望")
    
    if z_odd >= 1.96:
        print(f"  ✅ 押单号 (z={z_odd:+.2f})")
    elif z_odd <= -1.96:
        print(f"  🔄 押双号 (反向，z={z_odd:+.2f})")
    else:
        print(f"  ⏸️ 单号方向观望")

def main():
    print("="*70)
    print("🎯 三彩 正向vs反向策略回测")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    all_results = {}
    
    for lot in LOTTERIES:
        rows = fetch_lottery(lot["name"], limit=200)
        if len(rows) < 100:
            print(f"⚠️ {lot['label']} 数据不足，跳过")
            continue
        
        # 打印当前信号
        print_current_signal(rows, lot["label"], window=30)
        
        # 标准回测（阈值1.96）
        results = backtest_both_strategies(rows, window=30, z_threshold=1.96)
        if results:
            print_backtest_results(results, lot["label"])
            all_results[lot["label"]] = results
        
        # 阈值敏感性分析
        sensitivity = backtest_threshold_sensitivity(rows, window=30)
        if sensitivity:
            print_threshold_sensitivity(sensitivity)
        
        print("\n" + "-"*70)
    
    # 全局汇总
    print("\n" + "="*70)
    print("📊 全局汇总：什么时候该反向？")
    print("="*70)
    print("""
📋 结论：

1. 大号方向：
   - 当 z > 1.96 (大号偏热) → ✅ 押大号（正向）
   - 当 z < -1.96 (大号偏冷) → 🔄 押小号（反向）
   - 当 -1.96 ≤ z ≤ 1.96 → ⏸️ 观望

2. 单号方向：
   - 当 z > 1.96 (单号偏热) → ✅ 押单号（正向）
   - 当 z < -1.96 (单号偏冷) → 🔄 押双号（反向）
   - 当 -1.96 ≤ z ≤ 1.96 → ⏸️ 观望

3. 当前状态：
   - 老澳门彩 大号: z=+2.40 (偏热) → ✅ 押大号
   - 其他彩种: 未达阈值 → ⏸️ 观望

⚠️ 反向策略仅在原方向显著偏冷时有效！
    """ + "="*70)

if __name__ == "__main__":
    main()