#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# color_two_v43.py
# 新澳门 · 特二色 V43（正码特征 + 概率过滤 + 仓位分档 + 单双色模式）

import argparse
import gzip
import json
import math
import re
import time
import random
import urllib.request
from collections import Counter, defaultdict

# ================== 配置参数集中管理 ==================
CONFIG = {
    # ---- 赔率 ----
    "odds": {"红": 2.70, "蓝": 2.80, "绿": 2.80},

    # ---- 预测模式 ---- "dual" 二色, "single" 单色
    "pred_mode": "dual",

    # ---- 模型权重 ----
    "window_18_weight": 6.8,
    "window_55_weight": 2.6,
    "window_150_weight": 1.0,
    "omission_factor": 0.9,
    "omission_max": 11.5,
    "cycle_dev_low": 1.5,
    "cycle_dev_high": 3.0,
    "cycle_score_low": 3.5,
    "cycle_score_high": 7.0,
    "trans_weight": 6.5,
    "normal_main_weight": 4.0,   # 正码主要颜色转移加分

    # ---- 概率过滤 ----
    "min_calibrated_confidence": 68,   # 低于此置信度不投
    "min_score_diff": 10,              # 前两名得分差低于此不投

    # ---- 仓位管理 ----
    "bankroll": 10000,
    "kelly_fraction": 0.35,
    "max_bet_ratio_total": 0.10,       # 总仓位上限
    "min_bet_per_color": 200,
    "bet_step": 50,
    # 根据置信度分档：低(60-70)小仓, 中(70-80)标准, 高(>80)重仓
    "confidence_tiers": {
        "low": (0.03, 0.05),    # 总资金比例
        "mid": (0.05, 0.08),
        "high": (0.08, 0.12),
    },

    # ---- API ----
    "api_url": "https://marksix6.net/index.php?api=1",
    "max_retries": 6,
    "timeout": 30,

    # ---- 回测 ----
    "train_max_len": 420,
    "show_details": 25,
    "min_train": 30,            # 最小训练样本（需要正码特征）
}

