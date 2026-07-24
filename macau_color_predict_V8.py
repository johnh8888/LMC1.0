#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新澳门彩预测系统 - V9.2（修复版 + 半波类别对齐修复）
修复：半波推荐固定问题，现在会随历史动态变化。
新增：尾数/余数预测 + 参数防过拟合。

本次修复点：
- HALFHALF_CATEGORIES 原来只有6类（如"红大"、"蓝小"），
  但实际数据 halfhalf 字段是12类完整格式（如"红大单"、"蓝小双"）。
  两者格式不一致导致 EnsemblePredictor 对半波的 freq/gap/transition
  永远匹配不到实际值，最终每次都退化成固定顺序输出（"红大,红小"）。
  现已将 HALFHALF_CATEGORIES 改为完整的12类，与 get_halfhalf() 输出对齐。
"""

import re
import json
import urllib.request
import os
from collections import defaultdict

CONFIG = {
    "history_limit": 30,
    "api_url": "https://marksix6.net/index.php?api=1",
    "bet_count": 2,
    "zodiac_bet_count": 3,
    "bet_per_note": 50,
    "cache_file": "newmacau_cache.json",
    "zodiac_year": 2026,

    # ---- 综合版参数（轻度调整）----
    "recency_decay": 0.85,
    "weight_freq": 0.50,
    "weight_gap": 0.20,
    "weight_trans": 0.30,
    "backtest_periods": 20,
}

# 波色定义
RED = {1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE = {3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
GREEN = {5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}

ZODIAC_ORDER = ["鼠","牛","虎","兔","龙","蛇","马","羊","猴","鸡","狗","猪"]
ZODIAC_BASE_YEAR = 2020

# 修复：改为完整的12类（颜色+大小+单双），与 get_halfhalf() 的输出格式对齐
HALFHALF_CATEGORIES = [c + s + o for c in ["红", "蓝", "绿"] for s in ["大", "小"] for o in ["单", "双"]]
TAIL_CATEGORIES = [str(i) for i in range(10)]
MOD3_CATEGORIES = [f"余{i}" for i in range(3)]
MOD4_CATEGORIES = [f"余{i}" for i in range(4)]

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

def get_tail(n):
    return str(n % 10)

def get_mod3(n):
    return f"余{n % 3}"

def get_mod4(n):
    return f"余{n % 4}"

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

    print("🌐 正在获取最新数据...")
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
                        "mod3": get_mod3(special),
                        "mod4": get_mod4(special),
                    })
                break

        rows = list({r["issue"]: r for r in rows}.values())
        rows.sort(key=lambda x: x["issue"], reverse=True)
        with open(CONFIG["cache_file"], "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        return rows[:limit]
    except Exception as e:
        print(f"❌ 获取失败: {e}")
        print("💡 可使用缓存或手动提供历史数据继续运行。")
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

# 修复后的半波选择器（直接用 halfhalf 频率）
class DynamicHalfwaveSelector:
    def __init__(self, rows):
        self.rows = rows[:30]

    def select_best(self, count=2):
        c = defaultdict(int)
        for r in self.rows:
            c[r["halfhalf"]] += 1
        total = sum(c.values()) or 1
        freq = {k: round(v / total * 100, 2) for k, v in c.items()}
        sorted_hw = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return sorted_hw[:count]

class SimpleZodiacSelector:
    def __init__(self, zodiac_pred):
        self.zodiac_pred = zodiac_pred

    def select_best(self, count=3):
        full = {a: self.zodiac_pred.get(a, 0.0) for a in ZODIAC_ORDER}
        return sorted(full.items(), key=lambda x: x[1], reverse=True)[:count]

# EnsemblePredictor（综合版）保持原逻辑
def recency_weighted_freq(rows, key, decay=0.9):
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
    gaps = {}
    for cat in categories:
        gap = len(rows)
        for i, r in enumerate(rows):
            if r[key] == cat:
                gap = i
                break
        gaps[cat] = gap
    return gaps

def gap_score(gaps):
    total = sum(gaps.values()) or 1
    return {k: round(v / total * 100, 2) for k, v in gaps.items()}

def transition_matrix(rows, key):
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
    def __init__(self, rows, categories, key, decay=None, w_freq=None, w_gap=None, w_trans=None):
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

        # 简单版半波（使用修复后的选择器）
        hw_simple_list = DynamicHalfwaveSelector(history).select_best(2)
        hw_simple = [b[0] for b in hw_simple_list]
        zd_simple = [b[0] for b in SimpleZodiacSelector(zod_pred).select_best(3)]

        hw_ens = [b[0] for b in EnsemblePredictor(history, HALFHALF_CATEGORIES, "halfhalf").select_best(2)]
        zd_ens = [b[0] for b in EnsemblePredictor(history, ZODIAC_ORDER, "zodiac").select_best(3)]

        hw_actual = actual["halfhalf"]
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

def main():
    print("=" * 60)
    print("新澳门彩预测系统 - V9.2（半波修复版 + 类别对齐修复）")
    print(f"生肖年份基准: {CONFIG['zodiac_year']}年")
    print("=" * 60)

    rows = fetch_new_macau(CONFIG["history_limit"])
    if len(rows) < 10:
        print("❌ 数据不足")
        return

    run_backtest(rows, CONFIG["backtest_periods"])

    # 当前预测
    sp = SimplePredictor(rows)
    color_pred = sp.freq("color")
    size_pred = sp.freq("size")
    odd_pred = sp.freq("odd")
    zod_pred = sp.freq("zodiac")
    tail_pred = sp.freq("tail")
    mod3_pred = sp.freq("mod3")
    mod4_pred = sp.freq("mod4")

    print("\n🎯 当前最新预测（近30期基础统计）")
    print("颜色:", dict(sorted(color_pred.items(), key=lambda x: x[1], reverse=True)))
    print("大小:", size_pred)
    print("单双:", odd_pred)
    print("尾数:", dict(sorted(tail_pred.items(), key=lambda x: x[1], reverse=True)))
    print("余3:", mod3_pred)
    print("余4:", mod4_pred)

    hw_simple_list = DynamicHalfwaveSelector(rows).select_best(CONFIG["bet_count"])
    hw_ens = EnsemblePredictor(rows, HALFHALF_CATEGORIES, "halfhalf").select_best(CONFIG["bet_count"])
    zd_simple = SimpleZodiacSelector(zod_pred).select_best(CONFIG["zodiac_bet_count"])
    zd_ens = EnsemblePredictor(rows, ZODIAC_ORDER, "zodiac").select_best(CONFIG["zodiac_bet_count"])

    tail_simple = sorted(tail_pred.items(), key=lambda x: x[1], reverse=True)[:4]
    tail_ens = EnsemblePredictor(rows, TAIL_CATEGORIES, "tail").select_best(4)

    print("\n💡 半波推荐")
    print("  简单版:", ", ".join(f"{hw}({s:.1f})" for hw, s in hw_simple_list))
    print("  综合版:", ", ".join(f"{hw}({s:.1f})" for hw, s in hw_ens))

    print("\n💡 生肖推荐")
    print("  简单版:", ", ".join(f"{z}({s:.1f})" for z, s in zd_simple))
    print("  综合版:", ", ".join(f"{z}({s:.1f})" for z, s in zd_ens))

    print("\n💡 尾数推荐")
    print("  简单版:", ", ".join(f"{t}({s:.1f})" for t, s in tail_simple))
    print("  综合版:", ", ".join(f"{t}({s:.1f})" for t, s in tail_ens))

if __name__ == "__main__":
    main()
