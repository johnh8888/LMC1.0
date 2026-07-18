#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三彩大/单置信度下注建议 - 完整增强版
包含详细回测 + 蒙特卡洛风险模拟
"""

import re
import json
import math
import urllib.request
import random
from datetime import datetime, timedelta

API_URL = "https://marksix6.net/index.php?api=1"

# ============ 配置 ============
CONFIG = {
    "z_threshold": 1.96,
    "windows": [30, 50, 100],
    "min_agree_windows": 2,
    "min_data_required": 100,
    "per_bet_amount": 200,
    "max_daily_bets": 3,
    "weekly_target": 2000,
    "daily_target": 300,
    "weekly_stop_loss": -2000,
    "daily_stop_loss": -500,
    "consecutive_loss_days": 3,
}

LOTTERIES = [
    {"key": "hk", "name": "香港彩", "label": "香港彩"},
    {"key": "xam", "name": "新澳门彩", "label": "新澳门彩"},
    {"key": "lam", "name": "老澳门彩", "label": "老澳门彩"},
]

THEORY_P = 25 / 49


class WeeklyTracker:
    def __init__(self):
        self.week_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.week_start = self.week_start - timedelta(days=self.week_start.weekday())
        self.weekly_profit = 0
        self.daily_profit = 0
        self.bets_today = 0
        self.today_betted = []
        self.status = "正常"

    def can_bet(self, lottery_name):
        if self.status not in ["正常", "谨慎_亏损中"]:
            return False, self.get_recommendation()
        if lottery_name in self.today_betted:
            return False, f"⚠️ 今日已投过{lottery_name}"
        return True, "✅ 可以投注"

    def get_recommendation(self):
        messages = {
            "暂停_周止损": f"❌ 本周亏损{self.weekly_profit}元，已止损",
            "暂停_日止损": f"❌ 今日亏损{self.daily_profit}元，已止损",
            "谨慎_亏损中": f"⚠️ 本周亏损{self.weekly_profit}元，建议减仓",
        }
        return messages.get(self.status, "✅ 状态正常")


def parse_numbers(text):
    nums = re.findall(r"\d+", text)
    return [int(x) for x in nums if 1 <= int(x) <= 49]


def fetch_lottery(lottery_name, limit=200):
    print(f"📡 正在获取 {lottery_name} 数据...")
    try:
        req = urllib.request.Request(API_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        rows = []
        for item in data.get("lottery_data", []):
            if item.get("name", "").strip() == lottery_name:
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
                        "is_big": special >= 25,
                        "is_odd": special % 2 == 1,
                    })
                break

        unique_rows = {r["issue"]: r for r in rows}
        rows = list(unique_rows.values())
        rows.sort(key=lambda x: x["issue"], reverse=True)
        rows = rows[:limit]
        rows.sort(key=lambda x: x["issue"])
        
        print(f"✅ 获取 {len(rows)} 期数据")
        return rows
    except Exception as e:
        print(f"❌ 获取失败: {e}")
        return []


def z_test(hits, n):
    if n == 0: return 0.0
    p_hat = hits / n
    se = math.sqrt(THEORY_P * (1 - THEORY_P) / n)
    z = (p_hat - THEORY_P) / se if se > 0 else 0.0
    return round(z, 3)


def multi_window_decision(rows):
    if len(rows) < CONFIG["min_data_required"]: return None
    results = {}
    for w in CONFIG["windows"]:
        if len(rows) >= w:
            recent = rows[-w:]
            n = len(recent)
            z_big = z_test(sum(1 for r in recent if r["is_big"]), n)
            z_odd = z_test(sum(1 for r in recent if r["is_odd"]), n)
            results[w] = {
                "大": {"action": "下注" if z_big >= CONFIG["z_threshold"] else "观望", "z": z_big},
                "单": {"action": "下注" if z_odd >= CONFIG["z_threshold"] else "观望", "z": z_odd},
            }
    
    if len(results) < CONFIG["min_agree_windows"]: return None

    final = {}
    for dir_name in ["大", "单"]:
        votes = sum(1 for d in results.values() if d[dir_name]["action"] == "下注")
        final[dir_name] = {
            "action": "下注" if votes >= CONFIG["min_agree_windows"] else "观望",
            "votes": votes,
            "total": len(results),
            "detail": results
        }
    return final


def detailed_backtest(rows, window=50, test_periods=100):
    """详细历史回测"""
    if len(rows) < window + test_periods:
        print("⚠️ 数据不足，无法回测")
        return
    stats = {"大": {"bet":0, "hit":0}, "单": {"bet":0, "hit":0}}
    bet_amount = CONFIG["per_bet_amount"]
    
    for i in range(window, window + test_periods):
        if i >= len(rows): break
        decision = multi_window_decision(rows[:i])
        actual = rows[i]
        if decision:
            for d in ["大", "单"]:
                if decision[d]["action"] == "下注":
                    stats[d]["bet"] += 1
                    hit = (d == "大" and actual["is_big"]) or (d == "单" and actual["is_odd"])
                    if hit:
                        stats[d]["hit"] += 1
    print(f"\n📈 {window}期窗口回测结果（测试{test_periods}期）:")
    for label, s in stats.items():
        if s["bet"] > 0:
            acc = s["hit"] / s["bet"] * 100
            print(f"【{label}】 信号{s['bet']}次 | 命中{s['hit']}次 | 胜率{acc:.1f}%")
    return stats


def monte_carlo_simulation(rows, num_simulations=1000, future_periods=60):
    """蒙特卡洛风险模拟"""
    if len(rows) < 100: return
    recent = rows[-100:]
    big_rate = sum(1 for r in recent if r["is_big"]) / 100
    odd_rate = sum(1 for r in recent if r["is_odd"]) / 100
    
    results = []
    for _ in range(num_simulations):
        capital = 10000
        for _ in range(future_periods):
            if random.random() < 0.25:  # 信号概率
                is_big = random.random() < 0.5
                win_prob = big_rate if is_big else odd_rate
                if random.random() < win_prob:
                    capital += base_bet * 0.95
                else:
                    capital -= base_bet
            if capital < 2000: break
        results.append(capital)
    
    print(f"\n🎲 蒙特卡洛模拟 ({num_simulations}次):")
    print(f"平均最终资金: {sum(results)/num_simulations:.0f} 元")
    print(f"盈利概率: {sum(1 for x in results if x > 10000)/num_simulations*100:.1f}%")
    print(f"资金<5000概率: {sum(1 for x in results if x < 5000)/num_simulations*100:.1f}%")


def main():
    tracker = WeeklyTracker()
    print("=" * 80)
    print("🎯 三彩大/单置信度下注建议 - 完整版")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    for lot in LOTTERIES:
        rows = fetch_lottery(lot["name"], limit=200)
        if len(rows) < CONFIG["min_data_required"]:
            continue
        
        decision = multi_window_decision(rows)
        print(f"\n📊 {lot['label']} 最新分析:")
        if decision:
            for d in ["大", "单"]:
                if decision[d]["action"] == "下注":
                    avg_z = sum(info["z"] for info in decision[d]["detail"].values()) / len(decision[d]["detail"])
                    print(f"  ✅ {d} 信号 (avg z={avg_z:.2f}, {decision[d]['votes']}/{decision[d]['total']}窗口)")
        else:
            print("  ⏸️ 无信号")

    # 回测与模拟
    for lot in LOTTERIES:
        rows = fetch_lottery(lot["name"], limit=200)
        if len(rows) >= 150:
            detailed_backtest(rows)
            monte_carlo_simulation(rows)
            break

    print("\n⚠️  建议：只在强信号 + 风控允许时下注")


if __name__ == "__main__":
    main()