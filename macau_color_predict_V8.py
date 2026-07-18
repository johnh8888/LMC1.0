#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新澳门彩预测系统 - 最终完整版（含生肖预测）
包含详细10期回测 + 当前预测（波色/大小/单双/半波/生肖）
"""

import re
import json
import urllib.request
import os
from collections import defaultdict
from datetime import datetime

CONFIG = {
    "history_limit": 30,
    "api_url": "https://marksix6.net/index.php?api=1",
    "bet_count": 2,
    "bet_per_note": 50,
    "cache_file": "newmacau_cache.json",
    # 当前生肖年份：用于计算生肖对应表。
    # 注意：如接近农历新年前后（1-2月），请手动确认当年生肖是否已切换。
    "zodiac_year": 2026,
}

# 波色定义
RED = {1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE = {3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
GREEN = {5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}

# 生肖顺序（鼠年为基准，2020年 = 鼠年）
ZODIAC_ORDER = ["鼠","牛","虎","兔","龙","蛇","马","羊","猴","鸡","狗","猪"]
ZODIAC_BASE_YEAR = 2020  # 2020年为鼠年

def build_zodiac_map(year):
    """
    根据当年生肖，生成1-49号码对应的生肖表。
    规则：号码 n 对应的偏移 offset = ((n-1) % 12) + 1
         offset=1 对应当年生肖，offset=2 对应上一年生肖，依此类推倒推12个生肖。
    """
    current_idx = (year - ZODIAC_BASE_YEAR) % 12
    zmap = {}
    for n in range(1, 50):
        offset = ((n - 1) % 12) + 1
        animal_idx = (current_idx - (offset - 1)) % 12
        zmap[n] = ZODIAC_ORDER[animal_idx]
    return zmap

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
    return get_color(n) + get_size(n) + get_odd(n)

def get_zodiac(n):
    return ZODIAC_MAP.get(n, "?")

def parse_numbers(text):
    nums = re.findall(r"\d+", text)
    return [int(x) for x in nums if 1 <= int(x) <= 49]

def fetch_new_macau(limit=30):
    if os.path.exists(CONFIG["cache_file"]):
        try:
            with open(CONFIG["cache_file"], "r", encoding="utf-8") as f:
                cached = json.load(f)
                print("✅ 使用缓存数据")
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

class SimplePredictor:
    def __init__(self, rows):
        self.rows = rows[:30]

    def freq(self, key):
        c = defaultdict(int)
        for r in self.rows:
            c[r[key]] += 1
        total = sum(c.values()) or 1
        return {k: round(v / total * 100, 2) for k, v in c.items()}

    def predict_halfhalf(self):
        return self.freq("halfhalf")

    def predict_zodiac(self):
        return self.freq("zodiac")

class DynamicHalfwaveSelector:
    def __init__(self, color_pred, size_pred):
        self.color_pred = color_pred
        self.size_pred = size_pred

    def select_best(self, count=2):
        scores = {}
        for c in ["红", "蓝", "绿"]:
            for s in ["大", "小"]:
                scores[c + s] = self.color_pred.get(c, 33.3) * 0.5 + self.size_pred.get(s, 50) * 0.5
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        result = []
        used = set()
        for hw, score in sorted_scores:
            color = hw[0]
            if color not in used:
                result.append((hw, score))
                used.add(color)
            if len(result) >= count:
                break
        return result[:count]

class ZodiacSelector:
    """根据历史生肖出现频率，选出推荐生肖"""
    def __init__(self, zodiac_pred):
        self.zodiac_pred = zodiac_pred

    def select_best(self, count=3):
        # 确保12生肖都有基础分（未出现过的给0分，仍参与排序）
        full = {a: self.zodiac_pred.get(a, 0.0) for a in ZODIAC_ORDER}
        sorted_scores = sorted(full.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:count]

def detailed_backtest(rows):
    print("\n📊 详细10期盲测回测（半波 + 生肖）")
    print("=" * 90)
    print(f"{'期号':<12} {'实际':<10} {'实际生肖':<8} {'推荐半波':<20} {'半波命中':<8} {'推荐生肖':<20} {'生肖命中':<8}")
    print("-" * 90)

    hw_hits = 0
    zd_hits = 0
    total = min(10, len(rows) - 1)
    for i in range(total):
        history = rows[i + 1:]
        actual = rows[i]
        p = SimplePredictor(history)
        cp = p.freq("color")
        sp = p.freq("size")
        zp = p.freq("zodiac")

        selector = DynamicHalfwaveSelector(cp, sp)
        bets = [b[0] for b in selector.select_best(2)]
        hw_hit = (actual["color"] + actual["size"]) in bets
        if hw_hit:
            hw_hits += 1

        zselector = ZodiacSelector(zp)
        zbets = [b[0] for b in zselector.select_best(3)]
        zd_hit = actual["zodiac"] in zbets
        if zd_hit:
            zd_hits += 1

        print(f"{actual['issue']:<12} {actual['halfhalf']:<10} {actual['zodiac']:<8} "
              f"{','.join(bets):<20} {'✓' if hw_hit else '✗':<8} "
              f"{','.join(zbets):<20} {'✓' if zd_hit else '✗':<8}")

    print("-" * 90)
    print(f"半波命中率: {hw_hits}/{total} = {hw_hits/total*100:.1f}%")
    print(f"生肖命中率: {zd_hits}/{total} = {zd_hits/total*100:.1f}%")

def main():
    print("=" * 60)
    print("新澳门彩预测系统 - 最终完整版（含生肖）")
    print(f"生肖年份基准: {CONFIG['zodiac_year']}年")
    print("=" * 60)

    rows = fetch_new_macau(CONFIG["history_limit"])
    if len(rows) < 10:
        print("❌ 数据不足")
        return

    detailed_backtest(rows)

    # 当前预测
    predictor = SimplePredictor(rows)
    color_pred = predictor.freq("color")
    size_pred = predictor.freq("size")
    odd_pred = predictor.freq("odd")
    hh_pred = predictor.predict_halfhalf()
    zd_pred = predictor.predict_zodiac()

    print("\n🎯 当前最新预测")
    print("颜色:", dict(sorted(color_pred.items(), key=lambda x: x[1], reverse=True)))
    print("大小:", size_pred)
    print("单双:", odd_pred)

    print("\n🔥 TOP 6 半波:")
    for i, (hh, prob) in enumerate(list(sorted(hh_pred.items(), key=lambda x: x[1], reverse=True))[:6], 1):
        print(f"  {i}. {hh}  {prob}%")

    print("\n🐉 生肖出现频率（近30期）:")
    for animal, prob in sorted(zd_pred.items(), key=lambda x: x[1], reverse=True):
        print(f"  {animal}: {prob}%")

    selector = DynamicHalfwaveSelector(color_pred, size_pred)
    bets = selector.select_best(CONFIG["bet_count"])
    print("\n💡 动态半波推荐:")
    for i, (bw, score) in enumerate(bets, 1):
        print(f"  {i}. {bw} (得分 {score:.1f})")

    zselector = ZodiacSelector(zd_pred)
    zbets = zselector.select_best(3)
    print("\n💡 动态生肖推荐:")
    for i, (animal, score) in enumerate(zbets, 1):
        print(f"  {i}. {animal} (得分 {score:.1f})")

if __name__ == "__main__":
    main()
