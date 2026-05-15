#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
澳门彩 · 特二色预测（修复回测起点）
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
    "transition_weight": 4.5,
    "miss_streak_bonus": 4.0, "miss_streak_threshold": 2,
    "state_unilateral_bonus": 2.0, "state_chaos_bonus": 2.5,
    "kill_same_color_streak": 3,
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
                # 按期号去重（保留最后一次出现的，即最新）
                unique = {}
                for r in rows:
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
    # 状态识别
    recent = train_colors[:15]
    freq = Counter(recent)
    top_ratio = freq.most_common(1)[0][1] / len(recent)
    if top_ratio >= 0.6:
        state = "单边"
    elif len(set(recent[:6])) >= 3:
        state = "混乱"
    else:
        state = "正常"

    use_miss = miss_streak >= params.get("miss_streak_threshold", 2)

    windows = [
        (params["short_window"], params["w_short"]),
        (params["mid_window"], params["w_mid"]),
        (params["long_window"], params["w_long"]),
    ]
    score = Counter()
    for w, wgt in windows:
        for c in train_colors[:w]:
            score[c] += wgt

    omission = {}
    for c in COLORS:
        miss = 0
        for x in train_colors:
            if x == c: break
            miss += 1
        omission[c] = miss
        score[c] += min(miss * params["omission_weight"], params["omission_cap"])

    # 转移矩阵
    last = train_colors[0]
    trans = defaultdict(Counter)
    for i in range(len(train_colors)-1):
        trans[train_colors[i]][train_colors[i+1]] += 1
    if last in trans:
        total = sum(trans[last].values())
        if total > 0:
            for c, v in trans[last].items():
                score[c] += (v/total) * params["transition_weight"]

    # 状态奖励
    if state == "单边":
        hottest = score.most_common(1)[0][0]
        score[hottest] += params["state_unilateral_bonus"]
    elif state == "混乱":
        coldest = max(omission, key=omission.get)
        score[coldest] += params["state_chaos_bonus"]

    # 连空保护
    if use_miss:
        cold_rank = sorted(omission.items(), key=lambda x: x[1], reverse=True)
        bonus = params["miss_streak_bonus"] * (1 + 0.2 * miss_streak)
        for c,_ in cold_rank[:2]:
            score[c] += bonus

    # 同色过滤
    kill_streak = params.get("kill_same_color_streak", 3)
    if kill_streak > 0:
        last_n = train_colors[:kill_streak]
        if len(last_n) == kill_streak and all(x == last_n[0] for x in last_n):
            banned = last_n[0]
            candidates = [c for c,_ in score.most_common() if c != banned]
            return candidates[:2]

    ranked = [c for c,_ in score.most_common()]
    return ranked[:2]

def backtest_with_details(colors, issues, params, lookback=10):
    """
    回测最后 lookback 期（离现在最近的 lookback 期）
    colors: 从早到晚的颜色列表
    issues: 从早到晚的期号列表
    """
    if len(colors) < 80 + lookback:
        return 0.0, 0, []
    # 转为最新在前
    rev_c = list(reversed(colors))
    rev_i = list(reversed(issues))
    total = lookback
    # 起始索引：从最后 total 期开始（注意：测试期是 rev_c[start] ... rev_c[-1]）
    start = len(rev_c) - total
    # 确保有足够历史数据（至少80期）
    if start < 80:
        start = 80
        total = len(rev_c) - start
    if total <= 0:
        return 0.0, 0, []

    hits = 0
    miss_streak = 0
    max_miss = 0
    details = []
    for i in range(start, len(rev_c)):
        # 训练数据：rev_c[0:i] 是 i 条最新数据（逆序），需要转换为从早到晚
        train = list(reversed(rev_c[:i]))
        actual = rev_c[i]
        pred = predict_two_colors(train, miss_streak, params)
        hit = actual in pred
        if hit:
            hits += 1
            miss_streak = 0
        else:
            miss_streak += 1
            max_miss = max(max_miss, miss_streak)
        details.append({
            "issue": rev_i[i],
            "actual": actual,
            "pred": pred,
            "hit": hit
        })
    hit_rate = hits / total if total > 0 else 0.0
    return hit_rate, max_miss, details

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
        "miss_streak_threshold": trial.suggest_int("miss_streak_threshold", 1, 3),
        "state_unilateral_bonus": trial.suggest_float("state_unilateral_bonus", 1.0, 4.0),
        "state_chaos_bonus": trial.suggest_float("state_chaos_bonus", 1.0, 4.0),
        "kill_same_color_streak": trial.suggest_int("kill_same_color_streak", 2, 5),
    }
    hr, max_miss, _ = backtest_with_details(colors, [""]*len(colors), params, lookback=100)
    return hr - max_miss * 0.015

def tune_params():
    try:
        import optuna
    except ImportError:
        print("请先安装 optuna: pip install optuna")
        return
    print("获取数据...")
    rows = fetch_macau_records(400)
    if not rows:
        print("失败")
        return
    colors = [get_color(r["special_number"]) for r in reversed(rows)]
    print("开始调参 (100 trials)...")
    study = optuna.create_study(direction="maximize")
    study.optimize(lambda t: objective(t, colors), n_trials=100, show_progress_bar=True)
    best = study.best_params
    for k,v in DEFAULT_PARAMS.items():
        if k not in best:
            best[k] = v
    with open(BEST_PARAMS_FILE,"w") as f:
        json.dump(best, f, indent=2, ensure_ascii=False)
    print("\n最佳参数:\n", json.dumps(best, indent=2, ensure_ascii=False))
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
    hr100, max100, _ = backtest_with_details(colors, issues, params, 100)

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
