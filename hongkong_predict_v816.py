#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
香港彩 V8.16 回测分析工具
专门用来对比 TOP3、TOP4、TOP5 的真实表现

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
    "history_limit": 30,
    "api_url": "https://marksix6.net/index.php?api=1",
    "lottery_type": "香港彩",
    "weights": {
        "color": 0.25,
        "size": 0.30,
        "odd": 0.25,
        "halfhalf": 0.20
    }
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
            if name == CONFIG["lottery_type"]:
                target = item
                break
        
        if not target:
            print(f"未找到 {CONFIG['lottery_type']} 数据")
            return []
        
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
# 基础预测模型
# =====================================================

class Predictor:
    def __init__(self, rows):
        self.rows = rows[:30]
    
    def window_score(self, attr):
        score = defaultdict(float)
        for size, weight in [(10, 0.5), (20, 0.3), (30, 0.2)]:
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
        for size, weight in [(10, 0.5), (20, 0.3), (30, 0.2)]:
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
    
    def full_predict(self):
        color = self.color()
        size = self.size()
        odd = self.odd()
        
        candidates = []
        top_colors = sorted(color.items(), key=lambda x: x[1], reverse=True)[:2]
        
        for c, cp in top_colors:
            hh = self.halfhalf(c)
            for h, hp in list(hh.items())[:5]:
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
        return candidates


# =====================================================
# 回测引擎
# =====================================================

class BacktestEngine:
    def __init__(self, rows, odds_config=None, bet_amount=50):
        self.rows = rows
        self.bet_amount = bet_amount
        self.odds = odds_config or {
            "红大单": 15.76, "红大双": 11.82, "红小单": 9.45, "红小双": 9.45,
            "蓝大单": 9.45, "蓝大双": 11.82, "蓝小单": 15.76, "蓝小双": 11.82,
            "绿大单": 11.82, "绿大双": 11.82, "绿小单": 11.82, "绿小双": 15.76,
        }
    
    def backtest_mode(self, mode="TOP3", test_days=30):
        """回测指定模式"""
        results = []
        total_bet = 0
        total_return = 0
        total_profit = 0
        hit_count = 0
        balance = 0
        balance_history = []
        win_history = []  # 每期是否中奖
        
        start_idx = min(test_days, len(self.rows) - 1)
        
        print(f"\n{'='*60}")
        print(f"📊 {mode} 回测（最近{start_idx}期）")
        print(f"{'='*60}")
        
        for i in range(start_idx, 0, -1):
            history = self.rows[i:]
            actual = self.rows[i - 1]
            
            predictor = Predictor(history)
            candidates = predictor.full_predict()
            
            # 根据模式选择下注
            if mode == "TOP3":
                bet_list = [c["halfhalf"] for c in candidates[:3]]
            elif mode == "TOP4":
                bet_list = [c["halfhalf"] for c in candidates[:4]]
            elif mode == "TOP5":
                bet_list = [c["halfhalf"] for c in candidates[:5]]
            else:
                bet_list = []
            
            bet_count = len(bet_list)
            if bet_count == 0:
                continue
            
            bet = self.bet_amount * bet_count
            total_bet += bet
            
            # 判断中奖
            hit = False
            win_amount = 0
            hit_hh = None
            
            for hh in bet_list:
                if hh == actual["halfhalf"]:
                    hit = True
                    hit_hh = hh
                    odds = self.odds.get(hh, 9.45)
                    win_amount = self.bet_amount * odds
                    break
            
            if hit:
                hit_count += 1
                total_return += win_amount
                win_history.append(1)
            else:
                win_amount = 0
                win_history.append(0)
            
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
        hit_rate = hit_count / len(results) * 100 if results else 0
        
        return {
            "mode": mode,
            "results": results,
            "win_history": win_history,
            "total_bet": total_bet,
            "total_return": total_return,
            "total_profit": total_profit,
            "hit_count": hit_count,
            "total_periods": len(results),
            "hit_rate": hit_rate,
            "roi": roi,
            "balance_history": balance_history
        }
    
    def print_detail(self, data):
        """打印详细回测结果"""
        print(f"\n📋 每期明细:")
        print(f"{'期号':<12} {'实际开奖':<12} {'下注':<35} {'投注':<8} {'中奖':<10} {'盈亏':<10} {'余额':<10}")
        print("-" * 95)
        
        for r in data["results"][:20]:  # 最多显示20期
            bet_str = ",".join(r["bet_list"][:3])
            if len(r["bet_list"]) > 3:
                bet_str += f"+{len(r['bet_list'])-3}"
            hit_mark = "✅" if r["hit"] else "❌"
            print(f"{r['issue']:<12} {r['actual']:<12} {bet_str:<35} "
                  f"{r['bet_amount']:<8.0f} {r['win_amount']:<10.2f} "
                  f"{r['profit']:<+10.2f} {r['balance']:<10.2f}")
        
        if len(data["results"]) > 20:
            print(f"... 共{len(data['results'])}期，只显示前20期")
        
        print("-" * 95)
        
        # 汇总统计
        print(f"\n📊 汇总统计:")
        print(f"  回测期数: {data['total_periods']} 期")
        print(f"  命中次数: {data['hit_count']} 次")
        print(f"  命中率: {data['hit_rate']:.2f}%")
        print(f"  总投注: {data['total_bet']:.2f} 元")
        print(f"  总回报: {data['total_return']:.2f} 元")
        print(f"  净盈利: {data['total_profit']:+.2f} 元")
        print(f"  ROI: {data['roi']:+.2f}%")
        
        # 连续亏损分析
        max_consecutive_loss = 0
        current = 0
        for r in data["results"]:
            if not r["hit"]:
                current += 1
                max_consecutive_loss = max(max_consecutive_loss, current)
            else:
                current = 0
        
        print(f"  最大连续亏损: {max_consecutive_loss}期")
        
        # 盈亏柱状图
        if data["results"]:
            print(f"\n📈 盈亏走势（最近20期）:")
            max_profit = max([abs(r["profit"]) for r in data["results"][:20]]) or 1
            for i, r in enumerate(data["results"][:20]):
                bar_len = int((r["profit"] / max_profit) * 15)
                if r["profit"] > 0:
                    bar = "█" * min(bar_len, 15) + "░" * (15 - min(bar_len, 15))
                    print(f"  第{i+1:2d}期: {bar} +{r['profit']:6.2f}元")
                elif r["profit"] < 0:
                    bar = "█" * min(abs(bar_len), 15) + "░" * (15 - min(abs(bar_len), 15))
                    print(f"  第{i+1:2d}期: {bar} {r['profit']:6.2f}元")
                else:
                    print(f"  第{i+1:2d}期: {'░░░░░░░░░░░░░░░'} {r['profit']:6.2f}元")
        
        print("=" * 60)
        
        return data
    
    def compare_all_modes(self, test_days=30):
        """对比三种模式"""
        modes = ["TOP3", "TOP4", "TOP5"]
        results = {}
        
        print("\n" + "=" * 60)
        print(f"🔄 三种下注模式对比（最近{test_days}期）")
        print("=" * 60)
        
        for mode in modes:
            results[mode] = self.backtest_mode(mode, test_days)
        
        print(f"\n{'模式':<10} {'总投注':<12} {'总回报':<12} {'净盈利':<12} {'ROI':<12} {'命中率':<12} {'命中次数':<10}")
        print("-" * 80)
        
        for mode, data in results.items():
            print(f"{mode:<10} {data['total_bet']:<12.2f} {data['total_return']:<12.2f} "
                  f"{data['total_profit']:<+12.2f} {data['roi']:<+12.2f}% "
                  f"{data['hit_rate']:<12.2f}% {data['hit_count']:<10}")
        
        print("=" * 60)
        
        # 找出最优
        best_mode = max(results, key=lambda x: results[x]["roi"])
        best_roi = results[best_mode]["roi"]
        best_profit = results[best_mode]["total_profit"]
        
        print(f"\n🏆 最优模式: {best_mode}")
        print(f"   ROI: {best_roi:+.2f}%")
        print(f"   净盈利: {best_profit:+.2f}元")
        
        return results, best_mode


