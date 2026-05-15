#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
澳门彩 · 特二色预测（带简要回测）
- 获取澳门彩历史数据
- 预测下一期特码二色
- 显示最近10期、最近100期的命中率与最大连空
"""

import gzip
import json
import re
import urllib.request
from collections import Counter, defaultdict

# ========== 波色映射 ==========
RED = {1, 2, 7, 8, 12, 13, 18, 19, 23, 24, 29, 30, 34, 35, 40, 45, 46}
BLUE = {3, 4, 9, 10, 14, 15, 20, 25, 26, 31, 36, 37, 41, 42, 47, 48}
GREEN = {5, 6, 11, 16, 17, 21, 22, 27, 28, 32, 33, 38, 39, 43, 44, 49}
COLORS = ["红", "蓝", "绿"]


def get_color(n: int) -> str:
    if n in RED:
        return "红"
    if n in BLUE:
        return "蓝"
    if n in GREEN:
        return "绿"
    return "红"


def next_issue(issue_no: str) -> str:
    try:
        year, seq = issue_no.split('/')
        return f"{year}/{str(int(seq) + 1).zfill(3)}"
    except:
        return issue_no


def parse_numbers(value: str) -> list:
    out = []
    for t in re.split(r"[，,]", value):
        t = t.strip()
        if not t:
            continue
        try:
            n = int(t)
            if 1 <= n <= 49:
                out.append(n)
        except:
            pass
    return out


def fetch_macau_records(limit: int = 300) -> list:
    """只获取澳门彩（非新澳门）"""
    url = "https://marksix6.net/index.php?api=1"
    headers = {"User-Agent": "Mozilla/5.0"}

    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
                if "gzip" in resp.headers.get("Content-Encoding", "").lower():
                    raw = gzip.decompress(raw)
                data = json.loads(raw.decode("utf-8"))

                rows = []
                for item in data.get("lottery_data", []):
                    name = item.get("name", "")
                    if "澳门彩" in name and "新" not in name:
                        for line in item.get("history", []):
                            m = re.match(r"(\d{7})\s*期[：:]\s*([\d,，]+)", line)
                            if not m:
                                continue
                            nums = parse_numbers(m.group(2))
                            if len(nums) < 7:
                                continue
                            raw_issue = m.group(1)
                            issue_no = f"{raw_issue[2:4]}/{int(raw_issue[4:]):03d}"
                            rows.append({
                                "issue_no": issue_no,
                                "numbers": nums[:6],
                                "special_number": nums[6]
                            })
                rows.sort(key=lambda x: x["issue_no"], reverse=True)
                return rows[:limit]
        except Exception:
            continue
    return []


def predict_two_colors(train_colors: list, miss_streak: int = 0) -> list:
    """
    预测双色，支持连空保护
    """
    if not train_colors:
        return ["红", "蓝"]

    windows = [(12, 3.2), (30, 1.4), (60, 0.8)]
    omission_weight = 0.65
    omission_cap = 6.0
    transition_weight = 4.5
    miss_streak_bonus = 4.0

    score = Counter()
    for w, wgt in windows:
        recent = train_colors[:w]
        for c in recent:
            score[c] += wgt

    omission = {}
    for c in COLORS:
        miss = 0
        for x in train_colors:
            if x == c:
                break
            miss += 1
        omission[c] = miss
        score[c] += min(miss * omission_weight, omission_cap)

    last = train_colors[0]
    trans = defaultdict(Counter)
    for i in range(len(train_colors) - 1):
        cur = train_colors[i]
        nxt = train_colors[i + 1]
        trans[cur][nxt] += 1
    if last in trans:
        total = sum(trans[last].values())
        if total > 0:
            for c, v in trans[last].items():
                score[c] += (v / total) * transition_weight

    # 连空保护：如果连空≥1，奖励最冷的两个颜色
    if miss_streak >= 1:
        cold_rank = sorted(omission.items(), key=lambda x: x[1], reverse=True)
        for c, _ in cold_rank[:2]:
            score[c] += miss_streak_bonus

    ranked = [c for c, _ in score.most_common()]
    return ranked[:2]


def backtest(colors: list, dual: bool = True, lookback: int = 100) -> tuple:
    """
    回测，返回 (命中率, 最大连空)
    colors: 颜色历史列表（从早到晚）
    """
    if len(colors) < 80 + lookback:
        return 0.0, 0

    rev = list(reversed(colors))   # 最新在前
    total = min(lookback, len(rev) - 80)
    if total <= 0:
        return 0.0, 0

    hits = 0
    miss_streak = 0
    max_miss = 0

    for i in range(80, 80 + total):
        train = list(reversed(rev[:i]))
        actual = rev[i]
        pred = predict_two_colors(train, miss_streak)
        if actual in pred:
            hits += 1
            miss_streak = 0
        else:
            miss_streak += 1
            max_miss = max(max_miss, miss_streak)

    return hits / total, max_miss


def main():
    print("正在获取澳门彩数据...")
    rows = fetch_macau_records(300)
    if not rows:
        print("数据获取失败")
        return

    # 颜色历史（从早到晚）
    color_history = [get_color(r["special_number"]) for r in rows]
    color_history.reverse()   # 现在从早到晚

    # 最近300期的预测（需要当前 miss_streak=0 做预测）
    pred = predict_two_colors(color_history, miss_streak=0)

    latest_issue = rows[0]["issue_no"]
    pred_issue = next_issue(latest_issue)

    # 回测
    hr10, max_miss10 = backtest(color_history, lookback=10)
    hr100, max_miss100 = backtest(color_history, lookback=100)

    print("\n========== 澳门彩 · 特二色预测 ==========")
    print(f"预测期号：{pred_issue}")
    print(f"预测二色：{'、'.join(pred)}")
    print("=========================================")
    print(f"\n最近10期命中率：{hr10:.1%}，最大连空：{max_miss10}")
    print(f"最近100期命中率：{hr100:.1%}，最大连空：{max_miss100}")


if __name__ == "__main__":
    main()
