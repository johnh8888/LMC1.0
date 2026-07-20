#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新澳门彩预测系统 - 综合预测版
在原有"简单频率"预测基础上，新增：
  1. 近期加权频率（recency-weighted frequency）—— 越近的期数权重越高
  2. 遗漏值分析（gap analysis）—— 距上次出现的期数
  3. 状态转移概率（一阶马尔可夫）—— 上一期结果 -> 下一期结果 的历史概率
三者加权融合成"综合版"预测，并与原"简单版"在回测中对比命中率。

⚠️ 说明：遗漏值回补是经验性假设，并非统计学定律（各期开奖理论上独立）。
   这里的"综合版"目的是给你一个可回测、可调参的框架，而非保证提升胜率。
   真正是否有效，以下方回测的命中率对比为准。
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
    "zodiac_bet_count": 3,
    "bet_per_note": 50,
    "cache_file": "newmacau_cache.json",
    "zodiac_year": 2026,

    # ---- 综合版参数（可自行调参，配合下方回测对比效果）----
    "recency_decay": 0.90,   # 时间衰减系数：越接近1，各期权重越平均；越小，越偏重最近几期
    "weight_freq": 0.45,     # 近期加权频率 权重
    "weight_gap": 0.25,      # 遗漏值      权重
    "weight_trans": 0.30,    # 状态转移概率 权重
    "backtest_periods": 20,  # 回测期数（原版为10，调大以获得更可靠的统计）
}

