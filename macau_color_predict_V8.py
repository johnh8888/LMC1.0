#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新澳门彩预测系统 - 2026马年修正版（正确生肖排列）
生肖排列规则：1马2蛇3龙4兔5虎6牛7鼠8猪9狗10鸡11猴12羊
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

# 标准生肖顺序（正序）
ZODIAC_ORDER_STANDARD = ["鼠","牛","虎","兔","龙","蛇","马","羊","猴","鸡","狗","猪"]

# ========== 2026年马年生肖对照表（正确版） ==========
# 规则：1马 2蛇 3龙 4兔 5虎 6牛 7鼠 8猪 9狗 10鸡 11猴 12羊
# 这是逆序排列（马蛇龙兔虎牛鼠猪狗鸡猴羊）
ZODIAC_MAP_2026 = {
    1: "马", 2: "蛇", 3: "龙", 4: "兔", 5: "虎", 6: "牛",
    7: "鼠", 8: "猪", 9: "狗", 10: "鸡", 11: "猴", 12: "羊",
}

# 自动生成13-49的对应关系
for n in range(13, 50):
    base = ((n - 1) % 12) + 1
    ZODIAC_MAP_2026[n] = ZODIAC_MAP_2026[base]

# 用到的12生肖（2026年的顺序）
ZODIAC_ORDER = [ZODIAC_MAP_2026[i] for i in range(1, 13)]

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
    return ZODIAC_MAP_2026.get(n, "?")

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

# ========== 验证 ==========
def verify_zodiac_map():
    """验证2026年生肖对照表"""
    print("\n📋 2026年（马年）生肖对照表：")
    print("  规则：1马 2蛇 3龙 4兔 5虎 6牛 7鼠 8猪 9狗 10鸡 11猴 12羊")
    print(f"\n  完整号码对照：")
    
    for start in [1, 13, 25, 37]:
        end = min(start + 11, 49)
        row_str = "  "
        for n in range(start, end + 1):
            row_str += f"{n:>2}→{ZODIAC_MAP_2026[n]:<4}"
        print(row_str)
    
    print(f"\n  生肖号码归类：")
    for z in ZODIAC_ORDER:
        numbers = [n for n in range(1, 50) if ZODIAC_MAP_2026[n] == z]
        print(f"    {z}: {numbers}")

# ========== 综合生肖预测器 ==========
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
    """综合生肖预测"""
    if len(history) < 10:
        c = defaultdict(int)
        for r in history:
            c[r["zodiac"]] += 1
        total = sum(c.values()) or 1
        freq = {k: round(v/total*100, 2) for k, v in c.items()}
        full = {a: freq.get(a, 0.0) for a in ZODIAC_ORDER}
        return sorted(full.items(), key=lambda x: x[1], reverse=True)[:count]
    
    freq = recency_weighted_freq(history, "zodiac", decay)
    gaps = gap_analysis(history, "zodiac", ZODIAC_ORDER)
    gscore = gap_to_score(gaps)
    trans = transition_matrix(history, "zodiac")
    last_zodiac = history[0]["zodiac"]
    t_row = trans.get(last_zodiac, {})
    t_total = sum(t_row.values()) or 1
    t_pred = {c: round(t_row.get(c, 0)/t_total*100, 2) for c in ZODIAC_ORDER}
    
    result = {}
    for z in ZODIAC_ORDER:
        f = freq.get(z, 0.0)
        g = gscore.get(z, 0.0)
        t = t_pred.get(z, 0.0)
        result[z] = round(f * w_freq + g * w_gap + t * w_trans, 2)
    
    return sorted(result.items(), key=lambda x: x[1], reverse=True)[:count]

def simple_freq_predict(history, key, count=None):
    c = defaultdict(int)
    for r in history:
        c[r[key]] += 1
    total = sum(c.values()) or 1
    freq = {k: round(v/total*100, 2) for k, v in c.items()}
    
    if count is None:
        return sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return sorted(freq.items(), key=lambda x: x[1], reverse=True)[:count]

def halfhalf_predict(history, count=2):
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

