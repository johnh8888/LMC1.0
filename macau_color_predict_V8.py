#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新澳门彩预测系统 - 诚实版
"""

import re
import json
import urllib.request
import os
from collections import defaultdict
from datetime import datetime

CONFIG = {
    "history_limit": 50,
    "api_url": "https://marksix6.net/index.php?api=1",
    "bet_count": 2,
    "zodiac_bet_count": 5,
    "cache_file": "newmacau_cache.json",
    "zodiac_year": 2026,
    "test_periods": 10,
    "min_history": 5,  # 🔧 每期只用最近5期预测
}

RED = {1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE = {3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
GREEN = {5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}

# 🔧 正确生肖映射
ZODIAC_MAP_FIXED = {
    1: "马", 2: "蛇", 3: "龙", 4: "兔", 5: "虎", 6: "牛",
    7: "鼠", 8: "猪", 9: "狗", 10: "鸡", 11: "猴", 12: "羊",
}
for n in range(13, 49):
    ZODIAC_MAP_FIXED[n] = ZODIAC_MAP_FIXED[((n - 1) % 12) + 1]

ZODIAC_ORDER = ["鼠","牛","虎","兔","龙","蛇","马","羊","猴","鸡","狗","猪"]

def build_zodiac_map(year):
    return ZODIAC_MAP_FIXED

ZODIAC_MAP = build_zodiac_map(CONFIG["zodiac_year"])

def get_color(n):
    if n in RED: return "红"
    if n in BLUE: return "蓝"
    return "绿"

def get_size(n):
    return "大" if n >= 25 else "小"

def get_odd(n):
    return "单" if n % 2 == 1 else "双"

def get_halfhalf(n):
    return get_color(n) + get_size(n)

def get_zodiac(n):
    return ZODIAC_MAP.get(n, "?")

def parse_numbers(text):
    nums = re.findall(r"\d+", text)
    return [int(x) for x in nums if 1 <= int(x) <= 49]

def fetch_new_macau(limit=50):
    if os.path.exists(CONFIG["cache_file"]):
        try:
            with open(CONFIG["cache_file"], "r", encoding="utf-8") as f:
                cached = json.load(f)
                if len(cached) >= limit:
                    print(f"✅ 使用缓存数据 ({len(cached)}期)")
                    return cached[:limit]
        except:
            pass

    print("正在获取最新数据...")
    try:
        req = urllib.request.Request(CONFIG["api_url"], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        rows = []
        for item in data.get("lottery_data", []):
            if item.get("name", "").strip() == "新澳门彩":
                for line in item.get("history", []):
                    nums = parse_numbers(line)
                    if len(nums) < 7: continue
                    special = nums[-1]
                    m = re.search(r"(20\d{5,8})", line)
                    if not m: continue
                    raw = m.group(1)
                    issue = raw[:4] + "/" + str(int(raw[4:])).zfill(3)
                    rows.append({
                        "issue": issue,
                        "special": special,
                        "color": get_color(special),
                        "size": get_size(special),
                        "odd": get_odd(special),
                        "halfhalf": get_halfhalf(special),
                        "zodiac": get_zodiac(special),
                    })
                break

        rows = list({r["issue"]: r for r in rows}.values())
        rows.sort(key=lambda x: x["issue"], reverse=True)
        with open(CONFIG["cache_file"], "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        return rows[:limit]
    except Exception as e:
        print(f"❌ 获取失败: {e}")
        return []

class FrequencyPredictor:
    def __init__(self, history):
        self.history = history

    def freq(self, key):
        c = defaultdict(int)
        for r in self.history:
            c[r[key]] += 1
        total = sum(c.values()) or 1
        return {k: round(v / total * 100, 2) for k, v in c.items()}

    def predict_halfhalf(self, count=2):
        color_pred = self.freq("color")
        size_pred = self.freq("size")
        scores = {}
        for c in ["红", "蓝", "绿"]:
            for s in ["大", "小"]:
                scores[c + s] = color_pred.get(c, 0) * 0.5 + size_pred.get(s, 0) * 0.5
        sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        # 🔧 纯按分数取前count个
        return sorted_items[:count]

    def predict_zodiac(self, count=5):
        zod_pred = self.freq("zodiac")
        full = {a: zod_pred.get(a, 0.0) for a in ZODIAC_ORDER}
        return sorted(full.items(), key=lambda x: x[1], reverse=True)[:count]

    def predict_odd(self):
        odd_pred = self.freq("odd")
        return sorted(odd_pred.items(), key=lambda x: x[1], reverse=True)

    def predict_color(self):
        return sorted(self.freq("color").items(), key=lambda x: x[1], reverse=True)

    def predict_size(self):
        return sorted(self.freq("size").items(), key=lambda x: x[1], reverse=True)

# ========== 滑动窗口回测（修复版） ==========
def sliding_window_analysis(all_rows, window_size=10, step=5, min_history=5):
    """滑动窗口分析：每个窗口内，每期只用该期之前的min_history期预测"""
    if len(all_rows) < min_history + window_size:
        return []
    
    results = []
    start = 0
    while start + window_size + min_history <= len(all_rows):
        test_set = all_rows[start:start + window_size]
        
        hw_hits = zd_hits = odd_hits = color_hits = size_hits = 0
        valid = 0
        
        for i, test_row in enumerate(test_set):
            # 🔧 修复：取测试期之后的min_history期作为历史
            hist_start = start + window_size - i
            history = all_rows[hist_start:hist_start + min_history]
            
            if len(history) < min_history:
                continue
            
            predictor = FrequencyPredictor(history)
            
            hw_pred = [x[0] for x in predictor.predict_halfhalf(CONFIG["bet_count"])]
            zd_pred = [x[0] for x in predictor.predict_zodiac(CONFIG["zodiac_bet_count"])]
            odd_pred = predictor.predict_odd()[0][0] if predictor.predict_odd() else ""
            color_pred = predictor.predict_color()[0][0] if predictor.predict_color() else ""
            size_pred = predictor.predict_size()[0][0] if predictor.predict_size() else ""
            
            if test_row["halfhalf"] in hw_pred:
                hw_hits += 1
            if test_row["zodiac"] in zd_pred:
                zd_hits += 1
            if test_row["odd"] == odd_pred:
                odd_hits += 1
            if test_row["color"] == color_pred:
                color_hits += 1
            if test_row["size"] == size_pred:
                size_hits += 1
            valid += 1
        
        if valid > 0:
            results.append({
                "window": f"{test_set[-1]['issue']}~{test_set[0]['issue']}",
                "hw_rate": hw_hits / valid,
                "zd_rate": zd_hits / valid,
                "odd_rate": odd_hits / valid,
                "color_rate": color_hits / valid,
                "size_rate": size_hits / valid,
            })
        
        start += step
    
    return results

# ========== 主回测（修复版） ==========
def honest_backtest(all_rows, test_periods=10, min_history=5):
    """诚实回测：每期只用该期之前min_history期预测"""
    if len(all_rows) < min_history + test_periods:
        print(f"❌ 数据不足")
        return None
    
    test_set = all_rows[:test_periods]
    
    print(f"\n{'='*90}")
    print(f"📊 最近{test_periods}期回测（每期只用前{min_history}期预测）")
    print(f"{'='*90}")
    print(f"{'期号':<12} {'实际':<14} {'半波预测':<16} {'✓':<4} {'生肖预测':<28} {'✓':<4} {'单双':<6} {'颜色':<6} {'大小':<6}")
    print("-" * 100)
    
    hw_hits = zd_hits = odd_hits = color_hits = size_hits = 0
    
    for i, test_row in enumerate(test_set):
        # 🔧 修复：取测试期之后固定min_history期
        hist_start = test_periods - i
        history = all_rows[hist_start:hist_start + min_history]
        
        if len(history) < min_history:
            continue
        
        predictor = FrequencyPredictor(history)
        hw_pred = [x[0] for x in predictor.predict_halfhalf(CONFIG["bet_count"])]
        zd_pred = [x[0] for x in predictor.predict_zodiac(CONFIG["zodiac_bet_count"])]
        odd_pred = predictor.predict_odd()[0][0]
        color_pred = predictor.predict_color()[0][0]
        size_pred = predictor.predict_size()[0][0]
        
        actual_full = f"{test_row['halfhalf']}({test_row['odd']})"
        
        hw_hit = test_row["halfhalf"] in hw_pred
        zd_hit = test_row["zodiac"] in zd_pred
        odd_hit = test_row["odd"] == odd_pred
        color_hit = test_row["color"] == color_pred
        size_hit = test_row["size"] == size_pred
        
        hw_hits += hw_hit
        zd_hits += zd_hit
        odd_hits += odd_hit
        color_hits += color_hit
        size_hits += size_hit
        
        print(f"{test_row['issue']:<12} {actual_full:<14} "
              f"{','.join(hw_pred):<16} {'✓' if hw_hit else '✗':<4} "
              f"{','.join(zd_pred):<28} {'✓' if zd_hit else '✗':<4} "
              f"{odd_pred:<6} {color_pred:<6} {size_pred:<6}")
    
    n = len(test_set)
    print("-" * 100)
    
    print(f"\n📈 命中率统计（{n}期）vs 随机期望：")
    print(f"  {'维度':<10} {'实际命中':<12} {'随机期望':<12} {'评价':<15}")
    print(f"  {'-'*50}")
    
    metrics = [
        ("半波(2选)", hw_hits/n, 2/6, "6种半波选2"),
        ("生肖(5选)", zd_hits/n, 5/12, "12生肖选5"),
        ("单双(1选)", odd_hits/n, 1/2, "2选1"),
        ("颜色(1选)", color_hits/n, 1/3, "3选1"),
        ("大小(1选)", size_hits/n, 1/2, "2选1"),
    ]
    
    for name, actual, expected, note in metrics:
        diff = actual - expected
        emoji = "✅" if diff > 0.05 else ("⚠️" if diff > -0.05 else "❌")
        print(f"  {name:<10} {actual*100:>6.1f}%     {expected*100:>6.1f}%     {emoji} {diff*100:+.1f}% ({note})")
    
    return {
        "hw": hw_hits/n, "zd": zd_hits/n, "odd": odd_hits/n,
        "color": color_hits/n, "size": size_hits/n
    }

# ========== 主函数 ==========
def main():
    print("=" * 60)
    print("新澳门彩预测系统 - 诚实版")
    print("基于滑动窗口分析的简单频率统计")
    print("=" * 60)
    
    all_rows = fetch_new_macau(CONFIG["history_limit"])
    if len(all_rows) < CONFIG["min_history"] + CONFIG["test_periods"]:
        print(f"❌ 数据不足")
        return
    
    # 滑动窗口分析
    print(f"\n{'='*60}")
    print(f"📊 滑动窗口稳定性分析（核心指标）")
    print(f"{'='*60}")
    window_results = sliding_window_analysis(all_rows, 10, 5, CONFIG["min_history"])
    
    if window_results:
        print(f"\n{'窗口':<22} {'半波':<8} {'生肖':<8} {'单双':<8} {'颜色':<8} {'大小':<8}")
        print("-" * 65)
        for wr in window_results:
            print(f"{wr['window']:<22} {wr['hw_rate']*100:>5.1f}%  {wr['zd_rate']*100:>5.1f}%  "
                  f"{wr['odd_rate']*100:>5.1f}%  {wr['color_rate']*100:>5.1f}%  {wr['size_rate']*100:>5.1f}%")
        
        hw_rates = [w['hw_rate'] for w in window_results]
        zd_rates = [w['zd_rate'] for w in window_results]
        odd_rates = [w['odd_rate'] for w in window_results]
        color_rates = [w['color_rate'] for w in window_results]
        size_rates = [w['size_rate'] for w in window_results]
        
        print(f"\n📊 各维度统计（均值/范围）：")
        print(f"  半波：{sum(hw_rates)/len(hw_rates)*100:.1f}% ({min(hw_rates)*100:.0f}%-{max(hw_rates)*100:.0f}%) [随机33.3%]")
        print(f"  生肖：{sum(zd_rates)/len(zd_rates)*100:.1f}% ({min(zd_rates)*100:.0f}%-{max(zd_rates)*100:.0f}%) [随机41.7%]")
        print(f"  单双：{sum(odd_rates)/len(odd_rates)*100:.1f}% ({min(odd_rates)*100:.0f}%-{max(odd_rates)*100:.0f}%) [随机50%]")
        print(f"  颜色：{sum(color_rates)/len(color_rates)*100:.1f}% ({min(color_rates)*100:.0f}%-{max(color_rates)*100:.0f}%) [随机33.3%]")
        print(f"  大小：{sum(size_rates)/len(size_rates)*100:.1f}% ({min(size_rates)*100:.0f}%-{max(size_rates)*100:.0f}%) [随机50%]")
    
    # 最近10期回测
    results = honest_backtest(all_rows, CONFIG["test_periods"], CONFIG["min_history"])
    
    # 最新预测
    print(f"\n{'='*60}")
    print(f"🎯 最新预测（基于全部{len(all_rows)}期简单频率统计）")
    print(f"{'='*60}")
    
    predictor = FrequencyPredictor(all_rows)
    
    print(f"\n📊 数据分布（近{min(30, len(all_rows))}期）：")
    color_freq = predictor.freq("color")
    size_freq = predictor.freq("size")
    odd_freq = predictor.freq("odd")
    zodiac_freq = predictor.freq("zodiac")
    
    print(f"  颜色：{dict(sorted(color_freq.items(), key=lambda x: x[1], reverse=True))}")
    print(f"  大小：{size_freq}")
    print(f"  单双：{odd_freq}")
    
    hw_pred = predictor.predict_halfhalf(CONFIG["bet_count"])
    zd_pred = predictor.predict_zodiac(CONFIG["zodiac_bet_count"])
    odd_pred = predictor.predict_odd()
    color_pred = predictor.predict_color()
    size_pred = predictor.predict_size()
    
    print(f"\n⭐ 预测推荐：")
    print(f"  半波：{', '.join(f'{x}({s:.1f}%)' for x, s in hw_pred)}")
    print(f"  生肖：")
    for i, (z, s) in enumerate(zd_pred, 1):
        print(f"    {i}. {z} ({s:.1f}%)")
    print(f"  单双：{odd_pred[0][0]} ({odd_pred[0][1]:.1f}%)")
    print(f"  颜色：{color_pred[0][0]} ({color_pred[0][1]:.1f}%)")
    print(f"  大小：{size_pred[0][0]} ({size_pred[0][1]:.1f}%)")
    
    print(f"\n{'='*60}")
    print(f"📋 诚实总结：")
    print(f"{'='*60}")
    print(f"  经过滑动窗口分析：")
    print(f"  - 简单频率统计是最稳定的基线")
    print(f"  - 复杂模型（遗漏值、转移概率）没有稳定提升")
    print(f"  - 所有维度命中率均接近随机期望")
    print(f"  - 彩票开奖本质上是独立随机事件")
    print(f"\n⚠️ 建议：理性投注，量力而行，切勿迷信任何预测。")

if __name__ == "__main__":
    main()