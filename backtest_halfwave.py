#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
回测"大"和"单"的出现频率
统计最近100期中"大"和"单"的开出次数
"""

import re
import json
import urllib.request
from collections import defaultdict
from datetime import datetime

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

def fetch_lottery_data(lottery_name, limit=100):
    """获取彩票历史数据（最近100期）"""
    rows = []
    try:
        print(f"📡 正在获取 {lottery_name} 最近{limit}期数据...")
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
            return [], None

        update_time = target.get("update_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
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
                "halfhalf": get_halfhalf(special),
                "is_big": special >= 25,  # 大
                "is_small": special < 25,  # 小
                "is_odd": special % 2 == 1,  # 单
                "is_even": special % 2 == 0,  # 双
            })

    except Exception as e:
        print(f"❌ 获取失败: {e}")
        return [], None

    # 去重（按期号）
    cache = {}
    for r in rows:
        cache[r["issue"]] = r
    rows = list(cache.values())
    
    # 按期号排序（从新到旧）
    rows.sort(key=lambda x: x["issue"], reverse=True)
    
    # 只取最近limit期
    rows = rows[:limit]
    
    print(f"✅ 获取 {len(rows)} 期数据（最近{limit}期）")
    
    if rows:
        print(f"📅 最新期号: {rows[0]['issue']}")
        print(f"📅 最新特码: {rows[0]['special']} ({rows[0]['halfhalf']})")
        print(f"📅 最早期号: {rows[-1]['issue']}")
        print(f"📅 数据范围: {rows[-1]['issue']} ~ {rows[0]['issue']} (共{len(rows)}期)")
    
    return rows, update_time

def analyze_big_odd(rows, lottery_name):
    """分析最近100期大和单的出现次数"""
    periods = len(rows)
    
    if periods < 100:
        print(f"⚠️ {lottery_name} 数据不足100期，实际{periods}期")
    
    # rows已经是按从新到旧排序，取前10期作为最近10期
    recent_10 = rows[:10]  # 最近10期（从新到旧）
    
    # 统计"大"和"单" - 使用全部periods期
    big_count = 0
    big_issues = []
    big_numbers = []
    big_consecutive = 0
    big_max_consecutive = 0
    big_gaps = []
    big_last_index = -1
    
    odd_count = 0
    odd_issues = []
    odd_numbers = []
    odd_consecutive = 0
    odd_max_consecutive = 0
    odd_gaps = []
    odd_last_index = -1
    
    # 从旧到新遍历（用于计算间隔）
    rows_old_to_new = list(reversed(rows))
    
    for idx, r in enumerate(rows_old_to_new):
        # 统计"大"
        if r["is_big"]:
            big_count += 1
            big_issues.append(r["issue"])
            big_numbers.append(r["special"])
            big_consecutive += 1
            big_max_consecutive = max(big_max_consecutive, big_consecutive)
            if big_last_index != -1:
                big_gaps.append(idx - big_last_index)
            big_last_index = idx
        else:
            big_consecutive = 0
        
        # 统计"单"
        if r["is_odd"]:
            odd_count += 1
            odd_issues.append(r["issue"])
            odd_numbers.append(r["special"])
            odd_consecutive += 1
            odd_max_consecutive = max(odd_max_consecutive, odd_consecutive)
            if odd_last_index != -1:
                odd_gaps.append(idx - odd_last_index)
            odd_last_index = idx
        else:
            odd_consecutive = 0
    
    # 计算命中率
    big_rate = big_count / periods * 100 if periods > 0 else 0
    odd_rate = odd_count / periods * 100 if periods > 0 else 0
    
    # 计算平均间隔
    big_avg_gap = sum(big_gaps) / len(big_gaps) if big_gaps else 0
    odd_avg_gap = sum(odd_gaps) / len(odd_gaps) if odd_gaps else 0
    
    return {
        "lottery": lottery_name,
        "total_periods": periods,
        "big_count": big_count,
        "big_rate": big_rate,
        "big_max_consecutive": big_max_consecutive,
        "big_avg_gap": big_avg_gap,
        "big_issues": big_issues,
        "big_numbers": big_numbers,
        "big_gaps": big_gaps,
        "odd_count": odd_count,
        "odd_rate": odd_rate,
        "odd_max_consecutive": odd_max_consecutive,
        "odd_avg_gap": odd_avg_gap,
        "odd_issues": odd_issues,
        "odd_numbers": odd_numbers,
        "odd_gaps": odd_gaps,
        "recent_10": recent_10,  # 最近10期（从新到旧）
        "latest_issue": rows[0]["issue"] if rows else "N/A",
        "latest_special": rows[0]["special"] if rows else "N/A",
        "latest_halfhalf": rows[0]["halfhalf"] if rows else "N/A",
        "earliest_issue": rows[-1]["issue"] if rows else "N/A",
    }

def print_analysis(result):
    """打印分析结果"""
    if not result:
        return
    
    print("\n" + "=" * 70)
    print(f"📊 {result['lottery']} 最近{result['total_periods']}期大小单双分析")
    print("=" * 70)
    
    print(f"\n📅 数据范围:")
    print(f"  最新期号: {result['latest_issue']}")
    print(f"  最新特码: {result['latest_special']} ({result['latest_halfhalf']})")
    print(f"  最早期号: {result['earliest_issue']}")
    print(f"  总期数: {result['total_periods']}期（最近100期）")
    
    # 显示最近10期（从新到旧）
    print(f"\n📋 最近10期开奖明细（从新到旧）:")
    print(f"{'期号':<12} {'特码':<6} {'半半波':<12} {'是否大':<8} {'是否单':<8}")
    print("-" * 55)
    for r in result['recent_10']:
        big_status = "✅ 大" if r['is_big'] else "❌ 小"
        odd_status = "✅ 单" if r['is_odd'] else "❌ 双"
        print(f"{r['issue']:<12} {r['special']:<6} {r['halfhalf']:<12} {big_status:<8} {odd_status:<8}")
    
    print("\n" + "-" * 70)
    
    # "大"的统计
    print(f"\n📈 【大号】统计 (号码≥25):")
    print(f"  📅 回测期数: {result['total_periods']}期（最近100期）")
    print(f"  🎯 开出次数: {result['big_count']}次")
    print(f"  📈 开出率: {result['big_rate']:.2f}%")
    print(f"  🔥 最长连续开出: {result['big_max_consecutive']}期")
    print(f"  📊 平均间隔: {result['big_avg_gap']:.1f}期")
    print(f"  📊 理论概率: 50.00%")
    if result['big_rate'] > 51:
        print(f"  📊 偏差: {result['big_rate'] - 50.00:+.2f}% ✅ 大号偏热")
    elif result['big_rate'] < 49:
        print(f"  📊 偏差: {result['big_rate'] - 50.00:+.2f}% ⚠️ 小号偏热")
    else:
        print(f"  📊 偏差: {result['big_rate'] - 50.00:+.2f}% ⚖️ 大小平衡")
    
    # "单"的统计
    print(f"\n📈 【单号】统计 (奇数码):")
    print(f"  📅 回测期数: {result['total_periods']}期（最近100期）")
    print(f"  🎯 开出次数: {result['odd_count']}次")
    print(f"  📈 开出率: {result['odd_rate']:.2f}%")
    print(f"  🔥 最长连续开出: {result['odd_max_consecutive']}期")
    print(f"  📊 平均间隔: {result['odd_avg_gap']:.1f}期")
    print(f"  📊 理论概率: 50.00%")
    if result['odd_rate'] > 51:
        print(f"  📊 偏差: {result['odd_rate'] - 50.00:+.2f}% ✅ 单号偏热")
    elif result['odd_rate'] < 49:
        print(f"  📊 偏差: {result['odd_rate'] - 50.00:+.2f}% ⚠️ 双号偏热")
    else:
        print(f"  📊 偏差: {result['odd_rate'] - 50.00:+.2f}% ⚖️ 单双平衡")
    
    # 大单组合统计（最近10期）
    both_count = 0
    both_issues = []
    for r in result['recent_10']:
        if r['is_big'] and r['is_odd']:
            both_count += 1
            both_issues.append(r['issue'])
    
    print(f"\n📈 【大+单组合】最近10期统计:")
    print(f"  大单同时出现: {both_count}次")
    print(f"  占比: {both_count/10*100:.0f}%")
    print(f"  理论概率: 25.00%")
    print(f"  偏差: {both_count/10*100 - 25.00:+.2f}%")
    if both_count > 0:
        print(f"  出现期号: {' '.join(both_issues)}")
    
    print("\n" + "-" * 70)

def print_comparison(results):
    """打印对比结果"""
    if not results:
        return
    
    print("\n" + "=" * 70)
    print("📊 三彩最近100期大小单双对比分析")
    print("=" * 70)
    
    print(f"\n{'彩种':<12} {'大次数':<10} {'大开出率':<12} {'大最长连开':<12} {'单次数':<10} {'单开出率':<12} {'单最长连开':<12}")
    print("-" * 90)
    
    total_big = 0
    total_odd = 0
    total_periods = 0
    
    for r in results:
        if r:
            print(f"{r['lottery']:<12} {r['big_count']:<10} {r['big_rate']:.2f}%{'':<6} {r['big_max_consecutive']}期{'':<6} {r['odd_count']:<10} {r['odd_rate']:.2f}%{'':<6} {r['odd_max_consecutive']}期")
            total_big += r['big_count']
            total_odd += r['odd_count']
            total_periods += r['total_periods']
    
    print("-" * 90)
    
    if total_periods > 0:
        big_overall = total_big / total_periods * 100
        odd_overall = total_odd / total_periods * 100
        
        print(f"\n📊 三彩合计（最近{total_periods}期）:")
        print(f"  【大】总次数: {total_big}次, 综合开出率: {big_overall:.2f}% (理论50.00%, 偏差{big_overall - 50.00:+.2f}%)")
        print(f"  【单】总次数: {total_odd}次, 综合开出率: {odd_overall:.2f}% (理论50.00%, 偏差{odd_overall - 50.00:+.2f}%)")
        
        print(f"\n📅 最新一期汇总:")
        for r in results:
            big_status = "✅ 大" if r['recent_10'][0]['is_big'] else "❌ 小"
            odd_status = "✅ 单" if r['recent_10'][0]['is_odd'] else "❌ 双"
            print(f"  {r['lottery']}: {r['latest_issue']} 特码{r['latest_special']} {big_status} {odd_status}")

def main():
    print("=" * 70)
    print("🎯 最近100期大小单双出现频率回测")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    results = []
    
    # 获取三个彩种的最近100期数据并分析
    for lottery_name in ["香港彩", "新澳门彩", "老澳门彩"]:
        rows, update_time = fetch_lottery_data(lottery_name, limit=100)
        if rows:
            result = analyze_big_odd(rows, lottery_name)
            if result:
                result['update_time'] = update_time
                print_analysis(result)
                results.append(result)
    
    # 打印对比
    if results:
        print_comparison(results)
        
        # 总结
        print("\n" + "=" * 70)
        print("📋 最近100期结论")
        print("=" * 70)
        
        total_big = sum(r['big_count'] for r in results)
        total_odd = sum(r['odd_count'] for r in results)
        total_periods = sum(r['total_periods'] for r in results)
        big_rate = total_big / total_periods * 100 if total_periods > 0 else 0
        odd_rate = total_odd / total_periods * 100 if total_periods > 0 else 0
        
        print(f"""
