#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三彩（香港彩 / 新澳门彩 / 老澳门彩）大/单 置信度下注建议
------------------------------------------------------
逻辑：
  - "大"(>=25，含49) 和 "单"(奇数，含49) 理论概率均为 25/49 ≈ 51.02%
  - 本脚本用 z 检验，判断近期(默认30期)实际出现率是否显著偏离理论值。
  - 只有 z >= 1.96（95%置信度，显著偏高）才建议"下注"，否则一律"观望"。
  - 支持多窗口综合判断（30/50/100期）
  - 包含历史准确率回测
  - 每周固定投注方案
"""

import re
import json
import math
import urllib.request
from datetime import datetime, timedelta
from collections import defaultdict

API_URL = "https://marksix6.net/index.php?api=1"

# ============ 每周固定方案配置 ============
WEEKLY_CONFIG = {
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

# ============ 全局状态追踪 ============
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
    
    def update(self, profit, hit, lottery_name):
        self.weekly_profit += profit
        self.daily_profit += profit
        self.bets_today += 1
        self.bets_this_week += 1
        self.today_betted.append(lottery_name)
        
        if hit:
            self.consecutive_loss_days = 0
        else:
            self.consecutive_loss_days += 1
        
        self._update_status()
        self.history.append({
            "time": datetime.now(),
            "lottery": lottery_name,
            "profit": profit,
            "hit": hit,
            "status": self.status,
        })
    
    def _update_status(self):
        if self.weekly_profit <= WEEKLY_CONFIG["weekly_stop_loss"]:
            self.status = "暂停_周止损"
        elif self.daily_profit <= WEEKLY_CONFIG["daily_stop_loss"]:
            self.status = "暂停_日止损"
        elif self.consecutive_loss_days >= WEEKLY_CONFIG["consecutive_loss_days"]:
            self.status = "暂停_连亏"
        elif self.weekly_profit >= WEEKLY_CONFIG["weekly_target"]:
            self.status = "完成_周目标"
        elif self.daily_profit >= WEEKLY_CONFIG["daily_target"]:
            self.status = "完成_日目标"
        elif self.bets_today >= WEEKLY_CONFIG["max_daily_bets"]:
            self.status = "暂停_日次数"
        elif self.weekly_profit < 0:
            self.status = "谨慎_亏损中"
        else:
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

# ============ 核心功能 ============

def parse_numbers(text):
    nums = re.findall(r"\d+", text)
    return [int(x) for x in nums if 1 <= int(x) <= 49]

def fetch_lottery(lottery_name, limit=200):
    """获取彩票数据"""
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

        unique_rows = {}
        for r in rows:
            unique_rows[r["issue"]] = r
        rows = list(unique_rows.values())
        rows.sort(key=lambda x: x["issue"], reverse=True)
        rows = rows[:limit]
        rows.sort(key=lambda x: x["issue"])
        
        print(f"✅ 获取 {len(rows)} 期数据")
        if rows:
            print(f"📅 数据范围: {rows[0]['issue']} ~ {rows[-1]['issue']} (共{len(rows)}期)")
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

def bet_decision(rows, window=30, z_threshold=1.96):
    """单窗口判断"""
    if len(rows) < window:
        return None
    
    recent = rows[-window:]
    n = len(recent)
    hits_big = sum(1 for r in recent if r["is_big"])
    hits_odd = sum(1 for r in recent if r["is_odd"])
    hits_small = sum(1 for r in recent if r["is_small"])
    hits_even = sum(1 for r in recent if r["is_even"])

    z_big, p_big = z_test(hits_big, n)
    z_odd, p_odd = z_test(hits_odd, n)
    z_small, p_small = z_test(hits_small, n)
    z_even, p_even = z_test(hits_even, n)

    return {
        "大": {"action": "下注" if z_big >= z_threshold else "观望", "z": z_big, "p": p_big, "hits": hits_big, "n": n},
        "单": {"action": "下注" if z_odd >= z_threshold else "观望", "z": z_odd, "p": p_odd, "hits": hits_odd, "n": n},
        "小": {"action": "下注" if z_small >= z_threshold else "观望", "z": z_small, "p": p_small, "hits": hits_small, "n": n},
        "双": {"action": "下注" if z_even >= z_threshold else "观望", "z": z_even, "p": p_even, "hits": hits_even, "n": n},
    }

def multi_window_decision(rows, windows=[30, 50, 100], z_threshold=1.96):
    """多窗口综合判断"""
    if not rows or len(rows) < min(windows):
        return None
    
    results = {}
    for w in windows:
        if len(rows) >= w:
            d = bet_decision(rows, window=w, z_threshold=z_threshold)
            if d:
                results[w] = d
    
    if not results:
        return None
    
    directions = ["大", "单", "小", "双"]
    votes = {d: 0 for d in directions}
    
    for w, d in results.items():
        for dir_name in directions:
            if d[dir_name]["action"] == "下注":
                votes[dir_name] += 1
    
    total_windows = len(results)
    threshold = total_windows / 2
    
    result = {}
    for dir_name in directions:
        result[dir_name] = {
            "action": "下注" if votes[dir_name] > threshold else "观望",
            "votes": votes[dir_name],
            "total_windows": total_windows,
            "detail": {w: results[w][dir_name] for w in results.keys()}
        }
    
    return result

def backtest_signal_accuracy(rows, window=50, z_threshold=1.96):
    """历史准确率回测"""
    stats = {"大": {"bet_count": 0, "hit_count": 0},
             "单": {"bet_count": 0, "hit_count": 0}}

    if len(rows) < window + 1:
        print(f"\n⚠️ 数据不足 {window+1} 期，无法进行历史准确率回测")
        return stats

    for i in range(window, len(rows)):
        history = rows[:i]
        actual_next = rows[i]

        recent = history[-window:]
        n = len(recent)
        hits_big = sum(1 for r in recent if r["is_big"])
        hits_odd = sum(1 for r in recent if r["is_odd"])
        z_big, _ = z_test(hits_big, n)
        z_odd, _ = z_test(hits_odd, n)

        if z_big >= z_threshold:
            stats["大"]["bet_count"] += 1
            if actual_next["is_big"]:
                stats["大"]["hit_count"] += 1

        if z_odd >= z_threshold:
            stats["单"]["bet_count"] += 1
            if actual_next["is_odd"]:
                stats["单"]["hit_count"] += 1

    print(f"\n{'='*70}")
    print(f"📈 信号历史准确率回测（窗口={window}期，基于{len(rows)}期数据）")
    print("="*70)
    
    for label, s in stats.items():
        bc, hc = s["bet_count"], s["hit_count"]
        if bc == 0:
            print(f"【{label}】 历史从未触发下注信号")
            continue
        acc = hc / bc * 100
        z_acc, _ = z_test(hc, bc)
        
        if bc >= 50 and abs(z_acc) >= 1.96:
            verdict = "✅ 显著高于理论值" if z_acc > 0 else "⚠️ 显著低于理论值"
        elif bc >= 30:
            verdict = "📊 有一定参考价值（需继续观察）"
        else:
            verdict = "⚠️ 样本太少，结论不可靠"
            
        print(f"【{label}】 信号触发 {bc} 次，命中 {hc} 次 = {acc:.1f}%  "
              f"(理论基准 {THEORY_P*100:.1f}%)  → {verdict}")
        
        if bc > 0:
            se = math.sqrt(acc/100 * (1 - acc/100) / bc)
            ci_low = max(0, acc/100 - 1.96*se) * 100
            ci_high = min(1, acc/100 + 1.96*se) * 100
            print(f"   95%置信区间: {ci_low:.1f}% ~ {ci_high:.1f}%")
    
    return stats

def calculate_bet_amount(tracker, signal_strength):
    """计算投注额"""
    base = WEEKLY_CONFIG["per_bet_amount"]
    
    if tracker.status == "谨慎_亏损中":
        multiplier = 0.5
    elif tracker.weekly_profit > WEEKLY_CONFIG["weekly_target"] * 0.5:
        multiplier = 0.7
    else:
        multiplier = 1.0
    
    if signal_strength >= 2.5:
        multiplier *= 1.2
    elif signal_strength >= 2.0:
        multiplier *= 1.0
    else:
        multiplier *= 0.8
    
    if datetime.now().weekday() >= 5:
        multiplier *= 0.8
    
    bet = int(base * multiplier)
    bet = max(50, min(bet, 500))
    bet = round(bet, -1)
    return bet

def print_full_analysis(lottery_name, rows, decision, tracker):
    """完整分析打印"""
    print("\n" + "=" * 70)
    print(f"📊 {lottery_name} 综合分析")
    print("=" * 70)
    
    if not rows:
        print("❌ 无数据")
        return
    
    latest = rows[-1]
    print(f"\n📅 最新数据:")
    print(f"  期号: {latest['issue']}")
    print(f"  特码: {latest['special']}")
    print(f"  大号: {'是' if latest['is_big'] else '否'}")
    print(f"  单号: {'是' if latest['is_odd'] else '否'}")
    
    # 多窗口判断
    if decision:
        print(f"\n📊 多窗口综合判断 ({decision['大']['total_windows']}个窗口):")
        for dir_name in ["大", "单", "小", "双"]:
            d = decision[dir_name]
            status = "✅ 下注" if d["action"] == "下注" else "⏸️ 观望"
            print(f"  {dir_name}: {status} ({d['votes']}/{d['total_windows']}窗口)")
        
        # 各窗口详情
        print(f"\n📋 各窗口详情:")
        print(f"{'窗口':<8} {'大-z值':<10} {'大判断':<8} {'单-z值':<10} {'单判断':<8} {'小-z值':<10} {'双-z值':<10}")
        print("-" * 80)
        
        for w in sorted(decision["大"]["detail"].keys()):
            big = decision["大"]["detail"][w]
            odd = decision["单"]["detail"][w]
            small = decision["小"]["detail"][w]
            even = decision["双"]["detail"][w]
            print(f"{w}期{'':<4} {big['z']:+.2f}     {'✅' if big['action']=='下注' else '⏸️':<6} "
                  f"{odd['z']:+.2f}     {'✅' if odd['action']=='下注' else '⏸️':<6} "
                  f"{small['z']:+.2f}     {even['z']:+.2f}")
    
    # 每周方案建议
    print(f"\n💰 每周方案建议:")
    
    if decision:
        has_signal = False
        for dir_name in ["大", "单"]:
            if decision[dir_name]["action"] == "下注":
                has_signal = True
                can_bet, msg = tracker.can_bet(lottery_name)
                if not can_bet:
                    print(f"  ⏸️ {dir_name}: {msg}")
                else:
                    z = decision[dir_name]["detail"][50]["z"] if 50 in decision[dir_name]["detail"] else 0
                    bet = calculate_bet_amount(tracker, z)
                    print(f"  ✅ {dir_name}: 建议投注 {bet}元 (z={z:+.2f})")
        
        if not has_signal:
            print(f"  ⏸️ 无信号，建议观望")

def main():
    tracker = WeeklyTracker()
    
    print("=" * 70)
    print("🎯 三彩大/单置信度下注建议 + 每周固定方案")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # 显示每周状态
    print(f"\n📊 本周状态:")
    print(f"  本周盈亏: {tracker.weekly_profit:+.0f}元 (目标+{WEEKLY_CONFIG['weekly_target']}元)")
    print(f"  今日盈亏: {tracker.daily_profit:+.0f}元 (目标+{WEEKLY_CONFIG['daily_target']}元)")
    print(f"  今日已投: {tracker.bets_today}/{WEEKLY_CONFIG['max_daily_bets']}期")
    print(f"  状态: {tracker.status}")
    print(f"  建议: {tracker.get_recommendation()}")
    
    if tracker.status in ["暂停_周止损", "暂停_日止损", "暂停_连亏", "完成_周目标", "完成_日目标", "暂停_日次数"]:
        print(f"\n⏸️ {tracker.get_recommendation()}")
        print("今天不再分析，休息！")
        return
    
    # 分析每个彩种
    for lot in LOTTERIES:
        rows = fetch_lottery(lot["name"], limit=200)
        if len(rows) < 100:
            print(f"⚠️ {lot['label']} 数据不足，跳过")
            continue
        
        # 多窗口判断
        decision = multi_window_decision(rows, windows=[30, 50, 100], z_threshold=1.96)
        
        # 历史回测
        backtest_signal_accuracy(rows, window=50, z_threshold=1.96)
        
        # 打印完整分析
        print_full_analysis(lot["label"], rows, decision, tracker)
    
    # 每日汇总
    print("\n" + "=" * 70)
    print("📋 今日汇总")
    print("=" * 70)
    
    print(f"""
今日已投: {tracker.bets_today}/{WEEKLY_CONFIG['max_daily_bets']}期
今日盈亏: {tracker.daily_profit:+.0f}元 (目标+{WEEKLY_CONFIG['daily_target']}元)
本周盈亏: {tracker.weekly_profit:+.0f}元 (目标+{WEEKLY_CONFIG['weekly_target']}元)

建议:
{tracker.get_recommendation()}
""")
    
    print("=" * 70)
    print("⚠️ 只投强信号(z≥1.96)！没信号就等！")
    print("=" * 70)

if __name__ == "__main__":
    main()