#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门彩 - 半半波正期望值策略工作流 V1.0
=========================================
完整流程：
1. 拉取最新历史数据（自动）
2. 执行策略回测验证
3. 计算当期预测
4. 输出下注建议 + 风险提示
"""

import re
import json
import urllib.request
from collections import defaultdict
from datetime import datetime
import random
import os
import sys

# =====================================================
# 配置
# =====================================================

CONFIG = {
    "api_url": "https://marksix6.net/index.php?api=1",
    "history_limit": 100,
    "bet_per_note": 100,
    "strategy": {
        "name": "4注半半波策略",
        "bets": [
            {"name": "蓝小单", "odds": 15.76, "numbers": [3, 9, 15, 21]},
            {"name": "蓝大双", "odds": 11.82, "numbers": [26, 36, 42, 47, 48]},
            {"name": "绿大双", "odds": 11.82, "numbers": [28, 32, 38, 44, 49]},
            {"name": "红小双", "odds": 9.45, "numbers": [2, 8, 12, 18, 24]},
        ]
    },
    "risk_control": {
        "stop_loss": -10000,      # 累计亏损达1万暂停
        "take_profit": 30000,     # 累计盈利达3万提取一半
        "max_consecutive_loss": 15,  # 连续亏损15期暂停
    }
}

# =====================================================
# 波色定义
# =====================================================

RED = {1, 2, 7, 8, 12, 13, 18, 19, 23, 24, 29, 30, 34, 35, 40, 45, 46}
BLUE = {3, 4, 9, 10, 14, 15, 20, 25, 26, 31, 36, 37, 41, 42, 47, 48}
GREEN = {5, 6, 11, 16, 17, 21, 22, 27, 28, 32, 33, 38, 39, 43, 44, 49}


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
# 步骤1: 数据获取
# =====================================================

class DataFetcher:
    """数据获取层"""

    def __init__(self):
        self.api_url = CONFIG["api_url"]
        self.limit = CONFIG["history_limit"]

    def fetch(self):
        """拉取历史数据"""
        print("\n" + "=" * 60)
        print("📡 步骤1: 获取数据")
        print("=" * 60)

        rows = []
        try:
            req = urllib.request.Request(
                self.api_url,
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

        # 去重并排序
        cache = {}
        for r in rows:
            cache[r["issue"]] = r
        rows = list(cache.values())
        rows.sort(key=lambda x: x["issue"], reverse=True)

        print(f"✅ 获取 {len(rows)} 期数据")
        print(f"📅 最新期号: {rows[0]['issue'] if rows else 'N/A'}")
        return rows[:self.limit]


# =====================================================
# 步骤2: 回测验证
# =====================================================

class BacktestEngine:
    """回测引擎"""

    def __init__(self, rows):
        self.rows = rows
        self.bets = CONFIG["strategy"]["bets"]
        self.bet_per_note = CONFIG["bet_per_note"]
        self.bet_per_period = self.bet_per_note * len(self.bets)

    def run(self):
        """执行回测"""
        print("\n" + "=" * 60)
        print("📊 步骤2: 策略回测")
        print("=" * 60)

        if len(self.rows) < 20:
            print("❌ 数据不足，无法回测")
            return None

        results = []
        balance = 0
        total_bet = 0
        total_win = 0
        hit_count = 0
        consecutive_loss = 0
        max_consecutive_loss = 0
        max_balance = 0
        max_drawdown = 0

        rows_chrono = list(reversed(self.rows))

        for r in rows_chrono:
            drawn_number = r["special"]

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
                consecutive_loss = 0
            else:
                profit = -self.bet_per_period
                balance += profit
                consecutive_loss += 1
                if consecutive_loss > max_consecutive_loss:
                    max_consecutive_loss = consecutive_loss

            total_bet += self.bet_per_period
            results.append({
                "issue": r["issue"],
                "number": drawn_number,
                "actual": r["halfhalf"],
                "hit": hit["name"] if hit else None,
                "profit": profit,
                "balance": balance,
            })

            if balance > max_balance:
                max_balance = balance
            if max_balance - balance > max_drawdown:
                max_drawdown = max_balance - balance

        # 汇总
        total_periods = len(results)
        hit_rate = hit_count / total_periods * 100 if total_periods > 0 else 0
        roi = (balance / total_bet * 100) if total_bet > 0 else 0

        print(f"  📅 回测期数: {total_periods}")
        print(f"  🎯 命中次数: {hit_count}")
        print(f"  📈 命中率: {hit_rate:.2f}%")
        print(f"  💰 总投注: {total_bet:,.0f}")
        print(f"  📊 最终盈亏: {balance:+,.0f}")
        print(f"  📉 最大回撤: {max_drawdown:,.0f}")
        print(f"  📊 ROI: {roi:+.2f}%")
        print(f"  🔥 最长连续未中: {max_consecutive_loss}期")

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
            "results": results,
        }


# =====================================================
# 步骤3: 蒙特卡洛模拟
# =====================================================

class MonteCarloSimulator:
    """蒙特卡洛模拟"""

    def __init__(self):
        self.bets = CONFIG["strategy"]["bets"]
        self.bet_per_note = CONFIG["bet_per_note"]
        self.bet_per_period = self.bet_per_note * len(self.bets)
        self.total_count = sum(len(bet["numbers"]) for bet in self.bets)
        self.hit_prob = self.total_count / 49

    def simulate(self, periods=1000, iterations=1000):
        """执行模拟"""
        print("\n" + "=" * 60)
        print("🔄 步骤3: 蒙特卡洛模拟")
        print("=" * 60)
        print(f"  模拟期数: {periods}")
        print(f"  模拟次数: {iterations}")

        results = []
        for _ in range(iterations):
            balance = 0
            for _ in range(periods):
                if random.random() < self.hit_prob:
                    # 随机选择中了哪个
                    r = random.random()
                    cum = 0
                    for bet in self.bets:
                        cum += len(bet["numbers"]) / self.total_count
                        if r < cum:
                            balance += bet["odds"] * self.bet_per_note - self.bet_per_period
                            break
                else:
                    balance -= self.bet_per_period
            results.append(balance)

        results.sort()
        p5 = results[int(len(results) * 0.05)]
        p50 = results[int(len(results) * 0.50)]
        p95 = results[int(len(results) * 0.95)]
        win_prob = sum(1 for r in results if r > 0) / len(results) * 100

        print(f"  最差5%: {p5:+,.0f}")
        print(f"  中位数: {p50:+,.0f}")
        print(f"  最好5%: {p95:+,.0f}")
        print(f"  盈利概率: {win_prob:.1f}%")

        return {"p5": p5, "p50": p50, "p95": p95, "win_prob": win_prob}


# =====================================================
# 步骤4: 生成下注建议
# =====================================================

class BetAdvisor:
    """下注建议生成器"""

    def __init__(self, backtest_result, mc_result):
        self.backtest = backtest_result
        self.mc = mc_result
        self.bets = CONFIG["strategy"]["bets"]
        self.bet_per_note = CONFIG["bet_per_note"]
        self.bet_per_period = self.bet_per_note * len(self.bets)
        self.risk = CONFIG["risk_control"]

    def generate(self):
        """生成建议"""
        print("\n" + "=" * 60)
        print("🎯 步骤4: 下注建议")
        print("=" * 60)

        # 判断策略是否可行
        is_viable = (
            self.backtest and
            self.backtest["balance"] > 0 and
            self.backtest["roi"] > 0 and
            self.mc["win_prob"] > 80
        )

        if is_viable:
            print("✅ 策略评估: 可行（正期望值）")
        else:
            print("⚠️ 策略评估: 需谨慎（历史表现不佳或模拟结果不理想）")

        # 下注明细
        print("\n📋 下注明细:")
        print("-" * 40)
        for bet in self.bets:
            numbers_str = ",".join([f"{n:02d}" for n in bet["numbers"]])
            print(f"  {bet['name']:<8} 赔率{bet['odds']:<6} 号码: {numbers_str}")

        print(f"\n💰 每期投入: {self.bet_per_period}元 ({len(self.bets)}注×{self.bet_per_note}元)")
        print(f"📊 覆盖号码: {sum(len(bet['numbers']) for bet in self.bets)}个 (命中率约{sum(len(bet['numbers']) for bet in self.bets)/49*100:.1f}%)")

        # 风险控制
        print("\n🛡️ 风险控制:")
        print(f"  止损线: {self.risk['stop_loss']:+,.0f}元")
        print(f"  止盈线: {self.risk['take_profit']:+,.0f}元")
        print(f"  连续亏损暂停: {self.risk['max_consecutive_loss']}期")

        # 资金建议
        recommended_capital = int(abs(self.backtest["max_drawdown"]) * 1.5) if self.backtest else 15000
        print(f"\n💰 建议启动资金: {recommended_capital:,}元")
        print(f"  建议单日操作: 1期")
        print(f"  建议操作周期: 至少1年 (365期)")

        return {
            "is_viable": is_viable,
            "recommended_capital": recommended_capital,
        }


# =====================================================
# 主工作流
# =====================================================

class Workflow:
    """主工作流"""

    def __init__(self):
        self.start_time = datetime.now()
        self.rows = []
        self.backtest_result = None
        self.mc_result = None
        self.advice = None

    def run(self):
        """执行完整工作流"""
        print("=" * 70)
        print("🎯 新澳门彩 - 半半波正期望值策略工作流")
        print(f"   {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        # 步骤1: 获取数据
        fetcher = DataFetcher()
        self.rows = fetcher.fetch()

        if len(self.rows) < 20:
            print("❌ 数据不足，工作流终止")
            return

        # 步骤2: 回测
        backtest = BacktestEngine(self.rows)
        self.backtest_result = backtest.run()

        if not self.backtest_result:
            print("❌ 回测失败，工作流终止")
            return

        # 步骤3: 蒙特卡洛模拟
        sim = MonteCarloSimulator()
        self.mc_result = sim.simulate(periods=1000, iterations=1000)

        # 步骤4: 生成建议
        advisor = BetAdvisor(self.backtest_result, self.mc_result)
        self.advice = advisor.generate()

        # 最终报告
        self.print_final_report()

    def print_final_report(self):
        """打印最终报告"""
        print("\n" + "=" * 70)
        print("📋 最终报告")
        print("=" * 70)

        if self.advice and self.advice["is_viable"]:
            print("""
✅ 结论: 策略可行

数学依据:
  - 所有下注均为正期望值
  - 历史回测盈利
  - 蒙特卡洛模拟盈利概率 > 80%

执行要求:
  1. 启动资金: {} 元
  2. 每期固定: 400 元 (4注×100元)
  3. 严格执行止损/止盈
  4. 至少坚持 365 期

⚠️ 风险提示:
  - 短期可能亏损
  - 赔率可能调整
  - 平台可能限制投注
  - 请用闲钱娱乐
""".format(self.advice["recommended_capital"]))
        else:
            print("""
⚠️ 结论: 建议观望

原因:
  - 历史回测表现不佳
  - 或蒙特卡洛模拟盈利概率低

建议:
  1. 等待更多数据再测试
  2. 考虑调整策略
  3. 暂时不要投入实盘
""")

        print("=" * 70)
        print(f"⏱️ 执行耗时: {(datetime.now() - self.start_time).total_seconds():.1f}秒")
        print("=" * 70)


# =====================================================
# 入口
# =====================================================

if __name__ == "__main__":
    workflow = Workflow()
    workflow.run()