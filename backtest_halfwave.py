#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三彩（香港彩 / 新澳门彩 / 老澳门彩）大/单 置信度下注建议
优化版：更严格、更确定的决策规则
"""

import re
import json
import math
import urllib.request
from datetime import datetime, timedelta

API_URL = "https://marksix6.net/index.php?api=1"

# ============ 确定化配置 ============
CONFIG = {
    "z_threshold": 2.05,          # 提高门槛，更保守
    "windows": [30, 50, 100],
    "min_agree_windows": 2,       # 至少2个窗口同意
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
        self.daily_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        self.weekly_profit = 0
        self.daily_profit = 0
        self.bets_today = 0
        self.bets_this_week = 0
        self.consecutive_loss_days = 0
        self.today_betted = []
        self.history = []
        self.status = "正常"
    
    def can_bet(self, lottery_name):
        if self.status not in ["正常", "谨慎_亏损中"]:
            return False, self.get_recommendation()
        if lottery_name in self.today_betted:
            return False, f"⚠️ 今日已投过{lottery_name}"
        return True, "✅ 可以投注"
    
    def get_recommendation(self):
        messages = {
            "暂停_周止损": f"❌ 本周亏损{self.weekly_profit}元，已到止损线",
            "暂停_日止损": f"❌ 今日亏损{self.daily_profit}元，已到止损线",
            "暂停_连亏": f"❌ 已连续{self.consecutive_loss_days}天未中",
            "完成_周目标": f"✅ 本周已盈利{self.weekly_profit}元，达到目标",
            "完成_日目标": f"✅ 今日已盈利{self.daily_profit}元，达到目标",
            "暂停_日次数": f"⚠️ 今日已投{self.bets_today}期（上限3期）",
            "谨慎_亏损中": f"⚠️ 本周亏损{self.weekly_profit}元，建议减仓",
        }
        return messages.get(self.status, "✅ 状态正常")


# ============ 核心功能（数据部分保持不变） ============
def parse_numbers(text):
    nums = re.findall(r"\d+", text)
    return [int(x) for x in nums if 1 <= int(x) <= 49]

def fetch_lottery(lottery_name, limit=200):
    """获取彩票数据（完全保留你的原始逻辑）"""
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
                        "is_big": special >= 25,
                        "is_small": special < 25,
                        "is_odd": special % 2 == 1,
                        "is_even": special % 2 == 0,
                    })
                break

        unique_rows = {r["issue"]: r for r in rows}
        rows = list(unique_rows.values())
        rows.sort(key=lambda x: x["issue"], reverse=True)
        rows = rows[:limit]
        rows.sort(key=lambda x: x["issue"])
        
        print(f"✅ 获取 {len(rows)} 期数据")
        if rows:
            print(f"📅 数据范围: {rows[0]['issue']} ~ {rows[-1]['issue']}")
        return rows
    except Exception as e:
        print(f"❌ 获取失败: {e}")
        return []


def z_test(hits, n, p0=THEORY_P):
    if n == 0:
        return 0.0, 0.0
    p_hat = hits / n
    se = math.sqrt(p0 * (1 - p0) / n)
    z = (p_hat - p0) / se if se > 0 else 0.0
    return z, p_hat


def bet_decision(rows, window, z_threshold):
    if len(rows) < window:
        return None
    recent = rows[-window:]
    n = len(recent)
    hits_big = sum(1 for r in recent if r["is_big"])
    hits_odd = sum(1 for r in recent if r["is_odd"])

    z_big, _ = z_test(hits_big, n)
    z_odd, _ = z_test(hits_odd, n)

    return {
        "大": {"action": "下注" if z_big >= z_threshold else "观望", "z": z_big, "hits": hits_big, "n": n},
        "单": {"action": "下注" if z_odd >= z_threshold else "观望", "z": z_odd, "hits": hits_odd, "n": n},
    }


def multi_window_decision(rows):
    """多窗口判断"""
    if len(rows) < CONFIG["min_data_required"]:
        return None
    
    results = {}
    for w in CONFIG["windows"]:
        if len(rows) >= w:
            d = bet_decision(rows, w, CONFIG["z_threshold"])
            if d:
                results[w] = d
    
    if len(results) < CONFIG["min_agree_windows"]:
        return None

    directions = ["大", "单"]
    votes = {d: 0 for d in directions}
    
    for d in results.values():
        for dir_name in directions:
            if d[dir_name]["action"] == "下注":
                votes[dir_name] += 1
    
    final = {}
    for dir_name in directions:
        final[dir_name] = {
            "action": "下注" if votes[dir_name] >= CONFIG["min_agree_windows"] else "观望",
            "votes": votes[dir_name],
            "total_windows": len(results),
            "detail": {w: results[w][dir_name] for w in results}
        }
    return final


def calculate_bet_amount(tracker, avg_z):
    base = CONFIG["per_bet_amount"]
    multiplier = 1.0
    
    if tracker.status == "谨慎_亏损中":
        multiplier = 0.5
    if avg_z >= 2.5:
        multiplier *= 1.2
    if datetime.now().weekday() >= 5:   # 周末减仓
        multiplier *= 0.8
    
    bet = int(base * multiplier)
    return max(50, min(bet, 500))


def print_analysis(lottery_name, rows, decision, tracker):
    print("\n" + "=" * 75)
    print(f"📊 {lottery_name} 分析报告")
    print("=" * 75)
    
    if not rows:
        print("❌ 无数据")
        return
    
    latest = rows[-1]
    print(f"最新期号: {latest['issue']}  特码: {latest['special']} "
          f"({'大' if latest['is_big'] else '小'} {'单' if latest['is_odd'] else '双'})")
    
    if decision:
        print(f"\n🎯 最终决策（z阈值≥{CONFIG['z_threshold']}，需≥{CONFIG['min_agree_windows']}窗口）:")
        has_signal = False
        for dir_name in ["大", "单"]:
            d = decision[dir_name]
            if d["action"] == "下注":
                has_signal = True
                zs = [detail["z"] for detail in d["detail"].values()]
                avg_z = sum(zs) / len(zs)
                strength = "🔥 强信号" if avg_z >= 2.5 else "✅ 中强信号"
                
                can, msg = tracker.can_bet(lottery_name)
                if can:
                    bet = calculate_bet_amount(tracker, avg_z)
                    print(f"  {dir_name} → {strength} (avg z={avg_z:.2f}, {d['votes']}窗口)  【建议投注 {bet}元】")
                else:
                    print(f"  {dir_name} → {strength} （{msg}）")
        
        if not has_signal:
            print("  ⏸️ 无强信号，建议观望")
    else:
        print("  ⏸️ 数据不足或未达决策标准")


def main():
    tracker = WeeklyTracker()
    print("=" * 75)
    print("🎯 三彩大/单置信度下注建议（确定化优化版）")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 75)

    print(f"\n📊 当前状态: {tracker.status}  |  建议: {tracker.get_recommendation()}\n")

    if tracker.status not in ["正常", "谨慎_亏损中"]:
        print("⏸️ 今日停止投注")
        return

    for lot in LOTTERIES:
        rows = fetch_lottery(lot["name"], limit=200)
        if len(rows) < CONFIG["min_data_required"]:
            print(f"⚠️ {lot['label']} 数据不足，跳过")
            continue
        
        decision = multi_window_decision(rows)
        print_analysis(lot["label"], rows, decision, tracker)

    print("\n" + "=" * 75)
    print("📋 今日最终建议")
    print("=" * 75)
    print(f"状态: {tracker.status}")
    print(f"建议: {tracker.get_recommendation()}")
    print("\n⚠️  严格执行：只有强信号 + 状态允许 才下注！")


if __name__ == "__main__":
    main()