# 颜色定义
RED = {1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE = {3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
GREEN = {5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}
COLORS = ["红", "蓝", "绿"]

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

def fetch_macau(limit=800):
    """获取数据，包含正码"""
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
                    if not any(x in item.get("name", "") for x in ["新澳门", "六合彩"]):
                        continue
                    for line in item.get("history", []):
                        m = re.search(r"(\d{7})\s*期[：:]\s*([\d，,\s]+)", line)
                        if not m: continue
                        nums = parse_nums(m.group(2))
                        if len(nums) < 7: continue
                        raw_issue = m.group(1)
                        issue_no = f"{raw_issue[2:4]}/{int(raw_issue[4:]):03d}"
                        normal_nums = nums[:6]   # 正码
                        special = nums[6]        # 特码
                        rows.append({
                            "issue_no": issue_no,
                            "normal_numbers": normal_nums,
                            "special_number": special,
                            "color": get_color(special)
                        })
                if rows:
                    rows = sorted(rows, key=lambda x: x["issue_no"], reverse=True)
                    print(f"✅ 成功获取 {len(rows)} 期数据")
                    print(f"最新开奖: {rows[0]['issue_no']} 特码 {rows[0]['special_number']} → {rows[0]['color']}\n")
                    return rows[:limit]
        except Exception as e:
            print(f"获取失败 (尝试 {attempt+1}/{CONFIG['max_retries']}): {e}")
            time.sleep(2 ** attempt + random.random())
    print("❌ 无法获取数据")
    return []

# ================== 置信度校准器 ==================
class ConfidenceCalibrator:
    def __init__(self):
        self.bins = defaultdict(lambda: [0, 0])  # [命中, 总数]

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
        if all_total > 0:
            return all_hits / all_total * 100
        return 55.0

calibrator = ConfidenceCalibrator()

# ================== 预测核心（含正码特征） ==================
def professional_predict(train_colors, train_normals, miss_streak=0):
    """
    train_colors: 历史特码颜色列表（降序，最新在前）
    train_normals: 对应的历史正码列表（每期6个号码列表）
    """
    if len(train_colors) < CONFIG["min_train"]:
        return ["红", "绿"], {c: 50.0 for c in COLORS}, 50, "中", "数据不足", "二色", False

    score = defaultdict(float)

    # 1. 基本权重
    for i, c in enumerate(train_colors[:18]):
        score[c] += CONFIG["window_18_weight"] * (1 - i/35)
    for i, c in enumerate(train_colors[:55]):
        score[c] += CONFIG["window_55_weight"] * (1 - i/110)
    for i, c in enumerate(train_colors[:150]):
        score[c] += CONFIG["window_150_weight"] * (1 - i/260)

    # 2. 遗漏
    omission = {c: next((i for i, x in enumerate(train_colors) if x == c), len(train_colors)) for c in COLORS}
    for c in COLORS:
        score[c] += min(omission[c] * CONFIG["omission_factor"], CONFIG["omission_max"])

    # 3. 周期偏离
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

    # 4. 颜色转移
    trans = defaultdict(Counter)
    for i in range(len(train_colors)-1):
        trans[train_colors[i]][train_colors[i+1]] += 1
    if train_colors:
        last = train_colors[0]
        if last in trans:
            total = sum(trans[last].values())
            for c, v in trans[last].items():
                score[c] += (v / total) * CONFIG["trans_weight"]

    # 5. 正码特征：最近一期正码的主要颜色，统计历史同主要颜色时下一期特码颜色分布
    if train_normals and len(train_normals) > 1:
        # 最近一期正码 (index 0)
        last_norm = train_normals[0]
        main_color = Counter(get_color(n) for n in last_norm).most_common(1)[0][0]
        # 建立历史转移：对于每一期（除了第一期），检查其正码主要颜色，然后统计下一期特码颜色
        normal_trans = defaultdict(Counter)
        for i in range(1, len(train_colors)):   # i=1..len-1
            prev_norm = train_normals[i]        # 上期正码
            prev_main = Counter(get_color(n) for n in prev_norm).most_common(1)[0][0]
            normal_trans[prev_main][train_colors[i-1]] += 1   # 上一期特码（因为我们序列降序，所以上一期是 i-1）
        if main_color in normal_trans:
            total = sum(normal_trans[main_color].values())
            if total > 0:
                for c, v in normal_trans[main_color].items():
                    score[c] += (v / total) * CONFIG["normal_main_weight"]

    # 排序
    ranked = sorted(score.items(), key=lambda x: x[1], reverse=True)
    ranked_colors = [c for c, s in ranked]

    # 冷补模式（仅在严重连空时）
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

    # 计算得分差
    diff = ranked[0][1] - (ranked[1][1] if len(ranked) > 1 else 0)
    conf_cal = calibrator.get_confidence(diff)
    if miss_streak >= 2:
        conf_cal = min(97, conf_cal + 10)
    conf = max(52, min(97, conf_cal))

    # 概率过滤判定：是否满足最低置信度与得分差
    can_bet = conf >= CONFIG["min_calibrated_confidence"] and diff >= CONFIG["min_score_diff"]

    level = "高" if conf >= 80 else "中高" if conf >= 70 else "中" if conf >= 60 else "低"
    recent30_dom = Counter(train_colors[:30]).most_common(1)[0][1] if len(train_colors) >= 30 else 0
    state = "极强单边" if recent30_dom >= 13 else "强单边" if recent30_dom >= 9 else "单边" if recent30_dom >= 6 else "均衡"

    return pred_colors, dict(score), round(conf), level, state, mode, can_bet

# ================== 资金管理（仓位分档） ==================
def kelly_fraction(p_win, decimal_odds):
    b = decimal_odds - 1
    if b <= 0 or p_win <= 0:
        return 0.0
    kelly = (p_win * b - (1 - p_win)) / b
    return max(0.0, min(kelly * CONFIG["kelly_fraction"], 0.24))

def suggest_bet(scores, pred_colors, miss_streak=0, bankroll=None, conf=50):
    if bankroll is None:
        bankroll = CONFIG["bankroll"]
    if not pred_colors:
        return {}, 0

    # 根据置信度分档决定仓位比例范围
    if conf >= 80:
        low_ratio, high_ratio = CONFIG["confidence_tiers"]["high"]
    elif conf >= 70:
        low_ratio, high_ratio = CONFIG["confidence_tiers"]["mid"]
    else:
        low_ratio, high_ratio = CONFIG["confidence_tiers"]["low"]

    total_model = sum(scores.get(c, 30) for c in pred_colors)
    bet = {}
    total_bet = 0

    for c in pred_colors:
        model_p = scores.get(c, 30) / total_model
        kelly_f = kelly_fraction(model_p, CONFIG["odds"][c])
        # 基础金额
        raw_amount = int(bankroll * kelly_f / CONFIG["bet_step"]) * CONFIG["bet_step"]
        amount = max(CONFIG["min_bet_per_color"], min(raw_amount, int(bankroll * 0.25)))
        bet[c] = amount
        total_bet += amount

    # 应用仓位上限（总仓位比例限制）
    max_total = int(bankroll * CONFIG["max_bet_ratio_total"])
    if total_bet > max_total:
        scale = max_total / total_bet
        bet = {c: int(v * scale / CONFIG["bet_step"]) * CONFIG["bet_step"] for c, v in bet.items()}
        total_bet = sum(bet.values())

    # 应用分档的比例限制（确保总投注在low_ratio~high_ratio之间）
    if total_bet < bankroll * low_ratio:
        # 如果太低，可适度提升到下限（但不超过上限）
        target = int(bankroll * low_ratio / CONFIG["bet_step"]) * CONFIG["bet_step"]
        if total_bet > 0:
            scale = target / total_bet
            bet = {c: int(v * scale / CONFIG["bet_step"]) * CONFIG["bet_step"] for c, v in bet.items()}
            total_bet = sum(bet.values())
    elif total_bet > bankroll * high_ratio:
        scale = (bankroll * high_ratio) / total_bet
        bet = {c: int(v * scale / CONFIG["bet_step"]) * CONFIG["bet_step"] for c, v in bet.items()}
        total_bet = sum(bet.values())

    return bet, total_bet

# ================== 回测 ==================
def backtest(rows, lookback=200):
    """回测，需要 rows 包含 normal_numbers"""
    colors = [r["color"] for r in rows]
    normals = [r["normal_numbers"] for r in rows]   # 正码列表
    n = len(colors)
    if n < CONFIG["min_train"]:
        return 0.0, 0, 0.0, []

    total = min(lookback, n - CONFIG["min_train"])
    hits = 0
    miss_streak = 0
    max_miss = 0
    details = []
    bankroll = CONFIG["bankroll"]
    initial = bankroll
    max_bankroll = bankroll
    drawdown = 0.0

    for k in range(total):
        actual = colors[k]
        hist_colors = colors[k+1:]  # 更早的颜色
        hist_normals = normals[k+1:]  # 对应的正码
        # 取最近 train_max_len 期训练
        train_colors = hist_colors[:CONFIG["train_max_len"]][::-1]  # 时间升序
        train_normals = hist_normals[:CONFIG["train_max_len"]][::-1]

        pred_colors, scores, conf, level, state, mode, can_bet = professional_predict(
            hist_colors, hist_normals, miss_streak  # 注意这里传入的是降序的 hist_colors 和 hist_normals
        )
        # 修正：professional_predict 内部期望降序列表，所以我们直接传 hist_colors（降序）和 hist_normals
        # 但上面传入了 hist_colors 和 hist_normals（都是降序），与内部逻辑匹配

        ok = actual in pred_colors

        # 记录校准器
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        diff = sorted_scores[0][1] - (sorted_scores[1][1] if len(sorted_scores) > 1 else 0)
        calibrator.record(diff, ok)

        # 概率过滤：如果不能投注，本期仓位为0，不参与统计？
        # 我们仍然统计命中率，但模拟资金时不投注
        if can_bet:
            bet_dict, _ = suggest_bet(scores, pred_colors, miss_streak, bankroll, conf)
            cost = sum(bet_dict.values())
            return_ = 0
            if ok:
                for c, amt in bet_dict.items():
                    if c == actual:
                        return_ += amt * CONFIG["odds"][c]
            bankroll += return_ - cost
            # 更新回撤
            if bankroll > max_bankroll:
                max_bankroll = bankroll
            dd = (max_bankroll - bankroll) / max_bankroll * 100 if max_bankroll > 0 else 0
            drawdown = max(drawdown, dd)
        else:
            bet_dict = {}
            cost = 0
            dd = (max_bankroll - bankroll) / max_bankroll * 100 if max_bankroll > 0 else 0  # 无交易

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
                "pred": pred_colors,
                "actual": actual,
                "hit": ok,
                "conf": conf,
                "state": state,
                "mode": mode,
                "can_bet": can_bet,
                "bet": bet_dict,
                "miss_streak": miss_streak,
                "bankroll": round(bankroll, 2),
                "dd": round(dd, 2)
            })

    final_return = (bankroll - initial) / initial * 100 if initial > 0 else 0
    return hits / total if total > 0 else 0, max_miss, final_return, details[::-1]

