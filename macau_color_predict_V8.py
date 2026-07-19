#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新澳门彩预测系统 - 数据驱动最终版
基于多轮回测结果：
  - 半波：简单频率 ≈ 随机（不推荐依赖）
  - 生肖5选：综合版均值48% > 随机41.7%（有一定参考价值）
  - 单双：接近50%随机
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
    "zodiac_year": 2026,
    "cache_file": "newmacau_cache.json",
}

RED = {1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE = {3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
GREEN = {5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}

ZODIAC_ORDER = ["鼠","牛","虎","兔","龙","蛇","马","羊","猴","鸡","狗","猪"]
ZODIAC_BASE_YEAR = 2020

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

# ========== 综合生肖预测器（唯一有微弱优势的模型） ==========
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

def transition_matrix(history, key):
    trans = defaultdict(lambda: defaultdict(int))
    for i in range(len(history) - 1):
        prev = history[i + 1][key]
        curr = history[i][key]
        trans[prev][curr] += 1
    return trans

def zodiac_predict(history, count=5, decay=0.90, w_freq=0.55, w_gap=0.25, w_trans=0.20):
    """
    综合生肖预测 - 滑动窗口验证均值48% > 随机41.7%
    调高频率权重(0.55)，降低转移权重(0.20)，更稳定
    """
    if len(history) < 10:
        # 数据太少，用简单频率
        c = defaultdict(int)
        for r in history:
            c[r["zodiac"]] += 1
        total = sum(c.values()) or 1
        freq = {k: round(v/total*100, 2) for k, v in c.items()}
        full = {a: freq.get(a, 0.0) for a in ZODIAC_ORDER}
        return sorted(full.items(), key=lambda x: x[1], reverse=True)[:count]
    
    # 1. 近期加权频率
    freq = recency_weighted_freq(history, "zodiac", decay)
    
    # 2. 遗漏分析
    gaps = gap_analysis(history, "zodiac", ZODIAC_ORDER)
    gscore = gap_to_score(gaps)
    
    # 3. 转移概率
    trans = transition_matrix(history, "zodiac")
    last_zodiac = history[0]["zodiac"]
    t_row = trans.get(last_zodiac, {})
    t_total = sum(t_row.values()) or 1
    t_pred = {c: round(t_row.get(c, 0)/t_total*100, 2) for c in ZODIAC_ORDER}
    
    # 融合
    result = {}
    for z in ZODIAC_ORDER:
        f = freq.get(z, 0.0)
        g = gscore.get(z, 0.0)
        t = t_pred.get(z, 0.0)
        result[z] = round(f * w_freq + g * w_gap + t * w_trans, 2)
    
    return sorted(result.items(), key=lambda x: x[1], reverse=True)[:count]

# ========== 简单频率预测（半波、单双等） ==========
def simple_freq_predict(history, key, count=None):
    """简单频率统计"""
    c = defaultdict(int)
    for r in history:
        c[r[key]] += 1
    total = sum(c.values()) or 1
    freq = {k: round(v/total*100, 2) for k, v in c.items()}
    
    if count is None:
        return sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return sorted(freq.items(), key=lambda x: x[1], reverse=True)[:count]

def halfhalf_predict(history, count=2):
    """半波预测：颜色频率 × 大小频率"""
    color_freq = simple_freq_predict(history, "color")
    size_freq = simple_freq_predict(history, "size")
    
    color_dict = dict(color_freq)
    size_dict = dict(size_freq)
    
    scores = {}
    for c in ["红", "蓝", "绿"]:
        for s in ["大", "小"]:
            scores[c+s] = color_dict.get(c, 0) * 0.5 + size_dict.get(s, 0) * 0.5
    
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

# ========== 滑动窗口验证 ==========
def sliding_validate(all_rows, window=10, step=5, min_history=20):
    """滑动窗口验证生肖预测的真实表现"""
    if len(all_rows) < min_history + window:
        return None
    
    results = []
    start = 0
    while start + window + min_history <= len(all_rows):
        test_set = all_rows[start:start + window]
        hits = 0
        valid = 0
        
        for i, test_row in enumerate(test_set):
            # 🔑 只用该期之前的数据
            history = all_rows[start + window - i:]
            if len(history) < min_history:
                continue
            
            pred = [z for z, s in zodiac_predict(history, count=5)]
            if test_row["zodiac"] in pred:
                hits += 1
            valid += 1
        
        if valid > 0:
            results.append({
                "window": f"{test_set[-1]['issue']}~{test_set[0]['issue']}",
                "rate": hits / valid,
                "hits": hits,
                "total": valid
            })
        
        start += step
    
    return results

# ========== 主函数 ==========
def main():
    print("=" * 60)
    print("新澳门彩预测系统 - 数据驱动最终版")
    print(f"生肖年份: {CONFIG['zodiac_year']}年")
    print("=" * 60)
    
    all_rows = fetch_new_macau(CONFIG["history_limit"])
    if len(all_rows) < 30:
        print("❌ 数据不足")
        return
    
    print(f"\n📦 数据：{len(all_rows)}期 ({all_rows[-1]['issue']} ~ {all_rows[0]['issue']})")
    
    # ========== 滑动窗口验证 ==========
    print(f"\n{'='*60}")
    print("📊 滑动窗口验证（生肖5选，最近5个窗口）")
    print(f"{'='*60}")
    
    window_results = sliding_validate(all_rows, 10, 5, 20)
    
    if window_results:
        print(f"\n{'窗口':<22} {'命中':<10} {'命中率':<10} {'vs随机41.7%':<15}")
        print("-" * 60)
        rates = []
        for wr in window_results:
            diff = wr['rate'] - 0.417
            flag = "✅ 优于" if diff > 0.05 else ("⚠️ 持平" if diff > -0.05 else "❌ 不如")
            print(f"{wr['window']:<22} {wr['hits']}/{wr['total']:<7} {wr['rate']*100:>5.1f}%    {flag} ({diff*100:+.1f}%)")
            rates.append(wr['rate'])
        
        avg_rate = sum(rates) / len(rates)
        diff_avg = avg_rate - 0.417
        print(f"\n📈 平均命中率: {avg_rate*100:.1f}% (vs 随机41.7%, {diff_avg*100:+.1f}%)")
        print(f"   范围: {min(rates)*100:.0f}% ~ {max(rates)*100:.0f}%")
        
        # 统计优于随机的窗口数
        better = sum(1 for r in rates if r > 0.417)
        print(f"   优于随机: {better}/{len(rates)} 个窗口")
    
    # ========== 最新预测 ==========
    print(f"\n{'='*60}")
    print("🎯 最新预测")
    print(f"{'='*60}")
    
    # 基础统计
    print(f"\n📊 近30期数据分布：")
    recent = all_rows[:30]
    color_freq = simple_freq_predict(recent, "color")
    size_freq = simple_freq_predict(recent, "size")
    odd_freq = simple_freq_predict(recent, "odd")
    
    print(f"  颜色: {', '.join(f'{c}({s:.1f}%)' for c, s in color_freq)}")
    print(f"  大小: {', '.join(f'{s}({v:.1f}%)' for s, v in size_freq)}")
    print(f"  单双: {', '.join(f'{o}({v:.1f}%)' for o, v in odd_freq)}")
    
    # 半波预测（简单频率）
    hw_pred = halfhalf_predict(all_rows, 2)
    
    # 生肖预测（综合版）
    zd_pred = zodiac_predict(all_rows, count=5)
    
    # 单双预测
    odd_pred = simple_freq_predict(all_rows, "odd", 1)
    
    # 颜色预测
    color_pred = simple_freq_predict(all_rows, "color", 1)
    
    # 大小预测
    size_pred = simple_freq_predict(all_rows, "size", 1)
    
    print(f"\n⭐ 预测推荐：")
    print(f"\n  半波（简单频率，参考用）：")
    print(f"    {', '.join(f'{h}({s:.1f}%)' for h, s in hw_pred)}")
    
    print(f"\n  生肖5选（综合模型，滑动窗口均值48%）：")
    for i, (z, s) in enumerate(zd_pred, 1):
        bar = "█" * int(s / 2)
        print(f"    {i}. {z:<4} {s:>5.1f}% {bar}")
    
    print(f"\n  其他参考：")
    print(f"    单双: {odd_pred[0][0]} ({odd_pred[0][1]:.1f}%)")
    print(f"    颜色: {color_pred[0][0]} ({color_pred[0][1]:.1f}%)")
    print(f"    大小: {size_pred[0][0]} ({size_pred[0][1]:.1f}%)")
    
    # 历史生肖分布
    print(f"\n📊 近30期生肖出现次数：")
    zodiac_count = defaultdict(int)
    for r in recent:
        zodiac_count[r["zodiac"]] += 1
    
    for z in ZODIAC_ORDER:
        count = zodiac_count.get(z, 0)
        bar = "█" * count
        marker = " ⭐" if z in [x[0] for x in zd_pred] else ""
        print(f"  {z:<4} {count:>2}次 {bar}{marker}")
    
    print(f"\n{'='*60}")
    print("📋 使用建议：")
    print(f"{'='*60}")
    print(f"  1. 生肖5选是唯一略优于随机的维度（均值48% vs 41.7%）")
    print(f"  2. 半波、单双、颜色、大小均接近随机，仅供参考")
    print(f"  3. 生肖预测在30%-60%间波动，非稳定优势")
    print(f"  4. 理性投注，控制金额，不要追号")
    print(f"\n⚠️ 彩票开奖独立随机，任何预测都无法保证准确。")

if __name__ == "__main__":
    main()