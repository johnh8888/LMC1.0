#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门六合彩 - 4注半半波正期望值策略回测
=============================================
验证方案：每期固定4注（蓝小单+蓝大双+绿大双+红小双）
每注100元，每期400元
回测数据：从API拉取真实历史数据
"""

import re
import json
import urllib.request
from collections import defaultdict
from datetime import datetime
import sys

# =====================================================
# 配置
# =====================================================

CONFIG = {
    "api_url": "https://marksix6.net/index.php?api=1",
    "history_limit": 200,  # 拉取最近200期数据回测
    "bet_per_note": 100,
    "strategy": {
        "name": "4注半半波策略",
        "bets": [
            {"name": "蓝小单", "odds": 15.76, "numbers": [3, 9, 15, 21]},
            {"name": "蓝大双", "odds": 11.82, "numbers": [26, 36, 42, 47, 48]},
            {"name": "绿大双", "odds": 11.82, "numbers": [28, 32, 38, 44, 49]},
            {"name": "红小双", "odds": 9.45, "numbers": [2, 8, 12, 18, 24]},
        ]
    }
}

# =====================================================
# 波色定义（官方号码表）
# =====================================================

RED = {1, 2, 7, 8, 12, 13, 18, 19, 23, 24, 29, 30, 34, 35, 40, 45, 46}
BLUE = {3, 4, 9, 10, 14, 15, 20, 25, 26, 31, 36, 37, 41, 42, 47, 48}
GREEN = {5, 6, 11, 16, 17, 21, 22, 27, 28, 32, 33, 38, 39, 43, 44, 49}


def get_color(n):
    if n in RED:
        return "红"
    if n in BLUE:
        return "蓝"
    return "绿"


def get_size(n):
    return "大" if n >= 25 else "小"


def get_odd(n):
    return "单" if n % 2 else "双"


def get_halfhalf(n):
    return get_color(n) + get_size(n) + get_odd(n)


# =====================================================
# 数据获取
# =====================================================

def fetch_new_macau(limit=200):
    """获取新澳门彩历史数据"""
    rows = []
    try:
        print(f"📡 正在获取数据（最多{limit}期）...")
        req = urllib.request.Request(
            CONFIG["api_url"],
            headers={"User-Agent": "Mozilla/5.0"}
        )
        data = urllib.request.urlopen(req, timeout=60).read()
        data = json.loads(data.decode("utf-8"))

        target = None
        for item in data.get("lottery_data", []):
            if item.get("name", "").strip() == "新澳门彩":
                target = item
                break

        if not target:
            print("❌ 未找到新澳门彩数据")
            return []

        for line in target.get("history", []):
            nums = re.findall(r"\d+", line)
            nums = [int(x) for x in nums if 1 <= int(x) <= 49]
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
        print(f"❌ 获取失败: {e}")
        return []

    # 去重并排序（从旧到新）
    cache = {}
    for r in rows:
        cache[r["issue"]] = r
    rows = list(cache.values())
    rows.sort(key=lambda x: x["issue"])  # 从旧到新

    print(f"✅ 获取到 {len(rows)} 期数据")
    if rows:
        print(f"📅 数据范围: {rows[0]['issue']} ~ {rows[-1]['issue']}")

    return rows


# =====================================================
# 回测引擎
# =====================================================

def run_backtest(rows):
    """执行回测"""
    bets = CONFIG["strategy"]["bets"]
    bet_per_note = CONFIG["bet_per_note"]
    bet_per_period = bet_per_note * len(bets)

    print("\n" + "=" * 70)
    print("📊 回测配置")
    print("=" * 70)
    print(f"  策略: 4注半半波策略")
    print(f"  每注: {bet_per_note}元")
    print(f"  每期投入: {bet_per_period}元")
    print(f"  回测期数: {len(rows)}期")

    # 统计每个玩法的号码
    print("\n📋 下注明细:")
    for bet in bets:
        print(f"  {bet['name']}: 赔率{bet['odds']}, 号码{bet['numbers']}")

    total_count = sum(len(bet["numbers"]) for bet in bets)
    print(f"\n📊 覆盖号码: {total_count}个 / 49个 ({total_count/49*100:.1f}%)")

    # 执行回测
    results = []
    balance = 0
    total_bet = 0
    total_win = 0
    hit_count = 0
    consecutive_loss = 0
    max_consecutive_loss = 0
    max_balance = 0
    max_drawdown = 0
    drawdown_start = 0

    # 统计每个半半波的中奖次数
    hit_stats = defaultdict(int)

    for r in rows:
        drawn_number = r["special"]

        hit = None
        for bet in bets:
            if drawn_number in bet["numbers"]:
                hit = bet
                break

        if hit:
            hit_count += 1
            hit_stats[hit["name"]] += 1
            win_amount = hit["odds"] * bet_per_note
            profit = win_amount - bet_per_period
            total_win += win_amount
            balance += profit
            consecutive_loss = 0
        else:
            profit = -bet_per_period
            balance += profit
            consecutive_loss += 1
            if consecutive_loss > max_consecutive_loss:
                max_consecutive_loss = consecutive_loss

        total_bet += bet_per_period

        # 计算最大回撤
        if balance > max_balance:
            max_balance = balance
            drawdown_start = balance
        current_drawdown = drawdown_start - balance
        if current_drawdown > max_drawdown:
            max_drawdown = current_drawdown

        results.append({
            "issue": r["issue"],
            "number": drawn_number,
            "actual": r["halfhalf"],
            "hit": hit["name"] if hit else None,
            "profit": profit,
            "balance": balance,
        })

    # =====================================================
    # 输出回测报告
    # =====================================================

    total_periods = len(results)
    hit_rate = hit_count / total_periods * 100 if total_periods > 0 else 0
    roi = (balance / total_bet * 100) if total_bet > 0 else 0

    print("\n" + "=" * 70)
    print("📊 回测结果汇总")
    print("=" * 70)
    print(f"  📅 回测期数: {total_periods}期")
    print(f"  🎯 命中次数: {hit_count}次")
    print(f"  📈 命中率: {hit_rate:.2f}%")
    print(f"  💰 总投注: {total_bet:,.0f}元")
    print(f"  🏆 总中奖: {total_win:,.0f}元")
    print(f"  📊 最终盈亏: {balance:+,.0f}元")
    print(f"  📉 最大回撤: {max_drawdown:,.0f}元")
    print(f"  🔥 最长连续未中: {max_consecutive_loss}期")
    print(f"  📊 ROI: {roi:+.2f}%")

    # 各玩法命中统计
    print("\n🎯 各玩法命中统计:")
    for bet in bets:
        count = hit_stats.get(bet["name"], 0)
        print(f"  {bet['name']}: {count}次 (占命中{count/hit_count*100:.1f}%)" if hit_count > 0 else "  无命中")

    # =====================================================
    # 理论期望验证
    # =====================================================

    print("\n" + "=" * 70)
    print("🧮 理论期望验证")
    print("=" * 70)

    # 计算理论期望
    expected_per_period = 0
    for bet in bets:
        prob = len(bet["numbers"]) / 49
        expected_per_period += (bet["odds"] * bet_per_note - bet_per_period) * prob

    print(f"  理论每期期望: {expected_per_period:+.2f}元")
    print(f"  理论{total_periods}期盈利: {expected_per_period * total_periods:+.0f}元")
    print(f"  实际{total_periods}期盈利: {balance:+.0f}元")
    print(f"  偏差: {balance - expected_per_period * total_periods:+.0f}元")

    # 判断方案可行性
    print("\n" + "=" * 70)
    print("📋 可行性结论")
    print("=" * 70)

    if balance > 0 and roi > 0:
        print("  ✅ 方案可行！历史回测盈利，且为正期望值。")
        print(f"  📊 建议启动资金: {int(abs(max_drawdown) * 1.5):,}元")
    elif balance > 0 and roi <= 0:
        print("  ⚠️ 方案盈利但ROI为负，需警惕。")
    elif balance <= 0 and expected_per_period > 0:
        print("  ⚠️ 历史回测亏损，但理论期望为正。")
        print("     可能受短期波动影响，建议回测更多数据。")
    else:
        print("  ❌ 方案不可行！历史回测亏损，且理论期望为负。")

    # =====================================================
    # 每期明细（最近20期和最早20期）
    # =====================================================

    print("\n📋 最近20期盈亏明细:")
    print("-" * 70)
    print(f"{'期号':<12} {'开奖':<8} {'实际半波':<12} {'命中':<12} {'盈亏':<12} {'累计':<12}")
    print("-" * 70)

    for r in results[-20:]:
        hit_str = r["hit"] if r["hit"] else "❌未中"
        print(f"{r['issue']:<12} {r['number']:<8} {r['actual']:<12} {hit_str:<12} {r['profit']:<+12.0f} {r['balance']:<+12.0f}")

    print("\n📋 最早20期盈亏明细:")
    print("-" * 70)
    for r in results[:20]:
        hit_str = r["hit"] if r["hit"] else "❌未中"
        print(f"{r['issue']:<12} {r['number']:<8} {r['actual']:<12} {hit_str:<12} {r['profit']:<+12.0f} {r['balance']:<+12.0f}")

    return {
        "total_periods": total_periods,
        "hit_count": hit_count,
        "hit_rate": hit_rate,
        "total_bet": total_bet,
        "total_win": total_win,
        "balance": balance,
        "max_drawdown": max_drawdown,
        "max_consecutive_loss": max_consecutive_loss,
        "roi": roi,
        "expected_profit": expected_per_period * total_periods,
        "results": results,
        "hit_stats": hit_stats,
    }


# =====================================================
# 蒙特卡洛模拟
# =====================================================

def monte_carlo_simulation(periods=1000, iterations=10000):
    """蒙特卡洛模拟验证"""
    import random

    bets = CONFIG["strategy"]["bets"]
    bet_per_note = CONFIG["bet_per_note"]
    bet_per_period = bet_per_note * len(bets)
    total_count = sum(len(bet["numbers"]) for bet in bets)
    hit_prob = total_count / 49

    print("\n" + "=" * 70)
    print(f"🔄 蒙特卡洛模拟 ({iterations}次 × {periods}期)")
    print("=" * 70)

    mc_results = []
    for _ in range(iterations):
        balance = 0
        for _ in range(periods):
            if random.random() < hit_prob:
                # 随机选择中了哪个
                r = random.random()
                cum = 0
                for bet in bets:
                    cum += len(bet["numbers"]) / total_count
                    if r < cum:
                        balance += bet["odds"] * bet_per_note - bet_per_period
                        break
            else:
                balance -= bet_per_period
        mc_results.append(balance)

    mc_results.sort()
    p1 = mc_results[int(len(mc_results) * 0.01)]
    p5 = mc_results[int(len(mc_results) * 0.05)]
    p50 = mc_results[int(len(mc_results) * 0.50)]
    p95 = mc_results[int(len(mc_results) * 0.95)]
    p99 = mc_results[int(len(mc_results) * 0.99)]
    win_prob = sum(1 for r in mc_results if r > 0) / len(mc_results) * 100

    print(f"  最差1%: {p1:+.0f}元")
    print(f"  最差5%: {p5:+.0f}元")
    print(f"  中位数: {p50:+.0f}元")
    print(f"  最好5%: {p95:+.0f}元")
    print(f"  最好1%: {p99:+.0f}元")
    print(f"  盈利概率: {win_prob:.1f}%")

    if win_prob > 80:
        print("  ✅ 模拟结果稳定，盈利概率高")
    elif win_prob > 60:
        print("  ⚠️ 模拟结果中等，需谨慎")
    else:
        print("  ❌ 模拟结果不佳，建议放弃该策略")

    return mc_results


# =====================================================
# 主程序
# =====================================================

def main():
    print("=" * 70)
    print("🎯 新澳门六合彩 - 4注半半波策略回测")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 获取数据
    rows = fetch_new_macau(CONFIG["history_limit"])

    if len(rows) < 30:
        print("❌ 数据不足（需要至少30期）")
        return

    # 执行回测
    result = run_backtest(rows)

    # 蒙特卡洛模拟
    monte_carlo_simulation(periods=1000, iterations=10000)

    print("\n" + "=" * 70)
    print("📋 最终结论")
    print("=" * 70)

    if result["balance"] > 0 and result["roi"] > 0:
        print("""
✅ 策略可行！

建议:
  1. 启动资金: {} 元
  2. 每期固定投入: 400 元
  3. 严格执行止损/止盈
  4. 至少坚持 365 期

注意:
  - 短期可能亏损
  - 赔率可能调整
  - 平台可能限制
""".format(int(abs(result["max_drawdown"]) * 1.5)))
    else:
        print("""
❌ 策略暂不可行

原因:
  - 历史回测未盈利
  - 或收益率不理想

建议:
  1. 回测更多数据
  2. 调整策略参数
  3. 寻找其他正期望值玩法
""")


if __name__ == "__main__":
    main()