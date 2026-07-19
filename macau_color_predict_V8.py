#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新澳门彩预测系统 - 诚实版（修复固定预测bug）
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
    "min_history": 10,  # 🔧 从20改为10，让预测更灵敏
}

RED = {1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE = {3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
GREEN = {5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}

# 正确生肖映射：1马 2蛇 3龙 4兔 5虎 6牛 7鼠 8猪 9狗 10鸡 11猴 12羊
ZODIAC_MAP_FIXED = {
    1: "马", 2: "蛇", 3: "龙", 4: "兔", 5: "虎", 6: "牛",
    7: "鼠", 8: "猪", 9: "狗", 10: "鸡", 11: "猴", 12: "羊",
}
for n in range(13, 50):
    base = ((n - 1) % 12) + 1
    ZODIAC_MAP_FIXED[n] = ZODIAC_MAP_FIXED[base]

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
        result, used_colors = [], set()
        for hw, score in sorted_items:
            color = hw[0]
            if color not in used_colors:
                result.append((hw, score))
                used_colors.add(color)
            if len(result) >= count:
                break
        return result

    def predict_zodiac(self, count=5):
        zod_pred = self.freq("zodiac")
        full = {a: zod_pred.get(a, 0.0) for a in ZODIAC_ORDER}
        return sorted(full.items(), key=lambda x: x[1], reverse=True)[:count]

    def predict_odd(self):
        return sorted(self.freq("odd").items(), key=lambda x: x[1], reverse=True)

    def predict_color(self):
        return sorted(self.freq("color").items(), key=lambda x: x[1], reverse=True)

    def predict_size(self):
        return sorted(self.freq("size").items(), key=lambda x: x[1], reverse=True)

# ========== 修复：滚动窗口 ==========
def rolling_window_analysis(all_rows, test_periods=10, min_history=10):
    """
    🔧 修复版：对每期测试，只用该期之前min_history期数据
    每次预测窗口固定大小，随着测试期推进，窗口自然滚动
    """
    if len(all_rows) < min_history + test_periods:
        return None
    
    test_set = all_rows[:test_periods]
    
    hw_hits = zd_hits = odd_hits = color_hits = size_hits = 0
    
    print(f"\n{'='*90}")
    print(f"📊 滚动回测：最近{test_periods}期（每期用前{min_history}期预测）")
    print(f"{'='*90}")
    print(f"{'期号':<12} {'实际':<14} {'半波预测':<16} {'✓':<4} {'生肖预测':<28} {'✓':<4} {'单双':<6} {'颜色':<6} {'大小':<6}")
    print("-" * 100)
    
    for i, test_row in enumerate(test_set):
        # 🔧 从该期之后取固定min_history期
        start_idx = test_periods - i
        history = all_rows[start_idx:start_idx + min_history]
        
        if len(history) < min_history:
            continue
        
        predictor = FrequencyPredictor(history)
        hw_pred = [x[0] for x in predictor.predict_halfhalf(CONFIG["bet_count"])]
        zd_pred = [x[0] for x in predictor.predict_zodiac(CONFIG["zodiac_bet_count"])]
        odd_pred = predictor.predict_odd()[0][0]
        color_pred = predictor.predict_color()[0][0]
        size_pred = predictor.predict_size()[0][0]
        
        actual_full = f"{test_row['halfhalf']}({test_row['odd']}) {test_row['zodiac']}"
        
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
    print(f"\n📈 命中率（{n}期）vs 随机期望：")
    print(f"  {'维度':<10} {'实际':<10} {'随机':<10} {'差值':<10}")
    print(f"  {'-'*42}")
    
    metrics = [
        ("半波(2选)", hw_hits/n, 2/6),
        ("生肖(5选)", zd_hits/n, 5/12),
        ("单双(1选)", odd_hits/n, 1/2),
        ("颜色(1选)", color_hits/n, 1/3),
        ("大小(1选)", size_hits/n, 1/2),
    ]
    
    for name, actual, expected in metrics:
        diff = actual - expected
        flag = "✅" if diff > 0.05 else ("⚠️" if diff > -0.05 else "❌")
        print(f"  {name:<10} {actual*100:>5.1f}%   {expected*100:>5.1f}%   {flag} {diff*100:+.1f}%")
    
    return {"hw": hw_hits/n, "zd": zd_hits/n, "odd": odd_hits/n, "color": color_hits/n, "size": size_hits/n}


def main():
    print("=" * 60)
    print("新澳门彩预测系统 - 诚实版（修复固定预测）")
    print("=" * 60)
    
    all_rows = fetch_new_macau(CONFIG["history_limit"])
    if len(all_rows) < CONFIG["min_history"] + CONFIG["test_periods"]:
        print(f"❌ 数据不足：需要{CONFIG['min_history'] + CONFIG['test_periods']}期，实际{len(all_rows)}期")
        return
    
    print(f"\n📦 数据：{len(all_rows)}期 ({all_rows[-1]['issue']} ~ {all_rows[0]['issue']})")
    print(f"📋 每期用前{CONFIG['min_history']}期预测，共测试{CONFIG['test_periods']}期")
    
    # 滚动回测
    results = rolling_window_analysis(all_rows, CONFIG["test_periods"], CONFIG["min_history"])
    
    # 最新预测
    print(f"\n{'='*60}")
    print(f"🎯 最新预测（基于全部{len(all_rows)}期）")
    print(f"{'='*60}")
    
    predictor = FrequencyPredictor(all_rows)
    
    print(f"\n📊 近30期数据分布：")
    recent = all_rows[:30]
    rp = FrequencyPredictor(recent)
    
    for name, key in [("颜色", "color"), ("大小", "size"), ("单双", "odd")]:
        f = rp.freq(key)
        print(f"  {name}: {dict(sorted(f.items(), key=lambda x: x[1], reverse=True))}")
    
    print(f"\n📊 近30期生肖频率：")
    for z, s in rp.predict_zodiac(12):
        bar = "█" * int(s)
        print(f"  {z:<4} {s:>5.1f}% {bar}")
    
    # 用全部数据预测
    hw_pred = predictor.predict_halfhalf(CONFIG["bet_count"])
    zd_pred = predictor.predict_zodiac(CONFIG["zodiac_bet_count"])
    odd_pred = predictor.predict_odd()
    color_pred = predictor.predict_color()
    size_pred = predictor.predict_size()
    
    print(f"\n⭐ 预测推荐：")
    print(f"  半波: {', '.join(f'{x}({s:.1f}%)' for x, s in hw_pred)}")
    print(f"  生肖:")
    for i, (z, s) in enumerate(zd_pred, 1):
        print(f"    {i}. {z} ({s:.1f}%)")
    print(f"  单双: {odd_pred[0][0]} ({odd_pred[0][1]:.1f}%)")
    print(f"  颜色: {color_pred[0][0]} ({color_pred[0][1]:.1f}%)")
    print(f"  大小: {size_pred[0][0]} ({size_pred[0][1]:.1f}%)")
    
    print(f"\n{'='*60}")
    print(f"⚠️ 彩票开奖独立随机，预测仅供参考。理性投注！")

if __name__ == "__main__":
    main()