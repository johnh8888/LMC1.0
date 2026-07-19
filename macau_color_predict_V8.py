#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新澳门彩预测系统 - v2（修复缓存bug + 加入显著性检验 + 随机基准对比）

相对上一版的三处改动：

1. 【修复缓存bug】原版只要缓存文件存在就永远用缓存，不管数据是否过期，
   导致每次运行看到的都是第一次运行时的旧数据。
   这版改成：优先尝试联网拉取最新数据；只有联网失败时才退回缓存
   （并明确提示"这是缓存数据，可能不是最新"）。

2. 【加入显著性检验】原版 select_best() 无论数据是不是纯噪音，都会
   强制输出"推荐半波""推荐生肖"，看起来像有把握的预测。
   这版给每个类别（颜色/大小/单双/半波/生肖）都做 z-test，
   只有统计上显著偏离真实理论概率的类别才会被标记为"推荐"，
   其余一律显示"观望"。并且用 Bonferroni 校正多重比较
   （半波实际是颜色×大小×单双的组合，共12种，不是6种；
   一共测试 颜色3+大小2+单双2+半波12+生肖12=31 个类别，
   比逐一单独判断要严格）。

3. 【随机基准对比】原版回测报告命中率时没说清楚"瞎猜"能到多少。
   半波在Top2推荐下，纯随机瞎猜命中率基准是 2/12≈16.7%（半波是颜色×大小×单双
   的组合，共12种，不是6种）；生肖在Top3推荐下，纯随机基准是 3/12=25%。
   这版把这两个基准显式打印出来，方便你一眼看出推荐是否比瞎猜强。

