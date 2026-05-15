#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
澳门彩 · 特二色预测（带回测与自动调参）
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

# ========== 波色映射 ==========
RED = {1, 2, 7, 8, 12, 13, 18, 19, 23, 24, 29, 30, 34, 35, 40, 45, 46}
BLUE = {3, 4, 9, 10, 14, 15, 20, 25, 26, 31, 36, 37, 41, 42, 47, 48}
GREEN = {5, 6, 11, 16, 17, 21, 22, 27, 28, 32, 33, 38, 39, 43, 44, 49}
COLORS = ["红", "蓝", "绿"]

# 默认参数（经验值）
DEFAULT_PARAMS = {
    "short_window": 12,
    "mid_window": 30,
    "long_window": 60,
    "w_short": 3.2,
    "w_mid": 1.4,
    "w_long": 0.8,
    "omission_weight": 0.65,
    "omission_cap": 6.0,
    "transition_weight": 4.5,
    "miss_streak_bonus": 4.0,
}

BEST_PARAMS_FILE = "best_params_macau.json"


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


def fetch_macau_records(limit: int = 600) -> list:
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


def predict_two_colors(train_colors: list, miss_streak: int, params: dict) -> list:
    """
    使用给定参数预测双色，支持连空保护
    """
    if not train_colors:
        return ["红", "蓝"]

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
            if x == c:
                break
            miss += 1
        omission[c] = miss
        score[c] += min(miss * params["omission_weight"], params["omission_cap"])

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
                score[c] += (v / total) * params["transition_weight"]

    # 连空保护
    if miss_streak >= 1:
        cold_rank = sorted(omission.items(), key=lambda x: x[1], reverse=True)
        for c, _ in cold_rank[:2]:
            score[c] += params["miss_streak_bonus"]

    ranked = [c for c, _ in score.most_common()]
    return ranked[:2]


def backtest(colors: list, params: dict, lookback: int = 100) -> tuple:
    """
    回测，返回 (命中率, 最大连空)
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
        pred = predict_two_colors(train, miss_streak, params)
        if actual in pred:
            hits += 1
            miss_streak = 0
        else:
            miss_streak += 1
            max_miss = max(max_miss, miss_streak)

    return hits / total, max_miss


def objective(trial, colors):
    """Optuna 目标函数"""
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
    hr, max_miss = backtest(colors, params, lookback=100)
    # 评分 = 命中率 - 最大连空 * 0.015（与原版一致）
    score = hr - max_miss * 0.015
    return score


def tune_params():
    """使用 Optuna 搜索最佳参数并保存"""
    try:
        import optuna
    except ImportError:
        print("请先安装 optuna: pip install optuna")
        return

    print("正在获取澳门彩数据用于调参...")
    rows = fetch_macau_records(300)
    if not rows:
        print("数据获取失败")
        return

    color_history = [get_color(r["special_number"]) for r in rows]
    color_history.reverse()  # 从早到晚

    print("开始 Optuna 调参（约100次试验）...")
    study = optuna.create_study(direction="maximize")
    study.optimize(lambda trial: objective(trial, color_history), n_trials=100, show_progress_bar=True)

    best = study.best_params
    # 补充默认值中未出现在搜索空间的字段（保持兼容）
    for k, v in DEFAULT_PARAMS.items():
        if k not in best:
            best[k] = v

    # 保存最佳参数
    with open(BEST_PARAMS_FILE, "w", encoding="utf-8") as f:
        json.dump(best, f, ensure_ascii=False, indent=2)

    print("\n===== 最佳参数 =====")
    print(json.dumps(best, ensure_ascii=False, indent=2))
    print(f"\n最佳评分: {study.best_value:.4f}")
    print(f"已保存到 {BEST_PARAMS_FILE}")


def load_params() -> dict:
    """加载参数（优先使用调参结果）"""
    if os.path.exists(BEST_PARAMS_FILE):
        try:
            with open(BEST_PARAMS_FILE, "r", encoding="utf-8") as f:
                params = json.load(f)
            # 确保所有键存在
            for k, v in DEFAULT_PARAMS.items():
                if k not in params:
                    params[k] = v
            return params
        except:
            pass
    return DEFAULT_PARAMS.copy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tune", action="store_true", help="运行 Optuna 自动调参")
    args = parser.parse_args()

    if args.tune:
        tune_params()
        return

    print("正在获取澳门彩数据...")
    rows = fetch_macau_records(300)
    if not rows:
        print("数据获取失败")
        return

    color_history = [get_color(r["special_number"]) for r in rows]
    color_history.reverse()  # 从早到晚

    params = load_params()
    pred = predict_two_colors(color_history, miss_streak=0, params=params)

    latest_issue = rows[0]["issue_no"]
    pred_issue = next_issue(latest_issue)

    # 回测
    hr10, max_miss10 = backtest(color_history, params, lookback=10)
    hr100, max_miss100 = backtest(color_history, params, lookback=100)

    print("\n========== 澳门彩 · 特二色预测 ==========")
    print(f"预测期号：{pred_issue}")
    print(f"预测二色：{'、'.join(pred)}")
    print("=========================================")
    print(f"\n最近10期命中率：{hr10:.1%}，最大连空：{max_miss10}")
    print(f"最近100期命中率：{hr100:.1%}，最大连空：{max_miss100}")


if __name__ == "__main__":
    main()
