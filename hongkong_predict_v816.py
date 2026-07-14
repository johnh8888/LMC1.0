#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
香港彩 半波 vs 特码 回测对比工具

半波 = 颜色 + 大小（2个维度）
特码 = 颜色 + 大小 + 单双（3个维度）

"""

import re
import json
import urllib.request
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
# 预测模型
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

class CompareBacktest:
    def __init__(self, rows):
        self.rows = rows
        # 赔率配置
        self.odds = {
            # 特码赔率（颜色+大小+单双）
            "红大单": 15.76, "红大双": 11.82, "红小单": 9.45, "红小双": 9.45,
            "蓝大单": 9.45, "蓝大双": 11.82, "蓝小单": 15.76, "蓝小双": 11.82,
            "绿大单": 11.82, "绿大双": 11.82, "绿小单": 11.82, "绿小双": 15.76,
            # 半波赔率（颜色+大小）
            "红大": 6.75, "红小": 4.72,
            "绿大": 5.91, "绿小": 6.75,
            "蓝大": 5.25, "蓝小": 6.75,
        }
    
    def backtest_halfwave(self, test_days=29):
        """回测半波（颜色+大小）"""
        results = []
        total_bet = 0
        total_return = 0
        total_profit = 0
        hit_count = 0
        balance = 0
        balance_history = []
        
        start_idx = min(test_days, len(self.rows) - 1)
        
        print(f"\n{'='*60}")
        print(f"📊 半波（颜色+大小）回测")
        print(f"  下注: 绿大 + 红大（2注×50元=100元）")
        print(f"  赔率: 绿大 5.91 | 红大 6.75")
        print(f"{'='*60}")
        
        for i in range(start_idx, 0, -1):
            history = self.rows[i:]
            actual = self.rows[i - 1]
            
            predictor = Predictor(history)
            candidates = predictor.full_predict()
            
            # 半波：取TOP3中的颜色+大小，去重
            bet_set = set()
            for c in candidates[:5]:
                hh = c["halfhalf"]
                bw = hh[0] + hh[1]  # 颜色+大小
                bet_set.add(bw)
                if len(bet_set) >= 2:
                    break
            
            bet_list = list(bet_set)
            # 确保有绿大和红大
            if "绿大" not in bet_list and "红大" not in bet_list:
                # 如果预测没有绿大或红大，补充
                if "绿大" not in bet_list:
                    bet_list.append("绿大")
                if len(bet_list) < 2 and "红大" not in bet_list:
                    bet_list.append("红大")
            
            bet_list = bet_list[:2]
            
            bet_count = len(bet_list)
            if bet_count == 0:
                continue
            
            bet = self.bet_amount * bet_count
            total_bet += bet
            
            # 判断中奖
            hit = False
            win_amount = 0
            actual_bw = actual["color"] + actual["size"]
            
            for bw in bet_list:
                if bw == actual_bw:
                    hit = True
                    odds = self.odds.get(bw, 5.91)
                    win_amount = self.bet_amount * odds
                    break
            
            if hit:
                hit_count += 1
                total_return += win_amount
            else:
                win_amount = 0
            
            profit = win_amount - bet
            total_profit += profit
            balance += profit
            balance_history.append(balance)
            
            results.append({
                "issue": actual["issue"],
                "actual": actual_bw,
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
            "mode": "半波",
            "results": results,
            "total_bet": total_bet,
            "total_return": total_return,
            "total_profit": total_profit,
            "hit_count": hit_count,
            "total_periods": len(results),
            "hit_rate": hit_rate,
            "roi": roi,
            "balance_history": balance_history
        }
    
    def backtest_special(self, test_days=29):
        """回测特码（颜色+大小+单双）TOP4"""
        results = []
        total_bet = 0
        total_return = 0
        total_profit = 0
        hit_count = 0
        balance = 0
        balance_history = []
        
        start_idx = min(test_days, len(self.rows) - 1)
        
        print(f"\n{'='*60}")
        print(f"📊 特码（颜色+大小+单双）TOP4 回测")
        print(f"  下注: TOP4（4注×50元=200元）")
        print(f"  赔率: 9.45-15.76倍")
        print(f"{'='*60}")
        
        for i in range(start_idx, 0, -1):
            history = self.rows[i:]
            actual = self.rows[i - 1]
            
            predictor = Predictor(history)
            candidates = predictor.full_predict()
            
            bet_list = [c["halfhalf"] for c in candidates[:4]]
            
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
                    odds = self.odds.get(hh, 9.45)
                    win_amount = self.bet_amount * odds
                    break
            
            if hit:
                hit_count += 1
                total_return += win_amount
            else:
                win_amount = 0
            
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
            "mode": "特码TOP4",
            "results": results,
            "total_bet": total_bet,
            "total_return": total_return,
            "total_profit": total_profit,
            "hit_count": hit_count,
            "total_periods": len(results),
            "hit_rate": hit_rate,
            "roi": roi,
            "balance_history": balance_history
        }
    
    def compare(self, test_days=29):
        """对比两种玩法"""
        print("\n" + "=" * 60)
        print("🔄 半波 vs 特码 对比回测")
        print("=" * 60)
        
        # 半波
        half_data = self.backtest_halfwave(test_days)
        
        # 特码
        special_data = self.backtest_special(test_days)
        
        # 汇总对比
        print(f"\n{'='*60}")
        print("📊 汇总对比")
        print("=" * 60)
        
        print(f"\n{'指标':<20} {'半波':<20} {'特码TOP4':<20}")
        print("-" * 60)
        print(f"{'回测期数':<20} {half_data['total_periods']:<20} {special_data['total_periods']:<20}")
        print(f"{'总投注':<20} {half_data['total_bet']:<20.2f} {special_data['total_bet']:<20.2f}")
        print(f"{'总回报':<20} {half_data['total_return']:<20.2f} {special_data['total_return']:<20.2f}")
        print(f"{'净盈利':<20} {half_data['total_profit']:<+20.2f} {special_data['total_profit']:<+20.2f}")
        print(f"{'命中率':<20} {half_data['hit_rate']:<20.2f}% {special_data['hit_rate']:<20.2f}%")
        print(f"{'命中次数':<20} {half_data['hit_count']:<20} {special_data['hit_count']:<20}")
        print(f"{'ROI':<20} {half_data['roi']:<+20.2f}% {special_data['roi']:<+20.2f}%")
        
        # 结论
        print(f"\n{'='*60}")
        print("🎯 结论")
        print("=" * 60)
        
        if half_data["total_profit"] > special_data["total_profit"]:
            print(f"\n✅ 半波更赚钱！")
            print(f"   半波盈利: {half_data['total_profit']:+.2f}元")
            print(f"   特码盈利: {special_data['total_profit']:+.2f}元")
            print(f"   差距: {half_data['total_profit'] - special_data['total_profit']:+.2f}元")
            print(f"\n💡 建议: 买半波（2注100元）")
        elif special_data["total_profit"] > half_data["total_profit"]:
            print(f"\n✅ 特码更赚钱！")
            print(f"   特码盈利: {special_data['total_profit']:+.2f}元")
            print(f"   半波盈利: {half_data['total_profit']:+.2f}元")
            print(f"   差距: {special_data['total_profit'] - half_data['total_profit']:+.2f}元")
            print(f"\n💡 建议: 继续买特码（4注200元）")
        else:
            print(f"\n⚠️ 两者差不多")
        
        return half_data, special_data
    
    def set_bet_amount(self, amount):
        self.bet_amount = amount


# =====================================================
# 主程序
# =====================================================

def main():
    print("=" * 50)
    print("🎯 半波 vs 特码 回测对比")
    print("=" * 50)
    
    print("\n📡 正在获取香港彩数据...")
    rows = fetch_lottery(30)
    
    if len(rows) < 10:
        print("❌ 数据不足（需要至少10期）")
        return
    
    print(f"\n📋 获取到 {len(rows)} 期数据")
    
    engine = CompareBacktest(rows)
    engine.set_bet_amount(50)
    
    half_data, special_data = engine.compare(test_days=29)
    
    print("\n" + "=" * 50)
    print("✅ 回测完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()