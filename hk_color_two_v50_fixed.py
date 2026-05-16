#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 香港六合彩特二色预测 - 短期命中率提升版（基于V51搜索结果微调）

import argparse
import copy
import gzip
import json
import math
import re
import time
import random
import urllib.request
import os
from collections import Counter, defaultdict

# ================== 配置（采用短期搜索最佳参数 + 调低阈值）==================
CONFIG = {
    "odds": {"红": 2.70, "蓝": 2.80, "绿": 2.80},
    "pred_mode": "dual",
    "dual_alloc_mode": "score_proportional",

    # 以下为短期搜索找到的最佳参数（来自 best_params_short.json）
    "window_18_weight": 6.0,
    "window_55_weight": 2.0,
    "window_150_weight": 0.8,          # 原默认1.0，调低长期影响
    "omission_factor": 0.9,
    "omission_max": 11.5,
    "cycle_dev_low": 1.5,
    "cycle_dev_high": 3.0,
    "cycle_score_low": 3.5,
    "cycle_score_high": 7.0,
    "trans_weight": 7.0,               # 转移权重提高
    "normal_main_weight": 4.0,
    "szsd_trans_weight": 2.0,
    "normal_szsd_main_weight": 5.0,    # 正码大小单双权重大幅提高
    "beast_trans_weight": 0,           # 搜索显示野兽权重为0
    "normal_beast_main_weight": 0,

    # 关键调整：降低过滤门槛，增加投注频率
    "min_calibrated_confidence": 60,   # 原75 → 60，允许更多投注
    "min_score_diff": 3,               # 原5 → 3，允许更小分差
    "max_skip_streak": 6,

    # 资金管理（降低单注最小金额，减少回撤）
    "bankroll": 10000,
    "kelly_fraction": 0.35,
    "max_bet_ratio_total": 0.10,
    "min_bet_per_color": 100,          # 原200 → 100
    "bet_step": 50,
    "confidence_tiers": {"low": (0.03, 0.05), "mid": (0.05, 0.08), "high": (0.08, 0.12)},

    "api_url": "https://marksix6.net/index.php?api=1",
    "max_retries": 6,
    "timeout": 30,
    "train_max_len": 420,
    "show_details": 25,
    "min_train": 30,
}

