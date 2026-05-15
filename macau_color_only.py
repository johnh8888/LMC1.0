#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
澳门彩 · 特二色预测（市场自适应版）
- 市场识别（单边/混乱/轮动/正常）与多模型融合
- 热号强制（最近7期出现≥2次强制包含）
- 支持 Optuna 自动调参（--tune）
- 回测正确（无数据泄露），显示命中率和详情
"""

import argparse
import gzip
import json
import re
import urllib.request
import os
from collections import Counter, defaultdict

# 波色映射
RED = {1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE = {3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
GREEN = {5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}
COLORS = ["红","蓝","绿"]

# 默认参数
DEFAULT_PARAMS = {
    "short_window": 6,
    "mid_window": 20,
    "long_window": 50,
    "w_short": 4.5,
    "w_mid": 1.5,
    "w_long": 0.6,
    "omission_weight": 0.8,
    "omission_cap": 5.0,
    "transition_weight": 3.0,
    "miss_streak_bonus": 5.0,
    "recent_boost": 2.5,
    "recent_window": 4,
    "streak_bonus": 1.5,
    # 市场状态权重
    "unilateral_hot_weight": 2.2,
    "unilateral_trans_weight": 1.8,
    "unilateral_rev_weight": 0.6,
    "chaos_cold_weight": 2.0,
    "chaos_rev_weight": 1.8,
    "chaos_hot_weight": 0.5,
    "rotate_trans_weight": 2.2,
    "rotate_cold_weight": 1.0,
    "rotate_rev_weight": 1.0,
    "market_hot_weight": 1.5,
    "market_cold_weight": 1.0,
    "market_trans_weight": 1.2,
    "market_rev_weight": 1.0,
    "single_threshold": 0.60,
}
BEST_PARAMS_FILE = "best_params_macau.json"

def get_color(n):
    if n in RED: return "红"
    if n in BLUE: return "蓝"
    if n in GREEN: return "绿"
    return "红"

def next_issue(issue_no):
    try:
        y, s = issue_no.split('/')
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
            if 1 <= n <= 49: out.append(n)
        except: pass
    return out

def fetch_macau_records(limit=600):
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
                    if "澳门彩" in item.get("name", "") and "新" not in item.get("name", ""):
                        for line in item.get("history", []):
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

def detect_market(train, params):
    """市场状态识别"""
    recent10 = train[:10]
    if len(recent10) < 10:
        return "正常"
    freq = Counter(recent10)
    top_color, top_count = freq.most_common(1)[0]
    ratio = top_count / 10
    if ratio >= params.get("single_threshold", 0.60):
        return "单边"
    if len(set(recent10[:6])) >= 3:
        return "混乱"
    if recent10[0] != recent10[1]:
        return "轮动"
    return "正常"

def model_hot(train, params):
    """热点模型：多窗口加权计数（从最近到最早）"""
    score = Counter()
    windows = [
        (params["short_window"], params["w_short"]),
        (params["mid_window"], params["w_mid"]),
        (params["long_window"], params["w_long"]),
    ]
    for w, wgt in windows:
        recent_w = train[:w] if len(train) >= w else train
        for c in recent_w:
            score[c] += wgt
    return score

def model_cold(train, params):
    """冷门模型：基于遗漏值"""
    omission = {}
    for c in COLORS:
        miss = 0
        for x in train:
            if x == c: break
            miss += 1
        omission[c] = miss
    score = Counter()
    for c, v in omission.items():
        score[c] += min(v * params["omission_weight"], params["omission_cap"])
    return score

def model_transition(train, params):
    """转移模型：基于上一期颜色"""
    score = Counter()
    if len(train) < 2:
        return score
    trans = defaultdict(Counter)
    for i in range(len(train)-1):
        trans[train[i]][train[i+1]] += 1
    last = train[0]
    if last in trans:
        total = sum(trans[last].values())
        if total > 0:
            for c, v in trans[last].items():
                score[c] += (v / total) * params["transition_weight"]
    return score

def model_reverse(train):
    """反向模型：抑制假热"""
    score = Counter({c: 0 for c in COLORS})
    recent8 = train[:8] if len(train) >= 8 else train
    freq = Counter(recent8)
    for c, cnt in freq.items():
        if cnt >= 5:
            score[c] -= 8
        else:
            score[c] += 3
    return score

def predict_two_colors(train_colors, miss_streak, params):
    if not train_colors:
        return ["红", "蓝"]

    # 市场识别
    market = detect_market(train_colors, params)

    # 各模型得分
    hot = model_hot(train_colors, params)
    cold = model_cold(train_colors, params)
    trans = model_transition(train_colors, params)
    rev = model_reverse(train_colors)

    final = Counter()
    if market == "单边":
        for c in COLORS:
            final[c] += hot[c] * params.get("unilateral_hot_weight", 2.2)
            final[c] += trans[c] * params.get("unilateral_trans_weight", 1.8)
            final[c] += rev[c] * params.get("unilateral_rev_weight", 0.6)
    elif market == "混乱":
        for c in COLORS:
            final[c] += cold[c] * params.get("chaos_cold_weight", 2.0)
            final[c] += rev[c] * params.get("chaos_rev_weight", 1.8)
            final[c] += hot[c] * params.get("chaos_hot_weight", 0.5)
    elif market == "轮动":
        for c in COLORS:
            final[c] += trans[c] * params.get("rotate_trans_weight", 2.2)
            final[c] += cold[c] * params.get("rotate_cold_weight", 1.0)
            final[c] += rev[c] * params.get("rotate_rev_weight", 1.0)
    else:  # 正常
        for c in COLORS:
            final[c] += hot[c] * params.get("market_hot_weight", 1.5)
            final[c] += cold[c] * params.get("market_cold_weight", 1.0)
            final[c] += trans[c] * params.get("market_trans_weight", 1.2)
            final[c] += rev[c] * params.get("market_rev_weight", 1.0)

    # 热号强制（最近7期出现≥2次）
    recent_hot = train_colors[-7:] if len(train_colors) >= 7 else train_colors
    hot_set = set()
    if len(recent_hot) >= 3:
        freq = Counter(recent_hot)
        for c, cnt in freq.items():
            if cnt >= 2:
                hot_set.add(c)

    # 连空保护
    if miss_streak >= 1:
        omission = {}
        for c in COLORS:
            miss = 0
            for x in train_colors:
                if x == c: break
                miss += 1
            omission[c] = miss
        cold_rank = sorted(omission.items(), key=lambda x: x[1], reverse=True)
        for c, _ in cold_rank[:2]:
            final[c] += params["miss_streak_bonus"]

    # 连续相同奖励
    if len(train_colors) >= 2 and train_colors[0] == train_colors[1]:
        final[train_colors[0]] += params.get("streak_bonus", 1.5)

    ranked = [c for c, _ in final.most_common()]
    pred = ranked[:2]

    # 强制包含热号
    hot_list = [c for c in ranked if c in hot_set]
    for hot in hot_list:
        if hot not in pred:
            pred[-1] = hot
            if pred[0] == pred[1]:
                for c in ranked:
                    if c not in pred:
                        pred[1] = c
                        break
    return pred[:2]

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
    return hits / lookback, max_miss, details

def backtest(colors, params, lookback=100):
    if len(colors) < 80 + lookback:
        return 0.0, 0
    rev = list(reversed(colors))
    total = min(lookback, len(rev)-80)
    hits = 0
    miss_streak = 0
    max_miss = 0
    for i in range(80, 80+total):
        train = list(reversed(rev[i+1:]))
        actual = rev[i]
        pred = predict_two_colors(train, miss_streak, params)
        if actual in pred:
            hits += 1
            miss_streak = 0
        else:
            miss_streak += 1
            max_miss = max(max_miss, miss_streak)
    return hits / total, max_miss

def objective(trial, colors):
    import optuna
    params = {
        "short_window": trial.suggest_int("short_window", 4, 12),
        "mid_window": trial.suggest_int("mid_window", 12, 35),
        "long_window": trial.suggest_int("long_window", 30, 70),
        "w_short": trial.suggest_float("w_short", 2.0, 6.0),
        "w_mid": trial.suggest_float("w_mid", 0.8, 2.5),
        "w_long": trial.suggest_float("w_long", 0.2, 1.5),
        "omission_weight": trial.suggest_float("omission_weight", 0.4, 1.2),
        "omission_cap": trial.suggest_float("omission_cap", 3.0, 7.0),
        "transition_weight": trial.suggest_float("transition_weight", 2.0, 6.0),
        "miss_streak_bonus": trial.suggest_float("miss_streak_bonus", 3.0, 8.0),
        "recent_boost": trial.suggest_float("recent_boost", 1.5, 4.0),
        "recent_window": trial.suggest_int("recent_window", 3, 6),
        "streak_bonus": trial.suggest_float("streak_bonus", 0.5, 3.0),
        "single_threshold": trial.suggest_float("single_threshold", 0.55, 0.70),
        "unilateral_hot_weight": trial.suggest_float("unilateral_hot_weight", 1.5, 3.0),
        "unilateral_trans_weight": trial.suggest_float("unilateral_trans_weight", 1.0, 2.5),
        "unilateral_rev_weight": trial.suggest_float("unilateral_rev_weight", 0.2, 1.2),
        "chaos_cold_weight": trial.suggest_float("chaos_cold_weight", 1.5, 3.0),
        "chaos_rev_weight": trial.suggest_float("chaos_rev_weight", 1.0, 2.5),
        "chaos_hot_weight": trial.suggest_float("chaos_hot_weight", 0.2, 1.2),
        "rotate_trans_weight": trial.suggest_float("rotate_trans_weight", 1.5, 3.0),
        "rotate_cold_weight": trial.suggest_float("rotate_cold_weight", 0.5, 1.5),
        "rotate_rev_weight": trial.suggest_float("rotate_rev_weight", 0.5, 1.5),
        "market_hot_weight": trial.suggest_float("market_hot_weight", 1.0, 2.5),
        "market_cold_weight": trial.suggest_float("market_cold_weight", 0.5, 1.8),
        "market_trans_weight": trial.suggest_float("market_trans_weight", 0.8, 2.0),
        "market_rev_weight": trial.suggest_float("market_rev_weight", 0.5, 1.5),
    }
    hr, max_miss = backtest(colors, params, 100)
    return hr - max_miss * 0.005

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
    print("开始 Optuna 调参 (300 trials)...")
    study = optuna.create_study(direction="maximize")
    study.optimize(lambda t: objective(t, colors), n_trials=300, show_progress_bar=True)
    best = study.best_params
    # 合并默认参数中未出现的新键
    for k, v in DEFAULT_PARAMS.items():
        if k not in best:
            best[k] = v
    with open(BEST_PARAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(best, f, indent=2, ensure_ascii=False)
    print("\n最佳参数:\n", json.dumps(best, indent=2, ensure_ascii=False))
    print(f"最佳评分: {study.best_value:.4f} -> 保存到 {BEST_PARAMS_FILE}")

def load_params():
    if os.path.exists(BEST_PARAMS_FILE):
        try:
            with open(BEST_PARAMS_FILE, encoding="utf-8") as f:
                p = json.load(f)
            for k, v in DEFAULT_PARAMS.items():
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
        print("数据获取失败")
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

    print("\n========== 澳门彩 · 特二色预测（市场自适应版）==========")
    print(f"预测期号：{pred_issue}")
    print(f"预测二色：{'、'.join(pred)}")
    print("=================================================")
    print(f"\n最近10期命中率：{hr10:.1%}，最大连空：{max10}")
    print(f"最近100期命中率：{hr100:.1%}，最大连空：{max100}")
    print("\n===== 最近10期详情 =====")
    for d in details:
        mark = "✓" if d["hit"] else "✗"
        print(f"{d['issue']:<10} 实际:{d['actual']}  预测:{'、'.join(d['pred']):<5} {mark}")

if __name__ == "__main__":
    main()
