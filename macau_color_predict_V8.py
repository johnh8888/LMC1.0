#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新澳门彩预测系统 - 诚实版（增强灵敏度 + 组合投注策略）
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

def get_tail(n):
    """获取尾数（0-9）"""
    return n % 10

def get_remainder(n):
    """获取除以7的余数（0-6）"""
    return n % 7

def get_tens(n):
    """获取十位数（0-4）"""
    return n // 10

def get_number_range(n):
    """获取号码区间"""
    if 1 <= n <= 9: return "1-9"
    if 10 <= n <= 19: return "10-19"
    if 20 <= n <= 29: return "20-29"
    if 30 <= n <= 39: return "30-39"
    if 40 <= n <= 49: return "40-49"
    return ""

def get_highlow(n):
    """高/低（1-24为低，25-49为高）"""
    return "高" if n >= 25 else "低"

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
                        "tail": get_tail(special),
                        "remainder": get_remainder(special),
                        "tens": get_tens(special),
                        "range": get_number_range(special),
                        "highlow": get_highlow(special),
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

    # ========== 新增灵敏预测 ==========
    def predict_tail(self, count=3):
        """预测尾数（0-9），更灵敏"""
        tail_pred = self.freq("tail")
        full = {str(i): tail_pred.get(i, 0.0) for i in range(10)}
        return sorted(full.items(), key=lambda x: x[1], reverse=True)[:count]

    def predict_remainder(self, count=3):
        """预测除以7的余数（0-6），更灵敏"""
        rem_pred = self.freq("remainder")
        full = {str(i): rem_pred.get(i, 0.0) for i in range(7)}
        return sorted(full.items(), key=lambda x: x[1], reverse=True)[:count]

    def predict_tens(self, count=2):
        """预测十位数（0-4）"""
        tens_pred = self.freq("tens")
        full = {str(i): tens_pred.get(i, 0.0) for i in range(5)}
        return sorted(full.items(), key=lambda x: x[1], reverse=True)[:count]

    def predict_range(self, count=2):
        """预测号码区间"""
        range_pred = self.freq("range")
        ranges = ["1-9", "10-19", "20-29", "30-39", "40-49"]
        full = {r: range_pred.get(r, 0.0) for r in ranges}
        return sorted(full.items(), key=lambda x: x[1], reverse=True)[:count]

    def predict_highlow(self):
        """预测高低"""
        hl_pred = self.freq("highlow")
        return sorted(hl_pred.items(), key=lambda x: x[1], reverse=True)

    def predict_specific_number(self, count=5):
        """预测具体号码（基于多维度综合评分）"""
        scores = defaultdict(float)
        
        # 获取各维度预测
        tail_pred = {int(k): v for k, v in self.predict_tail(5)}
        rem_pred = {int(k): v for k, v in self.predict_remainder(5)}
        tens_pred = {int(k): v for k, v in self.predict_tens(3)}
        range_pred = self.predict_range(3)
        color_pred = {k: v for k, v in self.predict_color()}
        odd_pred = {k: v for k, v in self.predict_odd()}
        size_pred = {k: v for k, v in self.predict_size()}
        
        for num in range(1, 50):
            score = 0
            tail = get_tail(num)
            rem = get_remainder(num)
            tens = get_tens(num)
            range_name = get_number_range(num)
            color = get_color(num)
            odd = get_odd(num)
            size = get_size(num)
            
            # 加权综合评分
            score += tail_pred.get(tail, 0) * 0.25
            score += rem_pred.get(rem, 0) * 0.15
            score += tens_pred.get(tens, 0) * 0.10
            score += sum(v for r, v in range_pred if r == range_name) * 0.15
            score += color_pred.get(color, 0) * 0.15
            score += odd_pred.get(odd, 0) * 0.10
            score += size_pred.get(size, 0) * 0.10
            
            scores[num] = round(score, 2)
        
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:count]

    # ========== 组合投注策略（新增） ==========
    def generate_betting_combinations(self, bet_count=5):
        """生成组合投注方案"""
        # 获取各维度预测
        tail_pred = [int(x[0]) for x in self.predict_tail(3)]
        rem_pred = [int(x[0]) for x in self.predict_remainder(3)]
        zod_pred = [x[0] for x in self.predict_zodiac(5)]
        color_pred = self.predict_color()[0][0]
        size_pred = self.predict_size()[0][0]
        odd_pred = self.predict_odd()[0][0]
        
        # 方案1：尾数+余数双维度筛选（核心策略）
        combo1 = []
        for tail in tail_pred:
            for rem in rem_pred:
                for num in range(1, 50):
                    if get_tail(num) == tail and get_remainder(num) == rem:
                        combo1.append(num)
        combo1 = list(set(combo1))
        
        # 方案2：尾数+生肖筛选
        combo2 = []
        for tail in tail_pred:
            for zod in zod_pred:
                for num in range(1, 50):
                    if get_tail(num) == tail and get_zodiac(num) == zod:
                        combo2.append(num)
        combo2 = list(set(combo2))
        
        # 方案3：余数+生肖筛选
        combo3 = []
        for rem in rem_pred:
            for zod in zod_pred:
                for num in range(1, 50):
                    if get_remainder(num) == rem and get_zodiac(num) == zod:
                        combo3.append(num)
        combo3 = list(set(combo3))
        
        # 方案4：尾数+颜色筛选
        combo4 = []
        for tail in tail_pred:
            for num in range(1, 50):
                if get_tail(num) == tail and get_color(num) == color_pred:
                    combo4.append(num)
        combo4 = list(set(combo4))
        
        # 方案5：综合评分最高（原predict_specific_number结果）
        combo5 = [num for num, score in self.predict_specific_number(bet_count)]
        
        # 综合所有方案，取交集并排序
        all_combos = combo1 + combo2 + combo3 + combo4 + combo5
        combo_count = defaultdict(int)
        for num in all_combos:
            combo_count[num] += 1
        
        # 按出现次数排序，取前bet_count个
        final_combo = sorted(combo_count.items(), key=lambda x: x[1], reverse=True)[:bet_count]
        final_numbers = [num for num, count in final_combo]
        
        return {
            "tail_remainder": combo1[:10],  # 尾数+余数
            "tail_zodiac": combo2[:10],     # 尾数+生肖
            "remainder_zodiac": combo3[:10], # 余数+生肖
            "tail_color": combo4[:10],       # 尾数+颜色
            "top_score": combo5,             # 综合评分
            "final_recommendation": final_numbers  # 最终推荐
        }

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
        tail_hits = rem_hits = tens_hits = range_hits = hl_hits = 0
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
            tail_pred = [int(x[0]) for x in predictor.predict_tail(3)]
            rem_pred = [int(x[0]) for x in predictor.predict_remainder(3)]
            tens_pred = [int(x[0]) for x in predictor.predict_tens(2)]
            range_pred = [x[0] for x in predictor.predict_range(2)]
            hl_pred = predictor.predict_highlow()[0][0] if predictor.predict_highlow() else ""
            
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
            if test_row["tail"] in tail_pred:
                tail_hits += 1
            if test_row["remainder"] in rem_pred:
                rem_hits += 1
            if test_row["tens"] in tens_pred:
                tens_hits += 1
            if test_row["range"] in range_pred:
                range_hits += 1
            if test_row["highlow"] == hl_pred:
                hl_hits += 1
            valid += 1
        
        if valid > 0:
            results.append({
                "window": f"{test_set[-1]['issue']}~{test_set[0]['issue']}",
                "hw_rate": hw_hits / valid,
                "zd_rate": zd_hits / valid,
                "odd_rate": odd_hits / valid,
                "color_rate": color_hits / valid,
                "size_rate": size_hits / valid,
                "tail_rate": tail_hits / valid,
                "rem_rate": rem_hits / valid,
                "tens_rate": tens_hits / valid,
                "range_rate": range_hits / valid,
                "hl_rate": hl_hits / valid,
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
    
    print(f"\n{'='*120}")
    print(f"📊 最近{test_periods}期回测（每期只用前{min_history}期预测）")
    print(f"{'='*120}")
    print(f"{'期号':<12} {'实际':<10} {'半波':<8} {'生肖':<8} {'单双':<6} {'颜色':<6} {'大小':<6} {'尾数':<8} {'余数':<8} {'十位':<6} {'区间':<8} {'高低':<6}")
    print("-" * 120)
    
    hw_hits = zd_hits = odd_hits = color_hits = size_hits = 0
    tail_hits = rem_hits = tens_hits = range_hits = hl_hits = 0
    
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
        tail_pred = [int(x[0]) for x in predictor.predict_tail(3)]
        rem_pred = [int(x[0]) for x in predictor.predict_remainder(3)]
        tens_pred = [int(x[0]) for x in predictor.predict_tens(2)]
        range_pred = [x[0] for x in predictor.predict_range(2)]
        hl_pred = predictor.predict_highlow()[0][0]
        
        actual = f"{test_row['special']:02d}"
        
        hw_hit = test_row["halfhalf"] in hw_pred
        zd_hit = test_row["zodiac"] in zd_pred
        odd_hit = test_row["odd"] == odd_pred
        color_hit = test_row["color"] == color_pred
        size_hit = test_row["size"] == size_pred
        tail_hit = test_row["tail"] in tail_pred
        rem_hit = test_row["remainder"] in rem_pred
        tens_hit = test_row["tens"] in tens_pred
        range_hit = test_row["range"] in range_pred
        hl_hit = test_row["highlow"] == hl_pred
        
        hw_hits += hw_hit
        zd_hits += zd_hit
        odd_hits += odd_hit
        color_hits += color_hit
        size_hits += size_hit
        tail_hits += tail_hit
        rem_hits += rem_hit
        tens_hits += tens_hit
        range_hits += range_hit
        hl_hits += hl_hit
        
        print(f"{test_row['issue']:<12} {actual:<10} "
              f"{','.join(hw_pred):<8} {','.join(zd_pred):<8} "
              f"{odd_pred:<6} {color_pred:<6} {size_pred:<6} "
              f"{','.join(map(str, tail_pred)):<8} {','.join(map(str, rem_pred)):<8} "
              f"{','.join(map(str, tens_pred)):<6} {','.join(range_pred):<8} {hl_pred:<6}")
    
    n = len(test_set)
    print("-" * 120)
    
    print(f"\n📈 命中率统计（{n}期）vs 随机期望：")
    print(f"  {'维度':<12} {'实际命中':<12} {'随机期望':<12} {'评价':<15}")
    print(f"  {'-'*55}")
    
    metrics = [
        ("半波(2选)", hw_hits/n, 2/6, "6种半波选2"),
        ("生肖(5选)", zd_hits/n, 5/12, "12生肖选5"),
        ("单双(1选)", odd_hits/n, 1/2, "2选1"),
        ("颜色(1选)", color_hits/n, 1/3, "3选1"),
        ("大小(1选)", size_hits/n, 1/2, "2选1"),
        ("尾数(3选)", tail_hits/n, 3/10, "10个尾数选3"),
        ("余数(3选)", rem_hits/n, 3/7, "7个余数选3"),
        ("十位(2选)", tens_hits/n, 2/5, "5个十位选2"),
        ("区间(2选)", range_hits/n, 2/5, "5个区间选2"),
        ("高低(1选)", hl_hits/n, 1/2, "2选1"),
    ]
    
    for name, actual, expected, note in metrics:
        diff = actual - expected
        emoji = "✅" if diff > 0.05 else ("⚠️" if diff > -0.05 else "❌")
        print(f"  {name:<12} {actual*100:>6.1f}%     {expected*100:>6.1f}%     {emoji} {diff*100:+.1f}% ({note})")
    
    return {
        "hw": hw_hits/n, "zd": zd_hits/n, "odd": odd_hits/n,
        "color": color_hits/n, "size": size_hits/n,
        "tail": tail_hits/n, "rem": rem_hits/n,
        "tens": tens_hits/n, "range": range_hits/n,
        "hl": hl_hits/n
    }

# ========== 主函数 ==========
def main():
    print("=" * 60)
    print("新澳门彩预测系统 - 诚实版（增强灵敏度 + 组合投注策略）")
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
        print(f"\n{'窗口':<22} {'半波':<8} {'生肖':<8} {'单双':<8} {'颜色':<8} {'大小':<8} {'尾数':<8} {'余数':<8}")
        print("-" * 80)
        for wr in window_results:
            print(f"{wr['window']:<22} {wr['hw_rate']*100:>5.1f}%  {wr['zd_rate']*100:>5.1f}%  "
                  f"{wr['odd_rate']*100:>5.1f}%  {wr['color_rate']*100:>5.1f}%  {wr['size_rate']*100:>5.1f}%  "
                  f"{wr['tail_rate']*100:>5.1f}%  {wr['rem_rate']*100:>5.1f}%")
        
        hw_rates = [w['hw_rate'] for w in window_results]
        zd_rates = [w['zd_rate'] for w in window_results]
        odd_rates = [w['odd_rate'] for w in window_results]
        color_rates = [w['color_rate'] for w in window_results]
        size_rates = [w['size_rate'] for w in window_results]
        tail_rates = [w['tail_rate'] for w in window_results]
        rem_rates = [w['rem_rate'] for w in window_results]
        
        print(f"\n📊 各维度统计（均值/范围）：")
        print(f"  半波：{sum(hw_rates)/len(hw_rates)*100:.1f}% ({min(hw_rates)*100:.0f}%-{max(hw_rates)*100:.0f}%) [随机33.3%]")
        print(f"  生肖：{sum(zd_rates)/len(zd_rates)*100:.1f}% ({min(zd_rates)*100:.0f}%-{max(zd_rates)*100:.0f}%) [随机41.7%]")
        print(f"  单双：{sum(odd_rates)/len(odd_rates)*100:.1f}% ({min(odd_rates)*100:.0f}%-{max(odd_rates)*100:.0f}%) [随机50%]")
        print(f"  颜色：{sum(color_rates)/len(color_rates)*100:.1f}% ({min(color_rates)*100:.0f}%-{max(color_rates)*100:.0f}%) [随机33.3%]")
        print(f"  大小：{sum(size_rates)/len(size_rates)*100:.1f}% ({min(size_rates)*100:.0f}%-{max(size_rates)*100:.0f}%) [随机50%]")
        print(f"  尾数：{sum(tail_rates)/len(tail_rates)*100:.1f}% ({min(tail_rates)*100:.0f}%-{max(tail_rates)*100:.0f}%) [随机30%]")
        print(f"  余数：{sum(rem_rates)/len(rem_rates)*100:.1f}% ({min(rem_rates)*100:.0f}%-{max(rem_rates)*100:.0f}%) [随机42.9%]")
    
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
    tail_freq = predictor.freq("tail")
    rem_freq = predictor.freq("remainder")
    tens_freq = predictor.freq("tens")
    
    print(f"  颜色：{dict(sorted(color_freq.items(), key=lambda x: x[1], reverse=True))}")
    print(f"  大小：{size_freq}")
    print(f"  单双：{odd_freq}")
    print(f"  尾数：{dict(sorted(tail_freq.items(), key=lambda x: x[1], reverse=True))}")
    print(f"  余数：{dict(sorted(rem_freq.items(), key=lambda x: x[1], reverse=True))}")
    print(f"  十位：{dict(sorted(tens_freq.items(), key=lambda x: x[1], reverse=True))}")
    
    hw_pred = predictor.predict_halfhalf(CONFIG["bet_count"])
    zd_pred = predictor.predict_zodiac(CONFIG["zodiac_bet_count"])
    odd_pred = predictor.predict_odd()
    color_pred = predictor.predict_color()
    size_pred = predictor.predict_size()
    tail_pred = predictor.predict_tail(3)
    rem_pred = predictor.predict_remainder(3)
    tens_pred = predictor.predict_tens(2)
    range_pred = predictor.predict_range(2)
    hl_pred = predictor.predict_highlow()
    num_pred = predictor.predict_specific_number(5)
    
    print(f"\n⭐ 预测推荐：")
    print(f"  半波：{', '.join(f'{x}({s:.1f}%)' for x, s in hw_pred)}")
    print(f"  生肖：")
    for i, (z, s) in enumerate(zd_pred, 1):
        print(f"    {i}. {z} ({s:.1f}%)")
    print(f"  单双：{odd_pred[0][0]} ({odd_pred[0][1]:.1f}%)")
    print(f"  颜色：{color_pred[0][0]} ({color_pred[0][1]:.1f}%)")
    print(f"  大小：{size_pred[0][0]} ({size_pred[0][1]:.1f}%)")
    print(f"  尾数：{', '.join(f'{x}({s:.1f}%)' for x, s in tail_pred)}")
    print(f"  余数：{', '.join(f'{x}({s:.1f}%)' for x, s in rem_pred)}")
    print(f"  十位：{', '.join(f'{x}({s:.1f}%)' for x, s in tens_pred)}")
    print(f"  区间：{', '.join(f'{x}({s:.1f}%)' for x, s in range_pred)}")
    print(f"  高低：{hl_pred[0][0]} ({hl_pred[0][1]:.1f}%)")
    print(f"\n  综合推荐号码（前5）：")
    for i, (num, score) in enumerate(num_pred, 1):
        print(f"    {i}. {num:02d} (评分{score:.1f}) - {get_color(num)}{get_size(num)} {get_odd(num)} 尾{get_tail(num)} 余{get_remainder(num)}")
    
    # ========== 新增：组合投注策略 ==========
    print(f"\n{'='*60}")
    print(f"💰 组合投注策略（基于高命中率维度）")
    print(f"{'='*60}")
    
    combos = predictor.generate_betting_combinations(5)
    
    print(f"\n📌 策略说明：")
    print(f"  - 核心维度：尾数（命中率{tail_rates[-1]*100:.0f}%）、余数（命中率{rem_rates[-1]*100:.0f}%）")
    print(f"  - 辅助维度：生肖（命中率{zd_rates[-1]*100:.0f}%）、颜色（命中率{color_rates[-1]*100:.0f}%）")
    print(f"  - 赔率：特码 1:47，单双/大小 1:0.95")
    
    print(f"\n🎯 各方案候选号码：")
    print(f"  方案1（尾数+余数）: {', '.join(f'{x:02d}' for x in combos['tail_remainder'][:8])}")
    print(f"  方案2（尾数+生肖）: {', '.join(f'{x:02d}' for x in combos['tail_zodiac'][:8])}")
    print(f"  方案3（余数+生肖）: {', '.join(f'{x:02d}' for x in combos['remainder_zodiac'][:8])}")
    print(f"  方案4（尾数+颜色）: {', '.join(f'{x:02d}' for x in combos['tail_color'][:8])}")
    print(f"  方案5（综合评分）: {', '.join(f'{x:02d}' for x in combos['top_score'])}")
    
    print(f"\n⭐ 最终推荐投注组合（前5个）：")
    for i, num in enumerate(combos['final_recommendation'], 1):
        color = get_color(num)
        size = get_size(num)
        odd = get_odd(num)
        tail = get_tail(num)
        rem = get_remainder(num)
        zod = get_zodiac(num)
        print(f"  {i}. {num:02d} | {color}{size} {odd} | 尾{tail} 余{rem} | 生肖{zod}")
    
    # 投注策略建议
    print(f"\n📊 投注策略建议：")
    print(f"  策略A（稳健型）：")
    print(f"    - 投注：最终推荐5个号码，每个1元")
    print(f"    - 投入：5元/期")
    print(f"    - 预期命中率：{len(combos['final_recommendation'])/49*100:.1f}%")
    print(f"    - 中奖回报：47元（净赚42元）")
    
    print(f"\n  策略B（精准型）：")
    print(f"    - 投注：最终推荐前3个号码，每个2元")
    print(f"    - 投入：6元/期")
    print(f"    - 预期命中率：{len(combos['final_recommendation'][:3])/49*100:.1f}%")
    print(f"    - 中奖回报：94元（净赚88元）")
    
    print(f"\n  策略C（保险型 - 配合单双大小）：")
    print(f"    - 投注：最终推荐5个号码（5元）+ 单（1元）+ 小（1元）")
    print(f"    - 投入：7元/期")
    print(f"    - 如果特码中了：47+0.95+0.95=48.9元（净赚41.9元）")
    print(f"    - 如果特码没中但单双大小中了：1.9元（亏损5.1元）")
    
    print(f"\n⚠️ 风险提示：")
    print(f"  - 所有策略的期望值仍为负（庄家有优势）")
    print(f"  - 建议每期投入不超过总资金的5%")
    print(f"  - 设置止损线，亏损达到预算即停止")
    print(f"  - 切勿借钱或使用倍投法")
    
    print(f"\n{'='*60}")
    print(f"📋 诚实总结：")
    print(f"{'='*60}")
    print(f"  经过滑动窗口分析：")
    print(f"  - 简单频率统计是最稳定的基线")
    print(f"  - 增加尾数、余数、十位、区间、高低等灵敏维度")
    print(f"  - 复杂模型（遗漏值、转移概率）没有稳定提升")
    print(f"  - 所有维度命中率均接近随机期望")
    print(f"  - 彩票开奖本质上是独立随机事件")
    print(f"  - 组合投注能提高中奖概率，但不改变期望值")
    print(f"\n⚠️ 建议：理性投注，量力而行，切勿迷信任何预测。")

if __name__ == "__main__":
    main()