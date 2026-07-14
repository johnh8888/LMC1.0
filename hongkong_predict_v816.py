#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
香港彩预测系统 V9.1 - 防过拟合专业版

改进:
1. 30期数据 → 训练18期 → 验证6期 → 测试6期
2. 马尔可夫链 1阶 → 3阶（前3期预测下一期）
3. 概率校准（Platt缩放）
4. Frequency → EWMA指数加权平均
5. Trend → Momentum（EMA + MACD + Slope + CUSUM）
6. 保留V8.16所有功能（盲测、回测、优化等）

"""

import re
import json
import urllib.request
import random
import math
from collections import defaultdict
from datetime import datetime


# =====================================================
# 配置
# =====================================================

CONFIG = {
    "history_limit": 30,
    "api_url": "https://marksix6.net/index.php?api=1",
    "lottery_type": "香港彩",
    "train_size": 18,
    "val_size": 6,
    "test_size": 6,
    "bet_mode": "TOP4",
    "weights": {
        "color": 0.25,
        "size": 0.30,
        "odd": 0.25,
        "halfhalf": 0.20
    }
}

REPORT_FILE = "hongkong_result_v91.md"
BET_RECORD_FILE = "hongkong_bet_record_v91.md"


# =====================================================
# 波色定义
# =====================================================

RED = {1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE = {3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
GREEN = {5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}


# =====================================================
# 属性
# =====================================================

def get_color(n):
    if n in RED: return "红"
    if n in BLUE: return "蓝"
    return "绿"

def get_size(n):
    return "大" if n >= 25 else "小"

def get_odd(n):
    return "单" if n % 2 else "双"

def get_halfhalf(n):
    return get_color(n) + get_size(n) + get_odd(n)


# =====================================================
# 数据解析 & 获取
# =====================================================

def parse_numbers(text):
    nums = re.findall(r"\d+", text)
    return [int(x) for x in nums if 1 <= int(x) <= 49]

def fetch_lottery(limit=30):
    rows = []
    try:
        req = urllib.request.Request(
            CONFIG["api_url"],
            headers={"User-Agent": "Mozilla/5.0"}
        )
        data = urllib.request.urlopen(req, timeout=60).read()
        data = json.loads(data.decode("utf-8"))
        
        target = None
        for item in data.get("lottery_data", []):
            name = item.get("name", "").strip()
            print(name)
            if name == CONFIG["lottery_type"]:
                target = item
                break
        
        if not target:
            print(f"未找到 {CONFIG['lottery_type']} 数据")
            return []
        
        print(f"找到 {CONFIG['lottery_type']} 数据")
        
        for line in target.get("history", []):
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
    except Exception as e:
        print("获取失败:", e)
        return []
    
    cache = {}
    for r in rows:
        cache[r["issue"]] = r
    rows = list(cache.values())
    rows.sort(key=lambda x: x["issue"], reverse=True)
    return rows[:limit]


# =====================================================
# 1. EWMA指数加权平均
# =====================================================

class EWMA:
    """指数加权移动平均"""
    
    def __init__(self, rows, attr, alpha=0.3):
        self.rows = rows
        self.attr = attr
        self.alpha = alpha
        self.values = [r[self.attr] for r in rows]
        self.all_values = self._get_all_values(attr)
    
    def _get_all_values(self, attr):
        if attr == "color":
            return ["红", "蓝", "绿"]
        elif attr == "size":
            return ["大", "小"]
        elif attr == "odd":
            return ["单", "双"]
        else:
            return ["红大单", "红大双", "红小单", "红小双",
                    "蓝大单", "蓝大双", "蓝小单", "蓝小双",
                    "绿大单", "绿大双", "绿小单", "绿小双"]
    
    def predict(self):
        weights = defaultdict(float)
        for i, v in enumerate(self.values):
            weight = self.alpha * (1 - self.alpha) ** i
            weights[v] += weight
        
        total = sum(weights.values()) or 1
        result = {}
        for v in self.all_values:
            result[v] = round(weights.get(v, 0) / total * 100, 2)
        return result


# =====================================================
# 2. 3阶马尔可夫链
# =====================================================

class Markov3rdOrder:
    """3阶马尔可夫链 - 前3期预测下一期"""
    
    def __init__(self, rows, attr="halfhalf"):
        self.rows = rows
        self.attr = attr
        self.all_values = ["红大单", "红大双", "红小单", "红小双",
                           "蓝大单", "蓝大双", "蓝小单", "蓝小双",
                           "绿大单", "绿大双", "绿小单", "绿小双"]
        if attr == "color":
            self.all_values = ["红", "蓝", "绿"]
        elif attr == "size":
            self.all_values = ["大", "小"]
        elif attr == "odd":
            self.all_values = ["单", "双"]
        self.transition_matrix = defaultdict(lambda: defaultdict(int))
        self._build_matrix()
    
    def _build_matrix(self):
        for i in range(3, len(self.rows)):
            key = (self.rows[i-3][self.attr], 
                   self.rows[i-2][self.attr], 
                   self.rows[i-1][self.attr])
            next_val = self.rows[i][self.attr]
            self.transition_matrix[key][next_val] += 1
    
    def predict(self):
        if len(self.rows) < 4:
            return {v: 50 for v in self.all_values}
        
        key = (self.rows[0][self.attr],
               self.rows[1][self.attr],
               self.rows[2][self.attr])
        
        transitions = self.transition_matrix.get(key, {})
        total = sum(transitions.values()) or 1
        
        result = {}
        for v in self.all_values:
            result[v] = round(transitions.get(v, 0) / total * 100, 2)
        
        if total == 1:
            freq = defaultdict(int)
            for r in self.rows:
                freq[r[self.attr]] += 1
            total_freq = sum(freq.values()) or 1
            for v in self.all_values:
                result[v] = round(freq.get(v, 0) / total_freq * 100, 2)
        
        return result


# =====================================================
# 3. Momentum模型
# =====================================================

class MomentumModel:
    """趋势动量模型 - 多指标融合"""
    
    def __init__(self, rows, attr="halfhalf"):
        self.rows = rows
        self.attr = attr
        self.all_values = ["红大单", "红大双", "红小单", "红小双",
                           "蓝大单", "蓝大双", "蓝小单", "蓝小双",
                           "绿大单", "绿大双", "绿小单", "绿小双"]
        if attr == "color":
            self.all_values = ["红", "蓝", "绿"]
        elif attr == "size":
            self.all_values = ["大", "小"]
        elif attr == "odd":
            self.all_values = ["单", "双"]
        self.values = [r[self.attr] for r in rows]
    
    def _ema_score(self, window=10):
        alpha = 2 / (window + 1)
        scores = defaultdict(float)
        for i, v in enumerate(self.values[:window]):
            weight = alpha * (1 - alpha) ** i
            scores[v] += weight
        total = sum(scores.values()) or 1
        return {k: v / total * 100 for k, v in scores.items()}
    
    def _macd_score(self, fast=6, slow=12, signal=3):
        scores = defaultdict(float)
        if len(self.values) < slow:
            return {v: 50 for v in self.all_values}
        
        fast_ema = defaultdict(float)
        alpha_fast = 2 / (fast + 1)
        for i, v in enumerate(self.values[:slow]):
            fast_ema[v] = fast_ema.get(v, 0) * (1 - alpha_fast) + 1 * alpha_fast
        
        slow_ema = defaultdict(float)
        alpha_slow = 2 / (slow + 1)
        for i, v in enumerate(self.values[:slow]):
            slow_ema[v] = slow_ema.get(v, 0) * (1 - alpha_slow) + 1 * alpha_slow
        
        macd = {v: fast_ema.get(v, 0) - slow_ema.get(v, 0) for v in self.all_values}
        
        alpha_signal = 2 / (signal + 1)
        signal_line = defaultdict(float)
        for v in self.all_values:
            signal_line[v] = signal_line.get(v, 0) * (1 - alpha_signal) + macd.get(v, 0) * alpha_signal
        
        for v in self.all_values:
            scores[v] = macd.get(v, 0) - signal_line.get(v, 0)
        
        # 转换为概率
        min_val = min(scores.values()) if scores else -1
        max_val = max(scores.values()) if scores else 1
        if max_val > min_val:
            for k in scores:
                scores[k] = (scores[k] - min_val) / (max_val - min_val) * 100
        
        total = sum(scores.values()) or 1
        return {k: v / total * 100 for k, v in scores.items()}
    
    def _slope_score(self, window=8):
        scores = defaultdict(float)
        if len(self.values) < window:
            return {v: 50 for v in self.all_values}
        
        recent = self.values[:window]
        for v in self.all_values:
            positions = [i for i, x in enumerate(recent) if x == v]
            if positions and len(positions) > 1:
                n = len(positions)
                x_sum = sum(positions)
                y_sum = n
                xy_sum = sum(positions)
                x2_sum = sum([p**2 for p in positions])
                slope = (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum**2) if n * x2_sum - x_sum**2 != 0 else 0
                scores[v] = max(0, slope + 1)
            elif positions:
                scores[v] = 1
            else:
                scores[v] = 0
        
        total = sum(scores.values()) or 1
        return {k: v / total * 100 for k, v in scores.items()}
    
    def _cusum_score(self, threshold=0.5):
        scores = defaultdict(float)
        if len(self.values) < 10:
            return {v: 50 for v in self.all_values}
        
        freq = defaultdict(int)
        for v in self.values[:20]:
            freq[v] += 1
        total = sum(freq.values()) or 1
        baseline = {v: freq[v] / total for v in self.all_values}
        
        cusum = defaultdict(float)
        for v in self.values[:15]:
            for val in self.all_values:
                if val == v:
                    cusum[val] += (1 - baseline.get(val, 0.5)) - threshold
                else:
                    cusum[val] -= baseline.get(val, 0.5) + threshold
                cusum[val] = max(0, cusum[val])
        
        total_cusum = sum(cusum.values()) or 1
        return {k: v / total_cusum * 100 for k, v in cusum.items()}
    
    def predict(self):
        scores = defaultdict(float)
        
        weights = {"ema": 0.30, "macd": 0.25, "slope": 0.25, "cusum": 0.20}
        
        models = {
            "ema": self._ema_score(),
            "macd": self._macd_score(),
            "slope": self._slope_score(),
            "cusum": self._cusum_score()
        }
        
        for name, pred in models.items():
            weight = weights.get(name, 0.25)
            for k, v in pred.items():
                scores[k] += v * weight
        
        total = sum(scores.values()) or 1
        return {k: round(v / total * 100, 2) for k, v in scores.items()}


# =====================================================
# 4. 概率校准
# =====================================================

class ProbabilityCalibrator:
    def __init__(self):
        self.alpha = 1.0
        self.beta = 0.0
        self.is_fitted = False
    
    def fit(self, scores, actuals):
        if len(scores) < 5:
            self.is_fitted = False
            return
        
        try:
            import math
            from scipy.optimize import minimize
            
            def log_loss(params):
                a, b = params
                loss = 0
                for s, y in zip(scores, actuals):
                    p = 1 / (1 + math.exp(-(a * s + b)))
                    p = max(0.001, min(0.999, p))
                    loss -= y * math.log(p) + (1 - y) * math.log(1 - p)
                return loss
            
            result = minimize(log_loss, [1.0, 0.0], method='Nelder-Mead')
            self.alpha = result.x[0]
            self.beta = result.x[1]
            self.is_fitted = True
        except:
            self.is_fitted = False
    
    def calibrate(self, score):
        if not self.is_fitted:
            return score / 100
        import math
        p = 1 / (1 + math.exp(-(self.alpha * score + self.beta)))
        return max(0.01, min(0.99, p))


# =====================================================
# 5. 防过拟合训练器
# =====================================================

class AntiOverfitTrainer:
    def __init__(self, rows):
        self.rows = rows
        self.train_size = CONFIG["train_size"]
        self.val_size = CONFIG["val_size"]
        self.test_size = CONFIG["test_size"]
        
        self.train_rows = rows[:self.train_size]
        self.val_rows = rows[self.train_size:self.train_size + self.val_size]
        self.test_rows = rows[self.train_size + self.val_size:self.train_size + self.val_size + self.test_size]
    
    def train(self):
        print(f"\n📊 数据划分:")
        print(f"  训练集: {len(self.train_rows)}期")
        print(f"  验证集: {len(self.val_rows)}期")
        print(f"  测试集: {len(self.test_rows)}期")
        
        models = {
            "ewma": EWMA(self.train_rows, "halfhalf", alpha=0.3),
            "markov3": Markov3rdOrder(self.train_rows),
            "momentum": MomentumModel(self.train_rows)
        }
        
        best_model = None
        best_score = -1
        
        for name, model in models.items():
            correct = 0
            total = 0
            for r in self.val_rows:
                pred = model.predict()
                predicted = max(pred, key=pred.get)
                if predicted == r["halfhalf"]:
                    correct += 1
                total += 1
            
            accuracy = correct / total * 100 if total > 0 else 0
            print(f"  {name}: 验证集准确率 {accuracy:.1f}%")
            
            if accuracy > best_score:
                best_score = accuracy
                best_model = model
        
        if best_model:
            correct = 0
            total = 0
            for r in self.test_rows:
                pred = best_model.predict()
                predicted = max(pred, key=pred.get)
                if predicted == r["halfhalf"]:
                    correct += 1
                total += 1
            
            test_accuracy = correct / total * 100 if total > 0 else 0
            print(f"\n✅ 最优模型测试集准确率: {test_accuracy:.1f}%")
        
        return best_model


# =====================================================
# 6. V9.1 预测器
# =====================================================

class PredictorV91:
    def __init__(self, rows):
        self.rows = rows
        self.all_colors = ["红", "蓝", "绿"]
        self.all_sizes = ["大", "小"]
        self.all_odds = ["单", "双"]
        self.all_halfhalf = ["红大单", "红大双", "红小单", "红小双",
                             "蓝大单", "蓝大双", "蓝小单", "蓝小双",
                             "绿大单", "绿大双", "绿小单", "绿小双"]
    
    def predict_color(self):
        scores = defaultdict(float)
        ewma = EWMA(self.rows, "color", alpha=0.3)
        for k, v in ewma.predict().items():
            scores[k] += v * 0.40
        momentum = MomentumModel(self.rows, "color")
        for k, v in momentum.predict().items():
            scores[k] += v * 0.30
        markov = Markov3rdOrder(self.rows, "color")
        for k, v in markov.predict().items():
            scores[k] += v * 0.30
        
        total = sum(scores.values()) or 1
        return {k: round(v / total * 100, 2) for k, v in scores.items()}
    
    def predict_size(self):
        scores = defaultdict(float)
        ewma = EWMA(self.rows, "size", alpha=0.3)
        for k, v in ewma.predict().items():
            scores[k] += v * 0.40
        momentum = MomentumModel(self.rows, "size")
        for k, v in momentum.predict().items():
            scores[k] += v * 0.30
        markov = Markov3rdOrder(self.rows, "size")
        for k, v in markov.predict().items():
            scores[k] += v * 0.30
        
        total = sum(scores.values()) or 1
        return {k: round(v / total * 100, 2) for k, v in scores.items()}
    
    def predict_odd(self):
        scores = defaultdict(float)
        ewma = EWMA(self.rows, "odd", alpha=0.3)
        for k, v in ewma.predict().items():
            scores[k] += v * 0.40
        momentum = MomentumModel(self.rows, "odd")
        for k, v in momentum.predict().items():
            scores[k] += v * 0.30
        markov = Markov3rdOrder(self.rows, "odd")
        for k, v in markov.predict().items():
            scores[k] += v * 0.30
        
        total = sum(scores.values()) or 1
        return {k: round(v / total * 100, 2) for k, v in scores.items()}
    
    def predict_halfhalf(self):
        scores = defaultdict(float)
        ewma = EWMA(self.rows, "halfhalf", alpha=0.3)
        for k, v in ewma.predict().items():
            scores[k] += v * 0.35
        momentum = MomentumModel(self.rows, "halfhalf")
        for k, v in momentum.predict().items():
            scores[k] += v * 0.35
        markov = Markov3rdOrder(self.rows, "halfhalf")
        for k, v in markov.predict().items():
            scores[k] += v * 0.30
        
        total = sum(scores.values()) or 1
        return {k: round(v / total * 100, 2) for k, v in scores.items()}
    
    def predict(self):
        color = self.predict_color()
        size = self.predict_size()
        odd = self.predict_odd()
        halfhalf = self.predict_halfhalf()
        
        candidates = []
        top_colors = sorted(color.items(), key=lambda x: x[1], reverse=True)[:2]
        
        for c, cp in top_colors:
            for h, hp in list(halfhalf.items())[:5]:
                if not h.startswith(c):
                    continue
                s = h[1]
                o = h[2]
                score = (
                    cp * CONFIG["weights"]["color"] +
                    size.get(s, 0) * CONFIG["weights"]["size"] +
                    odd.get(o, 0) * CONFIG["weights"]["odd"] +
                    hp * CONFIG["weights"]["halfhalf"]
                )
                candidates.append({"halfhalf": h, "score": round(score, 2)})
        
        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "color": color,
            "size": size,
            "odd": odd,
            "halfhalf": halfhalf,
            "candidates": candidates[:5]
        }


# =====================================================
# 7. 盲测
# =====================================================

class BackTestV91:
    def __init__(self, rows):
        self.rows = rows
    
    def run(self, test_days=10):
        result = {
            "color": [0, 0],
            "size": [0, 0],
            "odd": [0, 0],
            "halfhalf": [0, 0],
            "top3": [0, 0]
        }
        total = min(test_days, len(self.rows) - 10)
        for i in range(total):
            history = self.rows[i+1:]
            actual = self.rows[i]
            predictor = PredictorV91(history)
            pred = predictor.predict()
            result["color"][1] += 1
            result["size"][1] += 1
            result["odd"][1] += 1
            result["halfhalf"][1] += 1
            result["top3"][1] += 1
            if max(pred["color"], key=pred["color"].get) == actual["color"]:
                result["color"][0] += 1
            if max(pred["size"], key=pred["size"].get) == actual["size"]:
                result["size"][0] += 1
            if max(pred["odd"], key=pred["odd"].get) == actual["odd"]:
                result["odd"][0] += 1
            hlist = [x["halfhalf"] for x in pred["candidates"]]
            if actual["halfhalf"] in hlist:
                result["halfhalf"][0] += 1
            if actual["halfhalf"] in [x["halfhalf"] for x in pred["candidates"][:3]]:
                result["top3"][0] += 1
        return result
    
    def print_result(self):
        r = self.run()
        print()
        print("=" * 40)
        print("V9.1 最近10期盲测")
        print("=" * 40)
        for k, v in r.items():
            print(f"{k}: {v[0]}/{v[1]} = {round(v[0]/v[1]*100, 2)}%")
        return r


# =====================================================
# 8. 精确投注回测
# =====================================================

class ExactBetBackTestV91:
    def __init__(self, rows, odds_config=None, bet_amount=50):
        self.rows = rows
        self.bet_amount = bet_amount
        self.odds = odds_config or {
            "红": 5.82, "蓝": 5.82, "绿": 5.82,
            "大": 6.6, "小": 4.7,
            "单": 5.82, "双": 5.16,
            "红大单": 9.45, "红大双": 11.82,
            "红小单": 9.45, "红小双": 9.45,
            "蓝大单": 9.45, "蓝大双": 11.82,
            "蓝小单": 15.76, "蓝小双": 11.82,
            "绿大单": 11.82, "绿大双": 11.82,
            "绿小单": 11.82, "绿小双": 15.76,
        }
    
    def simulate_mode(self, mode="TOP4", test_days=10):
        results = []
        total_bet = 0
        total_return = 0
        total_profit = 0
        hit_count = 0
        balance = 0
        balance_history = []
        start_idx = min(test_days, len(self.rows) - 1)
        for i in range(start_idx, 0, -1):
            history = self.rows[i:]
            actual = self.rows[i - 1]
            predictor = PredictorV91(history)
            pred = predictor.predict()
            candidates = pred["candidates"]
            bet_list = []
            if mode == "TOP3":
                bet_list = [c["halfhalf"] for c in candidates[:3]]
            elif mode == "TOP4":
                bet_list = [c["halfhalf"] for c in candidates[:4]]
            elif mode == "TOP5":
                bet_list = [c["halfhalf"] for c in candidates[:5]]
            bet_count = len(bet_list)
            if bet_count == 0:
                continue
            bet = self.bet_amount * bet_count
            total_bet += bet
            hit = False
            win_amount = 0
            for hh in bet_list:
                if hh == actual["halfhalf"]:
                    hit = True
                    odds = self.odds.get(hh, 0)
                    win_amount = self.bet_amount * odds
                    break
            if hit:
                hit_count += 1
                total_return += win_amount
            profit = win_amount - bet
            total_profit += profit
            balance += profit
            balance_history.append(balance)
            results.append({
                "issue": actual["issue"],
                "actual": actual["halfhalf"],
                "bet_list": bet_list,
                "bet_amount": bet,
                "win_amount": win_amount,
                "profit": profit,
                "balance": balance,
                "hit": hit
            })
        roi = (total_profit / total_bet * 100) if total_bet > 0 else 0
        return {
            "mode": mode,
            "results": results,
            "total_bet": total_bet,
            "total_return": total_return,
            "total_profit": total_profit,
            "hit_count": hit_count,
            "total_periods": len(results),
            "hit_rate": hit_count / len(results) * 100 if results else 0,
            "roi": roi
        }
    
    def compare_modes(self, test_days=10):
        modes = ["TOP3", "TOP4", "TOP5"]
        results = {}
        print(f"\n{'='*60}")
        print(f"🔄 V9.1 三种下注模式对比 (最近{test_days}期)")
        print(f"{'='*60}")
        for mode in modes:
            results[mode] = self.simulate_mode(mode, test_days)
        print(f"\n{'模式':<10} {'总投注':<12} {'总回报':<12} {'净盈利':<12} {'ROI':<12} {'命中率':<12}")
        print(f"{'-'*70}")
        for mode, data in results.items():
            print(f"{mode:<10} {data['total_bet']:<12.2f} {data['total_return']:<12.2f} "
                  f"{data['total_profit']:<+12.2f} {data['roi']:<+12.2f}% "
                  f"{data['hit_rate']:<12.2f}%")
        print(f"{'='*60}")
        best_mode = max(results, key=lambda x: x["roi"])
        print(f"\n🏆 最优模式: {best_mode} (ROI: {results[best_mode]['roi']:+.2f}%)")
        return results, best_mode
    
    def print_report(self, mode="TOP4", test_days=10):
        data = self.simulate_mode(mode, test_days)
        print(f"\n{'='*60}")
        print(f"📊 V9.1 {mode} 下注模式详细回测 (含本金)")
        print(f"  每注金额: {self.bet_amount} 元")
        print(f"  赔率计算: 中奖金额 = 投注 × 赔率")
        print(f"{'='*60}")
        print(f"\n📋 最近{test_days}期明细:")
        print(f"{'期号':<12} {'实际开奖':<12} {'下注':<25} {'投注':<8} {'中奖':<10} {'盈亏':<10} {'余额':<10}")
        print(f"{'-'*85}")
        for r in data["results"][:test_days]:
            bet_str = ",".join(r["bet_list"][:3])
            if len(r["bet_list"]) > 3:
                bet_str += f"+{len(r['bet_list'])-3}"
            print(f"{r['issue']:<12} {r['actual']:<12} {bet_str:<25} "
                  f"{r['bet_amount']:<8.0f} {r['win_amount']:<10.2f} "
                  f"{r['profit']:<+10.2f} {r['balance']:<10.2f}")
        print(f"{'-'*85}")
        print(f"\n📊 汇总统计:")
        print(f"  回测期数: {data['total_periods']} 期")
        print(f"  命中次数: {data['hit_count']} 次")
        print(f"  命中率: {data['hit_rate']:.2f}%")
        print(f"  总投注: {data['total_bet']:.2f} 元")
        print(f"  总回报: {data['total_return']:.2f} 元")
        print(f"  净盈利: {data['total_profit']:+.2f} 元")
        print(f"  ROI: {data['roi']:+.2f}%")
        return data


# =====================================================
# 9. 下注记录
# =====================================================

class BetRecord:
    def __init__(self):
        self.records = []
        self.total_bet = 0
        self.total_win = 0
        self.total_profit = 0
        self.consecutive_loss = 0
    
    def add_record(self, issue, bets, actual, win_amount):
        bet_amount = 50 * len(bets)
        profit = win_amount - bet_amount
        record = {
            "issue": issue,
            "bets": bets,
            "actual": actual,
            "bet_amount": bet_amount,
            "win_amount": win_amount,
            "profit": profit
        }
        self.records.append(record)
        self.total_bet += bet_amount
        self.total_win += win_amount
        self.total_profit += profit
        if profit < 0:
            self.consecutive_loss += 1
        else:
            self.consecutive_loss = 0
    
    def print_summary(self):
        print("\n" + "=" * 60)
        print("📋 下注记录汇总")
        print("=" * 60)
        if not self.records:
            print("暂无记录")
            return
        print(f"\n{'期号':<12} {'下注':<25} {'实际':<10} {'投注':<8} {'中奖':<10} {'盈亏':<10}")
        print("-" * 85)
        for r in self.records:
            bets_str = ",".join(r["bets"])
            print(f"{r['issue']:<12} {bets_str:<25} {r['actual']:<10} "
                  f"{r['bet_amount']:<8.0f} {r['win_amount']:<10.2f} {r['profit']:<+10.2f}")
        print("-" * 85)
        print(f"\n总投注: {self.total_bet:.2f}元")
        print(f"总中奖: {self.total_win:.2f}元")
        print(f"总盈亏: {self.total_profit:+.2f}元")
        print(f"连续亏损: {self.consecutive_loss}期")
        roi = (self.total_profit / self.total_bet * 100) if self.total_bet > 0 else 0
        print(f"ROI: {roi:+.2f}%")
        if self.consecutive_loss >= 2:
            print(f"\n⚠️ 连续亏损{self.consecutive_loss}期，建议观望1-2期！")
        print("=" * 60)
    
    def save_to_file(self):
        with open(BET_RECORD_FILE, "w", encoding="utf-8") as f:
            f.write("# 香港彩下注记录（V9.1）\n\n")
            f.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            if not self.records:
                f.write("暂无记录\n")
                return
            f.write("| 期号 | 下注 | 实际开奖 | 投注 | 中奖 | 盈亏 |\n")
            f.write("|------|------|----------|------|------|------|\n")
            for r in self.records:
                bets_str = ",".join(r["bets"])
                f.write(f"| {r['issue']} | {bets_str} | {r['actual']} | "
                       f"{r['bet_amount']:.0f} | {r['win_amount']:.2f} | {r['profit']:+.2f} |\n")
            f.write("\n## 汇总\n\n")
            f.write(f"- 总投注: {self.total_bet:.2f}元\n")
            f.write(f"- 总中奖: {self.total_win:.2f}元\n")
            f.write(f"- 总盈亏: {self.total_profit:+.2f}元\n")
            roi = (self.total_profit / self.total_bet * 100) if self.total_bet > 0 else 0
            f.write(f"- ROI: {roi:+.2f}%\n")
            f.write(f"- 连续亏损: {self.consecutive_loss}期\n")


# =====================================================
# 10. 报告
# =====================================================

def save_report(result):
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("# 香港彩 V9.1 预测报告\n\n")
        f.write("## 颜色预测\n\n")
        for k, v in sorted(result["color"].items(), key=lambda x: x[1], reverse=True):
            f.write(f"{k}: {v}%\n")
        f.write("\n## 大小预测\n\n")
        for k, v in sorted(result["size"].items(), key=lambda x: x[1], reverse=True):
            f.write(f"{k}: {v}%\n")
        f.write("\n## 单双预测\n\n")
        for k, v in sorted(result["odd"].items(), key=lambda x: x[1], reverse=True):
            f.write(f"{k}: {v}%\n")
        f.write("\n## 最终TOP5\n\n")
        for i, c in enumerate(result["candidates"], 1):
            f.write(f"{i}. {c['halfhalf']} {c['score']}\n")


# =====================================================
# 11. 主程序
# =====================================================

def main():
    print("=" * 50)
    print("🎯 香港彩预测系统 V9.1（防过拟合专业版）")
    print("=" * 50)
    
    print("\n📡 正在获取香港彩数据...")
    rows = fetch_lottery(30)
    
    if len(rows) < 18:
        print("❌ 数据不足（需要至少18期）")
        return
    
    print(f"\n📋 获取到 {len(rows)} 期数据")
    
    # =====================================================
    # 防过拟合训练
    # =====================================================
    trainer = AntiOverfitTrainer(rows)
    best_model = trainer.train()
    
    # =====================================================
    # 预测（只用训练集）
    # =====================================================
    print("\n" + "=" * 35)
    print("🔮 最终预测")
    print("=" * 35)
    
    predictor = PredictorV91(rows[:18])
    result = predictor.predict()
    
    print("\n🎨 颜色预测:")
    for k, v in sorted(result["color"].items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(v / 5)
        print(f"  {k}: {v}% {bar}")
    
    print("\n📏 大小预测:")
    for k, v in sorted(result["size"].items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(v / 5)
        print(f"  {k}: {v}% {bar}")
    
    print("\n🔢 单双预测:")
    for k, v in sorted(result["odd"].items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(v / 5)
        print(f"  {k}: {v}% {bar}")
    
    print("\n🏆 推荐下注 (TOP5):")
    for i, c in enumerate(result["candidates"][:5], 1):
        bar = "█" * int(c["score"] / 5)
        print(f"  {i}. {c['halfhalf']:8s} 得分: {c['score']:6.2f} {bar}")
    
    # =====================================================
    # 下注建议（TOP4）
    # =====================================================
    print("\n" + "=" * 50)
    print("🎯 今晚下注建议（TOP4）")
    print("=" * 50)
    
    bet_mode = CONFIG.get("bet_mode", "TOP4")
    bet_count = 4 if bet_mode == "TOP4" else 3
    bet_list = result["candidates"][:bet_count]
    
    colors_covered = set()
    for c in bet_list:
        colors_covered.add(c["halfhalf"][0])
    
    sizes_covered = set()
    for c in bet_list:
        sizes_covered.add(c["halfhalf"][1])
    
    odds_covered = set()
    for c in bet_list:
        odds_covered.add(c["halfhalf"][2])
    
    bet_amount = bet_count * 50
    
    print(f"\n📋 推荐下注（{bet_mode}，覆盖{len(colors_covered)}种颜色）:")
    for i, c in enumerate(bet_list, 1):
        print(f"  {i}. {c['halfhalf']} (得分: {c['score']})")
    
    print(f"\n🎨 覆盖颜色: {' + '.join(sorted(colors_covered))}")
    print(f"  颜色命中率: {len(colors_covered)/len(bet_list)*100:.0f}%")
    print(f"📏 大小覆盖: {' + '.join(sorted(sizes_covered))}（{len(sizes_covered)/len(bet_list)*100:.0f}%）")
    print(f"🔢 单双覆盖: {' + '.join(sorted(odds_covered))}（{len(odds_covered)/len(bet_list)*100:.0f}%）")
    print(f"\n💰 下注金额: {bet_amount}元 ({bet_count}注×50元)")
    for c in bet_list:
        print(f"  {c['halfhalf']}: 50元")
    
    # =====================================================
    # 盲测
    # =====================================================
    BackTestV91(rows).print_result()
    
    # =====================================================
    # 真实盈利回测
    # =====================================================
    print("\n" + "=" * 60)
    print("💰 V9.1 真实盈利回测")
    print("=" * 60)
    
    exact_test = ExactBetBackTestV91(rows, bet_amount=50)
    exact_test.compare_modes(test_days=10)
    print()
    exact_test.print_report(mode="TOP4", test_days=10)
    
    # =====================================================
    # 保存报告
    # =====================================================
    save_report(result)
    print(f"\n📄 报告已保存: {REPORT_FILE}")
    
    # =====================================================
    # 下注记录
    # =====================================================
    bet_record = BetRecord()
    bet_record.save_to_file()
    print(f"📄 下注记录已保存: {BET_RECORD_FILE}")
    
    print("\n" + "=" * 50)
    print("✅ 预测完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()