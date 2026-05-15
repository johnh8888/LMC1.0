#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
澳门彩 · 特二色预测（带回测与自动调参，增加最近10期详情）
用法:
    python macau_color_only.py              # 正常预测（使用已有最佳参数）
    python macau_color_only.py --tune       # 运行 Optuna 调参（生成 best_params_macau.json）
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
    "short_window": 12, "mid_window": 30, "long_window": 60,
    "w_short": 3.2, "w_mid": 1.4, "w_long": 0.8,
    "omission_weight": 0.65, "omission_cap": 6.0,
    "transition_weight": 4.5, "miss_streak_bonus": 4.0,
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
    windows = [
        (params["short_window"], params["w_short"]),
        (params["mid_window"], params["w_mid"]),
        (params["long_window"], params["w_long"]),
    ]
    score = Counter()
    for w, wgt in windows:
        recent = train_colors[:w]
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
                score[c] += (v/total) * params["transition_weight"]

    if miss_streak >= 1:
        cold_rank = sorted(omission.items(), key=lambda x: x[1], reverse=True)
        for c,_ in cold_rank[:2]:
            score[c] += params["miss_streak_bonus"]

    ranked = [c for c,_ in score.most_common()]
    return ranked[:2]

def backtest_with_details(colors, issues, params, lookback=10):
    """回测最近 lookback 期，返回 (命中率, 最大连空, 详情列表)"""
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
        "short_window": trial.suggest_int("short_window", 6, 20),
        "mid_window": trial.suggest_int("mid_window", 15, 50),
        "long_window": trial.suggest_int("long_window", 40, 90),
        "w_short": trial.suggest_float("w_short", 1.0, 6.0),
        "w_mid": trial.suggest_float("w_mid", 0.5, 3.0),
        "w_long": trial.suggest_float("w_long", 0.2, 2.0),
        "omission_weight": trial.suggest_float("omission_weight", 0.2, 1.5),
        "omission_cap": trial.suggest_float("omission_cap", 2.0, 10.0),
        "transition_weight": trial.suggest_float("transition_weight", 1.0, 8.0),
        "miss_streak_bonus": trial.suggest_float("miss_streak_bonus", 1.0, 8.0),
    }
    hr, max_miss = backtest(colors, params, 100)
    return hr - max_miss * 0.015

def tune_params():
    try:
        import optuna
    except ImportError:
        print("请先安装 optuna: pip install optuna")
        return
    print("获取数据用于调参...")
    rows = fetch_macau_records(400)
    if not rows:
        print("失败")
        return
    colors = [get_color(r["special_number"]) for r in reversed(rows)]
    print("开始 Optuna 调参 (150 trials)...")
    study = optuna.create_study(direction="maximize")
    study.optimize(lambda t: objective(t, colors), n_trials=150, show_progress_bar=True)
    best = study.best_params
    for k,v in DEFAULT_PARAMS.items():
        if k not in best:
            best[k] = v
    with open(BEST_PARAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(best, f, indent=2, ensure_ascii=False)
    print("\n最佳参数:\n", json.dumps(best, indent=2, ensure_ascii=False))
    print(f"评分: {study.best_value:.4f} -> 保存到 {BEST_PARAMS_FILE}")

def load_params():
    if os.path.exists(BEST_PARAMS_FILE):
        try:
            with open(BEST_PARAMS_FILE, encoding="utf-8") as f:
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
    rows = fetch_macau_records(400)
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
    print("\n===== 最近10期详情（由旧到新） =====")
    for d in details:
        mark = "✓" if d["hit"] else "✗"
        print(f"{d['issue']:<10} 实际:{d['actual']}  预测:{'、'.join(d['pred']):<5} {mark}")

if __name__ == "__main__":
    main()
