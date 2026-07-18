#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
回测"大"和"单"的出现频率
分别统计1-100期中"大"和"单"的开出次数
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
    """获取彩票历史数据"""
    rows = []
    try:
        print(f"📡 正在获取 {lottery_name} 数据...")
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
    rows.sort(key=lambda x: x["issue"], reverse=True)
    print(f"✅ 获取 {len(rows)} 期数据")
    
    if rows:
        print(f"📅 最新期号: {rows[0]['issue']}")
        print(f"📅 最新特码: {rows[0]['special']} ({rows[0]['halfhalf']})")
        print(f"📅 最早期号: {rows[-1]['issue']}")
    
    return rows[:limit], update_time

def analyze_big_odd(rows, lottery_name, periods=100):
    """分析大和单的出现次数"""
    if len(rows) < periods:
        print(f"⚠️ {lottery_name} 数据不足{periods}期，实际{len(rows)}期")
        periods = len(rows)
    
    # 取最近的periods期
    recent = rows[:periods]
    # 按时间顺序（从旧到新）
    recent_chrono = list(reversed(recent))
    
    # 统计"大"
    big_count = 0
    big_issues = []
    big_numbers = []
    big_consecutive = 0
    big_max_consecutive = 0
    big_gaps = []
    big_last_index = -1
    big_positions = []
    
    # 统计"单"
    odd_count = 0
    odd_issues = []
    odd_numbers = []
    odd_consecutive = 0
    odd_max_consecutive = 0
    odd_gaps = []
    odd_last_index = -1
    odd_positions = []
    
    # 最近10期
    recent_10 = []
    
    for idx, r in enumerate(recent_chrono):
        # 统计"大"
        if r["is_big"]:
            big_count += 1
            big_issues.append(r["issue"])
            big_numbers.append(r["special"])
            big_positions.append(idx + 1)
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
            odd_positions.append(idx + 1)
            odd_consecutive += 1
            odd_max_consecutive = max(odd_max_consecutive, odd_consecutive)
            if odd_last_index != -1:
                odd_gaps.append(idx - odd_last_index)
            odd_last_index = idx
        else:
            odd_consecutive = 0
        
        # 记录最近10期
        if idx < 10:
            recent_10.append({
                "issue": r["issue"],
                "special": r["special"],
                "is_big": r["is_big"],
                "is_odd": r["is_odd"],
                "halfhalf": r["halfhalf"]
            })
    
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
        "big_positions": big_positions,
        "big_issues": big_issues,
        "big_numbers": big_numbers,
        "big_gaps": big_gaps,
        "odd_count": odd_count,
        "odd_rate": odd_rate,
        "odd_max_consecutive": odd_max_consecutive,
        "odd_avg_gap": odd_avg_gap,
        "odd_positions": odd_positions,
        "odd_issues": odd_issues,
        "odd_numbers": odd_numbers,
        "odd_gaps": odd_gaps,
        "recent_10": recent_10,
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
    print(f"📊 {result['lottery']} 大小单双分析")
    print("=" * 70)
    
    print(f"\n📅 数据范围:")
    print(f"  最新期号: {result['latest_issue']}")
    print(f"  最新特码: {result['latest_special']} ({result['latest_halfhalf']})")
    print(f"  最早期号: {result['earliest_issue']}")
    
    # 显示最近10期
    print(f"\n📋 最近10期开奖:")
    print(f"{'期号':<12} {'特码':<6} {'半半波':<12} {'大':<6} {'单':<6}")
    print("-" * 50)
    for r in result['recent_10']:
        big_status = "✅" if r['is_big'] else "❌"
        odd_status = "✅" if r['is_odd'] else "❌"
        print(f"{r['issue']:<12} {r['special']:<6} {r['halfhalf']:<12} {big_status:<6} {odd_status:<6}")
    
    print("\n" + "-" * 70)
    
    # "大"的统计
    print(f"\n📈 【大】统计:")
    print(f"  📅 回测期数: {result['total_periods']}期")
    print(f"  🎯 开出次数: {result['big_count']}次")
    print(f"  📈 开出率: {result['big_rate']:.2f}%")
    print(f"  🔥 最长连续开出: {result['big_max_consecutive']}期")
    print(f"  📊 平均间隔: {result['big_avg_gap']:.1f}期")
    print(f"  📊 理论概率: 50.00%")
    print(f"  📊 偏差: {result['big_rate'] - 50.00:+.2f}%")
    
    # "单"的统计
    print(f"\n📈 【单】统计:")
    print(f"  📅 回测期数: {result['total_periods']}期")
    print(f"  🎯 开出次数: {result['odd_count']}次")
    print(f"  📈 开出率: {result['odd_rate']:.2f}%")
    print(f"  🔥 最长连续开出: {result['odd_max_consecutive']}期")
    print(f"  📊 平均间隔: {result['odd_avg_gap']:.1f}期")
    print(f"  📊 理论概率: 50.00%")
    print(f"  📊 偏差: {result['odd_rate'] - 50.00:+.2f}%")
    
    # 大单组合统计（同时满足大和单）
    both_count = 0
    for i in range(len(result['recent_10'])):
        if result['recent_10'][i]['is_big'] and result['recent_10'][i]['is_odd']:
            both_count += 1
    
    print(f"\n📈 【大+单组合】最近10期统计:")
    print(f"  大单同时出现: {both_count}次")
    print(f"  占比: {both_count/10*100:.0f}%")
    print(f"  理论概率: 25.00%")
    print(f"  偏差: {both_count/10*100 - 25.00:+.2f}%")
    
    # 显示大单出现位置
    if result['big_positions']:
        print(f"\n📍 大出现位置（第几期）:")
        positions_str = []
        for i, pos in enumerate(result['big_positions']):
            positions_str.append(str(pos))
            if (i + 1) % 20 == 0:
                print(f"    {' '.join(positions_str)}")
                positions_str = []
        if positions_str:
            print(f"    {' '.join(positions_str)}")
    
    if result['odd_positions']:
        print(f"\n📍 单出现位置（第几期）:")
        positions_str = []
        for i, pos in enumerate(result['odd_positions']):
            positions_str.append(str(pos))
            if (i + 1) % 20 == 0:
                print(f"    {' '.join(positions_str)}")
                positions_str = []
        if positions_str:
            print(f"    {' '.join(positions_str)}")
    
    print("\n" + "-" * 70)

