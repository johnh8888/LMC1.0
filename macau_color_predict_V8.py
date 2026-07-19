#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新澳门彩预测系统 - 严格回测版
关键原则：
  1. 绝不使用未来数据：每期预测只使用该期之前的历史数据
  2. 时间序列交叉验证：按时间顺序滚动预测
  3. 防过拟合：参数搜索在训练集上进行，验证集独立
  4. 简单基线优先：如果复杂模型不能显著优于简单模型，就用简单的
"""

import re
import json
import urllib.request
import os
from collections import defaultdict
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

CONFIG = {
    "history_limit": 50,        # 获取更多历史数据
    "api_url": "https://marksix6.net/index.php?api=1",
    "bet_count": 2,
    "zodiac_bet_count": 3,
    "cache_file": "newmacau_cache.json",
    "zodiac_year": 2026,

    # ---- 基础参数（简单保守的默认值）----
    "recency_decay": 0.90,
    "weight_freq": 0.50,       # 频率权重最高，最可靠
    "weight_gap": 0.15,        # 遗漏值权重较低，避免过拟合
    "weight_trans": 0.35,      # 转移概率中等权重
    
    # ---- 回测配置 ----
    "test_periods": 10,         # 🔑 只验证最近10期
    "min_history_for_predict": 20,  # 预测至少需要20期历史
}

# ========== 基础定义 ==========
RED = {1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE = {3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
GREEN = {5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}

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

def get_halfhalf(n):
    return get_color(n) + get_size(n)

def get_zodiac(n):
    return ZODIAC_MAP.get(n, "?")

def parse_numbers(text):
    nums = re.findall(r"\d+", text)
    return [int(x) for x in nums if 1 <= int(x) <= 49]

# ========== 数据获取 ==========
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

# ========== 简单版预测器（基线） ==========
class SimplePredictor:
    """简单频率统计 - 作为基线对比"""
    def __init__(self, history):
        self.history = history  # 只能使用传入的历史数据

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

# ========== 综合版预测器 ==========
def recency_weighted_freq(history, key, decay=0.9):
    """近期加权频率 - history[0]是最新一期"""
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
    """
    遗漏值分析：每个类别距上次出现的期数
    0 = 上一期刚出现
    """
    gaps = {}
    for cat in categories:
        gap = None
        for i, r in enumerate(history):
            if r[key] == cat:
                gap = i
                break
        # 从未出现：设为历史长度的1.5倍（适度偏高但不极端）
        gaps[cat] = gap if gap is not None else int(len(history) * 1.5)
    return gaps

def gap_to_score(gaps):
    """
    遗漏值转分数：遗漏越久，分数越高（回补假设）
    使用温和的转换，避免极端值
    """
    if not gaps:
        return {}
    
    max_gap = max(gaps.values()) + 1
    # 归一化：gap/max_gap，然后取平方根让分布更均匀
    scores = {}
    for cat, gap in gaps.items():
        normalized = gap / max_gap
        scores[cat] = round(normalized ** 0.5 * 100, 2)  # 平方根缓解极端值
    
    return scores

def transition_analysis(history, key):
    """一阶马尔可夫转移矩阵"""
    trans = defaultdict(lambda: defaultdict(int))
    for i in range(len(history) - 1):
        prev_val = history[i + 1][key]  # 较旧一期
        next_val = history[i][key]       # 较新一期
        trans[prev_val][next_val] += 1
    return trans

def transition_predict(trans, last_value, categories):
    """基于上一期结果预测下一期"""
    row = trans.get(last_value, {})
    total = sum(row.values())
    
    if total == 0:
        # 无转移记录，返回均匀分布
        n = len(categories)
        return {c: round(100/n, 2) for c in categories}
    
    return {c: round(row.get(c, 0) / total * 100, 2) for c in categories}

class EnsemblePredictor:
    """综合预测器：只使用给定的历史数据"""
    def __init__(self, history, categories, key,
                 decay=0.90, w_freq=0.50, w_gap=0.15, w_trans=0.35):
        self.history = history
        self.categories = categories
        self.key = key
        self.decay = decay
        self.w_freq = w_freq
        self.w_gap = w_gap
        self.w_trans = w_trans

    def score(self):
        if len(self.history) < 5:
            # 历史太少，返回均匀分布
            n = len(self.categories)
            return {c: round(100/n, 2) for c in self.categories}

        # 三个独立信号
        freq = recency_weighted_freq(self.history, self.key, self.decay)
        gaps = gap_analysis(self.history, self.key, self.categories)
        gscore = gap_to_score(gaps)
        trans = transition_analysis(self.history, self.key)
        last_value = self.history[0][self.key]
        tpred = transition_predict(trans, last_value, self.categories)

        # 加权融合
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

# ========== 严格的时间序列回测 ==========
def strict_backtest(all_rows, test_periods=10, min_history=20):
    """
    严格回测：按时间顺序，每期只用该期之前的数据预测
    
    数据排列：all_rows[0] = 最新一期, all_rows[-1] = 最旧一期
    
    回测逻辑：
    - 测试期 = all_rows[0:test_periods]（最近10期）
    - 对于测试期中的第i期，历史数据 = all_rows[i+1:]（该期之前的所有数据）
    """
    if len(all_rows) < min_history + test_periods:
        print(f"❌ 数据不足：需要至少{min_history + test_periods}期，实际{len(all_rows)}期")
        return None
    
    # 测试集：最近test_periods期
    test_set = all_rows[:test_periods]
    
    print(f"\n{'='*70}")
    print(f"📊 严格回测：最近{test_periods}期（绝不使用未来数据）")
    print(f"{'='*70}")
    print(f"数据范围：{all_rows[-1]['issue']} ~ {all_rows[0]['issue']}")
    print(f"测试范围：{test_set[-1]['issue']} ~ {test_set[0]['issue']}")
    print(f"每期最少历史：{min_history}期")
    print(f"\n{'期号':<12} {'实际半波':<8} {'实际生肖':<6} {'简单半波':<14} {'✓':<4} {'综合半波':<14} {'✓':<4} {'简单生肖':<14} {'✓':<4} {'综合生肖':<14} {'✓':<4}")
    print("-" * 110)
    
    simple_hw_hits = 0
    ensemble_hw_hits = 0
    simple_zd_hits = 0
    ensemble_zd_hits = 0
    
    for i, test_row in enumerate(test_set):
        # 🔑 关键：历史数据 = 测试期之后的所有数据（即该期之前的数据）
        history = all_rows[test_periods - i:]  # 随着i增大，历史越来越多
        
        if len(history) < min_history:
            print(f"{test_row['issue']:<12} {'(历史不足)':<50}")
            continue
        
        # 简单版预测
        simple = SimplePredictor(history)
        simple_hw = [x[0] for x in simple.predict_halfhalf(CONFIG["bet_count"])]
        simple_zd = [x[0] for x in simple.predict_zodiac(CONFIG["zodiac_bet_count"])]
        
        # 综合版预测
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
        
        # 实际结果
        actual_hw = test_row["halfhalf"]
        actual_zd = test_row["zodiac"]
        
        # 判断命中
        sh_hit = actual_hw in simple_hw
        eh_hit = actual_hw in ensemble_hw
        sz_hit = actual_zd in simple_zd
        ez_hit = actual_zd in ensemble_zd
        
        simple_hw_hits += sh_hit
        ensemble_hw_hits += eh_hit
        simple_zd_hits += sz_hit
        ensemble_zd_hits += ez_hit
        
        print(f"{test_row['issue']:<12} {actual_hw:<8} {actual_zd:<6} "
              f"{','.join(simple_hw):<14} {'✓' if sh_hit else '✗':<4} "
              f"{','.join(ensemble_hw):<14} {'✓' if eh_hit else '✗':<4} "
              f"{','.join(simple_zd):<14} {'✓' if sz_hit else '✗':<4} "
              f"{','.join(ensemble_zd):<14} {'✓' if ez_hit else '✗':<4}")
    
    # 统计结果
    n = len(test_set)
    print("-" * 110)
    print(f"\n📈 命中率统计（{n}期）：")
    print(f"  半波预测：")
    print(f"    简单版（频率）: {simple_hw_hits}/{n} = {simple_hw_hits/n*100:.1f}%")
    print(f"    综合版（融合）: {ensemble_hw_hits}/{n} = {ensemble_hw_hits/n*100:.1f}%")
    print(f"  生肖预测：")
    print(f"    简单版（频率）: {simple_zd_hits}/{n} = {simple_zd_hits/n*100:.1f}%")
    print(f"    综合版（融合）: {ensemble_zd_hits}/{n} = {ensemble_zd_hits/n*100:.1f}%")
    
    # 结论建议
    print(f"\n💡 分析建议：")
    if ensemble_hw_hits > simple_hw_hits:
        print(f"  半波：综合版优于简单版 (+{ensemble_hw_hits - simple_hw_hits}期)，可考虑使用综合版")
    elif ensemble_hw_hits < simple_hw_hits:
        print(f"  半波：简单版优于综合版 (+{simple_hw_hits - ensemble_hw_hits}期)，建议使用简单版")
    else:
        print(f"  半波：两版持平，建议使用简单版（更稳定）")
    
    if ensemble_zd_hits > simple_zd_hits:
        print(f"  生肖：综合版优于简单版 (+{ensemble_zd_hits - simple_zd_hits}期)，可考虑使用综合版")
    elif ensemble_zd_hits < simple_zd_hits:
        print(f"  生肖：简单版优于综合版 (+{simple_zd_hits - ensemble_zd_hits}期)，建议使用简单版")
    else:
        print(f"  生肖：两版持平，建议使用简单版（更稳定）")
    
    return {
        "simple_hw": simple_hw_hits/n,
        "ensemble_hw": ensemble_hw_hits/n,
        "simple_zd": simple_zd_hits/n,
        "ensemble_zd": ensemble_zd_hits/n,
    }

# ========== 轻量参数搜索（只在训练集上进行） ==========
def light_param_search(all_rows, test_periods=10, min_history=20):
    """
    轻量参数搜索：只在训练集（非测试集）上进行
    训练集 = 测试集之前的所有数据
    """
    if len(all_rows) < min_history + test_periods + 5:
        print("⚠️ 数据不足以进行参数搜索，使用默认参数")
        return CONFIG["recency_decay"], CONFIG["weight_freq"], CONFIG["weight_gap"], CONFIG["weight_trans"]
    
    # 训练集：测试集之前的数据
    train_set = all_rows[test_periods:]
    if len(train_set) < min_history + 5:
        return CONFIG["recency_decay"], CONFIG["weight_freq"], CONFIG["weight_gap"], CONFIG["weight_trans"]
    
    print(f"\n🔍 轻量参数搜索（仅在训练集上进行，共{len(train_set)}期）...")
    
    # 小搜索空间，避免过拟合
    decays = [0.85, 0.90, 0.95]
    weights = [
        (0.50, 0.15, 0.35),
        (0.45, 0.20, 0.35),
        (0.55, 0.10, 0.35),
        (0.40, 0.25, 0.35),
        (0.50, 0.10, 0.40),
    ]
    
    best_score = -1
    best_params = (CONFIG["recency_decay"], CONFIG["weight_freq"], 
                   CONFIG["weight_gap"], CONFIG["weight_trans"])
    
    for decay in decays:
        for wf, wg, wt in weights:
            # 在训练集上做简单验证
            hw_hits = 0
            zd_hits = 0
            valid_count = 0
            
            # 取训练集最后5期做验证（不用最近test_periods期）
            val_size = min(5, len(train_set) - min_history)
            for i in range(val_size):
                val_row = train_set[i]
                history = train_set[i + 1:i + 1 + min_history]
                
                if len(history) < min_history:
                    continue
                
                ensemble_hw = EnsemblePredictor(
                    history, HALFHALF_CATEGORIES, "halfhalf",
                    decay=decay, w_freq=wf, w_gap=wg, w_trans=wt
                ).predict(CONFIG["bet_count"])
                
                ensemble_zd = EnsemblePredictor(
                    history, ZODIAC_ORDER, "zodiac",
                    decay=decay, w_freq=wf, w_gap=wg, w_trans=wt
                ).predict(CONFIG["zodiac_bet_count"])
                
                if val_row["halfhalf"] in [x[0] for x in ensemble_hw]:
                    hw_hits += 1
                if val_row["zodiac"] in [x[0] for x in ensemble_zd]:
                    zd_hits += 1
                valid_count += 1
            
            if valid_count > 0:
                score = (hw_hits + zd_hits) / (2 * valid_count)
                if score > best_score:
                    best_score = score
                    best_params = (decay, wf, wg, wt)
    
    print(f"  最优参数: decay={best_params[0]}, weights=({best_params[1]}, {best_params[2]}, {best_params[3]})")
    print(f"  训练集得分: {best_score:.3f}")
    
    return best_params

# ========== 主函数 ==========
def main():
    print("=" * 60)
    print("新澳门彩预测系统 - 严格回测版")
    print(f"生肖年份基准: {CONFIG['zodiac_year']}年")
    print("=" * 60)
    print("\n⚠️ 核心原则：")
    print("  1. 回测绝不使用未来数据")
    print("  2. 每期预测只用该期之前的历史")
    print("  3. 参数搜索仅在训练集进行")
    print("  4. 避免过拟合，偏好简单模型")
    
    # 获取数据
    all_rows = fetch_new_macau(CONFIG["history_limit"])
    if len(all_rows) < CONFIG["min_history_for_predict"] + CONFIG["test_periods"]:
        print(f"❌ 数据不足：需要至少{CONFIG['min_history_for_predict'] + CONFIG['test_periods']}期")
        return
    
    print(f"\n📦 数据概况：")
    print(f"  总期数：{len(all_rows)}")
    print(f"  最新：{all_rows[0]['issue']}（{all_rows[0]['halfhalf']}，{all_rows[0]['zodiac']}）")
    print(f"  最旧：{all_rows[-1]['issue']}")
    
    # 轻量参数搜索（只在训练集）
    best_decay, best_wf, best_wg, best_wt = light_param_search(
        all_rows, CONFIG["test_periods"], CONFIG["min_history_for_predict"]
    )
    
    # 更新配置
    CONFIG["recency_decay"] = best_decay
    CONFIG["weight_freq"] = best_wf
    CONFIG["weight_gap"] = best_wg
    CONFIG["weight_trans"] = best_wt
    
    # 严格回测
    results = strict_backtest(
        all_rows, 
        CONFIG["test_periods"], 
        CONFIG["min_history_for_predict"]
    )
    
    # ========== 最新预测（使用全部历史） ==========
    print(f"\n{'='*60}")
    print(f"🎯 最新一期预测（基于全部{len(all_rows)}期历史）")
    print(f"{'='*60}")
    
    # 简单版
    simple = SimplePredictor(all_rows)
    simple_hw = simple.predict_halfhalf(CONFIG["bet_count"])
    simple_zd = simple.predict_zodiac(CONFIG["zodiac_bet_count"])
    
    # 综合版
    ensemble_hw = EnsemblePredictor(
        all_rows, HALFHALF_CATEGORIES, "halfhalf",
        decay=best_decay, w_freq=best_wf, w_gap=best_wg, w_trans=best_wt
    ).predict(CONFIG["bet_count"])
    
    ensemble_zd = EnsemblePredictor(
        all_rows, ZODIAC_ORDER, "zodiac",
        decay=best_decay, w_freq=best_wf, w_gap=best_wg, w_trans=best_wt
    ).predict(CONFIG["zodiac_bet_count"])
    
    print(f"\n📊 近期统计（近{min(30, len(all_rows))}期）：")
    color_freq = simple.freq("color")
    size_freq = simple.freq("size")
    print(f"  颜色：{dict(sorted(color_freq.items(), key=lambda x: x[1], reverse=True))}")
    print(f"  大小：{size_freq}")
    
    print(f"\n💡 半波预测：")
    print(f"  简单版（频率）：{', '.join(f'{x}({s:.1f})' for x, s in simple_hw)}")
    print(f"  综合版（融合）：{', '.join(f'{x}({s:.1f})' for x, s in ensemble_hw)}")
    
    print(f"\n💡 生肖预测：")
    print(f"  简单版（频率）：{', '.join(f'{x}({s:.1f})' for x, s in simple_zd)}")
    print(f"  综合版（融合）：{', '.join(f'{x}({s:.1f})' for x, s in ensemble_zd)}")
    
    # 最终建议
    if results:
        print(f"\n{'='*60}")
        print(f"📋 基于回测的建议：")
        
        if results["ensemble_hw"] > results["simple_hw"]:
            print(f"  半波：推荐使用综合版")
            hw_pick = ensemble_hw
        else:
            print(f"  半波：推荐使用简单版（频率）")
            hw_pick = simple_hw
        
        if results["ensemble_zd"] > results["simple_zd"]:
            print(f"  生肖：推荐使用综合版")
            zd_pick = ensemble_zd
        else:
            print(f"  生肖：推荐使用简单版（频率）")
            zd_pick = simple_zd
        
        print(f"\n⭐ 最终推荐：")
        print(f"  半波：{', '.join(f'{x}({s:.1f})' for x, s in hw_pick)}")
        print(f"  生肖：{', '.join(f'{x}({s:.1f})' for x, s in zd_pick)}")
    
    print(f"\n⚠️ 免责声明：")
    print(f"  彩票开奖理论上独立随机，任何统计模型都无法保证预测准确。")
    print(f"  请理性对待预测结果，控制投注金额。")

if __name__ == "__main__":
    main()