#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新澳门彩预测系统 - 简化重构版 V2 + 严格10期盲测
"""

import re
import json
import urllib.request
from collections import defaultdict
from datetime import datetime
import os

# 配置
CONFIG = {
    "history_limit": 30,
    "api_url": "https://marksix6.net/index.php?api=1",
    "bet_count": 2,
    "bet_per_note": 50,
    "cache_file": "newmacau_cache.json",
}

REPORT_FILE = "newmacau_result_simplified.md"

# 波色定义
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
    return "单" if n % 2 == 1 else "双"

def get_halfhalf(n): 
    return get_color(n) + get_size(n) + get_odd(n)

# 数据处理
def parse_numbers(text):
    nums = re.findall(r"\d+", text)
    return [int(x) for x in nums if 1 <= int(x) <= 49]

def load_cache():
    if os.path.exists(CONFIG["cache_file"]):
        try:
            with open(CONFIG["cache_file"], "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return []

def save_cache(rows):
    try:
        with open(CONFIG["cache_file"], "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
    except:
        pass

def fetch_new_macau(limit=30):
    cached = load_cache()
    if len(cached) >= 10:
        print("✅ 使用缓存数据")
        return cached[:limit]

    print("正在获取网络数据...")
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
                        "halfhalf": get_halfhalf(special)
                    })
                break

        rows = list({r["issue"]: r for r in rows}.values())
        rows.sort(key=lambda x: x["issue"], reverse=True)
        save_cache(rows)
        return rows[:limit]
    except Exception as e:
        print(f"❌ 获取失败: {e}")
        return cached[:limit]

# 预测器
class SimplePredictor:
    def __init__(self, rows):
        self.rows = rows[:30]

    def _frequency(self, key):
        count = defaultdict(int)
        for r in self.rows:
            count[r[key]] += 1
        total = sum(count.values()) or 1
        return {k: round(v / total * 100, 2) for k, v in count.items()}

    def predict_color(self):
        return self._frequency("color")

    def predict_size(self):
        return self._frequency("size")

    def predict_odd(self):
        return self._frequency("odd")

    def predict_halfhalf(self):
        freq = self._frequency("halfhalf")
        total = sum(freq.values()) or 1
        return {k: round(v / total * 100, 2) for k, v in freq.items()}

# 动态半波
class DynamicHalfwaveSelector:
    def __init__(self, color_pred, size_pred):
        self.color_pred = color_pred
        self.size_pred = size_pred

    def select_best(self, count=2):
        scores = {}
        for c in ["红", "蓝", "绿"]:
            for s in ["大", "小"]:
                scores[c + s] = self.color_pred.get(c, 33) * 0.5 + self.size_pred.get(s, 50) * 0.5
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        result = []
        used = set()
        for hw, score in sorted_scores:
            color = hw[0]
            if color not in used:
                result.append((hw, score))
                used.add(color)
            if len(result) >= count: break
        return result[:count]

# 新增：严格10期盲测
def backtest_10_periods(rows):
    print("\n" + "="*50)
    print("📊 严格10期盲测（不偷看未来数据）")
    print("="*50)

    total = min(10, len(rows) - 1)
    color_hits = size_hits = odd_hits = halfwave_hits = 0

    for i in range(total):
        # 历史数据 = 当前期之后的所有数据（不包含当前及未来）
        history = rows[i+1:]
        actual = rows[i]

        if len(history) < 5:
            continue

        pred = SimplePredictor(history)
        color_pred = pred.predict_color()
        size_pred = pred.predict_size()
        odd_pred = pred.predict_odd()

        # 颜色
        if max(color_pred, key=color_pred.get) == actual["color"]:
            color_hits += 1
        # 大小
        if max(size_pred, key=size_pred.get) == actual["size"]:
            size_hits += 1
        # 单双
        if max(odd_pred, key=odd_pred.get) == actual["odd"]:
            odd_hits += 1

        # 动态半波
        selector = DynamicHalfwaveSelector(color_pred, size_pred)
        bets = [bw for bw, _ in selector.select_best(2)]
        actual_hw = actual["color"] + actual["size"]
        if actual_hw in bets:
            halfwave_hits += 1

    print(f"颜色命中: {color_hits}/{total} = {color_hits/total*100:.1f}%")
    print(f"大小命中: {size_hits}/{total} = {size_hits/total*100:.1f}%")
    print(f"单双命中: {odd_hits}/{total} = {odd_hits/total*100:.1f}%")
    print(f"动态半波命中: {halfwave_hits}/{total} = {halfwave_hits/total*100:.1f}%")
    return halfwave_hits / total * 100 if total > 0 else 0

# 主程序
def main():
    print("="*60)
    print("新澳门彩预测系统 - 简化重构版 V2 + 盲测")
    print("="*60)

    rows = fetch_new_macau(CONFIG["history_limit"])

    if len(rows) < 10:
        print("❌ 数据不足")
        return

    print(f"✅ 加载 {len(rows)} 期数据")

    # 盲测
    backtest_10_periods(rows)

    # 当前预测
    predictor = SimplePredictor(rows)
    color_pred = predictor.predict_color()
    size_pred = predictor.predict_size()

    print("\n🎯 当前预测:")
    print("颜色:", dict(sorted(color_pred.items(), key=lambda x: x[1], reverse=True)))
    print("大小:", size_pred)

    selector = DynamicHalfwaveSelector(color_pred, size_pred)
    bets = selector.select_best(CONFIG["bet_count"])
    selector.print_recommendation = lambda b: print("\n推荐半波:", [x[0] for x in b])  # 简化打印
    selector.print_recommendation(bets)

if __name__ == "__main__":
    main()