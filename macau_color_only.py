#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
澳门彩 · 特二色预测（增强近期适应性版）
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

# 默认参数（针对近期优化）
DEFAULT_PARAMS = {
    "short_window": 8,      # 缩小短窗口
    "mid_window": 20,
    "long_window": 50,
    "w_short": 4.0,
    "w_mid": 1.2,
    "w_long": 0.5,
    "omission_weight": 0.8,
    "omission_cap": 5.0,
    "transition_weight": 3.0,
    "miss_streak_bonus": 5.0,
    "miss_streak_threshold": 1,   # 连空1期就奖励冷色
    "state_unilateral_bonus": 2.0,
    "state_chaos_bonus": 2.5,
    "kill_same_color_streak": 3,
    "recent_boost": 1.5,          # 新增：最近N期权重倍率
    "recent_boost_window": 5,     # 最近5期加权
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

    use_miss = miss_streak >= params.get("miss_streak_threshold", 1)

    windows = [
        (params["short_window"], params["w_short"]),
        (params["mid_window"], params["w_mid"]),
        (params["long_window"], params["w_long"]),
    ]
    score = Counter()
    recent_boost_window = params.get("recent_boost_window", 5)
    recent_boost_factor = params.get("recent_boost", 1.5)

    for w, wgt in windows:
        for i, c in enumerate(train_colors[:w]):
            # 基础权重
            weight = wgt
            # 对最近的 recent_boost_window 期增加权重
            if i < recent_boost_window:
                weight *= recent_boost_factor
            score[c] += weight

    # 遗漏计算
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
    """测试最后 lookback 期（最近N期）"""
    if len(colors) < 80 + lookback:
        return 0.0, 0, []
    test_indices = list(range(len(colors) - lookback, len(colors)))
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
    return hits / lookback, max_miss, details

def objective(trial, colors):
    import optuna
    params = {
        "short_window": trial.suggest_int("short_window", 4, 12),
        "mid_window": trial.suggest_int("mid_window", 15, 35),
        "long_window": trial.suggest_int("long_window", 40, 70),
        "w_short": trial.suggest_float("w_short", 2.0, 6.0),
        "w_mid": trial.suggest_float("w_mid", 0.8, 2.5),
        "w_long": trial.suggest_float("w_long", 0.3, 1.5),
        "omission_weight": trial.suggest_float("omission_weight", 0.5, 1.2),
        "omission_cap": trial.suggest_float("omission_cap", 3.0, 7.0),
        "transition_weight": trial.suggest_float("transition_weight", 2.0, 6.0),
        "miss_streak_bonus": trial.suggest_float("miss_streak_bonus", 3.0, 8.0),
        "miss_streak_threshold": trial.suggest_int("miss_streak_threshold", 1, 2),
        "state_unilateral_bonus": trial.suggest_float("state_unilateral_bonus", 1.0, 3.5),
        "state_chaos_bonus": trial.suggest_float("state_chaos_bonus", 1.0, 3.5),
        "kill_same_color_streak": trial.suggest_int("kill_same_color_streak", 2, 4),
        "recent_boost": trial.suggest_float("recent_boost", 1.2, 2.0),
        "recent_boost_window": trial.suggest_int("recent_boost_window", 3, 8),
    }
    # 回测最近100期，评分 = 命中率 - 最大连空 * 0.01（降低连空惩罚，鼓励命中率）
    hr, max_miss, _ = backtest_with_details(colors, [""]*len(colors), params, lookback=100)
    return hr - max_miss * 0.01

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
    print("开始调参 (200 trials)...")
    study = optuna.create_study(direction="maximize")
    study.optimize(lambda t: objective(t, colors), n_trials=200, show_progress_bar=True)
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