三彩最近100期综合统计:
  总回测期数: {total_periods}期
  
  【大号】(≥25)
  总次数: {total_big}次
  综合开出率: {big_rate:.2f}%
  理论概率: 50.00%
  偏差: {big_rate - 50.00:+.2f}%
  结论: {'✅ 大号偏热，近期大号出现频率较高' if big_rate > 51 else '⚠️ 小号偏热，近期小号出现频率较高' if big_rate < 49 else '⚖️ 大小基本平衡'}
  
  【单号】(奇数)
  总次数: {total_odd}次
  综合开出率: {odd_rate:.2f}%
  理论概率: 50.00%
  偏差: {odd_rate - 50.00:+.2f}%
  结论: {'✅ 单号偏热，近期单号出现频率较高' if odd_rate > 51 else '⚠️ 双号偏热，近期双号出现频率较高' if odd_rate < 49 else '⚖️ 单双基本平衡'}

策略建议（基于最近100期数据）:
  {'📌 可关注大号投注' if big_rate > 51 else '📌 可关注小号投注' if big_rate < 49 else '📌 大小号均衡投注'}
  {'📌 可关注单号投注' if odd_rate > 51 else '📌 可关注双号投注' if odd_rate < 49 else '📌 单双号均衡投注'}
""")

if __name__ == "__main__":
    main()