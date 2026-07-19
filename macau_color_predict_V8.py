#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新澳门彩预测系统 - 综合预测版 + 网格搜索优化
在原有基础上新增：
  1. 网格搜索自动寻找最优参数组合
  2. 交叉验证评估参数稳定性
  3. 参数敏感性分析
  4. 最优参数自动保存和加载
"""

import re
import json
import urllib.request
import os
import itertools
from collections import defaultdict
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

CONFIG = {
    "history_limit": 30,
    "api_url": "https://marksix6.net/index.php?api=1",
    "bet_count": 2,
    "zodiac_bet_count": 3,
    "bet_per_note": 50,
    "cache_file": "newmacau_cache.json",
    "zodiac_year": 2026,
    "best_params_file": "best_params.json",

    # ---- 综合版参数（初始值，网格搜索会优化）----
    "recency_decay": 0.90,
    "weight_freq": 0.45,
    "weight_gap": 0.25,
    "weight_trans": 0.30,
    "backtest_periods": 20,
    
    # ---- 网格搜索配置 ----
    "grid_search_folds": 5,  # 交叉验证折数
    "grid_search_min_periods": 15,  # 最少回测期数
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
        gap = len(rows)
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
    """结合近期加权频率 + 遗漏值 + 状态转移概率 的综合评分器"""
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
# 单次回测评估
# ============================================================

def evaluate_params(rows, params, backtest_periods, verbose=False):
    """
    使用给定参数进行回测，返回平均命中率
    params: (decay, w_freq, w_gap, w_trans)
    """
    decay, w_freq, w_gap, w_trans = params
    total = min(backtest_periods, len(rows) - 1)
    
    if total <= 0:
        return 0.0
    
    hw_hits = 0
    zd_hits = 0
    
    for i in range(total):
        history = rows[i + 1:]
        actual = rows[i]
        
        if len(history) < 5:  # 数据太少跳过
            continue
        
        # 综合版预测
        hw_ens = EnsemblePredictor(
            history, HALFHALF_CATEGORIES, "halfhalf",
            decay=decay, w_freq=w_freq, w_gap=w_gap, w_trans=w_trans
        ).select_best(CONFIG["bet_count"])
        
        zd_ens = EnsemblePredictor(
            history, ZODIAC_ORDER, "zodiac",
            decay=decay, w_freq=w_freq, w_gap=w_gap, w_trans=w_trans
        ).select_best(CONFIG["zodiac_bet_count"])
        
        hw_actual = actual["color"] + actual["size"]
        hw_list = [b[0] for b in hw_ens]
        zd_list = [b[0] for b in zd_ens]
        
        if hw_actual in hw_list:
            hw_hits += 1
        if actual["zodiac"] in zd_list:
            zd_hits += 1
    
    # 返回半波和生肖的平均命中率
    hw_rate = hw_hits / total if total > 0 else 0
    zd_rate = zd_hits / total if total > 0 else 0
    
    if verbose:
        return hw_rate, zd_rate
    
    # 综合得分（半波权重0.6，生肖权重0.4，因为半波更常用）
    return hw_rate * 0.6 + zd_rate * 0.4

# ============================================================
# 交叉验证评估
# ============================================================

def cross_validate(rows, params, n_folds=5, periods_per_fold=15):
    """
    交叉验证评估参数稳定性
    将数据分成多个时间段，分别测试
    """
    if len(rows) < (n_folds * periods_per_fold + 10):
        # 数据不够，减少折数
        n_folds = max(2, (len(rows) - 10) // periods_per_fold)
    
    if n_folds < 2:
        # 数据太少，只做单次评估
        return evaluate_params(rows, params, min(periods_per_fold, len(rows) - 1))
    
    scores = []
    fold_size = len(rows) // n_folds
    
    for fold in range(n_folds):
        start = fold * fold_size
        end = min(start + fold_size + periods_per_fold, len(rows))
        fold_data = rows[start:end]
        
        if len(fold_data) > periods_per_fold:
            score = evaluate_params(fold_data, params, periods_per_fold)
            scores.append(score)
    
    if not scores:
        return 0.0
    
    # 返回平均分和标准差
    avg_score = sum(scores) / len(scores)
    std_score = (sum((s - avg_score) ** 2 for s in scores) / len(scores)) ** 0.5
    
    return avg_score, std_score

# ============================================================
# 网格搜索
# ============================================================

def grid_search(rows, verbose=True):
    """
    网格搜索最优参数组合
    搜索空间：
    - recency_decay: 0.75, 0.80, 0.85, 0.90, 0.95
    - weight_freq: 0.3, 0.4, 0.5, 0.6
    - weight_gap: 0.1, 0.2, 0.3
    - weight_trans: 0.2, 0.3, 0.4
    (且weight_freq + weight_gap + weight_trans ≈ 1.0)
    """
    print("\n" + "="*60)
    print("🔍 开始网格搜索最优参数...")
    print("="*60)
    
    # 定义搜索空间
    decay_values = [0.75, 0.80, 0.85, 0.90, 0.95]
    
    # 生成权重组合（总和为1.0的组合）
    weight_combinations = []
    for w_freq in [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6]:
        for w_gap in [0.1, 0.15, 0.2, 0.25, 0.3]:
            w_trans = round(1.0 - w_freq - w_gap, 2)
            if 0.1 <= w_trans <= 0.5 and abs(w_freq + w_gap + w_trans - 1.0) < 0.01:
                weight_combinations.append((w_freq, w_gap, w_trans))
    
    # 去重
    weight_combinations = list(set(weight_combinations))
    
    total_combinations = len(decay_values) * len(weight_combinations)
    print(f"总参数组合数: {total_combinations}")
    print(f"  衰减系数: {len(decay_values)} 个值")
    print(f"  权重组合: {len(weight_combinations)} 组")
    
    backtest_periods = CONFIG.get("grid_search_min_periods", CONFIG["backtest_periods"])
    n_folds = CONFIG.get("grid_search_folds", 5)
    
    # 存储所有结果
    all_results = []
    best_score = -1
    best_params = None
    best_details = None
    
    # 执行网格搜索
    count = 0
    for decay in decay_values:
        for w_freq, w_gap, w_trans in weight_combinations:
            count += 1
            params = (decay, w_freq, w_gap, w_trans)
            
            # 使用交叉验证评估
            cv_result = cross_validate(rows, params, n_folds, backtest_periods)
            
            if isinstance(cv_result, tuple):
                avg_score, std_score = cv_result
            else:
                avg_score, std_score = cv_result, 0.0
            
            # 稳定性得分（考虑标准差，越稳定越好）
            stability_penalty = std_score * 0.5  # 惩罚不稳定参数
            adjusted_score = avg_score - stability_penalty
            
            all_results.append({
                'params': params,
                'avg_score': avg_score,
                'std_score': std_score,
                'adjusted_score': adjusted_score
            })
            
            if adjusted_score > best_score:
                best_score = adjusted_score
                best_params = params
                best_details = all_results[-1]
            
            if verbose and count % 20 == 0:
                print(f"  进度: {count}/{total_combinations} ({count/total_combinations*100:.1f}%)")
    
    # 按得分排序
    all_results.sort(key=lambda x: x['adjusted_score'], reverse=True)
    
    return best_params, best_details, all_results[:10]

# ============================================================
# 参数敏感性分析
# ============================================================

def sensitivity_analysis(rows, best_params):
    """分析最优参数附近的表现，了解参数敏感性"""
    print("\n" + "="*60)
    print("📊 参数敏感性分析")
    print("="*60)
    
    decay, w_freq, w_gap, w_trans = best_params
    
    # 测试衰减系数敏感性
    print(f"\n衰减系数敏感性 (基础值: {decay}):")
    for d in [decay - 0.05, decay - 0.02, decay, decay + 0.02, decay + 0.05]:
        if 0.1 <= d <= 0.99:
            score = evaluate_params(rows, (d, w_freq, w_gap, w_trans), 
                                   CONFIG["backtest_periods"])
            marker = " ★" if d == decay else ""
            print(f"  decay={d:.2f}: 得分={score:.4f}{marker}")
    
    # 测试权重敏感性
    print(f"\n权重敏感性 (基础值: freq={w_freq}, gap={w_gap}, trans={w_trans}):")
    perturbations = [
        (w_freq + 0.1, w_gap - 0.05, w_trans - 0.05),
        (w_freq - 0.1, w_gap + 0.05, w_trans + 0.05),
        (w_freq + 0.05, w_gap + 0.05, w_trans - 0.1),
        (w_freq - 0.05, w_gap - 0.05, w_trans + 0.1),
    ]
    
    for wf, wg, wt in perturbations:
        # 确保权重在合理范围且和为1
        wf = max(0.1, min(0.7, wf))
        wg = max(0.0, min(0.4, wg))
        wt = max(0.1, min(0.5, wt))
        total = wf + wg + wt
        wf, wg, wt = wf/total, wg/total, wt/total
        
        score = evaluate_params(rows, (decay, round(wf,2), round(wg,2), round(wt,2)), 
                               CONFIG["backtest_periods"])
        print(f"  ({wf:.2f}, {wg:.2f}, {wt:.2f}): 得分={score:.4f}")
    
    print(f"\n最优参数: decay={decay}, weights=({w_freq}, {w_gap}, {w_trans})")

# ============================================================
# 保存和加载最优参数
# ============================================================

def save_best_params(params, details, filename=None):
    """保存最优参数到文件"""
    if filename is None:
        filename = CONFIG.get("best_params_file", "best_params.json")
    
    data = {
        'timestamp': datetime.now().isoformat(),
        'params': {
            'recency_decay': params[0],
            'weight_freq': params[1],
            'weight_gap': params[2],
            'weight_trans': params[3]
        },
        'score': details['avg_score'],
        'std_score': details['std_score'],
        'adjusted_score': details['adjusted_score']
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 最优参数已保存到: {filename}")

def load_best_params(filename=None):
    """加载最优参数"""
    if filename is None:
        filename = CONFIG.get("best_params_file", "best_params.json")
    
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            params = data['params']
            return (params['recency_decay'], params['weight_freq'], 
                   params['weight_gap'], params['weight_trans']), data
        except:
            pass
    return None, None

# ============================================================
# 回测：简单版 vs 综合版（使用最优参数）
# ============================================================

def run_backtest(rows, periods, params=None):
    total = min(periods, len(rows) - 1)
    if total <= 0:
        print("❌ 数据不足以回测")
        return

    if params is None:
        params = (CONFIG["recency_decay"], CONFIG["weight_freq"], 
                 CONFIG["weight_gap"], CONFIG["weight_trans"])

    print(f"\n📊 详细回测（简单版 vs 综合版，共{total}期）")
    if params:
        print(f"综合版参数: decay={params[0]}, weights=({params[1]}, {params[2]}, {params[3]})")
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

        # 综合版（使用指定参数）
        hw_ens = [b[0] for b in EnsemblePredictor(
            history, HALFHALF_CATEGORIES, "halfhalf",
            decay=params[0], w_freq=params[1], w_gap=params[2], w_trans=params[3]
        ).select_best(2)]
        zd_ens = [b[0] for b in EnsemblePredictor(
            history, ZODIAC_ORDER, "zodiac",
            decay=params[0], w_freq=params[1], w_gap=params[2], w_trans=params[3]
        ).select_best(3)]

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
    
    return hw_simple_hits, hw_ens_hits, zd_simple_hits, zd_ens_hits, total

# ============================================================
# 主函数
# ============================================================

def main():
    print("=" * 60)
    print("新澳门彩预测系统 - 综合预测版 + 网格搜索")
    print(f"生肖年份基准: {CONFIG['zodiac_year']}年")
    print("=" * 60)

    # 获取数据
    rows = fetch_new_macau(CONFIG["history_limit"])
    if len(rows) < 10:
        print("❌ 数据不足")
        return

    # 检查是否有保存的最优参数
    saved_params, saved_data = load_best_params()
    use_grid_search = True
    
    if saved_params and saved_data:
        print(f"\n📂 发现已保存的最优参数 (保存时间: {saved_data['timestamp']})")
        print(f"   参数: decay={saved_params[0]}, weights=({saved_params[1]}, {saved_params[2]}, {saved_params[3]})")
        print(f"   得分: {saved_data['adjusted_score']:.4f}")
        
        response = input("\n是否使用已保存的参数？(y/n，默认y): ").strip().lower()
        if response != 'n':
            use_grid_search = False
            best_params = saved_params
    
    if use_grid_search:
        # 执行网格搜索
        best_params, best_details, top_results = grid_search(rows)
        
        print("\n" + "="*60)
        print("🏆 网格搜索完成！")
        print("="*60)
        print(f"\n最优参数:")
        print(f"  recency_decay: {best_params[0]}")
        print(f"  weight_freq: {best_params[1]}")
        print(f"  weight_gap: {best_params[2]}")
        print(f"  weight_trans: {best_params[3]}")
        print(f"\n最优得分: {best_details['avg_score']:.4f}")
        print(f"标准差: {best_details['std_score']:.4f}")
        print(f"调整得分: {best_details['adjusted_score']:.4f}")
        
        print("\n📈 TOP 10 参数组合:")
        print(f"{'排名':<6} {'decay':<8} {'freq':<8} {'gap':<8} {'trans':<8} {'得分':<10} {'标准差':<10}")
        print("-" * 60)
        for i, result in enumerate(top_results, 1):
            p = result['params']
            print(f"{i:<6} {p[0]:<8.2f} {p[1]:<8.2f} {p[2]:<8.2f} {p[3]:<8.2f} "
                  f"{result['avg_score']:<10.4f} {result['std_score']:<10.4f}")
        
        # 保存最优参数
        save_best_params(best_params, best_details)
        
        # 敏感性分析
        sensitivity_analysis(rows, best_params)
        
        # 更新CONFIG
        CONFIG["recency_decay"] = best_params[0]
        CONFIG["weight_freq"] = best_params[1]
        CONFIG["weight_gap"] = best_params[2]
        CONFIG["weight_trans"] = best_params[3]

    # 使用最优参数进行回测
    print("\n" + "="*60)
    print("📊 使用最优参数进行回测对比")
    print("="*60)
    run_backtest(rows, CONFIG["backtest_periods"], best_params)

    # 当前预测
    sp = SimplePredictor(rows)
    color_pred, size_pred, odd_pred, zod_pred = sp.freq("color"), sp.freq("size"), sp.freq("odd"), sp.freq("zodiac")

    print("\n🎯 当前最新预测（使用最优参数）")
    print("颜色分布:", dict(sorted(color_pred.items(), key=lambda x: x[1], reverse=True)))
    print("大小分布:", size_pred)
    print("单双分布:", odd_pred)

    hw_simple = DynamicHalfwaveSelector(color_pred, size_pred).select_best(CONFIG["bet_count"])
    hw_ens = EnsemblePredictor(
        rows, HALFHALF_CATEGORIES, "halfhalf",
        decay=best_params[0], w_freq=best_params[1], w_gap=best_params[2], w_trans=best_params[3]
    ).select_best(CONFIG["bet_count"])
    
    zd_simple = SimpleZodiacSelector(zod_pred).select_best(CONFIG["zodiac_bet_count"])
    zd_ens = EnsemblePredictor(
        rows, ZODIAC_ORDER, "zodiac",
        decay=best_params[0], w_freq=best_params[1], w_gap=best_params[2], w_trans=best_params[3]
    ).select_best(CONFIG["zodiac_bet_count"])

    print("\n💡 半波推荐")
    print("  简单版:", ", ".join(f"{hw}({s:.1f})" for hw, s in hw_simple))
    print("  综合版(优化):", ", ".join(f"{hw}({s:.1f})" for hw, s in hw_ens))

    print("\n💡 生肖推荐")
    print("  简单版:", ", ".join(f"{z}({s:.1f})" for z, s in zd_simple))
    print("  综合版(优化):", ", ".join(f"{z}({s:.1f})" for z, s in zd_ens))
    
    print("\n" + "="*60)
    print("✨ 分析完成！")
    print("="*60)

if __name__ == "__main__":
    main()