# ================== 颜色 & 生肖定义 ==================
RED = {1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE = {3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
GREEN = {5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}
COLORS = ["红", "蓝", "绿"]

ZODIAC_ORDER = ["鼠","牛","虎","兔","龙","蛇","马","羊","猴","鸡","狗","猪"]
BEAST_SET = {"鼠","虎","兔","龙","蛇","猴"}
NUM_TO_BEAST_TYPE = {}
for num in range(1, 50):
    idx = (num - 1) % 12
    zodiac = ZODIAC_ORDER[idx]
    NUM_TO_BEAST_TYPE[num] = "野兽" if zodiac in BEAST_SET else "家禽"

def get_beast_type(n): return NUM_TO_BEAST_TYPE.get(n, "家禽")
def get_size(n): return "小" if 1 <= n <= 24 else "大"
def get_odd_even(n): return "单" if n % 2 == 1 else "双"
def get_szsd_type(n): return f"{get_size(n)}{get_odd_even(n)}"
def get_color(n):
    if n in RED: return "红"
    if n in BLUE: return "蓝"
    if n in GREEN: return "绿"
    return "红"

def next_issue(issue_no):
    try:
        if "/" in issue_no:
            y, s = issue_no.split("/")
            return f"{y}/{str(int(s)+1).zfill(3)}"
        return f"{issue_no[:4]}/{str(int(issue_no[4:])+1).zfill(3)}"
    except:
        return issue_no

def parse_nums(value):
    return [int(x) for x in re.findall(r'\d+', value) if 1 <= int(x) <= 49]

def fetch_hk(limit=800):
    headers = {"User-Agent": "Mozilla/5.0"}
    for attempt in range(CONFIG["max_retries"]):
        try:
            req = urllib.request.Request(CONFIG["api_url"], headers=headers)
            with urllib.request.urlopen(req, timeout=CONFIG["timeout"]) as resp:
                raw = resp.read()
                if "gzip" in resp.headers.get("Content-Encoding", "").lower():
                    raw = gzip.decompress(raw)
                data = json.loads(raw.decode("utf-8"))
                rows = []
                for item in data.get("lottery_data", []):
                    name = item.get("name", "")
                    if "香港" not in name and "六合彩" not in name:
                        continue
                    for line in item.get("history", []):
                        m = re.search(r"(\d{6,7})\s*期[：:]\s*([\d，,\s]+)", line)
                        if not m: continue
                        nums = parse_nums(m.group(2))
                        if len(nums) < 7: continue
                        raw_issue = m.group(1)
                        if len(raw_issue) == 6:
                            issue_no = f"{raw_issue[:2]}/{int(raw_issue[2:]):03d}"
                        else:
                            issue_no = f"{raw_issue[2:4]}/{int(raw_issue[4:]):03d}"
                        rows.append({
                            "issue_no": issue_no,
                            "normal_numbers": nums[:6],
                            "special_number": nums[6],
                            "color": get_color(nums[6]),
                        })
                if rows:
                    rows = sorted(rows, key=lambda x: x["issue_no"], reverse=True)
                    print(f"✅ 获取 {len(rows)} 期数据，最新: {rows[0]['issue_no']} 特码 {rows[0]['special_number']} → {rows[0]['color']}\n")
                    return rows[:limit]
        except Exception as e:
            print(f"获取失败 ({attempt+1}/{CONFIG['max_retries']}): {e}")
            time.sleep(2**attempt + random.random())
    print("❌ 无法获取数据")
    return []

class ConfidenceCalibrator:
    def __init__(self):
        self.bins = defaultdict(lambda: [0, 0])
    def record(self, score_diff, hit):
        key = round(score_diff / 5) * 5
        self.bins[key][0] += 1 if hit else 0
        self.bins[key][1] += 1
    def get_confidence(self, score_diff):
        key = round(score_diff / 5) * 5
        hits, total = self.bins.get(key, (0, 0))
        if total >= 5:
            return hits / total * 100
        all_hits = sum(v[0] for v in self.bins.values())
        all_total = sum(v[1] for v in self.bins.values())
        return (all_hits / all_total * 100) if all_total > 0 else 55.0

calibrator = ConfidenceCalibrator()

def professional_predict(train_colors, train_normals, train_specials, miss_streak=0, skip_streak=0, calib=None):
    if calib is None:
        calib = calibrator
    if len(train_colors) < CONFIG["min_train"]:
        return ["红", "绿"], {c: 50.0 for c in COLORS}, 50, "中", "数据不足", "二色", False, ""

    score = defaultdict(float)

    for i, c in enumerate(train_colors[:18]):
        score[c] += CONFIG["window_18_weight"] * (1 - i/35)
    for i, c in enumerate(train_colors[:55]):
        score[c] += CONFIG["window_55_weight"] * (1 - i/110)
    for i, c in enumerate(train_colors[:150]):
        score[c] += CONFIG["window_150_weight"] * (1 - i/260)

    omission = {c: next((i for i, x in enumerate(train_colors) if x == c), len(train_colors)) for c in COLORS}
    for c in COLORS:
        score[c] += min(omission[c] * CONFIG["omission_factor"], CONFIG["omission_max"])

    for c in COLORS:
        positions = [i for i, x in enumerate(train_colors) if x == c]
        if len(positions) >= 5:
            intervals = [positions[i] - positions[i-1] for i in range(1, len(positions))]
            avg = sum(intervals) / len(intervals)
            curr = positions[0] if positions else len(train_colors)
            dev = curr - avg
            if dev > CONFIG["cycle_dev_high"]:
                score[c] += CONFIG["cycle_score_high"]
            elif dev > CONFIG["cycle_dev_low"]:
                score[c] += CONFIG["cycle_score_low"]

    if len(train_colors) > 1:
        trans = defaultdict(Counter)
        for i in range(len(train_colors)-1):
            trans[train_colors[i+1]][train_colors[i]] += 1
        last_prev = train_colors[1]
        if last_prev in trans:
            total = sum(trans[last_prev].values())
            for c, v in trans[last_prev].items():
                score[c] += (v / total) * CONFIG["trans_weight"]

    if train_normals and len(train_normals) > 1:
        last_norm = train_normals[0]
        main_color = Counter(get_color(n) for n in last_norm).most_common(1)[0][0]
        normal_trans = defaultdict(Counter)
        for i in range(1, len(train_colors)):
            prev_norm = train_normals[i]
            prev_main = Counter(get_color(n) for n in prev_norm).most_common(1)[0][0]
            normal_trans[prev_main][train_colors[i-1]] += 1
        if main_color in normal_trans:
            total = sum(normal_trans[main_color].values())
            if total > 0:
                for c, v in normal_trans[main_color].items():
                    score[c] += (v / total) * CONFIG["normal_main_weight"]

    if CONFIG["szsd_trans_weight"] > 0 and train_specials and len(train_specials) > 1:
        last_szsd = get_szsd_type(train_specials[0])
        szsd_trans = defaultdict(Counter)
        for i in range(1, len(train_colors)):
            prev_szsd = get_szsd_type(train_specials[i])
            szsd_trans[prev_szsd][train_colors[i-1]] += 1
        if last_szsd in szsd_trans:
            total = sum(szsd_trans[last_szsd].values())
            if total > 0:
                for c, v in szsd_trans[last_szsd].items():
                    score[c] += (v / total) * CONFIG["szsd_trans_weight"]

    if CONFIG["normal_szsd_main_weight"] > 0 and train_normals and len(train_normals) > 1:
        last_norm_nums = train_normals[0]
        szsd_counts = Counter(get_szsd_type(n) for n in last_norm_nums)
        main_szsd = szsd_counts.most_common(1)[0][0]
        normal_szsd_trans = defaultdict(Counter)
        for i in range(1, len(train_colors)):
            prev_norm = train_normals[i]
            prev_main_szsd = Counter(get_szsd_type(n) for n in prev_norm).most_common(1)[0][0]
            normal_szsd_trans[prev_main_szsd][train_colors[i-1]] += 1
        if main_szsd in normal_szsd_trans:
            total = sum(normal_szsd_trans[main_szsd].values())
            if total > 0:
                for c, v in normal_szsd_trans[main_szsd].items():
                    score[c] += (v / total) * CONFIG["normal_szsd_main_weight"]

    if CONFIG["beast_trans_weight"] > 0 and train_specials and len(train_specials) > 1:
        last_beast = get_beast_type(train_specials[0])
        beast_trans = defaultdict(Counter)
        for i in range(1, len(train_colors)):
            prev_beast = get_beast_type(train_specials[i])
            beast_trans[prev_beast][train_colors[i-1]] += 1
        if last_beast in beast_trans:
            total = sum(beast_trans[last_beast].values())
            if total > 0:
                for c, v in beast_trans[last_beast].items():
                    score[c] += (v / total) * CONFIG["beast_trans_weight"]

    if CONFIG["normal_beast_main_weight"] > 0 and train_normals and len(train_normals) > 1:
        last_norm_nums = train_normals[0]
        beast_counts = Counter(get_beast_type(n) for n in last_norm_nums)
        main_beast = beast_counts.most_common(1)[0][0]
        normal_beast_trans = defaultdict(Counter)
        for i in range(1, len(train_colors)):
            prev_norm = train_normals[i]
            prev_main_beast = Counter(get_beast_type(n) for n in prev_norm).most_common(1)[0][0]
            normal_beast_trans[prev_main_beast][train_colors[i-1]] += 1
        if main_beast in normal_beast_trans:
            total = sum(normal_beast_trans[main_beast].values())
            if total > 0:
                for c, v in normal_beast_trans[main_beast].items():
                    score[c] += (v / total) * CONFIG["normal_beast_main_weight"]

    ranked = sorted(score.items(), key=lambda x: x[1], reverse=True)
    ranked_colors = [c for c, _ in ranked]

    if miss_streak >= 5 or (miss_streak == 4 and max(omission.values()) >= 9):
        pred_colors = [max(COLORS, key=lambda c: omission[c])]
        mode = "单色冷补"
    else:
        if CONFIG["pred_mode"] == "single":
            pred_colors = [ranked_colors[0]]
            mode = "单色"
        else:
            pred_colors = ranked_colors[:2]
            mode = "二色"

    diff = ranked[0][1] - (ranked[1][1] if len(ranked) > 1 else 0)
    conf_cal = calib.get_confidence(diff)
    if miss_streak >= 2:
        conf_cal = min(97, conf_cal + 10)
    conf = max(52, min(97, conf_cal))

    filter_reason = ""
    if conf < CONFIG["min_calibrated_confidence"]:
        filter_reason = f"置信度不足({conf}% < {CONFIG['min_calibrated_confidence']}%)"
    elif diff < CONFIG["min_score_diff"]:
        filter_reason = f"得分差不足({diff:.1f} < {CONFIG['min_score_diff']})"

    can_bet = (not filter_reason) or (skip_streak >= CONFIG["max_skip_streak"])
    if skip_streak >= CONFIG["max_skip_streak"] and filter_reason:
        filter_reason += "，但连续未投已达上限，强制投注"

    level = "高" if conf >= 80 else "中高" if conf >= 70 else "中" if conf >= 60 else "低"
    recent30_dom = Counter(train_colors[:30]).most_common(1)[0][1] if len(train_colors) >= 30 else 0
    state = "极强单边" if recent30_dom >= 13 else "强单边" if recent30_dom >= 9 else "单边" if recent30_dom >= 6 else "均衡"
    return pred_colors, dict(score), round(conf), level, state, mode, can_bet, filter_reason

def suggest_bet(scores, pred_colors, bankroll=None, conf=50):
    if bankroll is None:
        bankroll = CONFIG["bankroll"]
    if not pred_colors:
        return {}, 0
    if conf >= 80:
        low_ratio, high_ratio = CONFIG["confidence_tiers"]["high"]
    elif conf >= 70:
        low_ratio, high_ratio = CONFIG["confidence_tiers"]["mid"]
    else:
        low_ratio, high_ratio = CONFIG["confidence_tiers"]["low"]
    bet = {}
    if len(pred_colors) == 1:
        c = pred_colors[0]
        kelly = max(0, min((1.0 * (CONFIG["odds"][c]-1)) / (CONFIG["odds"][c]-1), 0.24))
        raw = int(bankroll * kelly / CONFIG["bet_step"]) * CONFIG["bet_step"]
        bet[c] = max(CONFIG["min_bet_per_color"], min(raw, int(bankroll * 0.25)))
    else:
        total_score = sum(scores.get(c, 30) for c in pred_colors)
        weights = {c: scores.get(c, 30) / total_score for c in pred_colors}
        for c in pred_colors:
            kelly = max(0, min((weights[c] * (CONFIG["odds"][c]-1) - (1-weights[c])) / (CONFIG["odds"][c]-1), 0.24))
            raw = int(bankroll * kelly / CONFIG["bet_step"]) * CONFIG["bet_step"]
            bet[c] = max(CONFIG["min_bet_per_color"], min(raw, int(bankroll * 0.25)))
    total_bet = sum(bet.values())
    max_total = int(bankroll * CONFIG["max_bet_ratio_total"])
    if total_bet > max_total:
        scale = max_total / total_bet
        bet = {c: int(v * scale / CONFIG["bet_step"]) * CONFIG["bet_step"] for c, v in bet.items()}
        total_bet = sum(bet.values())
    if total_bet < bankroll * low_ratio and total_bet > 0:
        target = int(bankroll * low_ratio / CONFIG["bet_step"]) * CONFIG["bet_step"]
        scale = target / total_bet
        bet = {c: int(v * scale / CONFIG["bet_step"]) * CONFIG["bet_step"] for c, v in bet.items()}
    elif total_bet > bankroll * high_ratio:
        scale = (bankroll * high_ratio) / total_bet
        bet = {c: int(v * scale / CONFIG["bet_step"]) * CONFIG["bet_step"] for c, v in bet.items()}
    return bet, sum(bet.values())

def backtest(rows, lookback=200, calib=None):
    if calib is None:
        calib = calibrator
    colors = [r["color"] for r in rows]
    normals = [r["normal_numbers"] for r in rows]
    specials = [r["special_number"] for r in rows]
    n = len(colors)
    if n < CONFIG["min_train"]:
        return 0.0, 0, 0.0, []
    total = min(lookback, n - CONFIG["min_train"])
    hits = miss_streak = max_miss = skip_streak = 0
    bankroll = max_bankroll = CONFIG["bankroll"]
    initial = bankroll
    details = []
    for k in range(total):
        actual = colors[k]
        hist_colors = colors[k+1:]
        hist_normals = normals[k+1:]
        hist_specials = specials[k+1:]
        pred, scores, conf, _, _, _, can_bet, reason = professional_predict(
            hist_colors[:CONFIG["train_max_len"]],
            hist_normals[:CONFIG["train_max_len"]],
            hist_specials[:CONFIG["train_max_len"]],
            miss_streak, skip_streak, calib
        )
        ok = actual in pred
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        diff = sorted_scores[0][1] - (sorted_scores[1][1] if len(sorted_scores) > 1 else 0)
        calib.record(diff, ok)
        if can_bet:
            bet_dict, _ = suggest_bet(scores, pred, bankroll, conf)
            cost = sum(bet_dict.values())
            ret = sum(amt * CONFIG["odds"][c] for c, amt in bet_dict.items() if c == actual) if ok else 0
            bankroll += ret - cost
            max_bankroll = max(max_bankroll, bankroll)
            skip_streak = 0
        else:
            bet_dict = {}
            skip_streak += 1
        if ok:
            hits += 1
            miss_streak = 0
        else:
            miss_streak += 1
            max_miss = max(max_miss, miss_streak)
        if k < CONFIG["show_details"]:
            details.append({
                "issue": rows[k]["issue_no"],
                "special_num": rows[k]["special_number"],
                "pred": pred,
                "actual": actual,
                "hit": ok,
                "conf": conf,
                "bet": bet_dict,
                "reason": reason,
                "miss_streak": miss_streak,
                "bankroll": round(bankroll, 2),
            })
    final_return = (bankroll - initial) / initial * 100 if initial > 0 else 0
    return hits/total if total>0 else 0, max_miss, final_return, details[::-1]

def main():
    print("获取香港六合彩数据...")
    rows = fetch_hk(800)
    if not rows:
        print("数据获取失败")
        return

    colors = [r["color"] for r in rows]
    normals = [r["normal_numbers"] for r in rows]
    specials = [r["special_number"] for r in rows]
    latest_issue = rows[0]["issue_no"]

    pred_colors, scores, conf, level, state, mode, can_bet, reason = professional_predict(
        colors, normals, specials, miss_streak=0, skip_streak=0
    )

    print(f"\n【香港六合彩 特二色 短期命中率提升版】")
    print(f"预测期号: {next_issue(latest_issue)}")
    print(f"推荐颜色: {'、'.join(pred_colors)}   置信度: {conf}% ({level})  状态: {state}")
    print(f"投注允许: {'是' if can_bet else '否'}" + (f" → {reason}" if not can_bet else ""))
    print()

    if can_bet:
        bet_dict, total_bet = suggest_bet(scores, pred_colors, CONFIG["bankroll"], conf)
        print("💰 资金管理建议:")
        for c, amt in bet_dict.items():
            print(f"   {c}色 → {amt} 元 (赔率 {CONFIG['odds'][c]})")
        print(f"   总投注: {total_bet} 元\n")
    else:
        print("💰 本期无投注建议\n")

    print("🎯 颜色得分:")
    for c in COLORS:
        print(f"   {c}: {scores.get(c,0):.1f}")
    print()

    # 回测
    hr10, miss10, ret10, _ = backtest(rows, 10)
    hr100, miss100, ret100, _ = backtest(rows, 100)
    hr200, miss200, ret200, _ = backtest(rows, 200)

    print(f"最近10期 命中率: {hr10:.1%} 最大连空: {miss10} 收益: {ret10:+.1f}%")
    print(f"最近100期 命中率: {hr100:.1%} 最大连空: {miss100} 收益: {ret100:+.1f}%")
    print(f"最近200期 命中率: {hr200:.1%} 最大连空: {miss200} 收益: {ret200:+.1f}%")

    # 生成 result.md
    with open("result.md", "w", encoding="utf-8") as f:
        f.write("# 香港六合彩特二色预测报告（短期提升版）\n\n")
        f.write(f"**预测期号**: {next_issue(latest_issue)}\n\n")
        f.write(f"**推荐颜色**: {'、'.join(pred_colors)}\n\n")
        f.write(f"**置信度**: {conf}% ({level})\n\n")
        f.write(f"**模式**: {mode}\n\n**状态**: {state}\n\n")
        if can_bet:
            f.write("## 资金建议\n\n| 颜色 | 投注金额 | 赔率 |\n|------|----------|------|\n")
            for c, amt in bet_dict.items():
                f.write(f"| {c} | {amt} 元 | {CONFIG['odds'][c]} |\n")
            f.write(f"\n**总投注**: {total_bet} 元\n\n")
        else:
            f.write(f"**投注建议**: 否 → {reason}\n\n")
        f.write("## 颜色得分\n\n| 颜色 | 得分 |\n|------|------|\n")
        for c in COLORS:
            f.write(f"| {c} | {scores.get(c,0):.1f} |\n")
        f.write("\n## 回测绩效\n\n")
        f.write(f"- 最近10期命中率: {hr10:.1%}，最大连空: {miss10}，收益: {ret10:+.1f}%\n")
        f.write(f"- 最近100期命中率: {hr100:.1%}，最大连空: {miss100}，收益: {ret100:+.1f}%\n")
        f.write(f"- 最近200期命中率: {hr200:.1%}，最大连空: {miss200}，收益: {ret200:+.1f}%\n")

    print("\n📄 报告已保存至 result.md")

if __name__ == "__main__":
    main()