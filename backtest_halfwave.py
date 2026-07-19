#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三彩（香港彩 / 新澳门彩 / 老澳门彩）大/单 置信度下注建议 —— v2
本版相对上一版的三个主要改动：

1. 【多重比较校正】原版同时对 3 彩种 × 3 窗口 × 4 方向 = 36 次假设检验，
   都用同一个 z≥1.96（95%置信度）阈值判断"显著"。哪怕数据完全随机，
   平均也会有 1-2 次"显著"信号纯属巧合（假阳性）。
   这版用 Bonferroni 校正：把显著性阈值除以检验次数，
   例如 36 次检验、原目标 α=0.05，则校正后 α'=0.05/36≈0.0014，
   对应 z 阈值约 3.20，而不是 1.96。

2. 【真正的样本外回测 + 稳定性检查】不再只用一段历史数据回测一次，
   而是切成多个不重叠的子区间分别统计命中率，
   看这个"信号"在不同时间段是否稳定，还是时好时坏（说明是噪音）。

3. 【资金管理与信号预测解耦】WeeklyTracker（止损/止盈/次数限制）
   本身是合理的纪律工具，不依赖"预测是否准确"也该执行。
   这版把它拆成独立模块，即使你以后完全不用 z-test 信号，
   也可以单独使用资金管理部分来控制下注纪律。

