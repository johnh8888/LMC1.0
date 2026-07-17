#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新澳门彩预测系统 - 完整预测版 + 严格盲测
"""

import re
import json
import urllib.request
from collections import defaultdict
from datetime import datetime
import os

CONFIG = {
    "history_limit": 30,
    "api_url": "https://marksix6.net/index.php?api=1",
    "bet_count": 2,
    "bet_per_note": 50,
    "cache_file": "newmacau_cache.json",
}

# 波色定义（同前）
RED = {1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE = {3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
GREEN = {5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}

def get_color(n): 
    if n in RED: return "红"
    if n in BLUE: return "蓝"
    return "绿"

def get_size(n): return "大" if n >= 25 else "小"
def get_odd(n): return "单" if n % 2 == 1 else "双"
def get_halfhalf(n): return get_color(n) + get_size(n) + get_odd(n)

def parse_numbers(text):
    nums = re.findall(r"\d+", text)
    return [int(x) for x in nums if 1 <= int(x) <= 49]

def load_cache():
    if os.path.exists(CONFIG["cache_file"]):
        try:
            with open(CONFIG["cache_file"], "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return []

def fetch_new_macau(limit=30):
    cached = load_cache()
    if len(cached) >= 10:
        print("✅ 使用缓存")
        return cached[:limit]

    try:
        print("正在获取最新数据...")
        req = urllib.request.Request(CONFIG["api_url"], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        rows = []
        for item in data.get("lottery_data", []):
            if item.get("name", "").strip() != "新澳门彩": continue
            for line in item.get("history", []):
                nums = parse_numbers(line)
                if len(nums) < 7: continue
                special = nums[-1]
                m = re.search(r"(20\d{5,8})", line)
                if not m: continue
                raw = m.group(1)
                issue = raw[:4] + "/" + str(int(raw[4:])).zfill(3)

                rows.append({
                    "issue": issue, "special": special,
                    "color": get_color(special), "size": get_size(special),
                    "odd": get_odd(special), "halfhalf": get_halfhalf(special)
                })
            break

        rows = list({r["issue"]:r for r in rows}.values())
        rows.sort(key=lambda x: x["issue"], reverse=True)
        with open(CONFIG["cache_file"], "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        return rows[:limit]
    except Exception as e:
        print(f"获取失败: {e}")
        return cached[:limit]

class SimplePredictor:
    def __init__(self, rows):
        self.rows = rows[:30]

    def freq(self, key):
        c = defaultdict(int)
        for r in self.rows: c[r[key]] += 1
        total = sum(c.values()) or 1
        return {k: round(v/total*100, 2) for k,v in c.items()}

    def predict_halfhalf(self):
        freq = self.freq("halfhalf")
        total = sum(freq.values()) or 1
        return {k: round(v/total*100, 2) for k,v in sorted(freq.items(), key=lambda x:x[1], reverse=True)}

# 动态半波选择器
class DynamicHalfwaveSelector:
    def __init__(self, color_p, size_p):
        self.color_p = color_p
        self.size_p = size_p

    def select_best(self, count=2):
        scores = {}
        for c in ["红","蓝","绿"]:
            for s in ["大","小"]:
                scores[c+s] = self.color_p.get(c,33)*0.5 + self.size_p.get(s,50)*0.5
        sorted_list = sorted(scores.items(), key=lambda x:x[1], reverse=True)
        res, used = [], set()
        for hw, sc in sorted_list:
            col = hw[0]
            if col not in used:
                res.append((hw, sc))
                used.add(col)
            if len(res) >= count: break
        return res[:count]

def backtest_10(rows):
    print("\n📊 严格10期盲测")
    print("="*40)
    total = min(10, len(rows)-1)
    c_hit = s_hit = o_hit = hw_hit = 0
    for i in range(total):
        history = rows[i+1:]
        actual = rows[i]
        p = SimplePredictor(history)
        cp = p.freq("color")
        sp = p.freq("size")
        op = p.freq("odd")
        if max(cp, key=cp.get) == actual["color"]: c_hit += 1
        if max(sp, key=sp.get) == actual["size"]: s_hit += 1
        if max(op, key=op.get) == actual["odd"]: o_hit += 1
        sel = DynamicHalfwaveSelector(cp, sp)
        if actual["color"] + actual["size"] in [x[0] for x in sel.select_best(2)]:
            hw_hit += 1
    print(f"颜色: {c_hit}/{total} ({c_hit/total*100:.1f}%)")
    print(f"大小: {s_hit}/{total} ({s_hit/total*100:.1f}%)")
    print(f"单双: {o_hit}/{total} ({o_hit/total*100:.1f}%)")
    print(f"半波: {hw_hit}/{total} ({hw_hit/total*100:.1f}%)")

# 主函数
def main():
    print("="*60)
    print("新澳门彩预测系统 - 完整预测版")
    print("="*60)

    rows = fetch_new_macau(CONFIG["history_limit"])
    if len(rows) < 10:
        print("数据不足")
        return

    backtest_10(rows)

    print("\n🎯 当前最新预测")
    predictor = SimplePredictor(rows)
    color = predictor.freq("color")
    size = predictor.freq("size")
    odd = predictor.freq("odd")
    hh_pred = predictor.predict_halfhalf()

    print("颜色:", dict(sorted(color.items(), key=lambda x:x[1], reverse=True)))
    print("大小:", size)
    print("单双:", odd)

    print("\n🔥 TOP 6 半波预测:")
    for i, (hh, prob) in enumerate(list(hh_pred.items())[:6], 1):
        print(f"  {i:2d}. {hh}  {prob}%")

    selector = DynamicHalfwaveSelector(color, size)
    bets = selector.select_best(CONFIG["bet_count"])
    print("\n💡 动态半波推荐（颜色分散）:")
    for i, (bw, sc) in enumerate(bets, 1):
        print(f"  {i}. {bw} (得分 {sc:.1f})")

if __name__ == "__main__":
    main()