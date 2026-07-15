#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门彩 - 半半波正期望值策略回测
玩法：每期固定4注（蓝小单+蓝大双+绿大双+红小双）
每注100元，每期400元
"""

import re
import json
import urllib.request
from collections import defaultdict
from datetime import datetime
import random

# =====================================================
# 配置
# =====================================================

CONFIG = {
    "api_url": "https://marksix6.net/index.php?api=1",
    "history_limit": 100,  # 拉取最近100期
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
# 获取历史数据
# =====================================================

def fetch_history(limit=100):
    """获取新澳门彩历史开奖数据"""
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
        print("获取失败:", e)
        return []

    # 去重
    cache = {}
    for r in rows:
        cache[r["issue"]] = r
    rows = list(cache.values())
    rows.sort(key=lambda x: x["issue"], reverse=True)
    return rows[:limit]


# =====================================================
# 回测引擎
# =====================================================

class BacktestEngine:
    """半半波策略回测引擎"""

    def __init__(self, rows):
        self.rows = rows
        self.bets = [
            {"name": "蓝小单", "odds": 15.76, "numbers": {3, 9, 15, 21}},
            {"name": "蓝大双", "odds": 11.82, "numbers": {26, 36, 42, 47, 48}},
            {"name": "绿大双", "odds": 11.82, "numbers": {28, 32, 38, 44, 49}},
            {"name": "红小双", "odds": 9.45, "numbers": {2, 8, 12, 18, 24}},
        ]
        self.bet_per_note = 100
        self.bet_per_period = self.bet_per_note * len(self.bets)

    def run(self):
        """执行回测"""
        results = []
        balance = 0
        total_bet = 0
        total_win = 0
        hit_count = 0
        max_balance = 0
        max_drawdown = 0
        drawdown_start = 0
        in_drawdown = False

        print("\n" + "=" * 70)
        print("📊 回测开始")
        print("=" * 70)
        print(f"  策略: 每期固定4注（蓝小单+蓝大双+绿大双+红小双）")
        print(f"  每注: {self.bet_per_note}元")
        print(f"  每期投入: {self.bet_per_period}元")
        print(f"  回测期数: {len(self.rows)}期")
        print(f"  数据范围: {self.rows[-1]['issue']} ~ {self.rows[0]['issue']}")
        print("=" * 70)

        # 从最早到最晚（按时间顺序回测）
        rows_chrono = list(reversed(self.rows))

        for i, r in enumerate(rows_chrono, 1):
            drawn_number = r["special"]
            actual_halfhalf = r["halfhalf"]

            # 检查中了哪个
            hit = None
            for bet in self.bets:
                if drawn_number in bet["numbers"]:
                    hit = bet
                    break

            if hit:
                hit_count += 1
                win_amount = hit["odds"] * self.bet_per_note
                profit = win_amount - self.bet_per_period
                total_win += win_amount
                balance += profit

                # 记录中奖详情
                results.append({
                    "issue": r["issue"],
                    "number": drawn_number,
                    "actual": actual_halfhalf,
                    "hit": hit["name"],
                    "win_amount": win_amount,
                    "profit": profit,
                    "balance": balance,
                    "cumulative_hit": hit_count,
                })
            else:
                profit = -self.bet_per_period
                balance += profit
                results.append({
                    "issue": r["issue"],
                    "number": drawn_number,
                    "actual": actual_halfhalf,
                    "hit": None,
                    "win_amount": 0,
                    "profit": profit,
                    "balance": balance,
                    "cumulative_hit": hit_count,
                })

            total_bet += self.bet_per_period

            # 计算最大回撤
            if balance > max_balance:
                max_balance = balance
                drawdown_start = balance
                in_drawdown = False
            else:
                in_drawdown = True
                current_drawdown = drawdown_start - balance
                if current_drawdown > max_drawdown:
                    max_drawdown = current_drawdown

        # =====================================================
        # 输出报告
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
        print(f"  📊 ROI: {roi:+.2f}%")
        print("=" * 70)

        # =====================================================
        # 分期明细
        # =====================================================

        print("\n📋 每10期盈亏明细:")
        print("-" * 70)
        print(f"{'期号':<12} {'开奖号':<8} {'实际半波':<12} {'命中':<12} {'盈亏':<12} {'累计':<12}")
        print("-" * 70)

        for i, r in enumerate(results):
            if (i + 1) % 10 == 0 or i == len(results) - 1 or i < 5 or i > len(results) - 5:
                hit_str = r["hit"] if r["hit"] else "❌未中"
                print(f"{r['issue']:<12} {r['number']:<8} {r['actual']:<12} {hit_str:<12} {r['profit']:<+12.0f} {r['balance']:<+12.0f}")

        # =====================================================
        # 详细命中记录
        # =====================================================

        print("\n🎯 命中记录:")
        print("-" * 70)
        hit_records = [r for r in results if r["hit"]]
        if hit_records:
            for r in hit_records:
                print(f"  {r['issue']}  开{r['number']}  中{r['hit']}  盈利{r['profit']:+.0f}元  累计{r['balance']:.0f}元")
        else:
            print("  无命中记录")

        # =====================================================
        # 期望值验证
        # =====================================================

        print("\n" + "=" * 70)
        print("🧮 理论期望 vs 实际结果验证")
        print("=" * 70)

        # 理论期望
        expected_per_period = 0
        for bet in self.bets:
            prob = len(bet["numbers"]) / 49
            expected_per_period += (bet["odds"] * 100 * prob) - (100 * prob)
        # 减去未中时的亏损
        miss_prob = 1 - sum(len(bet["numbers"]) / 49 for bet in self.bets)
        expected_per_period -= miss_prob * self.bet_per_period

        print(f"  理论每期期望: {expected_per_period:+.2f}元")
        print(f"  理论{total_periods}期盈利: {expected_per_period * total_periods:+.0f}元")
        print(f"  实际{total_periods}期盈利: {balance:+.0f}元")
        print(f"  偏差: {balance - expected_per_period * total_periods:+.0f}元")

        if balance > expected_per_period * total_periods * 0.8:
            print("  ✅ 实际结果符合理论预期")
        elif balance > 0:
            print("  ⚠️ 实际盈利，但低于理论预期")
        else:
            print("  ❌ 实际亏损，可能受短期波动影响或策略失效")

        return {
            "total_periods": total_periods,
            "hit_count": hit_count,
            "hit_rate": hit_rate,
            "total_bet": total_bet,
            "total_win": total_win,
            "balance": balance,
            "max_drawdown": max_drawdown,
            "roi": roi,
            "expected_profit": expected_per_period * total_periods,
            "results": results,
        }


# =====================================================
# 主程序
# =====================================================

def main():
    print("=" * 70)
    print("🎯 新澳门彩 - 半半波正期望值策略回测")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    print("\n📡 获取历史数据...")
    rows = fetch_history(100)

    if len(rows) < 20:
        print("❌ 数据不足（需要至少20期）")
        return

    print(f"✅ 获取到 {len(rows)} 期历史数据")

    # 执行回测
    engine = BacktestEngine(rows)
    result = engine.run()

    # =====================================================
    # 模拟未来1000期（蒙特卡洛）
    # =====================================================

    print("\n" + "=" * 70)
    print("🔄 蒙特卡洛模拟（未来1000期 × 1000次）")
    print("=" * 70)

    # 模拟参数
    bets = [
        {"name": "蓝小单", "odds": 15.76, "count": 4},
        {"name": "蓝大双", "odds": 11.82, "count": 5},
        {"name": "绿大双", "odds": 11.82, "count": 5},
        {"name": "红小双", "odds": 9.45, "count": 5},
    ]
    total_count = sum(b["count"] for b in bets)  # 19个号码
    hit_prob = total_count / 49
    bet_per_period = 400

    # 计算平均每期中奖收益
    avg_win = 0
    for b in bets:
        avg_win += b["odds"] * 100 * (b["count"] / total_count)

    mc_results = []
    for _ in range(1000):
        balance = 0
        for _ in range(1000):
            if random.random() < hit_prob:
                # 随机决定中了哪个
                r = random.random()
                cum = 0
                for b in bets:
                    cum += b["count"] / total_count
                    if r < cum:
                        balance += b["odds"] * 100 - bet_per_period
                        break
            else:
                balance -= bet_per_period
        mc_results.append(balance)

    mc_results.sort()
    p5 = mc_results[int(len(mc_results) * 0.05)]
    p50 = mc_results[int(len(mc_results) * 0.50)]
    p95 = mc_results[int(len(mc_results) * 0.95)]

    print(f"\n📊 1000期 × 1000次模拟结果:")
    print(f"  最差5%情况: {p5:+.0f}元")
    print(f"  中位数: {p50:+.0f}元")
    print(f"  最好5%情况: {p95:+.0f}元")
    print(f"  盈利概率: {sum(1 for r in mc_results if r > 0) / len(mc_results) * 100:.1f}%")


if __name__ == "__main__":
    main()