⚠️ 重要说明：如果开奖是真随机独立事件，本质上不存在能稳定跑赢
理论概率的"预测算法"。这个工具的价值主要在于用统计方法诚实地
检验"是否存在可利用的规律"，而不是假设规律一定存在。如果长期
回测显示命中率始终在理论值附近浮动，最理性的结论是承认没有可
利用的信号，而不是继续调参数去找"看起来显著"的结果。
"""

import re
import json
import math
import urllib.request
from datetime import datetime, timedelta
from scipy import stats as scipy_stats  # 如果没装，见下方 fallback

API_URL = "https://marksix6.net/index.php?api=1"

LOTTERIES = [
    {"key": "hk", "name": "香港彩", "label": "香港彩"},
    {"key": "xam", "name": "新澳门彩", "label": "新澳门彩"},
    {"key": "lam", "name": "老澳门彩", "label": "老澳门彩"},
]

THEORY_P = 25 / 49
DIRECTIONS = ["大", "单", "小", "双"]
WINDOWS = [30, 50, 100]

# ============ 第1部分：多重比较校正 ============

def bonferroni_z_threshold(alpha=0.05, n_tests=None):
    """
    根据检验次数计算 Bonferroni 校正后的 z 阈值。
    n_tests 默认 = 彩种数 × 窗口数 × 方向数（但大/小、单/双是互补的，
    实际独立检验数约为一半，这里保守起见不打折）。
    """
    if n_tests is None:
        n_tests = len(LOTTERIES) * len(WINDOWS) * len(DIRECTIONS)
    corrected_alpha = alpha / n_tests
    # 双侧检验的临界值
    try:
        z_crit = abs(scipy_stats.norm.ppf(corrected_alpha / 2))
    except Exception:
        # 没装 scipy 的 fallback：用近似公式（Beasley-Springer-Moro 或查表）
        # 这里给几个常用值的手工查表，避免强依赖 scipy
        table = {0.05: 1.96, 0.01: 2.576, 0.001: 3.29, 0.0001: 3.89}
        # 找最接近的
        closest = min(table.keys(), key=lambda k: abs(k - corrected_alpha))
        z_crit = table[closest]
    return z_crit, corrected_alpha, n_tests


# ============ 第2部分：数据获取（与原版一致） ============

def parse_numbers(text):
    nums = re.findall(r"\d+", text)
    return [int(x) for x in nums if 1 <= int(x) <= 49]

def fetch_lottery(lottery_name, limit=400):
    """limit 从 200 提高到 400，给样本外回测留更多数据"""
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


# ============ 第3部分：信号计算（用校正后的阈值） ============

def bet_decision(rows, window, z_threshold):
    if len(rows) < window:
        return None
    recent = rows[-window:]
    n = len(recent)
    hits = {
        "大": sum(1 for r in recent if r["is_big"]),
        "单": sum(1 for r in recent if r["is_odd"]),
        "小": sum(1 for r in recent if r["is_small"]),
        "双": sum(1 for r in recent if r["is_even"]),
    }
    out = {}
    for d in DIRECTIONS:
        z, p = z_test(hits[d], n)
        out[d] = {"action": "下注" if z >= z_threshold else "观望", "z": z, "p": p, "hits": hits[d], "n": n}
    return out


def multi_window_decision(rows, windows, z_threshold):
    if not rows or len(rows) < min(windows):
        return None
    results = {w: bet_decision(rows, w, z_threshold) for w in windows if len(rows) >= w}
    results = {w: d for w, d in results.items() if d}
    if not results:
        return None

    votes = {d: 0 for d in DIRECTIONS}
    for w, d in results.items():
        for dir_name in DIRECTIONS:
            if d[dir_name]["action"] == "下注":
                votes[dir_name] += 1

    total_windows = len(results)
    threshold = total_windows / 2
    result = {}
    for dir_name in DIRECTIONS:
        result[dir_name] = {
            "action": "下注" if votes[dir_name] > threshold else "观望",
            "votes": votes[dir_name],
            "total_windows": total_windows,
            "detail": {w: results[w][dir_name] for w in results.keys()},
        }
    return result


# ============ 第4部分：样本外回测 + 跨子区间稳定性检查 ============

def rolling_backtest(rows, window, z_threshold, direction="大"):
    """
    逐期滚动的样本外回测：用 i 之前的数据判断信号，检验第 i 期是否命中。
    返回每次触发信号的位置和结果，方便后面切子区间看稳定性。
    """
    key_map = {"大": "is_big", "单": "is_odd", "小": "is_small", "双": "is_even"}
    field = key_map[direction]
    events = []  # (index, hit_bool)

    if len(rows) < window + 1:
        return events

    for i in range(window, len(rows)):
        history = rows[:i]
        actual_next = rows[i]
        recent = history[-window:]
        n = len(recent)
        hits = sum(1 for r in recent if r[field])
        z, _ = z_test(hits, n)
        if z >= z_threshold:
            events.append((i, actual_next[field]))
    return events


def stability_check(events, n_splits=3):
    """
    把触发信号的事件按时间顺序切成 n_splits 段，
    分别算每段的命中率。如果各段命中率差异很大（比如一段70%、
    另一段45%），说明这个"信号"不稳定，很可能只是噪音在特定
    时间段凑巧对齐，而不是真实规律。
    """
    if not events:
        return {"total": 0, "segments": [], "verdict": "从未触发，无法评估"}

    total = len(events)
    seg_size = max(1, total // n_splits)
    segments = []
    for i in range(0, total, seg_size):
        chunk = events[i:i + seg_size]
        if not chunk:
            continue
        hits = sum(1 for _, h in chunk if h)
        acc = hits / len(chunk) * 100
        segments.append({"n": len(chunk), "hits": hits, "acc": acc})

    if len(segments) < 2:
        verdict = "样本段数不足，无法判断稳定性"
    else:
        accs = [s["acc"] for s in segments]
        spread = max(accs) - min(accs)
        if spread > 20:
            verdict = f"⚠️ 不稳定：各段命中率相差{spread:.1f}个百分点，很可能是噪音"
        elif spread > 10:
            verdict = f"📊 中等波动：各段相差{spread:.1f}个百分点，需更多数据观察"
        else:
            verdict = f"✅ 相对稳定：各段命中率相差仅{spread:.1f}个百分点"

    overall_hits = sum(1 for _, h in events if h)
    overall_acc = overall_hits / total * 100
    return {
        "total": total,
        "overall_acc": overall_acc,
        "segments": segments,
        "verdict": verdict,
    }


def full_backtest_report(rows, window=50, z_threshold=1.96):
    print(f"\n{'='*74}")
    print(f"📈 样本外回测 + 稳定性检查（窗口={window}期，z阈值={z_threshold:.2f}，共{len(rows)}期数据）")
    print("=" * 74)

    for direction in ["大", "单"]:
        events = rolling_backtest(rows, window, z_threshold, direction)
        report = stability_check(events, n_splits=3)

        print(f"\n【{direction}】")
        if report["total"] == 0:
            print("  历史从未触发下注信号（说明z阈值下这个方向没有假阳性也没有真信号）")
            continue

        print(f"  总触发次数: {report['total']}，总体命中率: {report['overall_acc']:.1f}% "
              f"(理论基准 {THEORY_P*100:.1f}%)")
        for idx, seg in enumerate(report["segments"], 1):
            print(f"    第{idx}段: {seg['n']}次触发，命中{seg['hits']}次 = {seg['acc']:.1f}%")
        print(f"  稳定性结论: {report['verdict']}")


# ============ 第5部分：资金管理（完全独立，不依赖信号是否有效） ============

WEEKLY_CONFIG = {
    "per_bet_amount": 200,
    "max_daily_bets": 3,
    "weekly_target": 1000,
    "daily_target": 150,
    "weekly_stop_loss": -1000,
    "daily_stop_loss": -300,
    "consecutive_loss_days": 3,
}

class WeeklyTracker:
    """
    这个类只管纪律（止损/止盈/次数上限），完全不关心信号
    是否"显著"或"准确"。即使你哪天不用 z-test，只是凭感觉
    或看别的消息面下注，这套纪律依然值得遵守——它保护的是
    本金，不是预测准确率。

    每个彩种各管各的：每个彩种拥有独立的 WeeklyTracker 实例，
    独立的周/日盈亏、独立的止损止盈线、独立的连亏计数。
    某个彩种触发止损，只影响这一个彩种，不会连带暂停其它两个。
    """
    def __init__(self, lottery_name, config=None):
        self.lottery_name = lottery_name
        self.config = config or dict(WEEKLY_CONFIG)  # 每个彩种可以有自己的配置
        self.week_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.week_start -= timedelta(days=self.week_start.weekday())
        self.weekly_profit = 0
        self.daily_profit = 0
        self.bets_today = 0
        self.bets_this_week = 0
        self.consecutive_loss_days = 0
        self.status = "正常"

    def update(self, profit, hit):
        self.weekly_profit += profit
        self.daily_profit += profit
        self.bets_today += 1
        self.bets_this_week += 1
        self.consecutive_loss_days = 0 if hit else self.consecutive_loss_days + 1
        self._update_status()

    def _update_status(self):
        c = self.config
        if self.weekly_profit <= c["weekly_stop_loss"]:
            self.status = "暂停_周止损"
        elif self.daily_profit <= c["daily_stop_loss"]:
            self.status = "暂停_日止损"
        elif self.consecutive_loss_days >= c["consecutive_loss_days"]:
            self.status = "暂停_连亏"
        elif self.weekly_profit >= c["weekly_target"]:
            self.status = "完成_周目标"
        elif self.daily_profit >= c["daily_target"]:
            self.status = "完成_日目标"
        elif self.bets_today >= c["max_daily_bets"]:
            self.status = "暂停_日次数"
        elif self.weekly_profit < 0:
            self.status = "谨慎_亏损中"
        else:
            self.status = "正常"

    def can_bet(self):
        # 每个tracker只管一个彩种，不需要再传lottery_name来判重
        if self.status not in ["正常", "谨慎_亏损中"]:
            return False, self.get_recommendation()
        return True, "✅ 可以投注"

    def get_recommendation(self):
        c = self.config
        messages = {
            "暂停_周止损": f"❌ {self.lottery_name}本周亏损{self.weekly_profit}元，已到止损线({c['weekly_stop_loss']}元)",
            "暂停_日止损": f"❌ {self.lottery_name}今日亏损{self.daily_profit}元，已到止损线({c['daily_stop_loss']}元)",
            "暂停_连亏": f"❌ {self.lottery_name}已连续{self.consecutive_loss_days}天未中",
            "完成_周目标": f"✅ {self.lottery_name}本周已盈利{self.weekly_profit}元，达到目标(+{c['weekly_target']}元)",
            "完成_日目标": f"✅ {self.lottery_name}今日已盈利{self.daily_profit}元，达到目标(+{c['daily_target']}元)",
            "暂停_日次数": f"⚠️ {self.lottery_name}今日已投{self.bets_today}期（上限{c['max_daily_bets']}期）",
            "谨慎_亏损中": f"⚠️ {self.lottery_name}本周亏损{self.weekly_profit}元，建议减仓",
        }
        return messages.get(self.status, f"✅ {self.lottery_name}状态正常")


def calculate_bet_amount(tracker, signal_strength):
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
    return round(bet, -1)


# ============ 主流程 ============

def main():
    z_crit, corrected_alpha, n_tests = bonferroni_z_threshold(alpha=0.05)

    print("=" * 74)
    print("🎯 三彩大/单置信度下注建议 v2（含多重比较校正 + 样本外稳定性检查）")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 74)
    print(f"\n📐 本次共进行 {n_tests} 次假设检验")
    print(f"   原始显著性水平 α=0.05 → Bonferroni校正后 α'={corrected_alpha:.5f}")
    print(f"   对应 z 阈值：原版 1.96 → 校正后 {z_crit:.2f}")
    print(f"   （校正后阈值更高，意味着更难被判定为'显著'，但假阳性率也更低更可信）")

    # 每个彩种各管各的：独立tracker，各自的止损/止盈/次数限制互不影响
    trackers = {lot["label"]: WeeklyTracker(lot["label"]) for lot in LOTTERIES}

    for lot in LOTTERIES:
        name = lot["label"]
        tracker = trackers[name]

        print(f"\n{'#'*74}")
        print(f"# {name}")
        print("#" * 74)

        print(f"\n📊 {name} 独立状态: 本周{tracker.weekly_profit:+.0f}元 / "
              f"今日{tracker.daily_profit:+.0f}元 / 状态={tracker.status}")

        rows = fetch_lottery(name, limit=400)
        if len(rows) < 150:
            print(f"⚠️ {name} 数据不足150期，跳过（样本外回测需要较多数据才有意义）")
            continue

        # 用校正后的阈值做当前信号判断
        decision = multi_window_decision(rows, windows=WINDOWS, z_threshold=z_crit)

        # 样本外回测 + 稳定性检查（用同样校正后的阈值，保持逻辑一致）
        full_backtest_report(rows, window=50, z_threshold=z_crit)

        if decision:
            print(f"\n📊 当前多窗口判断（{decision['大']['total_windows']}个窗口，z阈值={z_crit:.2f}）:")
            for dir_name in DIRECTIONS:
                d = decision[dir_name]
                status = "✅ 下注" if d["action"] == "下注" else "⏸️ 观望"
                print(f"  {dir_name}: {status} ({d['votes']}/{d['total_windows']}窗口)")

            for dir_name in ["大", "单"]:
                if decision[dir_name]["action"] == "下注":
                    can_bet, msg = tracker.can_bet()
                    z = decision[dir_name]["detail"].get(50, {}).get("z", 0)
                    if can_bet:
                        bet = calculate_bet_amount(tracker, z)
                        print(f"  💰 {dir_name} 建议投注 {bet}元 (z={z:+.2f})")
                    else:
                        print(f"  ⏸️ {dir_name}: {msg}")
        else:
            print("\n⏸️ 数据不足以做多窗口判断")

    # 分彩种独立汇总（不合并成一个总账）
    print("\n" + "=" * 74)
    print("📋 各彩种独立状态汇总")
    print("=" * 74)
    for lot in LOTTERIES:
        t = trackers[lot["label"]]
        print(f"\n【{lot['label']}】")
        print(f"  本周盈亏: {t.weekly_profit:+.0f}元 (目标+{t.config['weekly_target']}元, "
              f"止损{t.config['weekly_stop_loss']}元)")
        print(f"  今日盈亏: {t.daily_profit:+.0f}元 (目标+{t.config['daily_target']}元, "
              f"止损{t.config['daily_stop_loss']}元)")
        print(f"  今日已投: {t.bets_today}/{t.config['max_daily_bets']}期")
        print(f"  状态: {t.status}")
        print(f"  建议: {t.get_recommendation()}")

    print("\n" + "=" * 74)
    print("📋 结论提示")
    print("=" * 74)
    print("""
如果每个彩种、每个方向的"稳定性检查"结果大多是⚠️不稳定，
说明历史上看起来显著的信号很可能只是噪音巧合，不建议据此加大投注。

每个彩种现在完全独立记账：某个彩种触发止损/达到目标，
只影响这一个彩种的后续下注建议，不会连带暂停其它彩种。
资金管理纪律（止损/止盈/次数限制）无论信号是否有效都建议继续执行，
它保护的是本金安全，而不是预测准确率。
""")

if __name__ == "__main__":
    main()