def print_comparison(results):
    """打印对比结果"""
    if not results:
        return
    
    print("\n" + "=" * 70)
    print("📊 三彩大小单双对比分析")
    print("=" * 70)
    
    print(f"\n{'彩种':<12} {'大次数':<10} {'大开出率':<12} {'大最长连开':<12} {'单次数':<10} {'单开出率':<12} {'单最长连开':<12}")
    print("-" * 85)
    
    total_big = 0
    total_odd = 0
    total_periods = 0
    
    for r in results:
        if r:
            print(f"{r['lottery']:<12} {r['big_count']:<10} {r['big_rate']:.2f}%{'':<6} {r['big_max_consecutive']}期{'':<6} {r['odd_count']:<10} {r['odd_rate']:.2f}%{'':<6} {r['odd_max_consecutive']}期")
            total_big += r['big_count']
            total_odd += r['odd_count']
            total_periods += r['total_periods']
    
    print("-" * 85)
    
    if total_periods > 0:
        big_overall = total_big / total_periods * 100
        odd_overall = total_odd / total_periods * 100
        
        print(f"\n📊 三彩合计:")
        print(f"  总期数: {total_periods}期")
        print(f"  大总次数: {total_big}次, 综合开出率: {big_overall:.2f}% (理论50.00%, 偏差{big_overall - 50.00:+.2f}%)")
        print(f"  单总次数: {total_odd}次, 综合开出率: {odd_overall:.2f}% (理论50.00%, 偏差{odd_overall - 50.00:+.2f}%)")
        
        print(f"\n📅 最新一期汇总:")
        for r in results:
            big_status = "✅ 大" if r['recent_10'][0]['is_big'] else "❌ 小"
            odd_status = "✅ 单" if r['recent_10'][0]['is_odd'] else "❌ 双"
            print(f"  {r['lottery']}: {r['latest_issue']} 特码{r['latest_special']} {big_status} {odd_status}")

def main():
    print("=" * 70)
    print("🎯 大小单双出现频率回测")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    results = []
    
    # 获取三个彩种的数据并分析
    for lottery_name in ["香港彩", "新澳门彩", "老澳门彩"]:
        rows, update_time = fetch_lottery_data(lottery_name, limit=100)
        if rows:
            result = analyze_big_odd(rows, lottery_name, periods=100)
            if result:
                result['update_time'] = update_time
                print_analysis(result)
                results.append(result)
    
    # 打印对比
    if results:
        print_comparison(results)
        
        # 总结
        print("\n" + "=" * 70)
        print("📋 结论")
        print("=" * 70)
        
        total_big = sum(r['big_count'] for r in results)
        total_odd = sum(r['odd_count'] for r in results)
        total_periods = sum(r['total_periods'] for r in results)
        big_rate = total_big / total_periods * 100 if total_periods > 0 else 0
        odd_rate = total_odd / total_periods * 100 if total_periods > 0 else 0
        
        print(f"""
三彩综合统计:
  总回测期数: {total_periods}期
  
  【大】
  总次数: {total_big}次
  综合开出率: {big_rate:.2f}%
  理论概率: 50.00%
  结论: {'✅ 大的出现频率高于理论值' if big_rate > 50 else '⚠️ 大的出现频率低于理论值'}
  
  【单】
  总次数: {total_odd}次
  综合开出率: {odd_rate:.2f}%
  理论概率: 50.00%
  结论: {'✅ 单的出现频率高于理论值' if odd_rate > 50 else '⚠️ 单的出现频率低于理论值'}

建议:
  {'📌 近期大号偏热，可关注大号' if big_rate > 50 else '📌 近期小号偏热，可关注小号'}
  {'📌 近期单号偏热，可关注单号' if odd_rate > 50 else '📌 近期双号偏热，可关注双号'}
""")

if __name__ == "__main__":
    main()