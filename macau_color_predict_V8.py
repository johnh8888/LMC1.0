#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新澳门彩预测系统 - 固定5期窗口版（修复版）
"""

import re
import json
import urllib.request
import os
from collections import defaultdict
from datetime import datetime

CONFIG = {
    "history_limit": 60,
    "api_url": "https://marksix6.net/index.php?api=1",
    "bet_count": 2,
    "zodiac_bet_count": 5,
    "cache_file": "newmacau_cache.json",
    "test_periods": 20,
    "window_size": 5,
}

RED = {1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE = {3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
GREEN = {5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}

ZODIAC_MAP_FIXED = {
    1: "马", 2: "蛇", 3: "龙", 4: "兔", 5: "虎", 6: "牛",
    7: "鼠", 8: "猪", 9: "狗", 10: "鸡", 11: "猴", 12: "羊",
}
for n in range(13, 50):
    ZODIAC_MAP_FIXED[n] = ZODIAC_MAP_FIXED[((n - 1) % 12) + 1]

ZODIAC_ORDER = ["鼠","牛","虎","兔","龙","蛇","马","羊","猴","鸡","狗","猪"]

def build_zodiac_map(year):
    return ZODIAC_MAP_FIXED

ZODIAC_MAP = build_zodiac_map(2026)

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

def fetch_new_macau(limit=60):
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
        return sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:count]

    def predict_zodiac(self, count=5):
        zod_pred = self.freq("zodiac")
        full = {a: zod_pred.get(a, 0.0) for a in ZODIAC_ORDER}
        # 🔧 按频率降序，频率相同按生肖名排序（稳定排序）
        return sorted(full.items(), key=lambda x: (-x[1], x[0]))[:count]

    def predict_odd(self):
        return sorted(self.freq("odd").items(), key=lambda x: (-x[1], x[0]))

    def predict_color(self):
        return sorted(self.freq("color").items(), key=lambda x: (-x[1], x[0]))

    def predict_size(self):
        return sorted(self.freq("size").items(), key=lambda x: (-x[1], x[0]))


def backtest(all_rows, test_periods=20):
    window = CONFIG["window_size"]
    
    if len(all_rows) < window + test_periods:
        print(f"❌ 数据不足：需要{window + test_periods}期，实际{len(all_rows)}期")
        return None
    
    test_set = all_rows[:test_periods]
    
    print(f"\n{'='*95}")
    print(f"📊 逐期回测：最近{test_periods}期（每期用前{window}期预测）")
    print(f"{'='*95}")
    print(f"{'期号':<12} {'实际':<18} {'半波预测':<16} {'✓':<4} {'生肖预测':<30} {'✓':<4} {'单双':<6} {'颜色':<6} {'大小':<6}")
    print("-" * 110)
    
    hw_hits = zd_hits = odd_hits = color_hits = size_hits = 0
    
    for i, test_row in enumerate(test_set):
        # 🔧 修复：test_row = all_rows[i]，它的前5期 = all_rows[i+1 : i+1+window]
        history = all_rows[i + 1 : i + 1 + window]
        
        if len(history) < window:
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
        
        print(f"{test_row['issue']:<12} {actual_full:<18} "
              f"{','.join(hw_pred):<16} {'✓' if hw_hit else '✗':<4} "
              f"{','.join(zd_pred):<30} {'✓' if zd_hit else '✗':<4} "
              f"{odd_pred:<6} {color_pred:<6} {size_pred:<6}")
    
    n = len(test_set)
    print("-" * 110)
    print(f"\n📈 命中率（{n}期，固定{window}期窗口）：")
    print(f"  {'维度':<10} {'命中':<8} {'随机期望':<10} {'差值':<10}")
    print(f"  {'-'*40}")
    for name, actual, expected in [
        ("半波(2选)", hw_hits/n, 2/6),
        ("生肖(5选)", zd_hits/n, 5/12),
        ("单双(1选)", odd_hits/n, 1/2),
        ("颜色(1选)", color_hits/n, 1/3),
        ("大小(1选)", size_hits/n, 1/2),
    ]:
        diff = actual - expected
        flag = "✅" if diff > 0.05 else ("⚠️" if diff > -0.05 else "❌")
        print(f"  {name:<10} {actual*100:>5.1f}%   {expected*100:>5.1f}%     {flag} {diff*100:+.1f}%")
    
    return {"hw": hw_hits/n, "zd": zd_hits/n, "odd": odd_hits/n, "color": color_hits/n, "size": size_hits/n}


def main():
    print("=" * 60)
    print(f"新澳门彩预测系统 - 固定{CONFIG['window_size']}期窗口版（修复版）")
    print("=" * 60)
    
    all_rows = fetch_new_macau(CONFIG["history_limit"])
    
    # 回测
    results = backtest(all_rows, CONFIG["test_periods"])
    
    # 最新预测
    print(f"\n{'='*60}")
    print(f"🎯 最新预测（近{CONFIG['window_size']}期）")
    print(f"{'='*60}")
    
    history = all_rows[:CONFIG["window_size"]]
    predictor = FrequencyPredictor(history)
    
    print(f"\n📊 近{CONFIG['window_size']}期数据：")
    for r in history:
        print(f"  {r['issue']} {r['special']:>2}号 → {r['halfhalf']}({r['odd']}) {r['zodiac']}")
    
    print(f"\n📊 频率分布：")
    for name, key in [("颜色", "color"), ("大小", "size"), ("单双", "odd")]:
        f = dict(predictor.freq(key))
        # 按频率降序显示
        sorted_f = dict(sorted(f.items(), key=lambda x: -x[1]))
        print(f"  {name}: {sorted_f}")
    
    print(f"\n📊 生肖频率：")
    for z, s in predictor.predict_zodiac(12):
        bar = "█" * int(s)
        print(f"  {z:<4} {s:>5.1f}% {bar}")
    
    hw_pred = predictor.predict_halfhalf(CONFIG["bet_count"])
    zd_pred = predictor.predict_zodiac(CONFIG["zodiac_bet_count"])
    odd_pred = predictor.predict_odd()
    color_pred = predictor.predict_color()
    size_pred = predictor.predict_size()
    
    print(f"\n⭐ 预测推荐：")
    print(f"  半波: {', '.join(f'{x}({s:.1f}%)' for x, s in hw_pred)}")
    print(f"  生肖(5选): {', '.join(f'{x}({s:.1f}%)' for x, s in zd_pred)}")
    print(f"  单双: {odd_pred[0][0]}({odd_pred[0][1]:.1f}%)")
    print(f"  颜色: {color_pred[0][0]}({color_pred[0][1]:.1f}%)")
    print(f"  大小: {size_pred[0][0]}({size_pred[0][1]:.1f}%)")
    
    print(f"\n⚠️ 彩票开奖独立随机，预测仅供参考。")

if __name__ == "__main__":
    main()