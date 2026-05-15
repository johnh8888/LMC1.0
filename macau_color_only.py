#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
澳门彩 · 特二色预测（动态参数选择版）
- 每次预测前，用最近100期数据评估多组候选参数
- 自动选择近期命中率最高的参数组进行预测
- 输出预测结果及参数选择情况
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
    if n in RED: return "红"
    if n in BLUE: return "蓝"
    if n in GREEN: return "绿"
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
        if not t: continue
        try:
            n = int(t)
            if 1 <= n <= 49: out.append(n)
        except: pass
    return out


def fetch_macau_records(limit: int = 600) -> list:
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
                            if not m: continue
                            nums = parse_numbers(m.group(2))
                            if len(nums) < 7: continue
                            raw_issue = m.group(1)
                            issue_no = f"{raw_issue[2:4]}/{int(raw_issue[4:]):03d}"
                            rows.append({
                                "issue_no": issue_no,
                                "special_number": nums[6]
                            })
                # 去重
                unique = {}
                for r in rows:
                    if r["issue_no"] not in unique:
                        unique[r["issue_no"]] = r
                rows = list(unique.values())
                rows.sort(key=lambda x: x["issue_no"], reverse=True)
                return rows[:limit]
        except:
            continue
    return []


def predict_with_params(train_colors, miss_streak, params):
    """根据给定参数预测双色"""
    if not train_colors:
        return ["红", "蓝"]
    windows = [
        (params["short_window"], params["w_short"]),
        (params["mid_window"], params["w_mid"]),
        (params["long_window"], params["w_long"]),
    ]
    score = Counter()
    for w, wgt in windows:
        recent = train_colors[:w] if len(train_colors) >= w else train_colors
        for c in recent:
            score[c] += wgt

    omission = {}
    for c in COLORS:
        miss = 0
        for x in train_colors:
            if x == c: break
            miss += 1
        omission[c] = miss
        score[c] += min(miss * params["omission_weight"], params["omission_cap"])

    last = train_colors[0]
    trans = defaultdict(Counter)
    for i in range(len(train_colors)-1):
        trans[train_colors[i]][train_colors[i+1]] += 1
    if last in trans:
        total = sum(trans[last].values())
        if total > 0:
            for c, v in trans[last].items():
                score[c] += (v / total) * params["transition_weight"]

    if miss_streak >= 1:
        cold_rank = sorted(omission.items(), key=lambda x: x[1], reverse=True)
        for c, _ in cold_rank[:2]:
            score[c] += params["miss_streak_bonus"]

    ranked = [c for c, _ in score.most_common()]
    return ranked[:2]


def evaluate_params(colors, params, lookback=100):
    """评估一组参数在最近 lookback 期上的命中率（从第80期开始）"""
    if len(colors) < 80 + lookback:
        return 0.0
    rev = list(reversed(colors))
    total = min(lookback, len(rev)-80)
    if total <= 0:
        return 0.0
    hits = 0
    miss_streak = 0
    for i in range(80, 80+total):
        train = list(reversed(rev[:i]))
        actual = rev[i]
        pred = predict_with_params(train, miss_streak, params)
        if actual in pred:
            hits += 1
            miss_streak = 0
        else:
            miss_streak += 1
    return hits / total


def select_best_params(colors):
    """候选参数池，评估每个参数在最近100期的命中率，返回最优参数"""
    candidate_params = [
        # 短中长窗口及权重组合 (short, mid, long, w_short, w_mid, w_long, omission_weight, omission_cap, transition_weight, miss_streak_bonus)
        # 参数组1: 原版经验
        {"short_window": 12, "mid_window": 30, "long_window": 60,
         "w_short": 3.2, "w_mid": 1.4, "w_long": 0.8,
         "omission_weight": 0.65, "omission_cap": 6.0,
         "transition_weight": 4.5, "miss_streak_bonus": 4.0},
        # 参数组2: 更敏感短期
        {"short_window": 8, "mid_window": 20, "long_window": 50,
         "w_short": 4.5, "w_mid": 1.8, "w_long": 0.7,
         "omission_weight": 0.8, "omission_cap": 5.0,
         "transition_weight": 3.5, "miss_streak_bonus": 5.0},
        # 参数组3: 强近期
        {"short_window": 6, "mid_window": 15, "long_window": 40,
         "w_short": 5.5, "w_mid": 2.0, "w_long": 0.6,
         "omission_weight": 0.7, "omission_cap": 4.5,
         "transition_weight": 3.0, "miss_streak_bonus": 6.0},
        # 参数组4: 长期主导
        {"short_window": 10, "mid_window": 25, "long_window": 70,
         "w_short": 3.0, "w_mid": 1.2, "w_long": 0.9,
         "omission_weight": 0.9, "omission_cap": 7.0,
         "transition_weight": 4.0, "miss_streak_bonus": 3.5},
        # 参数组5: 热号侧重
        {"short_window": 5, "mid_window": 18, "long_window": 45,
         "w_short": 6.0, "w_mid": 2.2, "w_long": 0.5,
         "omission_weight": 0.6, "omission_cap": 4.0,
         "transition_weight": 2.8, "miss_streak_bonus": 5.5},
    ]
    best = None
    best_hr = -1.0
    for params in candidate_params:
        hr = evaluate_params(colors, params, lookback=100)
        if hr > best_hr:
            best_hr = hr
            best = params
    return best, best_hr


def main():
    print("获取澳门彩数据...")
    rows = fetch_macau_records(600)
    if not rows:
        print("数据获取失败")
        return

    # 颜色历史（从早到晚）
    color_history = [get_color(r["special_number"]) for r in rows]
    color_history.reverse()

    # 动态选择最佳参数
    print("正在评估候选参数（最近100期表现）...")
    best_params, best_hr = select_best_params(color_history)
    print(f"最优参数命中率: {best_hr:.1%}")

    # 使用最佳参数预测下一期
    pred = predict_with_params(color_history, miss_streak=0, params=best_params)

    latest_issue = rows[0]["issue_no"]
    pred_issue = next_issue(latest_issue)

    print("\n========== 澳门彩 · 特二色预测 ==========")
    print(f"预测期号：{pred_issue}")
    print(f"预测二色：{'、'.join(pred)}")
    print("=========================================")
    # 可选：显示当前选中的参数
    print(f"\n当前使用参数: short={best_params['short_window']}, mid={best_params['mid_window']}, long={best_params['long_window']}")
    print(f"权重: {best_params['w_short']:.1f}, {best_params['w_mid']:.1f}, {best_params['w_long']:.1f}")


if __name__ == "__main__":
    main()
