#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新澳门彩预测系统 - 简化重构版 V2
- 移除过度优化，保留核心逻辑
- 更好的错误处理和数据缓存
- 动态半波 + 颜色分散
"""

import re
import json
import urllib.request
import random
from collections import defaultdict
from datetime import datetime
import os

# =====================================================
# 配置
# =====================================================

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

# =====================================================
# 数据获取与缓存
# =====================================================

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

    print("正在从网络获取数据...")
    try:
        req = urllib.request.Request(
            CONFIG["api_url"],
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        rows = []
        for item in data.get("lottery_data", []):
            if item.get("name", "").strip() == "新澳门彩":
                for line in item.get("history", []):
                    nums = parse_numbers(line)
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
        print("⚠️ 使用缓存数据...")
        return cached[:limit]

# =====================================================
# 简化预测模型
# =====================================================

class SimplePredictor:
    def __init__(self, rows):
        self.rows = rows[:30]

    def _frequency(self, key):
        count = defaultdict(int)
        for r in self.rows:
            count[r[key]] += 1
        total = sum(count.values()) or 1
        return {k: round(v / total * 100, 2) for k, v in count.items()}

    def _trend(self, key, recent=15):
        score = defaultdict(float)
        for i, r in enumerate(self.rows[:recent]):
            weight = (recent - i) * 0.5
            score[r[key]] += weight
        total = sum(score.values()) or 1
        return {k: round(v / total * 100, 2) for k, v in score.items()}

    def predict_color(self):
        return self._frequency("color")

    def predict_size(self):
        return self._frequency("size")

    def predict_odd(self):
        return self._frequency("odd")

    def predict_halfhalf(self):
        freq = self._frequency("halfhalf")
        trend = self._trend("halfhalf")
        combined = defaultdict(float)
        for k in freq:
            combined[k] = freq.get(k, 0) * 0.6 + trend.get(k, 0) * 0.4
        total = sum(combined.values()) or 1
        return {k: round(v / total * 100, 2) for k, v in combined.items()}

# =====================================================
# 动态半波选择器
# =====================================================

class DynamicHalfwaveSelector:
    def __init__(self, color_pred, size_pred):
        self.color_pred = color_pred
        self.size_pred = size_pred

    def select_best(self, count=2):
        scores = {}
        for c in ["红", "蓝", "绿"]:
            for s in ["大", "小"]:
                c_score = self.color_pred.get(c, 33.3)
                s_score = self.size_pred.get(s, 50)
                scores[c + s] = c_score * 0.5 + s_score * 0.5

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        result = []
        used_colors = set()
        for hw, score in sorted_scores:
            color = hw[0]
            if color not in used_colors:
                result.append((hw, score))
                used_colors.add(color)
            if len(result) >= count:
                break
        return result[:count]

    def print_recommendation(self, bets):
        print("\n" + "="*50)
        print("🎯 动态半波推荐 (颜色分散优化)")
        print("="*50)
        for i, (bw, score) in enumerate(bets, 1):
            print(f"  {i}. {bw}  (得分: {score:.1f})")
        print(f"\n💰 建议每注 {CONFIG['bet_per_note']}元，共 {len(bets)} 注")

# =====================================================
# 主程序
# =====================================================

def main():
    print("="*60)
    print("新澳门彩预测系统 - 简化重构版 V2")
    print("="*60)

    rows = fetch_new_macau(CONFIG["history_limit"])

    if len(rows) < 8:
        print("❌ 数据不足，无法预测。请检查网络或手动添加缓存。")
        return

    print(f"✅ 成功加载 {len(rows)} 期数据")

    predictor = SimplePredictor(rows)
    color_pred = predictor.predict_color()
    size_pred = predictor.predict_size()
    odd_pred = predictor.predict_odd()

    hh_scores = predictor.predict_halfhalf()
    candidates = sorted(hh_scores.items(), key=lambda x: x[1], reverse=True)[:5]

    print("\n颜色预测:", dict(sorted(color_pred.items(), key=lambda x: x[1], reverse=True)))
    print("大小预测:", size_pred)
    print("单双预测:", odd_pred)

    print("\nTOP5 半波预测:")
    for i, (hh, score) in enumerate(candidates, 1):
        print(f"  {i}. {hh} ({score}%)")

    selector = DynamicHalfwaveSelector(color_pred, size_pred)
    bets = selector.select_best(count=CONFIG["bet_count"])
    selector.print_recommendation(bets)

    # 保存报告
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("# 新澳门彩 简化预测报告\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## 预测结果\n")
        f.write(str({"color": color_pred, "size": size_pred, "candidates": candidates}))

    print(f"\n📄 报告已保存: {REPORT_FILE}")

if __name__ == "__main__":
    main()