#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新澳门彩预测系统 - V9.3（自动窗口调优版）
在 V9.2（半波类别对齐修复版）基础上新增：

1. AutoWindowSelector：自动为“每一期”挑选最优统计窗口长度（如最近15/20/30/40期），
   不再需要手动调 recency_decay / weight_* 这些参数。
   挑选过程本身是"滚动验证"（walk-forward）：
     - 对第 i 期做预测时，只允许用 rows[i+1:]（即该期之前的历史）。
     - 窗口大小的挑选，也只在这段历史内部做"回头验证"，
       绝不触碰第 i 期或更未来的数据 —— 避免用未来信息挑参数（数据泄露/过拟合的最大来源）。
2. 随机基线对照：每类预测都打印"如果瞎猜，命中率应该是多少"，
   方便判断模型是否真的跑赢随机，而不是自己骗自己。
3. 窗口选择分布打印：如果自动窗口在各期之间跳来跳去毫无规律，
   这是过拟合/不稳定的信号，可以直接从输出里看出来。

注意：这是一个统计彩票的历史频率分析工具，开奖机制设计上保证独立随机，
历史数据里不存在可持续利用的规律。这里做的一切"防过拟合"设计，
目的是让回测数字诚实，而不是让预测真的变准。
"""

import re
import json
import urllib.request
import os
from collections import defaultdict, Counter

CONFIG = {
    # 数据量必须能覆盖：回测期数 + 内部验证期数 + 最大窗口候选值 + 一些缓冲
    # 15(验证) + 40(最大窗口) + 20(回测) + 缓冲 ≈ 100，所以整体拉到100期
    "history_limit": 100,
    "api_url": "https://marksix6.net/index.php?api=1",
    "bet_count": 3,
    "zodiac_bet_count": 5,
    "tail_bet_count": 5,
    "bet_per_note": 50,
    "cache_file": "newmacau_cache.json",
    "zodiac_year": 2026,

    # ---- 综合版参数（人工设定，作为对照，不再是唯一方案）----
    "recency_decay": 0.85,
    "weight_freq": 0.50,
    "weight_gap": 0.20,
    "weight_trans": 0.30,
    "backtest_periods": 20,

    # ---- 自动窗口调优参数 ----
    # 候选窗口故意选得比较稀疏、跨度较大，而不是1~100逐一试探。
    # 候选越多、越密，越容易"挑到"历史偶然表现好的窗口，反而更容易过拟合。
    "window_candidates": [10, 15, 20, 25, 30, 40],
    "window_validation_periods": 15,
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

# ---------------------------------------------------------------------------
# 自动窗口调优（替代手动调参）
# ---------------------------------------------------------------------------
def _freq_from_rows(rows, key):
    """
    独立的频率统计函数，不走 SimplePredictor（它内部硬编码只看前30期）。
    自动窗口需要能测试比30更大的窗口候选值，所以单独写一个不设上限的版本。
    """
    c = defaultdict(int)
    for r in rows:
        c[r[key]] += 1
    total = sum(c.values()) or 1
    return {k: round(v / total * 100, 2) for k, v in c.items()}

class AutoWindowSelector:
    """
    对每一期预测，自动挑选最优统计窗口长度（数据窗口的“期数”），
    以此取代人工反复试参数。

    关键防泄露设计：
    - predict(history) 传入的 history 必须是"该期之前"的历史数据（不含当期和未来）。
    - 窗口挑选的验证过程（_window_hit_rate）同样只在 history 内部往回看，
      不会借用 history 之外（也就是当期或未来）的任何信息。
    - 打平分时优先选更大的窗口（更多数据、更稳定，不容易被短期偶然波动带偏）。
    """
    def __init__(self, key, categories, bet_count, candidates=None, validation_periods=None):
        self.key = key
        self.categories = categories
        self.bet_count = bet_count
        self.candidates = candidates or CONFIG["window_candidates"]
        self.validation_periods = validation_periods or CONFIG["window_validation_periods"]

    def _window_hit_rate(self, history, w):
        hits = 0
        count = 0
        for j in range(self.validation_periods):
            # j 期的"过去"是 history[j+1 : j+1+w]，j 期本身是 history[j]
            # 全部严格取自 history 内部更早的数据，不接触 history 之外的任何一期
            if j + 1 + w > len(history):
                break
            actual = history[j]
            window_data = history[j + 1: j + 1 + w]
            freq = _freq_from_rows(window_data, self.key)
            top = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:self.bet_count]
            top_cats = [t[0] for t in top]
            if actual[self.key] in top_cats:
                hits += 1
            count += 1
        return (hits / count) if count > 0 else None

    def select_window(self, history):
        scores = {}
        for w in self.candidates:
            s = self._window_hit_rate(history, w)
            if s is not None:
                scores[w] = s
        if not scores:
            # 数据不够验证任何窗口，退回一个保守默认值
            fallback = max(w for w in self.candidates if w <= len(history)) if history else self.candidates[0]
            return fallback, {}
        best_score = max(scores.values())
        # 打平分时选更大的窗口：更稳定，减少"刚好蒙对"式的过拟合
        tied = [w for w, s in scores.items() if s == best_score]
        return max(tied), scores

    def predict(self, history):
        best_window, scores = self.select_window(history)
        window_data = history[:best_window]
        freq = _freq_from_rows(window_data, self.key)
        top = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:self.bet_count]
        return best_window, top, scores

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
    aw_hw_hits = aw_zd_hits = aw_tail_hits = 0
    aw_hw_windows, aw_zd_windows, aw_tail_windows = [], [], []

    for i in range(total):
        history = rows[i + 1:]
        actual = rows[i]

        sp = SimplePredictor(history)
        color_pred, size_pred, zod_pred = sp.freq("color"), sp.freq("size"), sp.freq("zodiac")

        # 简单版半波（使用修复后的选择器）
        hw_simple_list = DynamicHalfwaveSelector(history).select_best(CONFIG["bet_count"])
        hw_simple = [b[0] for b in hw_simple_list]
        zd_simple = [b[0] for b in SimpleZodiacSelector(zod_pred).select_best(CONFIG["zodiac_bet_count"])]

        hw_ens = [b[0] for b in EnsemblePredictor(history, HALFHALF_CATEGORIES, "halfhalf").select_best(CONFIG["bet_count"])]
        zd_ens = [b[0] for b in EnsemblePredictor(history, ZODIAC_ORDER, "zodiac").select_best(CONFIG["zodiac_bet_count"])]

        hw_actual = actual["halfhalf"]
        hw_s_hit = hw_actual in hw_simple
        hw_e_hit = hw_actual in hw_ens
        zd_s_hit = actual["zodiac"] in zd_simple
        zd_e_hit = actual["zodiac"] in zd_ens

        hw_simple_hits += hw_s_hit
        hw_ens_hits += hw_e_hit
        zd_simple_hits += zd_s_hit
        zd_ens_hits += zd_e_hit

        # ---- 自动窗口版（只用 history，即第 i 期之前的数据，挑窗口+做预测）----
        aw_hw_window, aw_hw_top, _ = AutoWindowSelector("halfhalf", HALFHALF_CATEGORIES, CONFIG["bet_count"]).predict(history)
        aw_zd_window, aw_zd_top, _ = AutoWindowSelector("zodiac", ZODIAC_ORDER, CONFIG["zodiac_bet_count"]).predict(history)
        aw_tail_window, aw_tail_top, _ = AutoWindowSelector("tail", TAIL_CATEGORIES, CONFIG["tail_bet_count"]).predict(history)

        aw_hw_cats = [c for c, _ in aw_hw_top]
        aw_zd_cats = [c for c, _ in aw_zd_top]
        aw_tail_cats = [c for c, _ in aw_tail_top]

        aw_hw_hits += actual["halfhalf"] in aw_hw_cats
        aw_zd_hits += actual["zodiac"] in aw_zd_cats
        aw_tail_hits += actual["tail"] in aw_tail_cats

        aw_hw_windows.append(aw_hw_window)
        aw_zd_windows.append(aw_zd_window)
        aw_tail_windows.append(aw_tail_window)

        print(f"{actual['issue']:<12} {actual['halfhalf']:<8} {actual['zodiac']:<6} "
              f"{','.join(hw_simple):<14}{'✓' if hw_s_hit else '✗':<3} "
              f"{','.join(hw_ens):<14}{'✓' if hw_e_hit else '✗':<3} "
              f"{','.join(zd_simple):<16}{'✓' if zd_s_hit else '✗':<3} "
              f"{','.join(zd_ens):<16}{'✓' if zd_e_hit else '✗':<3}")

    print("-" * 118)
    print(f"半波命中率  简单版: {hw_simple_hits}/{total} = {hw_simple_hits/total*100:.1f}%   "
          f"综合版: {hw_ens_hits}/{total} = {hw_ens_hits/total*100:.1f}%   "
          f"自动窗口版: {aw_hw_hits}/{total} = {aw_hw_hits/total*100:.1f}%")
    print(f"生肖命中率  简单版: {zd_simple_hits}/{total} = {zd_simple_hits/total*100:.1f}%   "
          f"综合版: {zd_ens_hits}/{total} = {zd_ens_hits/total*100:.1f}%   "
          f"自动窗口版: {aw_zd_hits}/{total} = {aw_zd_hits/total*100:.1f}%")
    print(f"尾数命中率  自动窗口版: {aw_tail_hits}/{total} = {aw_tail_hits/total*100:.1f}%")

    # 随机基线：如果瞎猜，理论命中率应该是多少（用于判断是否真的跑赢随机）
    hw_baseline = CONFIG["bet_count"] / len(HALFHALF_CATEGORIES) * 100
    zd_baseline = CONFIG["zodiac_bet_count"] / len(ZODIAC_ORDER) * 100
    tail_baseline = CONFIG["tail_bet_count"] / len(TAIL_CATEGORIES) * 100
    print(f"\n📐 随机基线对照（瞎猜的理论命中率，命中率若长期贴近甚至低于这个数，说明模型没有实际预测力）")
    print(f"半波随机基线: {CONFIG['bet_count']}/{len(HALFHALF_CATEGORIES)} = {hw_baseline:.1f}%")
    print(f"生肖随机基线: {CONFIG['zodiac_bet_count']}/{len(ZODIAC_ORDER)} = {zd_baseline:.1f}%")
    print(f"尾数随机基线: {CONFIG['tail_bet_count']}/{len(TAIL_CATEGORIES)} = {tail_baseline:.1f}%")

    # 窗口选择分布：如果窗口在各期之间跳来跳去毫无规律，是不稳定/过拟合的信号
    print(f"\n🔍 自动窗口选择分布（越集中越稳定，越分散越可能是噪声驱动）")
    print(f"半波窗口分布: {dict(sorted(Counter(aw_hw_windows).items()))}")
    print(f"生肖窗口分布: {dict(sorted(Counter(aw_zd_windows).items()))}")
    print(f"尾数窗口分布: {dict(sorted(Counter(aw_tail_windows).items()))}")

def main():
    print("=" * 60)
    print("新澳门彩预测系统 - V9.3（自动窗口调优版）")
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

    tail_simple = sorted(tail_pred.items(), key=lambda x: x[1], reverse=True)[:CONFIG["tail_bet_count"]]
    tail_ens = EnsemblePredictor(rows, TAIL_CATEGORIES, "tail").select_best(CONFIG["tail_bet_count"])

    # 自动窗口版最终预测（用全部可用历史 rows 挑一次窗口，再输出）
    aw_hw_window, aw_hw_top, _ = AutoWindowSelector("halfhalf", HALFHALF_CATEGORIES, CONFIG["bet_count"]).predict(rows)
    aw_zd_window, aw_zd_top, _ = AutoWindowSelector("zodiac", ZODIAC_ORDER, CONFIG["zodiac_bet_count"]).predict(rows)
    aw_tail_window, aw_tail_top, _ = AutoWindowSelector("tail", TAIL_CATEGORIES, CONFIG["tail_bet_count"]).predict(rows)

    print("\n💡 半波推荐")
    print("  简单版:", ", ".join(f"{hw}({s:.1f})" for hw, s in hw_simple_list))
    print("  综合版:", ", ".join(f"{hw}({s:.1f})" for hw, s in hw_ens))
    print(f"  自动窗口版(窗口={aw_hw_window}期):", ", ".join(f"{hw}({s:.1f})" for hw, s in aw_hw_top))

    print("\n💡 生肖推荐")
    print("  简单版:", ", ".join(f"{z}({s:.1f})" for z, s in zd_simple))
    print("  综合版:", ", ".join(f"{z}({s:.1f})" for z, s in zd_ens))
    print(f"  自动窗口版(窗口={aw_zd_window}期):", ", ".join(f"{z}({s:.1f})" for z, s in aw_zd_top))

    print("\n💡 尾数推荐")
    print("  简单版:", ", ".join(f"{t}({s:.1f})" for t, s in tail_simple))
    print("  综合版:", ", ".join(f"{t}({s:.1f})" for t, s in tail_ens))
    print(f"  自动窗口版(窗口={aw_tail_window}期):", ", ".join(f"{t}({s:.1f})" for t, s in aw_tail_top))

if __name__ == "__main__":
    main()