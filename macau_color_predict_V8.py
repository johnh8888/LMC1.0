#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新澳门彩预测系统 - 自适应窗口版
3个不同窗口（5期/10期/15期）各自预测，根据近期命中率自动选择最佳窗口
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
    "test_periods": 20,        # 回测期数
    "validate_periods": 10,    # 用最近N期验证哪个窗口最好
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
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:count]

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


# ========== 自适应窗口选择器 ==========
def evaluate_window(rows, window_size, validate_periods):
    """用最近validate_periods期验证某个窗口大小的命中率"""
    if len(rows) < window_size + validate_periods:
        return 0, 0
    
    hw_hits = 0
    zd_hits = 0
    
    for i in range(validate_periods):
        hist_start = validate_periods - i
        history = rows[hist_start:hist_start + window_size]
        
        if len(history) < window_size:
            continue
        
        predictor = FrequencyPredictor(history)
        hw_pred = [x[0] for x in predictor.predict_halfhalf(CONFIG["bet_count"])]
        zd_pred = [x[0] for x in predictor.predict_zodiac(CONFIG["zodiac_bet_count"])]
        
        actual = rows[i]
        if actual["halfhalf"] in hw_pred:
            hw_hits += 1
        if actual["zodiac"] in zd_pred:
            zd_hits += 1
    
    n = min(validate_periods, len(rows) - window_size)
    return hw_hits / n if n > 0 else 0, zd_hits / n if n > 0 else 0


def auto_select_window(rows, validate_periods=10):
    """自动选择最佳窗口大小"""
    windows = [5, 10, 15]
    
    print(f"\n{'='*60}")
    print(f"🔍 自适应窗口选择（验证最近{validate_periods}期）")
    print(f"{'='*60}")
    print(f"\n{'窗口':<10} {'半波命中':<12} {'生肖命中':<12} {'综合得分':<12}")
    print("-" * 50)
    
    best_window = None
    best_score = -1
    
    for w in windows:
        hw_rate, zd_rate = evaluate_window(rows, w, validate_periods)
        score = hw_rate * 0.5 + zd_rate * 0.5  # 综合得分
        
        if score > best_score:
            best_score = score
            best_window = w
        
        print(f"  {w}期{'':<6} {hw_rate*100:>5.1f}%      {zd_rate*100:>5.1f}%      {score*100:>5.1f}%")
    
    print(f"\n✅ 最佳窗口：{best_window}期（综合得分{best_score*100:.1f}%）")
    return best_window


# ========== 回测（使用自动选择的窗口） ==========
def adaptive_backtest(all_rows, test_periods=20, validate_periods=10):
    """自适应回测：先用验证期选窗口，再用选中的窗口预测测试期"""
    if len(all_rows) < validate_periods + test_periods:
        print(f"❌ 数据不足")
        return None
    
    # 分割数据：验证期 + 测试期
    validate_set = all_rows[:validate_periods]
    test_set = all_rows[validate_periods:validate_periods + test_periods]
    
    # 自动选择最佳窗口
    best_window = auto_select_window(all_rows, validate_periods)
    
    print(f"\n{'='*90}")
    print(f"📊 回测：最近{test_periods}期（使用{best_window}期窗口预测）")
    print(f"{'='*90}")
    print(f"{'期号':<12} {'实际':<14} {'半波预测':<16} {'✓':<4} {'生肖预测':<28} {'✓':<4} {'单双':<6} {'颜色':<6} {'大小':<6}")
    print("-" * 100)
    
    hw_hits = zd_hits = odd_hits = color_hits = size_hits = 0
    
    for i, test_row in enumerate(test_set):
        hist_start = validate_periods + test_periods - i
        history = all_rows[hist_start:hist_start + best_window]
        
        if len(history) < best_window:
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
    print(f"\n📈 命中率（{n}期，窗口={best_window}）vs 随机：")
    print(f"  {'维度':<10} {'实际':<10} {'随机':<10} {'差值':<10}")
    print(f"  {'-'*42}")
    for name, actual, expected in [
        ("半波(2选)", hw_hits/n, 2/6),
        ("生肖(5选)", zd_hits/n, 5/12),
        ("单双(1选)", odd_hits/n, 1/2),
        ("颜色(1选)", color_hits/n, 1/3),
        ("大小(1选)", size_hits/n, 1/2),
    ]:
        diff = actual - expected
        flag = "✅" if diff > 0.05 else ("⚠️" if diff > -0.05 else "❌")
        print(f"  {name:<10} {actual*100:>5.1f}%   {expected*100:>5.1f}%   {flag} {diff*100:+.1f}%")
    
    return {"hw": hw_hits/n, "zd": zd_hits/n, "odd": odd_hits/n, "color": color_hits/n, "size": size_hits/n, "window": best_window}


def main():
    print("=" * 60)
    print("新澳门彩预测系统 - 自适应窗口版")
    print("自动从5/10/15期中选最佳窗口")
    print("=" * 60)
    
    all_rows = fetch_new_macau(CONFIG["history_limit"])
    
    # 自适应回测
    results = adaptive_backtest(all_rows, CONFIG["test_periods"], CONFIG["validate_periods"])
    
    # 最新预测
    print(f"\n{'='*60}")
    print(f"🎯 最新预测")
    print(f"{'='*60}")
    
    best_window = results["window"] if results else 10
    
    # 用最佳窗口预测
    history = all_rows[:best_window]
    predictor = FrequencyPredictor(history)
    
    print(f"\n📊 使用窗口：最近{best_window}期")
    for name, key in [("颜色", "color"), ("大小", "size"), ("单双", "odd")]:
        f = predictor.freq(key)
        print(f"  {name}: {dict(sorted(f.items(), key=lambda x: x[1], reverse=True))}")
    
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
    print(f"  生肖: {', '.join(f'{x}({s:.1f}%)' for x, s in zd_pred)}")
    print(f"  单双: {odd_pred[0][0]}({odd_pred[0][1]:.1f}%)")
    print(f"  颜色: {color_pred[0][0]}({color_pred[0][1]:.1f}%)")
    print(f"  大小: {size_pred[0][0]}({size_pred[0][1]:.1f}%)")
    
    print(f"\n⚠️ 彩票开奖独立随机，预测仅供参考。")

if __name__ == "__main__":
    main()