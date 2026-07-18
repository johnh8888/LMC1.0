#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
回测大单（绿大单）出现频率
统计1-100期中大单（绿大单）的开出次数
显示最新期数和数据更新时间
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

# 绿大单号码
BIG_ODD_GREEN = [27, 33, 39, 43, 49]

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

        # 获取数据更新时间
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
                "is_big_odd_green": special in BIG_ODD_GREEN,
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
    
    # 显示最新几期
    if rows:
        print(f"📅 最新期号: {rows[0]['issue']}")
        print(f"📅 最新特码: {rows[0]['special']} ({rows[0]['halfhalf']})")
        if rows[0]['is_big_odd_green']:
            print(f"🎯 最新一期是大单！")
        else:
            print(f"❌ 最新一期不是大单")
        print(f"📅 最早期号: {rows[-1]['issue']}")
    
    return rows[:limit], update_time

def analyze_big_odd_green(rows, lottery_name, periods=100):
    """分析大单出现次数"""
    if len(rows) < periods:
        print(f"⚠️ {lottery_name} 数据不足{periods}期，实际{len(rows)}期")
        periods = len(rows)
    
    # 取最近的periods期
    recent = rows[:periods]
    # 按时间顺序（从旧到新）
    recent_chrono = list(reversed(recent))
    
    total_big_odd_green = 0
    big_odd_green_issues = []
    big_odd_green_numbers = []
    consecutive_count = 0
    max_consecutive = 0
    gap_since_last = 0
    gaps = []
    last_index = -1
    positions = []
    
    # 最近10期大单情况
    recent_10_big = []
    
    for idx, r in enumerate(recent_chrono):
        if r["is_big_odd_green"]:
            total_big_odd_green += 1
            big_odd_green_issues.append(r["issue"])
            big_odd_green_numbers.append(r["special"])
            positions.append(idx + 1)
            consecutive_count += 1
            max_consecutive = max(max_consecutive, consecutive_count)
            
            # 计算间隔
            if last_index != -1:
                gaps.append(idx - last_index)
            last_index = idx
        else:
            consecutive_count = 0
        
        # 记录最近10期
        if idx < 10:
            recent_10_big.append({
                "issue": r["issue"],
                "special": r["special"],
                "is_big": r["is_big_odd_green"]
            })
    
    # 计算命中率
    hit_rate = total_big_odd_green / periods * 100 if periods > 0 else 0
    
    # 计算平均间隔
    avg_gap = sum(gaps) / len(gaps) if gaps else 0
    
    return {
        "lottery": lottery_name,
        "total_periods": periods,
        "hit_count": total_big_odd_green,
        "hit_rate": hit_rate,
        "max_consecutive": max_consecutive,
        "avg_gap": avg_gap,
        "positions": positions,
        "big_odd_green_issues": big_odd_green_issues,
        "big_odd_green_numbers": big_odd_green_numbers,
        "gaps": gaps,
        "recent_data": recent_chrono,
        "recent_10_big": recent_10_big,
        "latest_issue": rows[0]["issue"] if rows else "N/A",
        "latest_special": rows[0]["special"] if rows else "N/A",
        "latest_halfhalf": rows[0]["halfhalf"] if rows else "N/A",
        "earliest_issue": rows[-1]["issue"] if rows else "N/A",
    }

def print_analysis(result, show_detail=True):
    """打印分析结果"""
    if not result:
        return
    
    print("\n" + "=" * 70)
    print(f"📊 {result['lottery']} 大单（绿大单）分析")
    print("=" * 70)
    
    print(f"\n📅 数据范围:")
    print(f"  最新期号: {result['latest_issue']}")
    print(f"  最新特码: {result['latest_special']} ({result['latest_halfhalf']})")
    print(f"  最早期号: {result['earliest_issue']}")
    
    # 显示最近10期
    print(f"\n📋 最近10期开奖:")
    print(f"{'期号':<12} {'特码':<6} {'半半波':<12} {'是否大单':<10}")
    print("-" * 45)
    for r in result['recent_10_big']:
        status = "✅ 是" if r['is_big'] else "❌ 否"
        print(f"{r['issue']:<12} {r['special']:<6} {get_halfhalf(r['special']):<12} {status:<10}")
    
    print("\n" + "-" * 70)
    
    print(f"\n📈 基本统计:")
    print(f"  📅 回测期数: {result['total_periods']}期")
    print(f"  🎯 大单开出次数: {result['hit_count']}次")
    print(f"  📈 大单开出率: {result['hit_rate']:.2f}%")
    print(f"  🔥 最长连续开出: {result['max_consecutive']}期")
    print(f"  📊 平均间隔: {result['avg_gap']:.1f}期")
    
    if result['positions']:
        print(f"\n📍 大单开出位置（第几期）:")
        # 分组显示，每10个一组
        positions_str = []
        for i, pos in enumerate(result['positions']):
            positions_str.append(str(pos))
            if (i + 1) % 10 == 0:
                print(f"    {' '.join(positions_str)}")
                positions_str = []
        if positions_str:
            print(f"    {' '.join(positions_str)}")
    
    if result['gaps']:
        print(f"\n📏 间隔分布（期数）:")
        gap_counts = defaultdict(int)
        for g in result['gaps']:
            gap_counts[g] += 1
        
        # 显示主要间隔
        for gap in sorted(gap_counts.keys()):
            count = gap_counts[gap]
            bar = "█" * min(count, 20)
            print(f"  间隔 {gap}期: {count}次 {bar}")
    
    if show_detail and result['big_odd_green_issues']:
        print(f"\n🎯 大单开出期号及号码:")
        issues = result['big_odd_green_issues']
        numbers = result['big_odd_green_numbers']
        # 每行显示5个
        for i in range(0, len(issues), 5):
            issue_str = ' '.join(issues[i:i+5])
            num_str = ' '.join(str(n) for n in numbers[i:i+5])
            print(f"  期号: {issue_str}")
            print(f"  号码: {num_str}")
            print()
    
    print("\n" + "-" * 70)