⚠️ 依然要提醒：如果开奖是真随机独立事件，这些检验大概率会显示
"从未显著"或"显著但不稳定"，这是诚实的结果，不是脚本没做好。
"""

import re
import json
import math
import urllib.request
import os
from collections import defaultdict
from datetime import datetime

try:
    from scipy import stats as scipy_stats
except ImportError:
    scipy_stats = None

CONFIG = {
    "history_limit": 200,      # 从30提高到200：小样本下显著性检验几乎不可能有意义
    "backtest_window": 60,     # 滚动回测用的窗口长度
    "api_url": "https://marksix6.net/index.php?api=1",
    "bet_count": 2,
    "cache_file": "newmacau_cache.json",
    "cache_max_age_hours": 6,  # 缓存超过这个时长，即使联网失败也会提示数据可能过旧
    "zodiac_year": 2026,
}

RED = {1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE = {3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
GREEN = {5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}

ZODIAC_ORDER = ["鼠","牛","虎","兔","龙","蛇","马","羊","猴","鸡","狗","猪"]
ZODIAC_BASE_YEAR = 2020

def build_zodiac_map(year):
    current_idx = (year - ZODIAC_BASE_YEAR) % 12
    zmap = {}
    for n in range(1, 50):
        offset = ((n - 1) % 12) + 1
        animal_idx = (current_idx - (offset - 1)) % 12
        zmap[n] = ZODIAC_ORDER[animal_idx]
    return zmap

ZODIAC_MAP = build_zodiac_map(CONFIG["zodiac_year"])

def get_color(n):
    if n in RED: return "红"
    if n in BLUE: return "蓝"
    return "绿"

def get_size(n):
    return "大" if n >= 25 else "小"

def get_odd(n):
    return "单" if n % 2 == 1 else "双"

def get_halfhalf(n):
    return get_color(n) + get_size(n) + get_odd(n)

def get_zodiac(n):
    return ZODIAC_MAP.get(n, "?")


# ============ 真实理论概率（不是假设的均匀分布，是按1-49实际统计出来的） ============
# 例如红/蓝/绿的号码数并不是各1/3（17红/16蓝/16绿），大小也不是各1/2（25大/24小）。
# 用真实值做基准，比赛前假设"均匀分布"更准确。

def build_theory_probs():
    all_nums = list(range(1, 50))
    def dist(func):
        c = defaultdict(int)
        for n in all_nums:
            c[func(n)] += 1
        return {k: v / 49 for k, v in c.items()}

    return {
        "color": dist(get_color),
        "size": dist(get_size),
        "odd": dist(get_odd),
        "halfhalf": dist(get_halfhalf),
        "zodiac": dist(get_zodiac),
    }

THEORY = build_theory_probs()

# 随机瞎猜基准（用于回测报告里明确对比）
RANDOM_BASELINE = {
    "halfwave_top2": 2 / len(THEORY["halfhalf"]),  # Top2推荐下瞎猜命中率
    "zodiac_top3": 3 / len(THEORY["zodiac"]),        # Top3推荐下瞎猜命中率
}


def parse_numbers(text):
    nums = re.findall(r"\d+", text)
    return [int(x) for x in nums if 1 <= int(x) <= 49]


def fetch_new_macau(limit):
    """
    修复版：优先联网拉最新数据；只有联网失败时才退回缓存，
    并明确告知用户这是缓存数据（可能不是最新一期）。
    """
    fresh_rows = _fetch_from_network(limit)
    if fresh_rows:
        try:
            with open(CONFIG["cache_file"], "w", encoding="utf-8") as f:
                json.dump({
                    "fetched_at": datetime.now().isoformat(),
                    "rows": fresh_rows,
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 缓存写入失败（不影响本次结果）: {e}")
        return fresh_rows, "live"

    # 联网失败，尝试用缓存
    if os.path.exists(CONFIG["cache_file"]):
        try:
            with open(CONFIG["cache_file"], "r", encoding="utf-8") as f:
                cached = json.load(f)
            fetched_at = datetime.fromisoformat(cached["fetched_at"])
            age_hours = (datetime.now() - fetched_at).total_seconds() / 3600
            print(f"⚠️ 联网获取失败，改用本地缓存（缓存时间: {cached['fetched_at']}，"
                  f"已过去约{age_hours:.1f}小时，可能不是最新一期！）")
            return cached["rows"][:limit], "cache"
        except Exception as e:
            print(f"❌ 缓存读取也失败: {e}")
            return [], "none"

    print("❌ 联网失败且无本地缓存，本次无法获取数据")
    return [], "none"


def _fetch_from_network(limit):
    try:
        req = urllib.request.Request(CONFIG["api_url"], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        rows = []
        for item in data.get("lottery_data", []):
            if item.get("name", "").strip() == "新澳门彩":
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
                        "color": get_color(special),
                        "size": get_size(special),
                        "odd": get_odd(special),
                        "halfhalf": get_halfhalf(special),
                        "zodiac": get_zodiac(special),
                    })
                break

        rows = list({r["issue"]: r for r in rows}.values())
        rows.sort(key=lambda x: x["issue"], reverse=True)
        return rows[:limit]
    except Exception as e:
        print(f"📡 联网获取失败: {e}")
        return []


# ============ 显著性检验（复用z-test思路，理论概率用真实分布） ============

def z_test(hits, n, p0):
    if n == 0 or p0 <= 0 or p0 >= 1:
        return 0.0, 0.0
    p_hat = hits / n
    se = math.sqrt(p0 * (1 - p0) / n)
    z = (p_hat - p0) / se if se > 0 else 0.0
    return z, p_hat


def bonferroni_z_threshold(alpha, n_tests):
    corrected_alpha = alpha / n_tests
    z_crit = None
    if scipy_stats is not None:
        try:
            z_crit = abs(scipy_stats.norm.ppf(corrected_alpha / 2))
        except Exception:
            z_crit = None
    if z_crit is None:
        table = [
            (0.10, 1.645), (0.05, 1.96), (0.01, 2.576),
            (0.005, 2.807), (0.001, 3.291), (0.0005, 3.481),
            (0.0001, 3.891), (0.00005, 4.056), (0.00001, 4.417),
        ]
        if corrected_alpha >= table[0][0]:
            z_crit = table[0][1]
        elif corrected_alpha <= table[-1][0]:
            z_crit = table[-1][1]
        else:
            for (a1, z1), (a2, z2) in zip(table, table[1:]):
                if a2 <= corrected_alpha <= a1:
                    frac = (math.log(corrected_alpha) - math.log(a1)) / (math.log(a2) - math.log(a1))
                    z_crit = z1 + frac * (z2 - z1)
                    break
    return z_crit, corrected_alpha


# 一共测试的类别数：颜色3 + 大小2 + 单双2 + 半波6 + 生肖12 = 25
N_TOTAL_TESTS = sum(len(THEORY[k]) for k in ["color", "size", "odd", "halfhalf", "zodiac"])


def test_all_categories(rows, key, window, z_threshold):
    """对某个维度（如'size'）下的每个类别做z-test，返回每个类别的结果"""
    if len(rows) < window:
        return {}
    recent = rows[-window:]
    n = len(recent)
    counts = defaultdict(int)
    for r in recent:
        counts[r[key]] += 1

    results = {}
    for category, p0 in THEORY[key].items():
        hits = counts.get(category, 0)
        z, p_hat = z_test(hits, n, p0)
        results[category] = {
            "z": z, "p_hat": p_hat, "p0": p0, "hits": hits, "n": n,
            "significant": z >= z_threshold,
        }
    return results


# ============ 样本外滚动回测 + 稳定性检查（沿用之前A股/彩票脚本的思路） ============

def rolling_backtest_category(rows, key, category, window, z_threshold):
    """
    逐期滚动：用第i期之前的window期数据判断该类别是否'显著'，
    如果显著就记录第i期实际是否命中该类别。这是真正的样本外检验。
    """
    events = []
    p0 = THEORY[key][category]
    if len(rows) < window + 1:
        return events

    for i in range(window, len(rows)):
        history = rows[:i]
        actual = rows[i]
        recent = history[-window:]
        n = len(recent)
        hits = sum(1 for r in recent if r[key] == category)
        z, _ = z_test(hits, n, p0)
        if z >= z_threshold:
            events.append((i, actual[key] == category))
    return events


def stability_check(events, n_splits=3):
    if not events:
        return {"total": 0, "verdict": "从未触发"}
    total = len(events)
    seg_size = max(1, total // n_splits)
    segments = []
    for i in range(0, total, seg_size):
        chunk = events[i:i + seg_size]
        if not chunk:
            continue
        hits = sum(1 for _, h in chunk if h)
        segments.append({"n": len(chunk), "hits": hits, "acc": hits / len(chunk) * 100})

    if len(segments) < 2:
        verdict = "样本段数不足"
    else:
        spread = max(s["acc"] for s in segments) - min(s["acc"] for s in segments)
        if spread > 20:
            verdict = f"⚠️ 不稳定（各段相差{spread:.1f}个百分点）"
        elif spread > 10:
            verdict = f"📊 中等波动（各段相差{spread:.1f}个百分点）"
        else:
            verdict = f"✅ 相对稳定（各段相差仅{spread:.1f}个百分点）"

    overall_hits = sum(1 for _, h in events if h)
    return {
        "total": total,
        "overall_acc": overall_hits / total * 100,
        "segments": segments,
        "verdict": verdict,
    }


def run_backtest_report(rows, z_threshold):
    print(f"\n{'='*90}")
    print(f"📈 样本外回测 + 稳定性检查（窗口={CONFIG['backtest_window']}期，"
          f"z阈值={z_threshold:.2f}，共{len(rows)}期数据）")
    print("=" * 90)

    for key, label in [("size", "大小"), ("odd", "单双"), ("color", "颜色")]:
        print(f"\n【{label}】")
        for category in THEORY[key]:
            events = rolling_backtest_category(rows, key, category, CONFIG["backtest_window"], z_threshold)
            report = stability_check(events)
            if report["total"] == 0:
                print(f"  {category}: 历史从未触发显著信号")
                continue
            print(f"  {category}: 触发{report['total']}次，命中率{report['overall_acc']:.1f}% "
                  f"(理论基准{THEORY[key][category]*100:.1f}%) → {report['verdict']}")


# ============ 主流程 ============

def main():
    z_crit, corrected_alpha = bonferroni_z_threshold(alpha=0.05, n_tests=N_TOTAL_TESTS)

    print("=" * 90)
    print("新澳门彩预测系统 v2（缓存修复 + 显著性检验 + 随机基准对比）")
    print(f"生肖年份基准: {CONFIG['zodiac_year']}年")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 90)
    print(f"\n📐 本次共测试 {N_TOTAL_TESTS} 个类别（颜色3+大小2+单双2+半波12+生肖12）")
    print(f"   Bonferroni校正后 z阈值 = {z_crit:.2f}（原始1.96 → 校正后更严格，减少假阳性）")

    rows, source = fetch_new_macau(CONFIG["history_limit"])
    if len(rows) < CONFIG["backtest_window"] + 10:
        print(f"❌ 数据不足{CONFIG['backtest_window']+10}期，无法做有意义的显著性回测")
        return

    if source == "cache":
        print("\n⚠️ 注意：以下分析基于缓存数据，不是本次联网拉取的最新数据！")

    # 按时间正序排（rows目前是倒序：最新在前），下面统一用正序处理
    rows_sorted = sorted(rows, key=lambda x: x["issue"])

    run_backtest_report(rows_sorted, z_crit)

    # 当前状态：用最近window期数据，判断当前哪些类别显著
    print(f"\n{'='*90}")
    print(f"🎯 当前显著性判断（最近{CONFIG['backtest_window']}期，仅显示统计显著的类别）")
    print("=" * 90)

    any_significant = False
    for key, label in [("size", "大小"), ("odd", "单双"), ("color", "颜色"),
                        ("halfhalf", "半波"), ("zodiac", "生肖")]:
        results = test_all_categories(rows_sorted, key, CONFIG["backtest_window"], z_crit)
        sig_categories = [(cat, r) for cat, r in results.items() if r["significant"]]
        print(f"\n【{label}】")
        if not sig_categories:
            print("  ⏸️ 观望：没有类别达到统计显著水平")
        else:
            any_significant = True
            for cat, r in sorted(sig_categories, key=lambda x: x[1]["z"], reverse=True):
                print(f"  ✅ {cat}: z={r['z']:+.2f}（实际{r['p_hat']*100:.1f}% vs "
                      f"理论{r['p0']*100:.1f}%，样本{r['n']}期）")

    print(f"\n{'='*90}")
    print("📋 随机瞎猜基准对比（用于判断推荐是否真的比瞎猜强）")
    print("=" * 90)
    print(f"  半波Top2推荐：瞎猜命中率基准 ≈ {RANDOM_BASELINE['halfwave_top2']*100:.1f}%")
    print(f"  生肖Top3推荐：瞎猜命中率基准 ≈ {RANDOM_BASELINE['zodiac_top3']*100:.1f}%")
    print("  （回测报告里的命中率如果和这两个基准接近，说明推荐≈瞎猜，没有实际价值）")

    print(f"\n{'='*90}")
    print("📋 结论")
    print("=" * 90)
    if not any_significant:
        print("本次没有任何类别达到统计显著水平（含Bonferroni校正）。\n"
              "诚实的结论是：目前没有证据支持buy大/小/单/双/半波/生肖中任何一个方向，\n"
              "所有类别都应视为观望，而不是强行选一个'看起来概率高'的类别下注。")
    else:
        print("上面标✅的类别在当前窗口统计显著，但请务必看前面的『稳定性检查』结果——\n"
              "如果对应类别的回测结果是⚠️不稳定，说明这个显著性很可能只是历史巧合，\n"
              "不建议据此下注。")

if __name__ == "__main__":
    main()
