#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
澳门彩 · 特二色预测（冲击75%+命中率版）
- 强制包含最近7期内出现次数≥2的所有颜色
- 提高近期权重，优化调参目标
"""

import argparse
import gzip
import json
import re
import urllib.request
from collections import Counter, defaultdict
import os

RED = {1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE = {3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
GREEN = {5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}
COLORS = ["红","蓝","绿"]

DEFAULT_PARAMS = {
    "short_window": 5,
    "mid_window": 18,
    "long_window": 45,
    "w_short": 5.0,
    "w_mid": 1.8,
    "w_long": 0.7,
    "omission_weight": 0.6,
    "omission_cap": 4.0,
    "transition_weight": 3.5,
    "miss_streak_bonus": 3.0,
    "recent_boost": 3.5,
    "recent_window": 3,
    "streak_bonus": 1.8,
}
BEST_PARAMS_FILE = "best_params_macau.json"

def get_color(n):
    if n in RED: return "红"
    if n in BLUE: return "蓝"
    if n in GREEN: return "绿"
    return "红"

def next_issue(issue_no):
    try:
        y,s = issue_no.split('/')
        return f"{y}/{str(int(s)+1).zfill(3)}"
    except:
        return issue_no

def parse_numbers(value):
    out = []
    for t in re.split(r"[，,]", value):
        t = t.strip()
        if not t: continue
        try:
            n = int(t)
            if 1<=n<=49: out.append(n)
        except: pass
    return out

def fetch_macau_records(limit=600):
    url = "https://marksix6.net/index.php?api=1"
    headers = {"User-Agent":"Mozilla/5.0"}
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
                if "gzip" in resp.headers.get("Content-Encoding","").lower():
                    raw = gzip.decompress(raw)
                data = json.loads(raw.decode("utf-8"))
                rows = []
                for item in data.get("lottery_data",[]):
                    if "澳门彩" in item.get("name","") and "新" not in item.get("name",""):
                        for line in item.get("history",[]):
                            m = re.match(r"(\d{7})\s*期[：:]\s*([\d,，]+)", line)
                            if not m: continue
                            nums = parse_numbers(m.group(2))
                            if len(nums) < 7: continue
                            raw_issue = m.group(1)
                            issue_no = f"{raw_issue[2:4]}/{int(raw_issue[4:]):03d}"
                            rows.append({
                                "issue_no": issue_no,
                                "numbers": nums[:6],
                                "special_number": nums[6]
                            })
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

def predict_two_colors(train_colors, miss_streak, params):
    if not train_colors:
        return ["红","蓝"]

    # --- 热号强制：最近7期内出现次数≥2的所有颜色（最多两个）---
    recent_window_hot = 7
    recent = train_colors[-recent_window_hot:] if len(train_colors) >= recent_window_hot else train_colors
    hot_colors = []
    if len(recent) >= 3:
        freq = Counter(recent)
        for c, cnt in freq.most_common():
            if cnt >= 2 and len(hot_colors) < 2:
                hot_colors.append(c)

    # --- 多窗口加权得分 ---
    windows = [
        (params["short_window"], params["w_short"]),
        (params["mid_window"], params["w_mid"]),
        (params["long_window"], params["w_long"]),
    ]
    score = Counter()
    recent_boost = params.get("recent_boost", 1.0)
    boost_window = params.get("recent_window", 5)

    for w, wgt in windows:
        recent_w = train_colors[-w:] if len(train_colors) >= w else train_colors
        for i, c in enumerate(recent_w):
            weight = wgt
            if i < boost_window:
                weight *= recent_boost
            score[c] += weight

    # --- 遗漏加分 ---
    omission = {}
    for c in COLORS:
        miss = 0
        for x in reversed(train_colors):
            if x == c: break
            miss += 1
        omission[c] = miss
        score[c] += min(miss * params["omission_weight"], params["omission_cap"])

    # --- 转移矩阵 ---
    last = train_colors[-1] if train_colors else None
    trans = defaultdict(Counter)
    for i in range(len(train_colors)-1):
        trans[train_colors[i]][train_colors[i+1]] += 1
    if last and last in trans:
        total = sum(trans[last].values())
        if total > 0:
            for c, v in trans[last].items():
                score[c] += (v/total) * params["transition_weight"]

    # --- 连续状态奖励 ---
    if len(train_colors) >= 2 and train_colors[-1] == train_colors[-2]:
        score[train_colors[-1]] += params.get("streak_bonus", 1.5)

    # --- 连空保护（miss_streak>=1时奖励最冷两色）---
    if miss_streak >= 1:
        cold_rank = sorted(omission.items(), key=lambda x: x[1], reverse=True)
        for c,_ in cold_rank[:2]:
            score[c] += params["miss_streak_bonus"]

    ranked = [c for c,_ in score.most_common()]
    pred = ranked[:2]

    # --- 强制包含所有热号（按顺序替换，最多两个）---
    for hot in hot_colors:
        if hot not in pred:
            pred[-1] = hot
            # 去重
            if pred[0] == pred[1]:
                for c in ranked:
                    if c not in pred:
                        pred[1] = c
                        break
    return pred

def backtest_with_details(colors, issues, params, lookback=10):
    if len(colors) < 80 + lookback:
        return 0.0, 0, []
    test_indices = list(range(len(colors)-lookback, len(colors)))
    hits = 0
    miss_streak = 0
    max_miss = 0
    details = []
    for idx in test_indices:
        train = colors[:idx]
        actual = colors[idx]
        pred = predict_two_colors(train, miss_streak, params)
        hit = actual in pred
        if hit:
            hits += 1
            miss_streak = 0
        else:
            miss_streak += 1
            max_miss = max(max_miss, miss_streak)
        details.append({
            "issue": issues[idx],
            "actual": actual,
            "pred": pred,
            "hit": hit
        })
    return hits/lookback, max_miss, details

def backtest(colors, params, lookback=100):
    if len(colors) < 80 + lookback:
        return 0.0, 0
    rev = list(reversed(colors))
    total = min(lookback, len(rev)-80)
    hits = 0
    miss_streak = 0
    max_miss = 0
    for i in range(80, 80+total):
        train = list(reversed(rev[:i]))
        actual = rev[i]
        pred = predict_two_colors(train, miss_streak, params)
        if actual in pred:
            hits += 1
            miss_streak = 0
        else:
            miss_streak += 1
            max_miss = max(max_miss, miss_streak)
    return hits/total, max_miss

def objective(trial, colors):
    import optuna
    params = {
        "short_window": trial.suggest_int("short_window", 3, 10),
        "mid_window": trial.suggest_int("mid_window", 10, 30),
        "long_window": trial.suggest_int("long_window", 25, 60),
        "w_short": trial.suggest_float("w_short", 3.0, 7.0),
        "w_mid": trial.suggest_float("w_mid", 1.0, 3.0),
        "w_long": trial.suggest_float("w_long", 0.3, 1.5),
        "omission_weight": trial.suggest_float("omission_weight", 0.4, 1.0),
        "omission_cap": trial.suggest_float("omission_cap", 2.0, 6.0),
        "transition_weight": trial.suggest_float("transition_weight", 2.0, 6.0),
        "miss_streak_bonus": trial.suggest_float("miss_streak_bonus", 2.0, 5.0),
        "recent_boost": trial.suggest_float("recent_boost", 2.0, 5.0),
        "recent_window": trial.suggest_int("recent_window", 2, 5),
        "streak_bonus": trial.suggest_float("streak_bonus", 1.0, 3.0),
    }
    hr, max_miss = backtest(colors, params, 100)
    # 目标：命中率 - 极小的连空惩罚，侧重命中率
    return hr - max_miss * 0.002

def tune_params():
    try:
        import optuna
    except ImportError:
        print("请先安装 optuna: pip install optuna")
        return
    print("获取数据用于调参...")
    rows = fetch_macau_records(600)
    if not rows:
        print("数据获取失败")
        return
    colors = [get_color(r["special_number"]) for r in reversed(rows)]
    print("开始 Optuna 调参 (300 trials，目标近期命中率)...")
    study = optuna.create_study(direction="maximize")
    study.optimize(lambda t: objective(t, colors), n_trials=300, show_progress_bar=True)
    best = study.best_params
    for k,v in DEFAULT_PARAMS.items():
        if k not in best:
            best[k] = v
    with open(BEST_PARAMS_FILE, "w") as f:
        json.dump(best, f, indent=2)
    print("\n最佳参数:\n", json.dumps(best, indent=2))
    print(f"评分: {study.best_value:.4f} -> 保存到 {BEST_PARAMS_FILE}")

def load_params():
    if os.path.exists(BEST_PARAMS_FILE):
        try:
            with open(BEST_PARAMS_FILE) as f:
                p = json.load(f)
            for k,v in DEFAULT_PARAMS.items():
                p.setdefault(k, v)
            return p
        except:
            pass
    return DEFAULT_PARAMS.copy()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tune", action="store_true")
    args = parser.parse_args()
    if args.tune:
        tune_params()
        return

    print("获取澳门彩数据...")
    rows = fetch_macau_records(600)
    if not rows:
        print("失败")
        return
    rows_rev = list(reversed(rows))
    colors = [get_color(r["special_number"]) for r in rows_rev]
    issues = [r["issue_no"] for r in rows_rev]
    params = load_params()

    pred = predict_two_colors(colors, miss_streak=0, params=params)
    latest_issue = rows[0]["issue_no"]
    pred_issue = next_issue(latest_issue)

    hr10, max10, details = backtest_with_details(colors, issues, params, 10)
    hr100, max100 = backtest(colors, params, 100)

    print("\n========== 澳门彩 · 特二色预测 ==========")
    print(f"预测期号：{pred_issue}")
    print(f"预测二色：{'、'.join(pred)}")
    print("=========================================")
    print(f"\n最近10期命中率：{hr10:.1%}，最大连空：{max10}")
    print(f"最近100期命中率：{hr100:.1%}，最大连空：{max100}")
    print("\n===== 最近10期详情 =====")
    for d in details:
        mark = "✓" if d["hit"] else "✗"
        print(f"{d['issue']:<10} 实际:{d['actual']}  预测:{'、'.join(d['pred']):<5} {mark}")

if __name__ == "__main__":
    main()