def print_comparison(results):
    """打印对比结果"""
    if not results:
        return
    
    print("\n" + "=" * 70)
    print("📊 三彩大单对比分析")
    print("=" * 70)
    
    print(f"\n{'彩种':<12} {'回测期数':<10} {'大单次数':<10} {'开出率':<12} {'最长连开':<12} {'平均间隔':<12} {'最新期号':<12}")
    print("-" * 85)
    
    total_hits = 0
    total_periods = 0
    
    for r in results:
        if r:
            print(f"{r['lottery']:<12} {r['total_periods']:<10} {r['hit_count']:<10} {r['hit_rate']:.2f}%{'':<6} {r['max_consecutive']}期{'':<6} {r['avg_gap']:.1f}期{'':<4} {r['latest_issue']:<12}")
            total_hits += r['hit_count']
            total_periods += r['total_periods']
    
    print("-" * 85)
    
    if total_periods > 0:
        overall_rate = total_hits / total_periods * 100
        print(f"\n📊 三彩合计:")
        print(f"  总期数: {total_periods}期")
        print(f"  大单总次数: {total_hits}次")
        print(f"  综合开出率: {overall_rate:.2f}%")
        print(f"  理论概率: {len(BIG_ODD_GREEN)/49 * 100:.2f}%")
        print(f"  偏差: {overall_rate - len(BIG_ODD_GREEN)/49 * 100:+.2f}%")
        
        # 显示最新一期情况
        print(f"\n📅 最新数据汇总:")
        for r in results:
            status = "✅ 是大单" if r['recent_10_big'][0]['is_big'] else "❌ 不是大单"
            print(f"  {r['lottery']}: {r['latest_issue']} 特码{r['latest_special']} {status}")

def main():
    print("=" * 70)
    print("🎯 大单（绿大单）出现频率回测")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    results = []
    
    # 获取三个彩种的数据并分析
    for lottery_name in ["香港彩", "新澳门彩", "老澳门彩"]:
        rows, update_time = fetch_lottery_data(lottery_name, limit=100)
        if rows:
            result = analyze_big_odd_green(rows, lottery_name, periods=100)
            if result:
                result['update_time'] = update_time
                print_analysis(result, show_detail=True)
                results.append(result)
    
    # 打印对比
    if results:
        print_comparison(results)
        
        # 总结
        print("\n" + "=" * 70)
        print("📋 结论")
        print("=" * 70)
        
        total_rate = sum(r['hit_rate'] for r in results) / len(results)
        total_hits = sum(r['hit_count'] for r in results)
        total_periods = sum(r['total_periods'] for r in results)
        overall_rate = total_hits / total_periods * 100 if total_periods > 0 else 0
        
        print(f"""
大单（绿大单）号码: {BIG_ODD_GREEN}
理论开出概率: {len(BIG_ODD_GREEN)/49 * 100:.2f}%

三彩综合统计:
  总回测期数: {total_periods}期
  大单总次数: {total_hits}次
  平均开出率: {total_rate:.2f}%
  综合开出率: {overall_rate:.2f}%

结论:
  {'✅ 实际开出率高于理论值，大单出现频率较高' if overall_rate > len(BIG_ODD_GREEN)/49 * 100 else '⚠️ 实际开出率低于理论值，大单出现频率较低'}
  
  如果每期投注大单:
  预期每{100/total_rate:.0f}期出现{1:.0f}次
  平均间隔约{100/total_rate:.1f}期
""")

if __name__ == "__main__":
    main()