# =====================================================
# 主程序
# =====================================================

def main():
    print("=" * 50)
    print("🎯 香港彩回测分析工具")
    print("=" * 50)
    
    print("\n📡 正在获取香港彩数据...")
    rows = fetch_lottery(30)
    
    if len(rows) < 10:
        print("❌ 数据不足（需要至少10期）")
        return
    
    print(f"\n📋 获取到 {len(rows)} 期数据")
    
    # 回测引擎
    engine = BacktestEngine(rows, bet_amount=50)
    
    # 三种模式对比
    results, best_mode = engine.compare_all_modes(test_days=30)
    
    # 详细显示最优模式
    print(f"\n📋 {best_mode} 详细回测报告")
    engine.print_detail(results[best_mode])
    
    # 额外分析：TOP3 vs TOP4 对比
    print("\n" + "=" * 60)
    print("📊 TOP3 vs TOP4 关键对比")
    print("=" * 60)
    
    top3 = results["TOP3"]
    top4 = results["TOP4"]
    
    print(f"\n  {'指标':<20} {'TOP3':<15} {'TOP4':<15} {'差距':<15}")
    print("-" * 65)
    print(f"  {'总投注':<20} {top3['total_bet']:<15.2f} {top4['total_bet']:<15.2f} {top3['total_bet'] - top4['total_bet']:<+15.2f}")
    print(f"  {'命中次数':<20} {top3['hit_count']:<15} {top4['hit_count']:<15} {top3['hit_count'] - top4['hit_count']:<+15}")
    print(f"  {'命中率':<20} {top3['hit_rate']:<15.2f}% {top4['hit_rate']:<15.2f}% {top3['hit_rate'] - top4['hit_rate']:<+15.2f}%")
    print(f"  {'净盈利':<20} {top3['total_profit']:<+15.2f} {top4['total_profit']:<+15.2f} {top3['total_profit'] - top4['total_profit']:<+15.2f}")
    print(f"  {'ROI':<20} {top3['roi']:<+15.2f}% {top4['roi']:<+15.2f}% {top3['roi'] - top4['roi']:<+15.2f}%")
    
    if top3["roi"] > top4["roi"]:
        print(f"\n✅ 结论: TOP3 比 TOP4 更好（ROI高 {top3['roi'] - top4['roi']:.2f}%）")
        print(f"   建议使用 TOP3 模式，每期投注150元")
    else:
        print(f"\n✅ 结论: TOP4 比 TOP3 更好（ROI高 {top4['roi'] - top3['roi']:.2f}%）")
        print(f"   建议使用 TOP4 模式，每期投注200元")
    
    print("\n" + "=" * 50)
    print("✅ 回测完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()