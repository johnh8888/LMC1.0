#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Macau Zodiac Projection V51
科研级 · 波色/大小单双/野兽家禽 → 特五生肖 投影系统

功能：
- 波色特征
- 大小单双特征
- 野兽家禽特征
- Markov 转移
- 遗漏周期
- 生肖概率投影
- 特五生肖推荐
- Kelly 资金管理
- Walk Forward 回测

用于 GitHub Actions 手动运行，输出 result.md 报告。
"""

import json
import math
import random
import re
import statistics
import time
from collections import Counter, defaultdict

import requests

API_URL = "https://marksix6.net/index.php?api=1"

# =========================
# 波色
# =========================
RED = {1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE = {3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
GREEN = {5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}

# =========================
# 生肖映射（马为1）
# =========================
ZODIAC_ORDER = ["马","羊","猴","鸡","狗","猪","鼠","牛","虎","兔","龙","蛇"]

NUM_TO_ZODIAC = {}
for n in range(1, 50):
    NUM_TO_ZODIAC[n] = ZODIAC_ORDER[(n - 1) % 12]

FOWL = {"牛","马","羊","鸡","狗","猪"}
BEAST = {"鼠","虎","兔","龙","蛇","猴"}

ZODIACS = list(set(NUM_TO_ZODIAC.values()))

# =========================
# 参数
# =========================
CONFIG = {
    "bankroll": 10000,
    "train_len": 300,
    "lookback": 200,
    "kelly": 0.25,
    "top_n": 5,
}

# =========================
# 基础函数
# =========================
def get_color(n):
    if n in RED:
        return "红"
    if n in BLUE:
        return "蓝"
    return "绿"

def get_size(n):
    return "大" if n >= 25 else "小"

def get_odd_even(n):
    return "单" if n % 2 else "双"

def get_szsd(n):
    return f"{get_size(n)}{get_odd_even(n)}"

def get_zodiac(n):
    return NUM_TO_ZODIAC[n]

def get_beast(n):
    z = get_zodiac(n)
    return "野兽" if z in BEAST else "家禽"

# =========================
# 获取数据 (改用 requests)
# =========================
def fetch(limit=800):
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    # requests 自动处理 gzip
    resp = requests.get(API_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    rows = []

    for item in data.get("lottery_data", []):
        if "澳门" not in item.get("name", ""):
            continue

        for line in item.get("history", []):
            m = re.search(r"(\\d{7})\\s*期[：:]\\s*([\\d，,\\s]+)", line)

            if not m:
                continue

            nums = [int(x) for x in re.findall(r"\\d+", m.group(2))]

            if len(nums) < 7:
                continue

            issue = m.group(1)
            special = nums[-1]

            rows.append({
                "issue": issue,
                "special": special,
                "zodiac": get_zodiac(special),
                "color": get_color(special),
                "szsd": get_szsd(special),
                "beast": get_beast(special),
            })

    rows = sorted(rows, key=lambda x: x["issue"], reverse=True)
    return rows[:limit]

# =========================
# 转移矩阵
# =========================
def build_transition(seq):
    trans = defaultdict(Counter)
    for i in range(len(seq)-1):
        trans[seq[i]][seq[i+1]] += 1
    return trans

# =========================
# 生肖概率投影
# =========================
def project_zodiac(train):
    colors = [x["color"] for x in train]
    szsds = [x["szsd"] for x in train]
    beasts = [x["beast"] for x in train]
    zodiacs = [x["zodiac"] for x in train]

    color_trans = build_transition(colors)
    szsd_trans = build_transition(szsds)
    beast_trans = build_transition(beasts)
    zodiac_trans = build_transition(zodiacs)

    last_color = colors[0]
    last_szsd = szsds[0]
    last_beast = beasts[0]
    last_zodiac = zodiacs[0]

    zodiac_score = defaultdict(float)

    # 1. 生肖遗漏
    for z in ZODIACS:
        omission = next((i for i, x in enumerate(zodiacs) if x == z), len(zodiacs))
        zodiac_score[z] += omission * 0.9

    # 2. 波色投影
    if last_color in color_trans:
        total = sum(color_trans[last_color].values())
        for nxt, v in color_trans[last_color].items():
            p = v / total
            for z in ZODIACS:
                nums = [n for n in range(1,50) if get_zodiac(n)==z]
                if any(get_color(n)==nxt for n in nums):
                    zodiac_score[z] += p * 8

    # 3. 大小单双投影
    if last_szsd in szsd_trans:
        total = sum(szsd_trans[last_szsd].values())
        for nxt, v in szsd_trans[last_szsd].items():
            p = v / total
            for z in ZODIACS:
                nums = [n for n in range(1,50) if get_zodiac(n)==z]
                if any(get_szsd(n)==nxt for n in nums):
                    zodiac_score[z] += p * 6

    # 4. 野兽家禽投影
    if last_beast in beast_trans:
        total = sum(beast_trans[last_beast].values())
        for nxt, v in beast_trans[last_beast].items():
            p = v / total
            for z in ZODIACS:
                if ("野兽" if z in BEAST else "家禽") == nxt:
                    zodiac_score[z] += p * 5

    # 5. 生肖 Markov
    if last_zodiac in zodiac_trans:
        total = sum(zodiac_trans[last_zodiac].values())
        for z, v in zodiac_trans[last_zodiac].items():
            zodiac_score[z] += (v / total) * 12

    ranked = sorted(zodiac_score.items(), key=lambda x: x[1], reverse=True)
    return ranked

# =========================
# Kelly
# =========================
def kelly(p, odds=2.2):
    b = odds - 1
    q = 1 - p
    k = (b*p - q) / b if b != 0 else 0
    return max(0, min(k * CONFIG["kelly"], 0.25))

# =========================
# 回测
# =========================
def backtest(rows):
    hits = 0
    miss = 0
    max_miss = 0
    bankroll = CONFIG["bankroll"]
    curve = []

    for i in range(CONFIG["lookback"]):
        actual = rows[i]["zodiac"]
        hist = rows[i+1:i+1+CONFIG["train_len"]]

        if len(hist) < 100:
            continue

        ranked = project_zodiac(hist)
        pred = [x[0] for x in ranked[:CONFIG["top_n"]]]

        top_score = ranked[0][1]
        total_score = sum(x[1] for x in ranked[:5])
        p = top_score / total_score if total_score else 0.5
        stake_ratio = kelly(p)
        stake = bankroll * stake_ratio

        if actual in pred:
            hits += 1
            miss = 0
            bankroll += stake * 1.2
        else:
            miss += 1
            max_miss = max(max_miss, miss)
            bankroll -= stake

        curve.append(bankroll)

    hit_rate = hits / CONFIG["lookback"] if CONFIG["lookback"] else 0
    ret = (bankroll - CONFIG["bankroll"]) / CONFIG["bankroll"] * 100

    # 计算夏普
    sharpe = None
    if len(curve) > 2:
        returns = []
        for i in range(1, len(curve)):
            r = (curve[i] - curve[i-1]) / curve[i-1]
            returns.append(r)
        if statistics.pstdev(returns) > 0:
            sharpe = (statistics.mean(returns) / statistics.pstdev(returns)) * math.sqrt(252)

    return hit_rate, max_miss, ret, curve, sharpe

# =========================
# 主程序
# =========================
def main():
    print("="*60)
    print("Macau Zodiac Projection V51")
    print("="*60)

    # 拉取数据
    rows = fetch(800)
    if len(rows) < 400:
        print("数据不足，退出")
        return

    latest = rows[0]
    train = rows[:CONFIG["train_len"]]
    ranked = project_zodiac(train)
    top5 = ranked[:5]

    print(f"\n预测期：{latest['issue']}")
    print("\n推荐特五生肖：")
    for i, (z, s) in enumerate(top5, 1):
        print(f"{i}. {z:<2}  得分={s:.2f}")

    print("\n完整排名：")
    for z, s in ranked:
        print(f"{z:<2}  {s:.2f}")

    print("\n开始回测...\n")
    hr, mm, ret, curve, sharpe = backtest(rows)

    print(f"命中率: {hr:.1%}")
    print(f"最大连空: {mm}")
    print(f"模拟收益: {ret:+.1f}%")

    if curve:
        peak = max(curve)
        trough = min(curve)
        mdd = (peak - trough) / peak * 100
        print(f"最大回撤: {mdd:.1f}%")
    else:
        mdd = None

    if sharpe is not None:
        print(f"Sharpe Ratio: {sharpe:.2f}")

    # ---- 生成 Markdown 报告 ----
    with open("result.md", "w", encoding="utf-8") as f:
        f.write(f"# Macau Zodiac Projection V51\n\n")
        f.write(f"**预测期**：{latest['issue']}\n\n")
        f.write("## 推荐特五生肖\n\n")
        f.write("| 排名 | 生肖 | 得分 |\n")
        f.write("|------|------|------|\n")
        for i, (z, s) in enumerate(top5, 1):
            f.write(f"| {i} | {z} | {s:.2f} |\n")

        f.write("\n## 完整排名\n\n")
        f.write("| 生肖 | 得分 |\n")
        f.write("|------|------|\n")
        for z, s in ranked:
            f.write(f"| {z} | {s:.2f} |\n")

        f.write("\n## 回测结果\n\n")
        f.write(f"- 命中率: {hr:.1%}\n")
        f.write(f"- 最大连空: {mm}\n")
        f.write(f"- 模拟收益: {ret:+.1f}%\n")
        if mdd is not None:
            f.write(f"- 最大回撤: {mdd:.1f}%\n")
        if sharpe is not None:
            f.write(f"- 夏普比率: {sharpe:.2f}\n")

    print("\n✅ 报告已保存到 result.md")

if __name__ == "__main__":
    main()