def sliding_validate(all_rows, window=10, step=5, min_history=20):
    """滑动窗口验证"""
    if len(all_rows) < min_history + window:
        return None
    
    results = []
    start = 0
    while start + window + min_history <= len(all_rows):
        test_set = all_rows[start:start + window]
        hits = 0
        valid = 0
        
        for i, test_row in enumerate(test_set):
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
    print("新澳门彩预测系统 - 2026马年（正确生肖排列）")
    print("=" * 60)
    print("生肖规则：1马2蛇3龙4兔5虎6牛7鼠8猪9狗10鸡11猴12羊")
    
    # 验证
    verify_zodiac_map()
    
    all_rows = fetch_new_macau(CONFIG["history_limit"])
    if len(all_rows) < 30:
        print("❌ 数据不足")
        return
    
    print(f"\n📦 历史数据：{len(all_rows)}期")
    print(f"  范围：{all_rows[-1]['issue']} ~ {all_rows[0]['issue']}")
    
    # 验证最近开奖
    print(f"\n📋 最近10期开奖验证：")
    print(f"  {'期号':<12} {'特码':<6} {'波色':<8} {'生肖':<6}")
    print(f"  {'-'*35}")
    for r in all_rows[:10]:
        print(f"  {r['issue']:<12} {r['special']:>2}号   {r['halfhalf']:<8} {r['zodiac']:<6}")
    
    # 滑动窗口
    print(f"\n{'='*60}")
    print("📊 滑动窗口验证（生肖5选）")
    print(f"{'='*60}")
    
    window_results = sliding_validate(all_rows, 10, 5, 20)
    
    if window_results:
        print(f"\n  {'窗口':<22} {'命中':<8} {'命中率':<8} {'vs随机41.7%':<15}")
        print(f"  {'-'*55}")
        rates = []
        for wr in window_results:
            diff = wr['rate'] - 0.417
            flag = "✅" if diff > 0.05 else ("⚠️" if diff > -0.05 else "❌")
            print(f"  {wr['window']:<22} {wr['hits']}/{wr['total']:<5} {wr['rate']*100:>5.1f}%   {flag} ({diff*100:+.1f}%)")
            rates.append(wr['rate'])
        
        avg_rate = sum(rates) / len(rates)
        diff_avg = avg_rate - 0.417
        print(f"\n  📈 均值: {avg_rate*100:.1f}% (vs 41.7%, {diff_avg*100:+.1f}%)")
        print(f"  📊 范围: {min(rates)*100:.0f}%~{max(rates)*100:.0f}%")
        print(f"  ✅ 优于随机: {sum(1 for r in rates if r > 0.417)}/{len(rates)} 窗口")
    
    # 最新预测
    print(f"\n{'='*60}")
    print("🎯 最新预测")
    print(f"{'='*60}")
    
    recent = all_rows[:30]
    
    print(f"\n📊 近30期统计：")
    color_freq = simple_freq_predict(recent, "color")
    size_freq = simple_freq_predict(recent, "size")
    odd_freq = simple_freq_predict(recent, "odd")
    
    print(f"  颜色：{', '.join(f'{c}({s:.1f}%)' for c, s in color_freq)}")
    print(f"  大小：{', '.join(f'{s}({v:.1f}%)' for s, v in size_freq)}")
    print(f"  单双：{', '.join(f'{o}({v:.1f}%)' for o, v in odd_freq)}")
    
    # 生肖频率
    zodiac_freq = simple_freq_predict(recent, "zodiac")
    print(f"\n📊 近30期生肖频率：")
    for z, s in zodiac_freq:
        bar = "█" * int(s)
        print(f"  {z:<4} {s:>5.1f}% {bar}")
    
    # 预测
    hw_pred = halfhalf_predict(all_rows, 2)
    zd_pred = zodiac_predict(all_rows, count=5)
    odd_pred = simple_freq_predict(all_rows, "odd", 1)
    color_pred = simple_freq_predict(all_rows, "color", 1)
    size_pred = simple_freq_predict(all_rows, "size", 1)
    
    print(f"\n⭐ 推荐：")
    print(f"\n  半波（2选）：{', '.join(f'{h}({s:.1f}%)' for h, s in hw_pred)}")
    
    print(f"\n  生肖（5选）：")
    for i, (z, s) in enumerate(zd_pred, 1):
        bar = "█" * int(s)
        print(f"    {i}. {z:<4} {s:>5.1f}% {bar}")
    
    print(f"\n  单双：{odd_pred[0][0]} ({odd_pred[0][1]:.1f}%)")
    print(f"  颜色：{color_pred[0][0]} ({color_pred[0][1]:.1f}%)")
    print(f"  大小：{size_pred[0][0]} ({size_pred[0][1]:.1f}%)")
    
    print(f"\n{'='*60}")
    print("⚠️ 彩票开奖独立随机，预测仅供参考。理性投注！")

if __name__ == "__main__":
    main()