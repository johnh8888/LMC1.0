#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
香港彩预测系统 V9.0 - 精简版（只保留最强模型）

核心功能:
1. 颜色：只用遗漏值分析
2. 大小：只用遗漏值分析  
3. 单双：只用连号检测
4. 半半波：只用马尔可夫链
5. 保留所有V8.16功能（盲测、回测、优化等）

"""

import re
import json
import urllib.request
import random
from collections import defaultdict


# =====================================================
# 配置
# =====================================================

CONFIG = {
    "history_limit": 50,
    "api_url": "https://marksix6.net/index.php?api=1",
    "lottery_type": "香港彩",
    "weights": {
        "color": 0.25,
        "size": 0.30,
        "odd": 0.25,
        "halfhalf": 0.20
    }
}

REPORT_FILE = "hongkong_result_v9_lite.md"


# =====================================================
# 各维度内部权重配置（精简版 - 只保留最强模型）
# =====================================================

COLOR_WEIGHTS = {
    "miss": 1.0,      # 只用遗漏值
    "frequency": 0.0,
    "trend": 0.0,
    "markov": 0.0,
    "zone": 0.0
}

SIZE_WEIGHTS = {
    "miss": 1.0,      # 只用遗漏值
    "frequency": 0.0,
    "trend": 0.0,
    "markov": 0.0,
    "consecutive": 0.0
}

ODD_WEIGHTS = {
    "consecutive": 1.0,  # 只用连号检测
    "frequency": 0.0,
    "trend": 0.0,
    "markov": 0.0,
    "tail": 0.0
}

ENSEMBLE_WEIGHTS = {
    "attribute": 0.35,
    "markov": 0.25,
    "frequency": 0.20,
    "trend": 0.20
}


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
# 数据解析
# =====================================================

def parse_numbers(text):
    nums = re.findall(r"\d+", text)
    return [int(x) for x in nums if 1 <= int(x) <= 49]


# =====================================================
# 获取数据
# =====================================================

def fetch_lottery(limit=50):
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
# V9.0 精简预测模型（只保留最强模型）
# =====================================================

class LitePredictor:
    """精简预测模型 - 每个维度只用最强模型"""
    
    def __init__(self, rows):
        self.rows = rows[:50]
        self.all_colors = ["红", "蓝", "绿"]
        self.all_sizes = ["大", "小"]
        self.all_odds = ["单", "双"]
        self.all_halfhalf = ["红大单", "红大双", "红小单", "红小双",
                             "蓝大单", "蓝大双", "蓝小单", "蓝小双",
                             "绿大单", "绿大双", "绿小单", "绿小双"]
    
    # =================================================
    # 颜色：只用遗漏值分析（最强）
    # =================================================
    def color_miss_score(self):
        score = defaultdict(float)
        for v in self.all_colors:
            miss = 0
            for r in self.rows:
                if r["color"] == v:
                    break
                miss += 1
            score[v] = min(miss * 1.2, 20)
        total = sum(score.values()) or 1
        return {k: round(v / total * 100, 2) for k, v in score.items()}
    
    # =================================================
    # 大小：只用遗漏值分析（最强）
    # =================================================
    def size_miss_score(self):
        score = defaultdict(float)
        for v in self.all_sizes:
            miss = 0
            for r in self.rows:
                if r["size"] == v:
                    break
                miss += 1
            score[v] = min(miss * 1.2, 20)
        total = sum(score.values()) or 1
        return {k: round(v / total * 100, 2) for k, v in score.items()}
    
    # =================================================
    # 单双：只用连号检测（最强）
    # =================================================
    def odd_consecutive_score(self):
        score = defaultdict(float)
        recent = [r["odd"] for r in self.rows[:15]]
        if len(recent) < 3:
            return {"单": 50, "双": 50}
        
        consecutive_odd = 0
        consecutive_even = 0
        for o in recent[:10]:
            if o == "单":
                consecutive_odd += 1
                consecutive_even = 0
            else:
                consecutive_even += 1
                consecutive_odd = 0
        
        if consecutive_odd >= 3:
            score["双"] = 70
            score["单"] = 30
        elif consecutive_even >= 3:
            score["单"] = 70
            score["双"] = 30
        else:
            score["单"] = 50
            score["双"] = 50
        return score
    
    # =================================================
    # 半半波：只用马尔可夫链（最强）
    # =================================================
    def halfhalf_markov_score(self):
        score = defaultdict(float)
        if len(self.rows) < 2:
            return {v: 50 for v in self.all_halfhalf}
        
        current = self.rows[0]["halfhalf"]
        transitions = defaultdict(lambda: defaultdict(int))
        for i in range(len(self.rows) - 1):
            curr = self.rows[i]["halfhalf"]
            next_hh = self.rows[i + 1]["halfhalf"]
            transitions[curr][next_hh] += 1
        
        total = sum(transitions[current].values()) or 1
        for v in self.all_halfhalf:
            score[v] = round(transitions[current].get(v, 0) / total * 100, 2)
        return score
    
    # =================================================
    # 综合预测
    # =================================================
    def predict(self):
        color = self.color_miss_score()
        size = self.size_miss_score()
        odd = self.odd_consecutive_score()
        
        candidates = []
        top_colors = sorted(color.items(), key=lambda x: x[1], reverse=True)[:2]
        
        for c, cp in top_colors:
            hh = self.halfhalf_markov_score()
            for h, hp in list(hh.items())[:5]:
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
        
        if len(candidates) >= 3:
            signal_strength = candidates[0]["score"] - candidates[2]["score"]
        else:
            signal_strength = 0
        
        return {
            "color": color,
            "size": size,
            "odd": odd,
            "candidates": candidates[:5],
            "signal_strength": round(signal_strength, 2)
        }


# =====================================================
# V8.16 保留功能：基础统计模型
# =====================================================

class AttributeModel:
    def __init__(self, rows):
        self.rows = rows[:50]

    def window_score(self, attr):
        score = defaultdict(float)
        for size, weight in [(15, 0.5), (30, 0.3), (50, 0.2)]:
            for i, r in enumerate(self.rows[:size]):
                score[r[attr]] += (size - i) * weight
        return score

    def miss_score(self, attr, values):
        result = defaultdict(float)
        for v in values:
            miss = 0
            for r in self.rows:
                if r[attr] == v:
                    break
                miss += 1
            result[v] = min(miss * 1.5, 15)
        return result

    def trend_balance(self, attr, score):
        recent = [r[attr] for r in self.rows[:8]]
        count = {x: recent.count(x) for x in set(recent)}
        for k, v in count.items():
            if v >= 3:
                score[k] -= v * 3
        return score

    def predict(self, attr, values):
        score = self.window_score(attr)
        miss = self.miss_score(attr, values)
        for k in values:
            score[k] += miss[k]
        score = self.trend_balance(attr, score)
        total = sum(score.values()) or 1
        return {k: round(max(score[k], 0) / total * 100, 2) for k in values}

    def color(self):
        return self.predict("color", ["红", "蓝", "绿"])

    def size(self):
        return self.predict("size", ["大", "小"])

    def odd(self):
        return self.predict("odd", ["单", "双"])

    def halfhalf(self, color=None):
        score = defaultdict(float)
        for size, weight in [(15, 0.5), (30, 0.3), (50, 0.2)]:
            for i, r in enumerate(self.rows[:size]):
                hh = r["halfhalf"]
                if color and not hh.startswith(color):
                    continue
                score[hh] += (size - i) * weight
        for k in list(score.keys()):
            miss = 0
            for r in self.rows:
                if r["halfhalf"] == k:
                    break
                miss += 1
            score[k] += min(miss, 10)
        total = sum(score.values()) or 1
        return {k: round(v / total * 100, 2) for k, v in sorted(score.items(), key=lambda x: x[1], reverse=True)}


# =====================================================
# V8.16 保留功能：最终融合
# =====================================================

class FusionV816:
    def __init__(self, rows, weights=None):
        self.rows = rows
        self.model = AttributeModel(rows)
        self.weights = weights or CONFIG["weights"]

    def predict(self):
        color = self.model.color()
        size = self.model.size()
        odd = self.model.odd()
        candidates = []
        top_colors = sorted(color.items(), key=lambda x: x[1], reverse=True)[:2]
        for c, cp in top_colors:
            hh = self.model.halfhalf(c)
            for h, hp in list(hh.items())[:5]:
                s = h[1]
                o = h[2]
                score = (
                    cp * self.weights["color"] +
                    size.get(s, 0) * self.weights["size"] +
                    odd.get(o, 0) * self.weights["odd"] +
                    hp * self.weights["halfhalf"]
                )
                candidates.append({"halfhalf": h, "score": round(score, 2)})
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return {
            "color": color,
            "size": size,
            "odd": odd,
            "candidates": candidates[:5]
        }


# =====================================================
# V8.16 保留功能：盲测回测系统
# =====================================================

class BackTest816:
    def __init__(self, rows):
        self.rows = rows

    def run(self):
        result = {
            "color": [0, 0],
            "size": [0, 0],
            "odd": [0, 0],
            "halfhalf": [0, 0],
            "top3": [0, 0]
        }
        total = min(10, len(self.rows) - 10)
        for i in range(total):
            history = self.rows[i+1:]
            actual = self.rows[i]
            model = FusionV816(history)
            pred = model.predict()
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
        print("V8.16 最近10期盲测")
        print("=" * 40)
        for k, v in r.items():
            print(f"{k}: {v[0]}/{v[1]} = {round(v[0]/v[1]*100, 2)}%")
        return r


# =====================================================
# V9.0 精简版盲测
# =====================================================

class BackTestLite:
    def __init__(self, rows):
        self.rows = rows

    def run(self, test_days=15):
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
            predictor = LitePredictor(history)
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
        print("V9.0精简版 最近15期盲测")
        print("=" * 40)
        for k, v in r.items():
            print(f"{k}: {v[0]}/{v[1]} = {round(v[0]/v[1]*100, 2)}%")
        return r


# =====================================================
# V9.0精简版 精确投注回测
# =====================================================

class ExactBetBackTestLite:
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
    
    def simulate_mode(self, mode="TOP3", test_days=10):
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
            predictor = LitePredictor(history)
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
        print(f"🔄 V9.0精简版 三种下注模式对比 (最近{test_days}期)")
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


# =====================================================
# 报告
# =====================================================

def save_report(result):
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("# 香港彩 V9.0精简版 预测报告\n\n")
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
# 主程序
# =====================================================

def main():
    print("=" * 50)
    print("🎯 香港彩预测系统 V9.0精简版")
    print("=" * 50)
    
    print("\n📡 正在获取香港彩数据...")
    rows = fetch_lottery(50)
    
    if len(rows) < 10:
        print("❌ 数据不足（需要至少10期）")
        return
    
    print(f"\n📋 获取到 {len(rows)} 期数据")
    
    # =====================================================
    # V8.16 预测
    # =====================================================
    print("\n" + "=" * 35)
    print("V8.16 香港彩预测 (50期数据版)")
    print("=" * 35)
    
    model = FusionV816(rows)
    result = model.predict()
    
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
    
    print("\n🏆 最终TOP5:")
    for i, c in enumerate(result["candidates"], 1):
        score_bar = "█" * int(c["score"] / 5)
        print(f"  {i}. {c['halfhalf']:8s} 得分: {c['score']:6.2f} {score_bar}")
    
    # =====================================================
    # V9.0精简版 预测
    # =====================================================
    print("\n" + "=" * 35)
    print("V9.0精简版 预测 (只用最强模型)")
    print("=" * 35)
    
    lite_predictor = LitePredictor(rows)
    result_lite = lite_predictor.predict()
    
    print("\n🎨 颜色预测 (遗漏值):")
    for k, v in sorted(result_lite["color"].items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(v / 5)
        print(f"  {k}: {v}% {bar}")
    
    print("\n📏 大小预测 (遗漏值):")
    for k, v in sorted(result_lite["size"].items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(v / 5)
        print(f"  {k}: {v}% {bar}")
    
    print("\n🔢 单双预测 (连号检测):")
    for k, v in sorted(result_lite["odd"].items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(v / 5)
        print(f"  {k}: {v}% {bar}")
    
    print("\n🏆 推荐下注 (TOP5):")
    print("-" * 40)
    for i, c in enumerate(result_lite["candidates"][:5], 1):
        score_bar = "█" * int(c["score"] / 5)
        print(f"  {i}. {c['halfhalf']:8s} 得分: {c['score']:6.2f} {score_bar}")
    
    print(f"\n📊 信号强度: {result_lite['signal_strength']}")
    
    if result_lite['signal_strength'] > 10:
        print(f"\n✅ 信号较强，建议下注:")
        top3 = [c["halfhalf"] for c in result_lite["candidates"][:3]]
        print(f"   TOP3: {'  '.join(top3)}")
        print(f"   每注50元，共150元")
    else:
        print(f"\n⚠️ 信号较弱，建议观望")
    
    # =====================================================
    # V8.16 盲测
    # =====================================================
    BackTest816(rows).print_result()
    
    # =====================================================
    # V9.0精简版 盲测
    # =====================================================
    BackTestLite(rows).print_result()
    
    # =====================================================
    # V9.0精简版 盈利回测
    # =====================================================
    print("\n" + "=" * 60)
    print("💰 V9.0精简版 真实盈利回测")
    print("=" * 60)
    
    exact_lite = ExactBetBackTestLite(rows, bet_amount=50)
    exact_lite.compare_modes(test_days=10)
    
    # =====================================================
    # 保存报告
    # =====================================================
    save_report(result_lite)
    print(f"\n📄 报告已保存: {REPORT_FILE}")
    
    print("\n" + "=" * 50)
    print("✅ 预测完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()