# 波色定义
RED = {1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE = {3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
GREEN = {5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}

# 生肖顺序（鼠年为基准，2020年 = 鼠年）
ZODIAC_ORDER = ["鼠","牛","虎","兔","龙","蛇","马","羊","猴","鸡","狗","猪"]
ZODIAC_BASE_YEAR = 2020

HALFHALF_CATEGORIES = [c + s for c in ["红", "蓝", "绿"] for s in ["大", "小"]]

def build_zodiac_map(year):
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

# ============================================================
# 简单版：基础频率统计（原版逻辑，保留作为对照基线）
# ============================================================

class SimplePredictor:
    def __init__(self, rows):
        self.rows = rows[:30]

    def freq(self, key):
        c = defaultdict(int)
        for r in self.rows:
            c[r[key]] += 1
        total = sum(c.values()) or 1
        return {k: round(v / total * 100, 2) for k, v in c.items()}

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
        result, used = [], set()
        for hw, score in sorted_scores:
            color = hw[0]
            if color not in used:
                result.append((hw, score))
                used.add(color)
            if len(result) >= count:
                break
        return result[:count]

class SimpleZodiacSelector:
    def __init__(self, zodiac_pred):
        self.zodiac_pred = zodiac_pred

    def select_best(self, count=3):
        full = {a: self.zodiac_pred.get(a, 0.0) for a in ZODIAC_ORDER}
        return sorted(full.items(), key=lambda x: x[1], reverse=True)[:count]

# ============================================================
# 综合版：近期加权频率 + 遗漏值 + 状态转移 的融合预测器
# ============================================================

def recency_weighted_freq(rows, key, decay=0.9):
    """rows[0] 为最近一期；越靠前权重越高"""
    scores = defaultdict(float)
    total_weight = 0.0
    for i, r in enumerate(rows):
        w = decay ** i
        scores[r[key]] += w
        total_weight += w
    if total_weight == 0:
        return {}
    return {k: round(v / total_weight * 100, 2) for k, v in scores.items()}

def gap_map(rows, key, categories):
    """每个类别距上次出现的期数（0=上一期刚出现，值越大遗漏越久）"""
    gaps = {}
    for cat in categories:
        gap = len(rows)  # 从未出现，取样本长度
        for i, r in enumerate(rows):
            if r[key] == cat:
                gap = i
                break
        gaps[cat] = gap
    return gaps

def gap_score(gaps):
    """遗漏值越大分数越高（回补倾向，经验假设）"""
    total = sum(gaps.values()) or 1
    return {k: round(v / total * 100, 2) for k, v in gaps.items()}

def transition_matrix(rows, key):
    """一阶马尔可夫转移表：较旧一期的值 -> 较新一期的值"""
    trans = defaultdict(lambda: defaultdict(int))
    for i in range(len(rows) - 1):
        prev_val = rows[i + 1][key]
        next_val = rows[i][key]
        trans[prev_val][next_val] += 1
    return trans

def transition_predict(trans, last_value, categories):
    row = trans.get(last_value, {})
    total = sum(row.values())
    if total == 0:
        n = len(categories) or 1
        return {c: round(100 / n, 2) for c in categories}
    return {c: round(row.get(c, 0) / total * 100, 2) for c in categories}

class EnsemblePredictor:
    """结合近期加权频率 + 遗漏值 + 状态转移概率 的综合评分器（适用于任意分类字段）"""
    def __init__(self, rows, categories, key,
                 decay=None, w_freq=None, w_gap=None, w_trans=None):
        self.rows = rows
        self.categories = categories
        self.key = key
        self.decay = decay if decay is not None else CONFIG["recency_decay"]
        self.w_freq = w_freq if w_freq is not None else CONFIG["weight_freq"]
        self.w_gap = w_gap if w_gap is not None else CONFIG["weight_gap"]
        self.w_trans = w_trans if w_trans is not None else CONFIG["weight_trans"]

    def score(self):
        if not self.rows:
            n = len(self.categories) or 1
            return {c: round(100 / n, 2) for c in self.categories}

        freq = recency_weighted_freq(self.rows, self.key, self.decay)
        gaps = gap_map(self.rows, self.key, self.categories)
        gscore = gap_score(gaps)
        trans = transition_matrix(self.rows, self.key)
        last_value = self.rows[0][self.key]
        tpred = transition_predict(trans, last_value, self.categories)

        result = {}
        for c in self.categories:
            f = freq.get(c, 0.0)
            g = gscore.get(c, 0.0)
            t = tpred.get(c, 0.0)
            result[c] = round(f * self.w_freq + g * self.w_gap + t * self.w_trans, 2)
        return result

    def select_best(self, count=3):
        s = self.score()
        return sorted(s.items(), key=lambda x: x[1], reverse=True)[:count]

# ============================================================
# 回测：简单版 vs 综合版
# ============================================================

def run_backtest(rows, periods):
    total = min(periods, len(rows) - 1)
    if total <= 0:
        print("❌ 数据不足以回测")
        return

    print(f"\n📊 详细回测（简单版 vs 综合版，共{total}期）")
    print("=" * 118)
    header = (f"{'期号':<12} {'实际':<8} {'实际生肖':<6} "
              f"{'简单半波':<14}{'✓':<3} {'综合半波':<14}{'✓':<3} "
              f"{'简单生肖':<16}{'✓':<3} {'综合生肖':<16}{'✓':<3}")
    print(header)
    print("-" * 118)

    hw_simple_hits = hw_ens_hits = zd_simple_hits = zd_ens_hits = 0

    for i in range(total):
        history = rows[i + 1:]
        actual = rows[i]

        sp = SimplePredictor(history)
        color_pred, size_pred, zod_pred = sp.freq("color"), sp.freq("size"), sp.freq("zodiac")

        # 简单版
        hw_simple = [b[0] for b in DynamicHalfwaveSelector(color_pred, size_pred).select_best(2)]
        zd_simple = [b[0] for b in SimpleZodiacSelector(zod_pred).select_best(3)]

        # 综合版
        hw_ens = [b[0] for b in EnsemblePredictor(history, HALFHALF_CATEGORIES, "halfhalf").select_best(2)]
        zd_ens = [b[0] for b in EnsemblePredictor(history, ZODIAC_ORDER, "zodiac").select_best(3)]

        hw_actual = actual["color"] + actual["size"]
        hw_s_hit = hw_actual in hw_simple
        hw_e_hit = hw_actual in hw_ens
        zd_s_hit = actual["zodiac"] in zd_simple
        zd_e_hit = actual["zodiac"] in zd_ens

        hw_simple_hits += hw_s_hit
        hw_ens_hits += hw_e_hit
        zd_simple_hits += zd_s_hit
        zd_ens_hits += zd_e_hit

        print(f"{actual['issue']:<12} {actual['halfhalf']:<8} {actual['zodiac']:<6} "
              f"{','.join(hw_simple):<14}{'✓' if hw_s_hit else '✗':<3} "
              f"{','.join(hw_ens):<14}{'✓' if hw_e_hit else '✗':<3} "
              f"{','.join(zd_simple):<16}{'✓' if zd_s_hit else '✗':<3} "
              f"{','.join(zd_ens):<16}{'✓' if zd_e_hit else '✗':<3}")

    print("-" * 118)
    print(f"半波命中率  简单版: {hw_simple_hits}/{total} = {hw_simple_hits/total*100:.1f}%   "
          f"综合版: {hw_ens_hits}/{total} = {hw_ens_hits/total*100:.1f}%")
    print(f"生肖命中率  简单版: {zd_simple_hits}/{total} = {zd_simple_hits/total*100:.1f}%   "
          f"综合版: {zd_ens_hits}/{total} = {zd_ens_hits/total*100:.1f}%")
    print("\n💡 请以上方命中率对比为准来决定采用简单版还是综合版；")
    print("   也可以调整 CONFIG 中的 recency_decay / weight_freq / weight_gap / weight_trans 后重新回测。")

def main():
    print("=" * 60)
    print("新澳门彩预测系统 - 综合预测版")
    print(f"生肖年份基准: {CONFIG['zodiac_year']}年")
    print("=" * 60)

    rows = fetch_new_macau(CONFIG["history_limit"])
    if len(rows) < 10:
        print("❌ 数据不足")
        return

    run_backtest(rows, CONFIG["backtest_periods"])

    # ---- 当前预测 ----
    sp = SimplePredictor(rows)
    color_pred, size_pred, odd_pred, zod_pred = sp.freq("color"), sp.freq("size"), sp.freq("odd"), sp.freq("zodiac")

    print("\n🎯 当前最新预测（近30期基础统计）")
    print("颜色:", dict(sorted(color_pred.items(), key=lambda x: x[1], reverse=True)))
    print("大小:", size_pred)
    print("单双:", odd_pred)

    hw_simple = DynamicHalfwaveSelector(color_pred, size_pred).select_best(CONFIG["bet_count"])
    hw_ens = EnsemblePredictor(rows, HALFHALF_CATEGORIES, "halfhalf").select_best(CONFIG["bet_count"])
    zd_simple = SimpleZodiacSelector(zod_pred).select_best(CONFIG["zodiac_bet_count"])
    zd_ens = EnsemblePredictor(rows, ZODIAC_ORDER, "zodiac").select_best(CONFIG["zodiac_bet_count"])

    print("\n💡 半波推荐")
    print("  简单版:", ", ".join(f"{hw}({s:.1f})" for hw, s in hw_simple))
    print("  综合版:", ", ".join(f"{hw}({s:.1f})" for hw, s in hw_ens))

    print("\n💡 生肖推荐")
    print("  简单版:", ", ".join(f"{z}({s:.1f})" for z, s in zd_simple))
    print("  综合版:", ", ".join(f"{z}({s:.1f})" for z, s in zd_ens))

if __name__ == "__main__":
    main()
