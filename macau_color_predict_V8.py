#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新澳门彩预测系统 - 增强分析版
新增：
  1. 滑动窗口回测（不同时间段验证稳定性）
  2. 单双预测（新增维度）
  3. 预测置信度评估
  4. 连续命中/失误追踪
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
    "zodiac_bet_count": 3,
    "cache_file": "newmacau_cache.json",
    "zodiac_year": 2026,

    # 基础参数
    "recency_decay": 0.85,
    "weight_freq": 0.50,
    "weight_gap": 0.15,
    "weight_trans": 0.35,
    
    # 回测配置
    "test_periods": 10,
    "min_history_for_predict": 20,
}

RED = {1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE = {3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
GREEN = {5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}

ZODIAC_ORDER = ["鼠","牛","虎","兔","龙","蛇","马","羊","猴","鸡","狗","猪"]
ZODIAC_BASE_YEAR = 2020
HALFHALF_CATEGORIES = [c + s for c in ["红", "蓝", "绿"] for s in ["大", "小"]]
ODD_CATEGORIES = ["单", "双"]

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

# ========== 预测器 ==========
class SimplePredictor:
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

    def predict_zodiac(self, count=3):
        zod_pred = self.freq("zodiac")
        full = {a: zod_pred.get(a, 0.0) for a in ZODIAC_ORDER}
        return sorted(full.items(), key=lambda x: x[1], reverse=True)[:count]
    
    def predict_odd(self):
        odd_pred = self.freq("odd")
        return sorted(odd_pred.items(), key=lambda x: x[1], reverse=True)

def recency_weighted_freq(history, key, decay=0.85):
    scores = defaultdict(float)
    total_weight = 0.0
    for i, r in enumerate(history):
        w = decay ** i
        scores[r[key]] += w
        total_weight += w
    if total_weight == 0:
        return {}
    return {k: round(v / total_weight * 100, 2) for k, v in scores.items()}

def gap_analysis(history, key, categories):
    gaps = {}
    for cat in categories:
        gap = None
        for i, r in enumerate(history):
            if r[key] == cat:
                gap = i
                break
        gaps[cat] = gap if gap is not None else int(len(history) * 1.5)
    return gaps

def gap_to_score(gaps):
    if not gaps:
        return {}
    max_gap = max(gaps.values()) + 1
    scores = {}
    for cat, gap in gaps.items():
        normalized = gap / max_gap
        scores[cat] = round(normalized ** 0.5 * 100, 2)
    return scores

def transition_analysis(history, key):
    trans = defaultdict(lambda: defaultdict(int))
    for i in range(len(history) - 1):
        prev_val = history[i + 1][key]
        next_val = history[i][key]
        trans[prev_val][next_val] += 1
    return trans

def transition_predict(trans, last_value, categories):
    row = trans.get(last_value, {})
    total = sum(row.values())
    if total == 0:
        n = len(categories)
        return {c: round(100/n, 2) for c in categories}
    return {c: round(row.get(c, 0) / total * 100, 2) for c in categories}

class EnsemblePredictor:
    def __init__(self, history, categories, key,
                 decay=0.85, w_freq=0.50, w_gap=0.15, w_trans=0.35):
        self.history = history
        self.categories = categories
        self.key = key
        self.decay = decay
        self.w_freq = w_freq
        self.w_gap = w_gap
        self.w_trans = w_trans

    def score(self):
        if len(self.history) < 5:
            n = len(self.categories)
            return {c: round(100/n, 2) for c in self.categories}

        freq = recency_weighted_freq(self.history, self.key, self.decay)
        gaps = gap_analysis(self.history, self.key, self.categories)
        gscore = gap_to_score(gaps)
        trans = transition_analysis(self.history, self.key)
        last_value = self.history[0][self.key]
        tpred = transition_predict(trans, last_value, self.categories)

        result = {}
        for c in self.categories:
            f = freq.get(c, 0.0)
            g = gscore.get(c, 0.0)
            t = tpred.get(c, 0.0)
            result[c] = round(f * self.w_freq + g * self.w_gap + t * self.w_trans, 2)
        return result

    def predict(self, count=3):
        s = self.score()
        return sorted(s.items(), key=lambda x: x[1], reverse=True)[:count]
    
    def confidence(self, top_count=2):
        """计算预测置信度：前N名与后面的分数差距"""
        s = self.score()
        sorted_s = sorted(s.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_s) <= top_count:
            return 0.0
        top_avg = sum(x[1] for x in sorted_s[:top_count]) / top_count
        rest_avg = sum(x[1] for x in sorted_s[top_count:]) / (len(sorted_s) - top_count)
        if rest_avg == 0:
            return 100.0
        confidence = (top_avg - rest_avg) / top_avg * 100
        return round(max(0, min(100, confidence)), 1)

# ========== 滑动窗口回测 ==========
def sliding_window_backtest(all_rows, window_size=10, step=5, min_history=20):
    """
    滑动窗口回测：测试模型在不同时间段的稳定性
    """
    if len(all_rows) < min_history + window_size:
        print("❌ 数据不足以进行滑动窗口回测")
        return []
    
    results = []
    start = 0
    while start + window_size + min_history <= len(all_rows):
        test_set = all_rows[start:start + window_size]
        
        hw_hits = 0
        zd_hits = 0
        valid = 0
        
        for i, test_row in enumerate(test_set):
            history = all_rows[start + i + 1:start + i + 1 + min_history]
            if len(history) < min_history:
                continue
            
            # 综合版预测
            ensemble_hw = [x[0] for x in EnsemblePredictor(
                history, HALFHALF_CATEGORIES, "halfhalf",
                decay=CONFIG["recency_decay"],
                w_freq=CONFIG["weight_freq"],
                w_gap=CONFIG["weight_gap"],
                w_trans=CONFIG["weight_trans"]
            ).predict(CONFIG["bet_count"])]
            
            ensemble_zd = [x[0] for x in EnsemblePredictor(
                history, ZODIAC_ORDER, "zodiac",
                decay=CONFIG["recency_decay"],
                w_freq=CONFIG["weight_freq"],
                w_gap=CONFIG["weight_gap"],
                w_trans=CONFIG["weight_trans"]
            ).predict(CONFIG["zodiac_bet_count"])]
            
            if test_row["halfhalf"] in ensemble_hw:
                hw_hits += 1
            if test_row["zodiac"] in ensemble_zd:
                zd_hits += 1
            valid += 1
        
        if valid > 0:
            results.append({
                "start_issue": test_set[-1]["issue"],
                "end_issue": test_set[0]["issue"],
                "hw_rate": hw_hits / valid,
                "zd_rate": zd_hits / valid,
                "avg_rate": (hw_hits + zd_hits) / (2 * valid),
            })
        
        start += step
    
    return results

# ========== 主回测 ==========
def strict_backtest(all_rows, test_periods=10, min_history=20):
    if len(all_rows) < min_history + test_periods:
        print(f"❌ 数据不足")
        return None
    
    test_set = all_rows[:test_periods]
    
    print(f"\n{'='*80}")
    print(f"📊 严格回测：最近{test_periods}期")
    print(f"{'='*80}")
    
    header = (f"{'期号':<12} {'实际':<10} {'简单半波':<16} {'✓':<4} "
              f"{'综合半波':<16} {'✓':<4} {'信':<5} "
              f"{'简单生肖':<16} {'✓':<4} {'综合生肖':<16} {'✓':<4}")
    print(header)
    print("-" * 110)
    
    simple_hw_hits = 0
    ensemble_hw_hits = 0
    simple_zd_hits = 0
    ensemble_zd_hits = 0
    odd_hits = 0
    
    for i, test_row in enumerate(test_set):
        history = all_rows[test_periods - i:]
        
        if len(history) < min_history:
            continue
        
        # 预测
        simple = SimplePredictor(history)
        simple_hw = [x[0] for x in simple.predict_halfhalf(CONFIG["bet_count"])]
        simple_zd = [x[0] for x in simple.predict_zodiac(CONFIG["zodiac_bet_count"])]
        
        ensemble_hw_pred = EnsemblePredictor(
            history, HALFHALF_CATEGORIES, "halfhalf",
            decay=CONFIG["recency_decay"],
            w_freq=CONFIG["weight_freq"],
            w_gap=CONFIG["weight_gap"],
            w_trans=CONFIG["weight_trans"]
        )
        ensemble_zd_pred = EnsemblePredictor(
            history, ZODIAC_ORDER, "zodiac",
            decay=CONFIG["recency_decay"],
            w_freq=CONFIG["weight_freq"],
            w_gap=CONFIG["weight_gap"],
            w_trans=CONFIG["weight_trans"]
        )
        
        ensemble_hw = [x[0] for x in ensemble_hw_pred.predict(CONFIG["bet_count"])]
        ensemble_zd = [x[0] for x in ensemble_zd_pred.predict(CONFIG["zodiac_bet_count"])]
        
        # 置信度
        confidence = ensemble_hw_pred.confidence(CONFIG["bet_count"])
        
        # 实际结果
        actual_hw = test_row["halfhalf"]
        actual_zd = test_row["zodiac"]
        actual_full = f"{actual_hw}({test_row['odd']})"
        
        # 判断
        sh_hit = actual_hw in simple_hw
        eh_hit = actual_hw in ensemble_hw
        sz_hit = actual_zd in simple_zd
        ez_hit = actual_zd in ensemble_zd
        
        simple_hw_hits += sh_hit
        ensemble_hw_hits += eh_hit
        simple_zd_hits += sz_hit
        ensemble_zd_hits += ez_hit
        
        print(f"{test_row['issue']:<12} {actual_full:<10} "
              f"{','.join(simple_hw):<16} {'✓' if sh_hit else '✗':<4} "
              f"{','.join(ensemble_hw):<16} {'✓' if eh_hit else '✗':<4} "
              f"{confidence:>4.0f}% "
              f"{','.join(simple_zd):<16} {'✓' if sz_hit else '✗':<4} "
              f"{','.join(ensemble_zd):<16} {'✓' if ez_hit else '✗':<4}")
    
    n = len(test_set)
    print("-" * 110)
    
    print(f"\n📈 命中率统计（{n}期）：")
    print(f"  {'类别':<10} {'简单版':<12} {'综合版':<12} {'差值':<10}")
    print(f"  {'半波':<10} {simple_hw_hits/n*100:>6.1f}%     {ensemble_hw_hits/n*100:>6.1f}%     {('+' if ensemble_hw_hits > simple_hw_hits else '')}{ensemble_hw_hits - simple_hw_hits:>+d}期")
    print(f"  {'生肖':<10} {simple_zd_hits/n*100:>6.1f}%     {ensemble_zd_hits/n*100:>6.1f}%     {('+' if ensemble_zd_hits > simple_zd_hits else '')}{ensemble_zd_hits - simple_zd_hits:>+d}期")
    
    return {
        "simple_hw": simple_hw_hits/n,
        "ensemble_hw": ensemble_hw_hits/n,
        "simple_zd": simple_zd_hits/n,
        "ensemble_zd": ensemble_zd_hits/n,
    }

# ========== 主函数 ==========
def main():
    print("=" * 60)
    print("新澳门彩预测系统 - 增强分析版")
    print(f"生肖年份基准: {CONFIG['zodiac_year']}年")
    print("=" * 60)
    
    all_rows = fetch_new_macau(CONFIG["history_limit"])
    if len(all_rows) < CONFIG["min_history_for_predict"] + CONFIG["test_periods"]:
        print(f"❌ 数据不足")
        return
    
    # 严格回测
    results = strict_backtest(all_rows, CONFIG["test_periods"], CONFIG["min_history_for_predict"])
    
    # 滑动窗口回测
    print(f"\n{'='*60}")
    print(f"📊 滑动窗口回测（稳定性检验）")
    print(f"{'='*60}")
    window_results = sliding_window_backtest(all_rows, 10, 5, CONFIG["min_history_for_predict"])
    
    if window_results:
        print(f"\n{'窗口':<20} {'半波命中':<10} {'生肖命中':<10} {'平均命中':<10}")
        print("-" * 50)
        for wr in window_results:
            print(f"{wr['start_issue']}~{wr['end_issue']:<8} "
                  f"{wr['hw_rate']*100:>6.1f}%    {wr['zd_rate']*100:>6.1f}%    {wr['avg_rate']*100:>6.1f}%")
        
        hw_rates = [w['hw_rate'] for w in window_results]
        zd_rates = [w['zd_rate'] for w in window_results]
        
        print(f"\n📊 稳定性分析：")
        print(f"  半波命中率：均值={sum(hw_rates)/len(hw_rates)*100:.1f}%, "
              f"范围={min(hw_rates)*100:.0f}%-{max(hw_rates)*100:.0f}%")
        print(f"  生肖命中率：均值={sum(zd_rates)/len(zd_rates)*100:.1f}%, "
              f"范围={min(zd_rates)*100:.0f}%-{max(zd_rates)*100:.0f}%")
    
    # 最新预测
    print(f"\n{'='*60}")
    print(f"🎯 最新预测（基于全部{len(all_rows)}期）")
    print(f"{'='*60}")
    
    simple = SimplePredictor(all_rows)
    simple_hw = simple.predict_halfhalf(CONFIG["bet_count"])
    simple_zd = simple.predict_zodiac(CONFIG["zodiac_bet_count"])
    simple_odd = simple.predict_odd()
    
    ensemble_hw_pred = EnsemblePredictor(
        all_rows, HALFHALF_CATEGORIES, "halfhalf",
        decay=CONFIG["recency_decay"],
        w_freq=CONFIG["weight_freq"],
        w_gap=CONFIG["weight_gap"],
        w_trans=CONFIG["weight_trans"]
    )
    ensemble_zd_pred = EnsemblePredictor(
        all_rows, ZODIAC_ORDER, "zodiac",
        decay=CONFIG["recency_decay"],
        w_freq=CONFIG["weight_freq"],
        w_gap=CONFIG["weight_gap"],
        w_trans=CONFIG["weight_trans"]
    )
    ensemble_odd_pred = EnsemblePredictor(
        all_rows, ODD_CATEGORIES, "odd",
        decay=CONFIG["recency_decay"],
        w_freq=CONFIG["weight_freq"],
        w_gap=CONFIG["weight_gap"],
        w_trans=CONFIG["weight_trans"]
    )
    
    ensemble_hw = ensemble_hw_pred.predict(CONFIG["bet_count"])
    ensemble_zd = ensemble_zd_pred.predict(CONFIG["zodiac_bet_count"])
    ensemble_odd = ensemble_odd_pred.predict(1)
    
    hw_confidence = ensemble_hw_pred.confidence(CONFIG["bet_count"])
    zd_confidence = ensemble_zd_pred.confidence(CONFIG["zodiac_bet_count"])
    
    print(f"\n📊 基础统计：")
    print(f"  颜色：{dict(sorted(simple.freq('color').items(), key=lambda x: x[1], reverse=True))}")
    print(f"  大小：{simple.freq('size')}")
    print(f"  单双：{simple.freq('odd')}")
    
    print(f"\n🎯 预测推荐：")
    print(f"\n  半波预测（置信度：{hw_confidence}%）：")
    print(f"    简单版：{', '.join(f'{x}({s:.1f})' for x, s in simple_hw)}")
    print(f"    综合版：{', '.join(f'{x}({s:.1f})' for x, s in ensemble_hw)}")
    
    print(f"\n  生肖预测（置信度：{zd_confidence}%）：")
    print(f"    简单版：{', '.join(f'{x}({s:.1f})' for x, s in simple_zd)}")
    print(f"    综合版：{', '.join(f'{x}({s:.1f})' for x, s in ensemble_zd)}")
    
    print(f"\n  单双预测：")
    print(f"    简单版：{', '.join(f'{x}({s:.1f})' for x, s in simple_odd)}")
    print(f"    综合版：{', '.join(f'{x}({s:.1f})' for x, s in ensemble_odd)}")
    
    # 最终建议
    if results:
        print(f"\n{'='*60}")
        print(f"📋 综合建议：")
        if results["ensemble_hw"] > results["simple_hw"]:
            print(f"  ✅ 半波：推荐综合版（近期命中率{results['ensemble_hw']*100:.0f}%）")
            final_hw = ensemble_hw
        else:
            print(f"  ✅ 半波：推荐简单版（近期命中率{results['simple_hw']*100:.0f}%）")
            final_hw = simple_hw
        
        if results["ensemble_zd"] > results["simple_zd"]:
            print(f"  ✅ 生肖：推荐综合版（近期命中率{results['ensemble_zd']*100:.0f}%）")
            final_zd = ensemble_zd
        else:
            print(f"  ✅ 生肖：推荐简单版（近期命中率{results['simple_zd']*100:.0f}%）")
            final_zd = simple_zd
        
        print(f"\n⭐ 最终推荐：")
        print(f"  半波：{', '.join(f'{x}({s:.1f})' for x, s in final_hw)}")
        print(f"  生肖：{', '.join(f'{x}({s:.1f})' for x, s in final_zd)}")
        print(f"  单双：{ensemble_odd[0][0]}（参考）")
    
    print(f"\n⚠️ 免责声明：彩票开奖独立随机，预测仅供参考。")

if __name__ == "__main__":
    main()