# ================== 主程序 ==================
def main():
    print("正在获取新澳门最新数据...\n")
    rows = fetch_macau(800)
    if not rows:
        print("数据获取失败")
        return

    colors = [r["color"] for r in rows]
    normals = [r["normal_numbers"] for r in rows]
    latest_issue = rows[0]["issue_no"]

    # 当前预测（无未来信息）
    pred_colors, scores, conf, level, state, mode, can_bet = professional_predict(
        colors, normals, miss_streak=0
    )
    print("【新澳门 特二色 V43 正码过滤版】")
    print(f"预测期号: {next_issue(latest_issue)}")
    print(f"预测模式: {mode}")
    print(f"推荐颜色: {'、'.join(pred_colors)}   置信度: {conf}% ({level})  状态: {state}")
    print(f"投注允许: {'是' if can_bet else '否（置信度或得分差不足）'}\n")

    if can_bet:
        bet_dict, total_bet = suggest_bet(scores, pred_colors, 0, CONFIG["bankroll"], conf)
        print("💰 资金管理建议（分档仓位）:")
        expected = 0
        for c, amt in bet_dict.items():
            net = CONFIG["odds"][c] - 1
            print(f"   {c}色 → {amt:4d} 元   (赔率 {CONFIG['odds'][c]}，净{net:.2f})")
            expected += amt * net
        print(f"   本期总投注: {total_bet} 元")
        print(f"   若命中预计净利: +{expected:.0f} 元\n")
    else:
        print("💰 本期无投注建议（未满足过滤条件）\n")

    print("🎯 颜色强度得分:")
    for c in COLORS:
        print(f"   {c}色: {scores.get(c, 0):.1f} 分")
    print(f"   最强: 【{max(COLORS, key=lambda c: scores.get(c,0))}】\n")

    print("回测中...\n")
    hr10,  miss10,  ret10,  det10  = backtest(rows, 10)
    hr100, miss100, ret100, _      = backtest(rows, 100)
    hr200, miss200, ret200, _      = backtest(rows, 200)

    print(f"===== 最近10期   命中率: {hr10:.1%}    最大连空: {miss10}    模拟收益: {ret10:+.1f}% =====")
    print(f"===== 最近100期  命中率: {hr100:.1%}   最大连空: {miss100}   模拟收益: {ret100:+.1f}% =====")
    print(f"===== 最近200期  命中率: {hr200:.1%}   最大连空: {miss200}   模拟收益: {ret200:+.1f}% =====")

    if ret200 < -10 or miss200 >= 6:
        print("\n⚠️ 风险提示：长期收益为负或连空次数较高，请谨慎参与。")

    print(f"\n===== 最近{CONFIG['show_details']}期详细回测 =====")
    for d in det10:
        pred_str = "、".join(d["pred"])
        mark = "✓" if d["hit"] else "✗"
        bet_str = " | ".join([f"{c}{v}元" for c, v in d["bet"].items()]) if d["can_bet"] else "未投"
        print(f"{d['issue']} | 特码{d['special_num']:2d} | {pred_str:<9} 实际:{d['actual']} {mark} "
              f"[{d['conf']}%] {d['state']} ({d['mode']}) 连空:{d['miss_streak']}")
        print(f"   投注: {bet_str}  资金: {d['bankroll']:.0f}  回撤: {d['dd']:.1f}%")
        print("-" * 90)

if __name__ == "__main__":
    main()