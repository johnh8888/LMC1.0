#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import math
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.request import Request, urlopen

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH_DEFAULT = str(SCRIPT_DIR / "new_macau.db")
OFFICIAL_URL_DEFAULT = ""
THIRD_PARTY_URLS_DEFAULT: List[str] = ["https://marksix6.net/index.php?api=1"]
MINED_CONFIG_KEY = "mined_strategy_config_v1"
ALL_NUMBERS = list(range(1, 50))
STRATEGY_LABELS = {
    "balanced_v1": "组合策略", "hot_v1": "热号策略", "cold_rebound_v1": "冷号回补",
    "momentum_v1": "近期动量", "ensemble_v2": "集成投票", "pattern_mined_v1": "规律挖掘",
}
STRATEGY_IDS = ["balanced_v1", "hot_v1", "cold_rebound_v1", "momentum_v1", "ensemble_v2", "pattern_mined_v1"]

RED_WAVE  = {1, 2, 7, 8, 12, 13, 18, 19, 23, 24, 29, 30, 34, 35, 40, 45, 46}
BLUE_WAVE = {3, 4, 9, 10, 14, 15, 20, 25, 26, 31, 36, 37, 41, 42, 47, 48}
GREEN_WAVE= {5, 6, 11, 16, 17, 21, 22, 27, 28, 32, 33, 38, 39, 43, 44, 49}
VALID_NUMBERS = set(range(1, 50))
ALL_COLORS = ["红", "蓝", "绿"]

CANDIDATE_WINDOWS = tuple(range(6, 16))
WINDOW_DECAY_CANDIDATES = [(w, d) for w in range(8, 31) for d in [0.20, 0.25, 0.30]]
WEIGHT_CANDIDATES = [
    (0.35, 0.20, 0.10, 0.10, 0.10, 0.05, 0.05, 0.05),
    (0.25, 0.30, 0.15, 0.10, 0.10, 0.05, 0.03, 0.02),
    (0.40, 0.15, 0.10, 0.15, 0.10, 0.05, 0.03, 0.02),
]
COLOR_GAP_HIGH   = 0.25
COLOR_GAP_MEDIUM = 0.08
BS_GAP_HIGH      = 0.30
BS_GAP_MEDIUM    = 0.15
OE_GAP_HIGH      = 0.30
OE_GAP_MEDIUM    = 0.15
RISK_SCORE_HIGH  = 2
RISK_COLOR_RATE_LOW = 0.333
RISK_BS_RATE_LOW    = 0.40
RISK_OE_RATE_LOW    = 0.40
BS_CONSECUTIVE_ERROR_THRESHOLD = 2
OE_CONSECUTIVE_ERROR_THRESHOLD = 2
COLOR_WEIGHT_TRANS_HIGH = 0.20
COLOR_WEIGHT_TRANS_LOW  = 0.05
ZODIAC_STREAK_PENALTY_FACTOR = 0.03
ZODIAC_STREAK_PENALTY_MAX   = 0.10
DEFAULT_BACKTEST_LIMIT = 18
EXPECTED_DB_VERSION = 2

ZODIAC_MAP = {
    1:"马",2:"蛇",3:"龙",4:"兔",5:"虎",6:"牛",7:"鼠",8:"猪",9:"狗",10:"鸡",
    11:"猴",12:"羊",13:"马",14:"蛇",15:"龙",16:"兔",17:"虎",18:"牛",19:"鼠",20:"猪",
    21:"狗",22:"鸡",23:"猴",24:"羊",25:"马",26:"蛇",27:"龙",28:"兔",29:"虎",30:"牛",
    31:"鼠",32:"猪",33:"狗",34:"鸡",35:"猴",36:"羊",37:"马",38:"蛇",39:"龙",40:"兔",
    41:"虎",42:"牛",43:"鼠",44:"猪",45:"狗",46:"鸡",47:"猴",48:"羊",49:"马"
}
ALL_ZODIACS = ['马','蛇','龙','兔','虎','牛','鼠','猪','狗','鸡','猴','羊']
ZODIAC_ORDER = {z: i for i, z in enumerate(ALL_ZODIACS)}

def _safe_test_periods(train_len, min_p=5, default=10):
    return max(min_p, min(default, train_len - max(CANDIDATE_WINDOWS) - 1))

def get_zodiac(num: int) -> str:
    return ZODIAC_MAP.get(num, "未知")

def get_color(num: int) -> str:
    if num in RED_WAVE:   return "红"
    if num in BLUE_WAVE:  return "蓝"
    return "绿"

def get_parity(num: int) -> str:
    return "单" if num % 2 == 1 else "双"

def _build_color_zodiac_map() -> Dict[str, set]:
    m = {"红": set(), "蓝": set(), "绿": set()}
    for n, z in ZODIAC_MAP.items():
        c = get_color(n)
        if c in m: m[c].add(z)
    return m

def _build_size_zodiac_map() -> Dict[str, set]:
    m = {"大": set(), "小": set()}
    for n, z in ZODIAC_MAP.items():
        m["大" if n >= 25 else "小"].add(z)
    return m

def special_attributes(num: int) -> Dict[str, str]:
    ones = num % 10; tens = num // 10; he = tens + ones
    color = get_color(num)
    if ones in (1,6): element = "水"
    elif ones in (2,7): element = "火"
    elif ones in (3,8): element = "木"
    elif ones in (4,9): element = "金"
    else: element = "土"
    return {
        "单双": "单" if num%2==1 else "双",
        "大小": "大" if num>=25 else "小",
        "合单双": "单" if he%2==1 else "双",
        "合大小": "大" if he>=7 else "小",
        "尾大小": "大" if ones>=5 else "小",
        "色波": color, "五行": element, "生肖": get_zodiac(num)
    }

# ---------- 波色预测 ----------
def predict_color_weighted(specials: List[int], window: int = 8) -> Tuple[str,str,str,float,float,float]:
    if len(specials) < 5: return "红","蓝","绿",0.0,0.0,0.0
    recent = specials[-window:] if len(specials) >= window else specials
    colors = [get_color(n) for n in recent]
    score: Dict[str,float] = {"红":0.0,"蓝":0.0,"绿":0.0}
    total_w = 0.0
    for i, c in enumerate(reversed(colors)):
        w = float(window - i); score[c] += w; total_w += w
    if total_w > 0:
        for c in score: score[c] = score[c]/total_w*0.50
    omit: Dict[str,int] = {}
    for c in ALL_COLORS:
        miss = 0
        for n in reversed(specials):
            if get_color(n) == c: break
            miss += 1
        omit[c] = miss
    max_omit = max(omit.values()) or 1
    for c in score: score[c] += 0.30*(omit[c]/max_omit)
    if len(colors) >= 2:
        current = colors[-1]; trans: Dict[str,int] = {"红":0,"蓝":0,"绿":0}; total_trans = 0
        for i in range(len(colors)-1):
            if colors[i] == current: trans[colors[i+1]] += 1; total_trans += 1
        if total_trans > 0:
            for c in score: score[c] += 0.20*(trans[c]/total_trans)
    streak_color = colors[-1]; streak = 1
    for i in range(len(colors)-2,-1,-1):
        if colors[i] == streak_color: streak += 1
        else: break
    if streak >= 2: score[streak_color] *= max(0.35, 1.0-streak*0.15)
    ranked = sorted(score.items(), key=lambda x: x[1], reverse=True)
    return ranked[0][0],ranked[1][0],ranked[2][0],ranked[0][1],ranked[1][1],ranked[2][1]

def predict_color_simple(specials: List[int], window: int = 8) -> Tuple[str,str,str,float,float,float]:
    if len(specials) < 5: return "红","蓝","绿",0.0,0.0,0.0
    colors = [get_color(n) for n in specials[-window:]]
    freq = Counter(colors); total = sum(freq.values())
    ranked = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    while len(ranked) < 3:
        for c in ALL_COLORS:
            if c not in [r[0] for r in ranked]: ranked.append((c,0)); break
    return ranked[0][0],ranked[1][0],ranked[2][0],ranked[0][1]/total,ranked[1][1]/total,ranked[2][1]/total

def predict_color_enhanced(specials: List[int], window: int = 8) -> Tuple[str,str,str,float,float,float]:
    if len(specials) < 5: return "红","蓝","绿",0.0,0.0,0.0
    if len(specials) >= 4:
        wrong = sum(1 for i in range(1,4)
                    if len(specials[:-i]) >= 5 and
                    predict_color_simple(specials[:-i], window)[0] != get_color(specials[-i]))
        if wrong >= 3: return predict_color_simple(specials, window)
    recent = specials[-window:] if len(specials) >= window else specials
    colors = [get_color(n) for n in recent]
    score: Dict[str,float] = {"红":0.0,"蓝":0.0,"绿":0.0}
    total_w = 0.0
    for i, c in enumerate(reversed(colors)):
        w = math.exp(-0.5*i); score[c] += w; total_w += w
    if total_w > 0:
        for c in score: score[c] = score[c]/total_w*0.50
    omit: Dict[str,int] = {}
    for c in ALL_COLORS:
        miss = 0
        for n in reversed(specials):
            if get_color(n) == c: break
            miss += 1
        omit[c] = miss
    max_omit = max(omit.values()) or 1
    for c in score: score[c] += 0.30*(omit[c]/max_omit)
    trans_weight = COLOR_WEIGHT_TRANS_HIGH
    if len(colors) >= 2 and len(specials) >= 6:
        hits = sum(1 for i in range(1,6)
                   if len(specials[:-i]) >= 5 and
                   predict_color_weighted(specials[:-i], window)[0] == get_color(specials[-i]))
        if hits/min(5,len(specials)-1) < 0.3: trans_weight = COLOR_WEIGHT_TRANS_LOW
    if len(colors) >= 2:
        current = colors[-1]; trans: Dict[str,int] = {"红":0,"蓝":0,"绿":0}; total_trans = 0
        for i in range(len(colors)-1):
            if colors[i] == current: trans[colors[i+1]] += 1; total_trans += 1
        if total_trans > 0:
            for c in score: score[c] += trans_weight*(trans[c]/total_trans)
    streak_color = colors[-1]; streak = 1
    for i in range(len(colors)-2,-1,-1):
        if colors[i] == streak_color: streak += 1
        else: break
    if streak >= 2: score[streak_color] *= max(0.35, 1.0-streak*0.15)
    ranked = sorted(score.items(), key=lambda x: x[1], reverse=True)
    mc, sc_color, ec = ranked[0][0], ranked[1][0], ranked[2][0]
    if len(specials) >= 4:
        tl, tp = specials[:-1], specials[:-2]
        if len(tl) >= 5 and len(tp) >= 5:
            _,_,excl1,_,_,_ = predict_color_weighted(tl, window)
            _,_,excl2,_,_,_ = predict_color_weighted(tp, window)
            a1, a2 = get_color(specials[-1]), get_color(specials[-2])
            if a1 != excl1 and a2 != excl2 and excl1 == excl2 and mc == excl1:
                mc, sc_color = sc_color, mc
    return mc, sc_color, ec, score[mc], score[sc_color], 0

def predict_color(specials, window=8, method="weighted"):
    if method == "simple": return predict_color_simple(specials, window)
    return predict_color_enhanced(specials, window)

def predict_color_ensemble(specials, method="weighted", windows=CANDIDATE_WINDOWS):
    if len(specials) < 20: return predict_color(specials, window=8, method=method)
    test_limit = _safe_test_periods(len(specials))
    if test_limit <= 0: return predict_color(specials, window=8, method=method)
    weights = []
    for w in windows:
        hits = sum(1 for i in range(len(specials)-test_limit, len(specials))
                   if predict_color(specials[:i], window=w, method=method)[0] == get_color(specials[i]))
        weights.append(hits / test_limit)
    squared = [w ** 2 for w in weights]
    sq_total = sum(squared) or 1
    norm_weights = [s / sq_total for s in squared]
    color_scores = {"红":0.0,"蓝":0.0,"绿":0.0}
    for w, weight in zip(windows, norm_weights):
        m, s, _, _, _, _ = predict_color(specials, window=w, method=method)
        color_scores[m] += 2 * weight
        color_scores[s] += 1 * weight
    ranked = sorted(color_scores.items(), key=lambda x: x[1], reverse=True)
    mc, sc_color, ec = ranked[0][0], ranked[1][0], ranked[2][0]
    return mc, sc_color, ec, color_scores[mc], color_scores[sc_color], 0

def color_confidence_dynamic(specials, main_score, second_score, window=8, method="weighted"):
    lookback = window * 2; gap = main_score - second_score
    if len(specials) < lookback + 10: return ("低" if gap < COLOR_GAP_MEDIUM else ("中" if gap < COLOR_GAP_HIGH else "高")), gap
    gaps = []
    for i in range(len(specials)-lookback, len(specials)):
        train = specials[:i]
        if len(train) < 5: continue
        _, _, _, ms, ss, _ = predict_color(train, window=window, method=method)
        gaps.append(ms - ss)
    if not gaps: return ("低" if gap < COLOR_GAP_MEDIUM else ("中" if gap < COLOR_GAP_HIGH else "高")), gap
    gs = sorted(gaps); n = len(gs)
    hi = gs[int(n*2/3)]; lo = gs[int(n*1/3)]
    level = "高" if gap >= hi else "中" if gap >= lo else "低"
    return level, gap

# ---------- 大小预测（增强版）----------
def _attr_score(attrs, score_keys, specials_raw, attr_fn, window):
    score = {k: 0.0 for k in score_keys}
    total_w = 0.0
    for i, a in enumerate(reversed(attrs)):
        w = float(window - i); score[a] += w; total_w += w
    if total_w > 0:
        for k in score: score[k] = score[k]/total_w*0.50
    omit = {}
    for k in score_keys:
        miss = 0
        for n in reversed(specials_raw):
            if attr_fn(n) == k: break
            miss += 1
        omit[k] = miss
    max_omit = max(omit.values()) or 1
    for k in score: score[k] += 0.25*(omit[k]/max_omit)
    return score

def _detect_alternating_pattern(attrs):
    if len(attrs) < 4: return False
    recent4 = attrs[-4:]
    return (recent4[0] != recent4[1] and recent4[1] != recent4[2] and recent4[2] != recent4[3] and recent4[0] == recent4[2])

def predict_big_small(specials, window=8):
    if len(specials) < 5: return "大", 0.0
    recent = specials[-window:] if len(specials) >= window else specials
    bs_fn = lambda n: "大" if n>=25 else "小"
    attrs = [bs_fn(n) for n in recent]
    score = _attr_score(attrs, ["大","小"], specials, bs_fn, window)
    he_attrs = [("大" if (n//10+n%10)>=7 else "小") for n in recent]
    he_score = {"大":0.0,"小":0.0}; hw = 0.0
    for i, a in enumerate(reversed(he_attrs)):
        w = float(window-i); he_score[a] += w; hw += w
    if hw > 0:
        for k in he_score: he_score[k] = he_score[k]/hw*0.18
    score[max(he_score, key=he_score.get)] += max(he_score.values())
    wei_attrs = [("大" if (n%10)>=5 else "小") for n in recent]
    wei_score = {"大":0.0,"小":0.0}; ww = 0.0
    for i, a in enumerate(reversed(wei_attrs)):
        w = float(window-i); wei_score[a] += w; ww += w
    if ww > 0:
        for k in wei_score: wei_score[k] = wei_score[k]/ww*0.07
    score[max(wei_score, key=wei_score.get)] += max(wei_score.values())
    trans_weight = 0.15
    if _detect_alternating_pattern(attrs):
        trans_weight = 0.05
    if len(attrs) >= 2:
        current = attrs[-1]; trans = {"大":0,"小":0}; tt = 0
        for i in range(len(attrs)-1):
            if attrs[i] == current: trans[attrs[i+1]] += 1; tt += 1
        if tt > 0:
            for k in score: score[k] += trans_weight*(trans[k]/tt)
    sv = attrs[-1]; streak = 1
    for i in range(len(attrs)-2,-1,-1):
        if attrs[i] == sv: streak += 1
        else: break
    if streak >= 2: score[sv] *= max(0.35, 1.0-streak*0.15)
    ranked = sorted(score.items(), key=lambda x: x[1], reverse=True)
    return ranked[0][0], ranked[0][1]-ranked[1][1]

def predict_big_small_ensemble(specials, windows=CANDIDATE_WINDOWS):
    if len(specials) < 20: return predict_big_small(specials, window=8)
    test_limit = _safe_test_periods(len(specials))
    if test_limit <= 0: return predict_big_small(specials, window=8)
    weights = []
    for w in windows:
        hits = sum(1 for i in range(len(specials)-test_limit, len(specials))
                   if predict_big_small(specials[:i], window=w)[0] == ("大" if specials[i]>=25 else "小"))
        weights.append(hits/test_limit)
    total_w = sum(weights) or 1
    squared = [w**2 for w in weights]
    sq_total = sum(squared) or 1
    weights = [s/sq_total for s in squared]
    score = {"大":0.0,"小":0.0}
    for w, weight in zip(windows, weights):
        pred, _ = predict_big_small(specials, window=w)
        score[pred] += weight
    winner = max(score, key=score.get)
    gap = abs(score[winner]/sum(score.values())-0.5)*2
    return winner, gap

def apply_bs_correction(train_specials, pred_bs, consecutive_threshold=BS_CONSECUTIVE_ERROR_THRESHOLD):
    if len(train_specials) < consecutive_threshold + 1:
        return pred_bs, ""
    all_wrong = True
    for i in range(len(train_specials) - consecutive_threshold, len(train_specials)):
        sub = train_specials[:i]
        actual = "大" if train_specials[i] >= 25 else "小"
        pred, _ = (predict_big_small_ensemble(sub) if len(sub) >= 20
                   else predict_big_small(sub, window=8))
        if pred == actual:
            all_wrong = False
            break
    if all_wrong:
        flipped = "小" if pred_bs == "大" else "大"
        return flipped, "(连错纠正)"
    return pred_bs, ""

# ---------- 单双预测（结构对齐大小预测）----------
def predict_odd_even(specials, window=8):
    """结构与 predict_big_small 完全对齐：本位单双 + 合数单双(辅) + 头数单双(辅)
    + 转移概率 + 连续同一结果衰减。返回 (主推单/双, 主次差值)。"""
    if len(specials) < 5: return "单", 0.0
    recent = specials[-window:] if len(specials) >= window else specials
    oe_fn = lambda n: get_parity(n)
    attrs = [oe_fn(n) for n in recent]
    score = _attr_score(attrs, ["单","双"], specials, oe_fn, window)
    # 合数单双（辅助信号，权重对齐大小预测的合数大小 0.18）
    he_attrs = [("单" if (n//10+n%10)%2==1 else "双") for n in recent]
    he_score = {"单":0.0,"双":0.0}; hw = 0.0
    for i, a in enumerate(reversed(he_attrs)):
        w = float(window-i); he_score[a] += w; hw += w
    if hw > 0:
        for k in he_score: he_score[k] = he_score[k]/hw*0.18
    score[max(he_score, key=he_score.get)] += max(he_score.values())
    # 头数单双（十位数字奇偶，辅助信号，权重对齐尾数大小 0.07）
    tou_attrs = [("单" if (n//10)%2==1 else "双") for n in recent]
    tou_score = {"单":0.0,"双":0.0}; tw = 0.0
    for i, a in enumerate(reversed(tou_attrs)):
        w = float(window-i); tou_score[a] += w; tw += w
    if tw > 0:
        for k in tou_score: tou_score[k] = tou_score[k]/tw*0.07
    score[max(tou_score, key=tou_score.get)] += max(tou_score.values())
    # 转移概率
    trans_weight = 0.15
    if _detect_alternating_pattern(attrs):
        trans_weight = 0.05
    if len(attrs) >= 2:
        current = attrs[-1]; trans = {"单":0,"双":0}; tt = 0
        for i in range(len(attrs)-1):
            if attrs[i] == current: trans[attrs[i+1]] += 1; tt += 1
        if tt > 0:
            for k in score: score[k] += trans_weight*(trans[k]/tt)
    sv = attrs[-1]; streak = 1
    for i in range(len(attrs)-2,-1,-1):
        if attrs[i] == sv: streak += 1
        else: break
    if streak >= 2: score[sv] *= max(0.35, 1.0-streak*0.15)
    ranked = sorted(score.items(), key=lambda x: x[1], reverse=True)
    return ranked[0][0], ranked[0][1]-ranked[1][1]

def predict_odd_even_ensemble(specials, windows=CANDIDATE_WINDOWS):
    if len(specials) < 20: return predict_odd_even(specials, window=8)
    test_limit = _safe_test_periods(len(specials))
    if test_limit <= 0: return predict_odd_even(specials, window=8)
    weights = []
    for w in windows:
        hits = sum(1 for i in range(len(specials)-test_limit, len(specials))
                   if predict_odd_even(specials[:i], window=w)[0] == get_parity(specials[i]))
        weights.append(hits/test_limit)
    squared = [w**2 for w in weights]
    sq_total = sum(squared) or 1
    weights = [s/sq_total for s in squared]
    score = {"单":0.0,"双":0.0}
    for w, weight in zip(windows, weights):
        pred, _ = predict_odd_even(specials, window=w)
        score[pred] += weight
    winner = max(score, key=score.get)
    gap = abs(score[winner]/sum(score.values())-0.5)*2
    return winner, gap

def apply_oe_correction(train_specials, pred_oe, consecutive_threshold=OE_CONSECUTIVE_ERROR_THRESHOLD):
    """与 apply_bs_correction 完全对齐：最近 N 期若连续全错则反转推荐。"""
    if len(train_specials) < consecutive_threshold + 1:
        return pred_oe, ""
    all_wrong = True
    for i in range(len(train_specials) - consecutive_threshold, len(train_specials)):
        sub = train_specials[:i]
        actual = get_parity(train_specials[i])
        pred, _ = (predict_odd_even_ensemble(sub) if len(sub) >= 20
                   else predict_odd_even(sub, window=8))
        if pred == actual:
            all_wrong = False
            break
    if all_wrong:
        flipped = "双" if pred_oe == "单" else "单"
        return flipped, "(连错纠正)"
    return pred_oe, ""

# ---------- 自动调优（回测隔离版）----------
def auto_tune_color_window(specials, test_periods=None):
    """
    调优只在 specials[:-test_periods] 上选窗口，
    不让调优过程"看见"测试区间的数据。
    """
    if test_periods is None:
        test_periods = _safe_test_periods(len(specials))
    train_end = len(specials) - test_periods
    if train_end < max(CANDIDATE_WINDOWS) + 1:
        return 8
    train_for_tune = specials[:train_end]
    best_w, best_hits = 8, -1
    for w in CANDIDATE_WINDOWS:
        if len(train_for_tune) < w + 5:
            continue
        tp = _safe_test_periods(len(train_for_tune))
        hits = sum(
            1 for i in range(len(train_for_tune) - tp, len(train_for_tune))
            if predict_color(train_for_tune[:i], window=w, method='weighted')[0]
               == get_color(train_for_tune[i])
        )
        if hits > best_hits:
            best_hits, best_w = hits, w
    return best_w

def auto_tune_bs_window(specials, test_periods=None):
    """同上，大小窗口调优也隔离测试区间。"""
    if test_periods is None:
        test_periods = _safe_test_periods(len(specials))
    train_end = len(specials) - test_periods
    if train_end < max(CANDIDATE_WINDOWS) + 1:
        return 8
    train_for_tune = specials[:train_end]
    best_w, best_hits = 8, -1
    for w in CANDIDATE_WINDOWS:
        if len(train_for_tune) < w + 5:
            continue
        tp = _safe_test_periods(len(train_for_tune))
        hits = sum(
            1 for i in range(len(train_for_tune) - tp, len(train_for_tune))
            if predict_big_small(train_for_tune[:i], window=w)[0]
               == ("大" if train_for_tune[i] >= 25 else "小")
        )
        if hits > best_hits:
            best_hits, best_w = hits, w
    return best_w

def auto_tune_oe_window(specials, test_periods=None):
    """与 auto_tune_bs_window 完全对齐的单双窗口调优（回测隔离）。"""
    if test_periods is None:
        test_periods = _safe_test_periods(len(specials))
    train_end = len(specials) - test_periods
    if train_end < max(CANDIDATE_WINDOWS) + 1:
        return 8
    train_for_tune = specials[:train_end]
    best_w, best_hits = 8, -1
    for w in CANDIDATE_WINDOWS:
        if len(train_for_tune) < w + 5:
            continue
        tp = _safe_test_periods(len(train_for_tune))
        hits = sum(
            1 for i in range(len(train_for_tune) - tp, len(train_for_tune))
            if predict_odd_even(train_for_tune[:i], window=w)[0]
               == get_parity(train_for_tune[i])
        )
        if hits > best_hits:
            best_hits, best_w = hits, w
    return best_w

# ---------- 风险控制 ----------
def calc_color_recent_hit_rate(specials, recent=5, window=8):
    if len(specials) < recent + 5: return None
    hits = 0
    for i in range(len(specials)-recent, len(specials)):
        train = specials[:i]
        w = auto_tune_color_window(train) if len(train) >= 30 else 8
        m,_,_,_,_,_ = predict_color(train, window=w, method='weighted')
        if m == get_color(specials[i]): hits += 1
    return hits / recent

def calc_bs_recent_hit_rate(specials, recent=5):
    if len(specials) < recent + 5: return None
    hits = 0
    for i in range(len(specials)-recent, len(specials)):
        train = specials[:i]
        pred, _ = predict_big_small_ensemble(train) if len(train)>=20 else predict_big_small(train, window=8)
        pred, _ = apply_bs_correction(train, pred)
        if pred == ("大" if specials[i]>=25 else "小"): hits += 1
    return hits / recent

def calc_oe_recent_hit_rate(specials, recent=5):
    if len(specials) < recent + 5: return None
    hits = 0
    for i in range(len(specials)-recent, len(specials)):
        train = specials[:i]
        pred, _ = predict_odd_even_ensemble(train) if len(train)>=20 else predict_odd_even(train, window=8)
        pred, _ = apply_oe_correction(train, pred)
        if pred == get_parity(specials[i]): hits += 1
    return hits / recent

def calc_risk_score(specials, color_conf, bs_conf, bs_gap, color_gap, oe_conf=None):
    score = 0
    if color_conf == "高": score += 1
    if bs_conf == "高": score += 1
    color_rate = calc_color_recent_hit_rate(specials, recent=5)
    if color_rate is not None and color_rate < RISK_COLOR_RATE_LOW: score -= 1
    bs_rate = calc_bs_recent_hit_rate(specials, recent=5)
    if bs_rate is not None and bs_rate < RISK_BS_RATE_LOW: score -= 2
    pred_bs_raw, _ = predict_big_small_ensemble(specials) if len(specials)>=20 else predict_big_small(specials, window=8)
    _, ce = apply_bs_correction(specials, pred_bs_raw)
    if ce: score -= 1
    oe_rate = calc_oe_recent_hit_rate(specials, recent=5)
    if oe_conf == "高": score += 1
    if oe_rate is not None and oe_rate < RISK_OE_RATE_LOW: score -= 2
    pred_oe_raw, _ = predict_odd_even_ensemble(specials) if len(specials)>=20 else predict_odd_even(specials, window=8)
    _, oe_ce = apply_oe_correction(specials, pred_oe_raw)
    if oe_ce: score -= 1
    return score, color_rate, bs_rate, oe_rate

def risk_level(score):
    if score >= RISK_SCORE_HIGH: return "🟢", "低风险", "信号较强，可小注参考"
    if score >= 0: return "🟡", "中风险", "信号混杂，建议观望或极小注"
    return "🔴", "高风险", "信号矛盾或近期连续错误，建议本期暂停"

def build_dimension_advice(color_conf, bs_conf, bs_ce, bs_rate, color_rate, bs_gap, color_gap, bs_conf_str,
                            oe_conf_str=None, oe_ce="", oe_rate=None):
    lines = []
    if color_conf == "高" and (color_rate is None or color_rate >= RISK_COLOR_RATE_LOW):
        lines.append(f"   波色：🟢 可参考（信心{color_conf}，近期命中{f'{color_rate*100:.0f}%' if color_rate else '计算中'}）")
    elif color_conf == "低":
        lines.append(f"   波色：🔴 不建议（信心低，差值{color_gap:.3f}）")
    else:
        lines.append(f"   波色：🟡 谨慎（信心{color_conf}，近期命中{f'{color_rate*100:.0f}%' if color_rate else '计算中'}）")
    if bs_ce:
        lines.append(f"   大小：🔴 不建议（{bs_ce}，近期命中{f'{bs_rate*100:.0f}%' if bs_rate else '计算中'}）")
    elif bs_conf_str == "低" or (bs_rate is not None and bs_rate < RISK_BS_RATE_LOW):
        lines.append(f"   大小：🔴 不建议（信心{bs_conf_str}，近期命中{f'{bs_rate*100:.0f}%' if bs_rate else '计算中'}）")
    elif bs_conf_str == "高" and (bs_rate is None or bs_rate >= 0.50):
        lines.append(f"   大小：🟢 可参考（信心高，近期命中{f'{bs_rate*100:.0f}%' if bs_rate else '计算中'}）")
    else:
        lines.append(f"   大小：🟡 谨慎（信心{bs_conf_str}，近期命中{f'{bs_rate*100:.0f}%' if bs_rate else '计算中'}）")
    if oe_conf_str is not None:
        if oe_ce:
            lines.append(f"   单双：🔴 不建议（{oe_ce}，近期命中{f'{oe_rate*100:.0f}%' if oe_rate else '计算中'}）")
        elif oe_conf_str == "低" or (oe_rate is not None and oe_rate < RISK_OE_RATE_LOW):
            lines.append(f"   单双：🔴 不建议（信心{oe_conf_str}，近期命中{f'{oe_rate*100:.0f}%' if oe_rate else '计算中'}）")
        elif oe_conf_str == "高" and (oe_rate is None or oe_rate >= 0.50):
            lines.append(f"   单双：🟢 可参考（信心高，近期命中{f'{oe_rate*100:.0f}%' if oe_rate else '计算中'}）")
        else:
            lines.append(f"   单双：🟡 谨慎（信心{oe_conf_str}，近期命中{f'{oe_rate*100:.0f}%' if oe_rate else '计算中'}）")
    if bs_conf_str == "低":
        lines.append("   生肖：🟡 谨慎（大小信心低，已跳过大小筛选，仅按波色选肖）")
        lines.append("   六码：🔴 不建议（依赖大小方向，当前不稳定）")
    elif bs_rate is not None and bs_rate < RISK_BS_RATE_LOW:
        lines.append("   生肖：🟡 谨慎（大小近期准确率低）")
        lines.append("   六码：🔴 不建议（大小命中率低于40%，六码可靠性低）")
    else:
        lines.append("   生肖：🟢 可参考（漏斗方向正常）")
        lines.append("   六码：🟡 谨慎（基线12.2%，仅供参考）")
    return "\n".join(lines)

def backtest_big_small_by_confidence(conn, recent_limit=DEFAULT_BACKTEST_LIMIT):
    rows = conn.execute("SELECT special_number FROM draws ORDER BY draw_date ASC, issue_no ASC").fetchall()
    specials = [r["special_number"] for r in rows]
    if len(specials) < recent_limit + 10: recent_limit = max(10, len(specials)-10)
    result = {"高": {"total":0,"hit":0,"periods":[]}, "中": {"total":0,"hit":0,"periods":[]}, "低": {"total":0,"hit":0,"periods":[]}}
    start = len(specials) - recent_limit
    for i in range(start, len(specials)):
        train = specials[:i]; actual_bs = "大" if specials[i]>=25 else "小"
        pred_bs, gap = predict_big_small_ensemble(train) if len(train)>=20 else predict_big_small(train, window=8)
        pred_bs, _ = apply_bs_correction(train, pred_bs)
        conf = "高" if gap>=BS_GAP_HIGH else "中" if gap>=BS_GAP_MEDIUM else "低"
        result[conf]["total"] += 1
        hit = pred_bs == actual_bs
        if hit: result[conf]["hit"] += 1
        result[conf]["periods"].append({"idx":i-start+1,"pred":pred_bs,"actual":actual_bs,"actual_num":specials[i],"hit":hit,"gap":gap})
    return result

def backtest_odd_even_by_confidence(conn, recent_limit=DEFAULT_BACKTEST_LIMIT):
    """与 backtest_big_small_by_confidence 完全对齐的单双版本。"""
    rows = conn.execute("SELECT special_number FROM draws ORDER BY draw_date ASC, issue_no ASC").fetchall()
    specials = [r["special_number"] for r in rows]
    if len(specials) < recent_limit + 10: recent_limit = max(10, len(specials)-10)
    result = {"高": {"total":0,"hit":0,"periods":[]}, "中": {"total":0,"hit":0,"periods":[]}, "低": {"total":0,"hit":0,"periods":[]}}
    start = len(specials) - recent_limit
    for i in range(start, len(specials)):
        train = specials[:i]; actual_oe = get_parity(specials[i])
        pred_oe, gap = predict_odd_even_ensemble(train) if len(train)>=20 else predict_odd_even(train, window=8)
        pred_oe, _ = apply_oe_correction(train, pred_oe)
        conf = "高" if gap>=OE_GAP_HIGH else "中" if gap>=OE_GAP_MEDIUM else "低"
        result[conf]["total"] += 1
        hit = pred_oe == actual_oe
        if hit: result[conf]["hit"] += 1
        result[conf]["periods"].append({"idx":i-start+1,"pred":pred_oe,"actual":actual_oe,"actual_num":specials[i],"hit":hit,"gap":gap})
    return result

def backtest_big_small_only(conn, recent_limit=DEFAULT_BACKTEST_LIMIT):
    rows = conn.execute("SELECT special_number FROM draws ORDER BY draw_date ASC, issue_no ASC").fetchall()
    specials = [r["special_number"] for r in rows]
    if len(specials) < recent_limit+10: return {}
    result = {"big_small":{"total":0,"hit":0,"periods":[]}}
    start = len(specials)-recent_limit
    for i in range(start, len(specials)):
        train = specials[:i]; actual_bs = "大" if specials[i]>=25 else "小"
        pred_bs, gap = predict_big_small_ensemble(train) if len(train)>=20 else predict_big_small(train, window=8)
        pred_bs, _ = apply_bs_correction(train, pred_bs)
        bs_hit = pred_bs==actual_bs
        result["big_small"]["total"]+=1
        if bs_hit: result["big_small"]["hit"]+=1
        result["big_small"]["periods"].append({"idx":i-start+1,"pred":pred_bs,"actual":actual_bs,"actual_num":specials[i],"hit":bs_hit})
    return result

def backtest_odd_even_only(conn, recent_limit=DEFAULT_BACKTEST_LIMIT):
    """与 backtest_big_small_only 对齐的单双滚动回测。"""
    rows = conn.execute("SELECT special_number FROM draws ORDER BY draw_date ASC, issue_no ASC").fetchall()
    specials = [r["special_number"] for r in rows]
    if len(specials) < recent_limit+10: return {}
    result = {"odd_even":{"total":0,"hit":0,"periods":[]}}
    start = len(specials)-recent_limit
    for i in range(start, len(specials)):
        train = specials[:i]; actual_oe = get_parity(specials[i])
        pred_oe, gap = predict_odd_even_ensemble(train) if len(train)>=20 else predict_odd_even(train, window=8)
        pred_oe, _ = apply_oe_correction(train, pred_oe)
        oe_hit = pred_oe==actual_oe
        result["odd_even"]["total"]+=1
        if oe_hit: result["odd_even"]["hit"]+=1
        result["odd_even"]["periods"].append({"idx":i-start+1,"pred":pred_oe,"actual":actual_oe,"actual_num":specials[i],"hit":oe_hit})
    return result

def backtest_zodiac_and_special_nums(conn, recent_limit=DEFAULT_BACKTEST_LIMIT):
    rows = conn.execute("SELECT special_number FROM draws ORDER BY draw_date ASC, issue_no ASC").fetchall()
    specials = [r["special_number"] for r in rows]
    if len(specials) < recent_limit+10: return {}
    result = {"zodiac":{"total":0,"hit":0,"periods":[]},"special_nums":{"total":0,"hit":0,"periods":[]}}
    start = len(specials)-recent_limit
    for i in range(start, len(specials)):
        train = specials[:i]; actual_num = specials[i]; actual_zodiac = get_zodiac(actual_num)
        cw = auto_tune_color_window(train) if len(train)>=30 else 8
        if len(train)>=20:
            pred_bs, bs_gap = predict_big_small_ensemble(train)
            mc,sc_color,ec,_,_,_ = predict_color_ensemble(train, method='weighted')
        else:
            pred_bs, bs_gap = predict_big_small(train, window=8)
            mc,sc_color,ec,_,_,_ = predict_color(train, window=cw, method='weighted')
        pred_bs, _ = apply_bs_correction(train, pred_bs)
        bs_conf = "高" if bs_gap>=BS_GAP_HIGH else "中" if bs_gap>=BS_GAP_MEDIUM else "低"
        pred_zodiacs, zodiac_scores = predict_zodiac(train, window=cw, big_small=pred_bs,
                                                     main_color=mc, second_color=sc_color, exclude_color=ec,
                                                     bs_confidence=bs_conf)
        pred_nums, num_scores = predict_special_nums_from_zodiacs(train, pred_zodiacs, big_small=pred_bs,
                                                                  main_color=mc, second_color=sc_color, exclude_color=ec,
                                                                  bs_confidence=bs_conf)
        zodiac_hit = actual_zodiac in pred_zodiacs
        num_hit = actual_num in pred_nums
        result["zodiac"]["total"]+=1; result["special_nums"]["total"]+=1
        if zodiac_hit: result["zodiac"]["hit"]+=1
        if num_hit: result["special_nums"]["hit"]+=1
        result["zodiac"]["periods"].append({"idx":i-start+1,"pred":pred_zodiacs,"actual":actual_zodiac,
            "hit":zodiac_hit,"big_small":pred_bs,"main_color":mc,"second_color":sc_color,"bs_conf":bs_conf,"zodiac_scores":zodiac_scores})
        result["special_nums"]["periods"].append({"idx":i-start+1,"pred_nums":pred_nums,
            "actual_num":actual_num,"hit":num_hit,"num_scores":num_scores})
    return result

def backtest_colors(conn, recent_limit=DEFAULT_BACKTEST_LIMIT):
    rows = conn.execute("SELECT special_number FROM draws ORDER BY draw_date ASC, issue_no ASC").fetchall()
    specials = [r["special_number"] for r in rows]
    if len(specials) < recent_limit+10: return 0,0,0,0
    total = mh = sh = ah = 0
    start = len(specials)-recent_limit
    for i in range(start, len(specials)):
        train = specials[:i]; actual = get_color(specials[i])
        w = auto_tune_color_window(train) if len(train)>=30 else 8
        m,s,_,_,_,_ = predict_color(train, window=w, method='weighted')
        if m==actual: mh+=1
        if s==actual: sh+=1
        if m==actual or s==actual: ah+=1
        total+=1
    return total,mh,sh,ah

def backtest_colors_by_confidence(conn, recent_limit=DEFAULT_BACKTEST_LIMIT):
    rows = conn.execute("SELECT special_number FROM draws ORDER BY draw_date ASC, issue_no ASC").fetchall()
    specials = [r["special_number"] for r in rows]
    if len(specials) < recent_limit+10: return {}
    result = {lv:{"total":0,"main_hit":0,"two_color_hit":0,"periods":[]} for lv in ["高","中","低"]}
    start = len(specials)-recent_limit
    for i in range(start, len(specials)):
        train = specials[:i]; actual = get_color(specials[i])
        w = auto_tune_color_window(train) if len(train)>=30 else 8
        m,s,excl,ms,ss,_ = predict_color(train, window=w, method='weighted')
        level,gap = color_confidence_dynamic(train, ms, ss, window=w, method='weighted')
        r = result[level]; r["total"]+=1
        main_ok = m==actual; two_ok = actual!=excl
        if main_ok: r["main_hit"]+=1; mark="▲"
        elif s==actual: mark="△"
        else: mark="✗"
        if two_ok: r["two_color_hit"]+=1
        r["periods"].append({"idx":i-start+1,"main":m,"second":s,"exclude":excl,"actual_color":actual,"actual_num":specials[i],"gap":gap,"mark":mark,"two_ok":two_ok})
    return result

# ---------- 生肖预测（返回得分）----------
def predict_zodiac(specials: List[int], window: int = 8,
                   big_small: str = None,
                   main_color: str = None, second_color: str = None,
                   exclude_color: str = None,
                   bs_confidence: str = "高") -> Tuple[List[str], Dict[str, float]]:
    if len(specials) < 5:
        return ALL_ZODIACS[:5], {z: 0.0 for z in ALL_ZODIACS[:5]}
    czm = _build_color_zodiac_map()
    szm = _build_size_zodiac_map()
    use_size_filter = (big_small and big_small in szm and bs_confidence != "低")
    size_pool = szm[big_small] if use_size_filter else set(ALL_ZODIACS)
    color_pool: set = set()
    if main_color and main_color in czm: color_pool |= (czm[main_color] & size_pool)
    if second_color and second_color in czm: color_pool |= (czm[second_color] & size_pool)
    candidate_pool = set(color_pool)
    if len(candidate_pool) < 5 and exclude_color and exclude_color in czm:
        candidate_pool |= (czm[exclude_color] & size_pool)
    if len(candidate_pool) < 5: candidate_pool |= size_pool
    if len(candidate_pool) < 5: candidate_pool = set(ALL_ZODIACS)
    if len(candidate_pool) < 3:
        freq_all = Counter(get_zodiac(n) for n in specials[-window:])
        top5 = [z for z, _ in freq_all.most_common(5)]
        return top5, {z: 1.0 for z in top5}
    recent = specials[-window:] if len(specials) >= window else specials
    omit = {z: 0 for z in candidate_pool}
    for z in candidate_pool:
        for n in reversed(specials):
            if get_zodiac(n) == z: break
            omit[z] += 1
    max_omit = max(omit.values()) or 1
    freq = {z: 0.0 for z in candidate_pool}
    for idx, n in enumerate(reversed(recent)):
        z = get_zodiac(n)
        if z in freq: freq[z] += 1.0/(idx+1)
    streak_z = get_zodiac(specials[-1]); streak = 1
    for n in reversed(recent[:-1]):
        if get_zodiac(n) == streak_z: streak += 1
        else: break
    scores = {}
    for z in candidate_pool:
        penalty = min(ZODIAC_STREAK_PENALTY_MAX, streak*ZODIAC_STREAK_PENALTY_FACTOR) if z == streak_z and streak >= 2 else 0.0
        scores[z] = (omit[z]/max_omit)*0.60 + freq[z]*0.35 - penalty
    sorted_zodiacs = sorted(scores, key=scores.get, reverse=True)[:5]
    return sorted_zodiacs, scores

def predict_special_nums_from_zodiacs(specials, zodiacs, big_small=None,
                                       main_color=None, second_color=None,
                                       exclude_color=None, bs_confidence="高") -> Tuple[List[int], Dict[int, float]]:
    nums = [n for n in ALL_NUMBERS if get_zodiac(n) in zodiacs]
    if bs_confidence != "低":
        if big_small == "大": nums = [n for n in nums if n >= 25] or nums
        elif big_small == "小": nums = [n for n in nums if n <= 24] or nums
    preferred = []
    if main_color:   preferred += [n for n in nums if get_color(n) == main_color]
    if second_color: preferred += [n for n in nums if get_color(n) == second_color and n not in preferred]
    rest = [n for n in nums if n not in preferred and not (exclude_color and get_color(n) == exclude_color)]
    pool = preferred + rest
    if len(pool) < 6: pool += [n for n in nums if n not in pool]
    recent = specials[-20:] if len(specials) >= 20 else specials
    omit_m = {}
    for n in pool:
        miss = 0
        for s in reversed(specials):
            if s == n: break
            miss += 1
        omit_m[n] = miss
    max_omit = max(omit_m.values()) or 1
    freq_m = {n: 0.0 for n in pool}
    for idx, s in enumerate(reversed(recent)):
        if s in freq_m: freq_m[s] += 1.0/(idx+1)
    scores = {n: (omit_m[n]/max_omit)*0.55 + freq_m[n]*0.45 for n in pool}
    ranked = sorted(pool, key=lambda n: scores[n], reverse=True)
    picked = ranked[:6]
    for n in pool:
        if n not in picked: picked.append(n)
        if len(picked) == 6: break
    return picked[:6], scores

# ---------- 独肖预测（返回得分）----------
def predict_single_zodiac_v2(draws: List[List[int]], window: int = 20,
                              weights: Tuple = None, decay: float = 0.25) -> Tuple[str, float]:
    if not draws or len(draws) < 5: return "马", 0.0
    if weights is None: weights = WEIGHT_CANDIDATES[0]
    w_freq,w_omit,w_momentum,w_cont,w_interval,w_special,w_position,w_neighbor = weights
    recent = draws[-window:] if len(draws)>=window else draws
    omit = {z:0 for z in ALL_ZODIACS}
    for z in ALL_ZODIACS:
        miss = 0
        for draw in reversed(draws):
            if any(get_zodiac(n)==z for n in draw): break
            miss += 1
        omit[z] = miss
    max_omit = max(omit.values()) or 1
    freq = {z:0.0 for z in ALL_ZODIACS}
    for i,draw in enumerate(reversed(recent)):
        w = math.exp(-decay*i)
        for n in draw[:6]: z = get_zodiac(n); freq[z] += w
        if len(draw)==7: z = get_zodiac(draw[6]); freq[z] += w*1.5
    max_freq = max(freq.values()) or 1
    mean_omit = sum(omit.values())/len(ALL_ZODIACS)
    momentum = {z: (omit[z]/max_omit)*0.15 if omit[z]>mean_omit else 0.0 for z in ALL_ZODIACS}
    intervals = {z:[] for z in ALL_ZODIACS}; last_seen = {z:-1 for z in ALL_ZODIACS}
    for pos,draw in enumerate(draws):
        appeared = {get_zodiac(n) for n in draw}
        for z in appeared:
            if last_seen[z]!=-1: intervals[z].append(pos-last_seen[z])
            last_seen[z] = pos
    interval_score = {}
    for z in ALL_ZODIACS:
        if not intervals[z]: interval_score[z]=0.0
        else:
            avg_int = sum(intervals[z])/len(intervals[z])
            ratio = omit[z]/avg_int if avg_int>0 else 0
            interval_score[z] = min(1.0, max(0, (ratio-0.8)*2))
    cont_bonus = {z:0.0 for z in ALL_ZODIACS}
    if len(draws)>=50:
        cont_count = total_opp = 0
        for i in range(len(draws)-50, len(draws)-1):
            prev_set = {get_zodiac(n) for n in draws[i]}
            curr_set = {get_zodiac(n) for n in draws[i+1]}
            common = prev_set & curr_set
            cont_count += len(common); total_opp += len(prev_set)
        if total_opp>0:
            actual_rate = cont_count/total_opp
            base = 1 - (11/12)**7
            if actual_rate > base+0.05:
                last_set = {get_zodiac(n) for n in draws[-1]}
                boost = (actual_rate-base)*0.5
                for z in last_set: cont_bonus[z] = boost
            elif actual_rate < base-0.05:
                last_set = {get_zodiac(n) for n in draws[-1]}
                penalty = (base-actual_rate)*0.3
                for z in last_set: cont_bonus[z] = -penalty
    special_omit = {}
    for z in ALL_ZODIACS:
        miss = 0
        for d in reversed(draws):
            if len(d)>=7:
                if get_zodiac(d[6])==z: break
            else:
                if get_zodiac(d[-1])==z: break
            miss += 1
        special_omit[z] = miss
    max_special_omit = max(special_omit.values()) or 1
    special_freq = {z:0.0 for z in ALL_ZODIACS}
    for i,d in enumerate(reversed(recent)):
        w = math.exp(-0.3*i)
        z = get_zodiac(d[6]) if len(d)>=7 else get_zodiac(d[-1])
        special_freq[z] += w
    max_special_freq = max(special_freq.values()) or 1
    special_score = {z: (special_omit[z]/max_special_omit)*0.3 + (special_freq[z]/max_special_freq)*0.7
                     for z in ALL_ZODIACS}
    pos_score = {z:0.0 for z in ALL_ZODIACS}
    for pos in range(6):
        pos_freq = {z:0 for z in ALL_ZODIACS}
        for draw in recent:
            if len(draw)>pos:
                sorted_nums = sorted(draw[:6])
                z = get_zodiac(sorted_nums[pos]); pos_freq[z] += 1
        if sum(pos_freq.values())>0:
            mx = max(pos_freq.values()) or 1
            for z in ALL_ZODIACS: pos_score[z] += pos_freq[z]/mx * (1.0/(pos+1))
    neighbor_score = {z:0.0 for z in ALL_ZODIACS}
    if draws and len(draws[-1])>=7:
        last_special = draws[-1][6]
        idx = ZODIAC_ORDER.get(get_zodiac(last_special))
        if idx is not None:
            prev_z = ALL_ZODIACS[(idx-1)%12]; next_z = ALL_ZODIACS[(idx+1)%12]
            cnt_prev = cnt_next = 0
            for i in range(max(0,len(draws)-50), len(draws)-1):
                curr_set = {get_zodiac(n) for n in draws[i+1]}
                if prev_z in curr_set: cnt_prev += 1
                if next_z in curr_set: cnt_next += 1
            total = min(50, len(draws)-1)
            if total>0:
                if cnt_prev/total>0.1: neighbor_score[prev_z] += 0.2
                if cnt_next/total>0.1: neighbor_score[next_z] += 0.2
    scores = {}
    for z in ALL_ZODIACS:
        scores[z] = (
            w_freq * freq[z]/max_freq + w_omit * omit[z]/max_omit +
            w_momentum * momentum[z] + w_cont * cont_bonus[z] +
            w_interval * interval_score[z] + w_special * special_score[z] +
            w_position * pos_score[z] + w_neighbor * neighbor_score[z]
        )
    best = max(scores, key=scores.get)
    return best, scores[best]

def auto_tune_single_zodiac_window(draws, test_periods=None):
    if test_periods is None: test_periods = max(5, min(10, len(draws)-21))
    if len(draws) < test_periods + 10: return 15, 0.25
    best_hits = -1; best_w, best_d = 15, 0.25
    for w, d in WINDOW_DECAY_CANDIDATES:
        if len(draws) < w + test_periods: continue
        hits = sum(1 for i in range(len(draws)-test_periods, len(draws))
                   if any(get_zodiac(n)==predict_single_zodiac_v2(draws[:i], window=w, decay=d)[0]
                          for n in draws[i]))
        if hits > best_hits: best_hits = hits; best_w, best_d = w, d
    return best_w, best_d

def select_best_weight(train_draws, test_periods=None):
    if test_periods is None: test_periods = max(5, min(8, len(train_draws)-10))
    if len(train_draws) < test_periods + 5: return WEIGHT_CANDIDATES[0]
    best_w, best_hits = None, -1
    for wt in WEIGHT_CANDIDATES:
        hits = sum(1 for i in range(len(train_draws)-test_periods, len(train_draws))
                   if any(get_zodiac(n)==predict_single_zodiac_v2(train_draws[:i], window=12, weights=wt)[0]
                          for n in train_draws[i]))
        if hits > best_hits: best_hits = hits; best_w = wt
    return best_w

def backtest_single_zodiac_v2(conn, recent_limit=DEFAULT_BACKTEST_LIMIT):
    rows = conn.execute("SELECT numbers_json, special_number FROM draws ORDER BY draw_date ASC, issue_no ASC").fetchall()
    draws = [json.loads(r["numbers_json"]) + [r["special_number"]] for r in rows]
    if len(draws) < recent_limit+10: return {"total":0,"hit":0,"periods":[]}
    total = hit = 0; periods = []; start = len(draws)-recent_limit
    for i in range(start, len(draws)):
        train = draws[:i]
        tp = max(5, min(10, len(train)-21))
        w, d = auto_tune_single_zodiac_window(train, test_periods=tp)
        best_weights = select_best_weight(train)
        pred, pred_score = predict_single_zodiac_v2(train, window=w, weights=best_weights, decay=d)
        is_hit = any(get_zodiac(n)==pred for n in draws[i])
        if is_hit: hit+=1
        total+=1
        periods.append({"idx":i-start+1,"pred":pred,"hit":is_hit,"window":w,"score":pred_score})
    return {"total":total,"hit":hit,"periods":periods}

# ---------- 数据库 ----------
@dataclass
class DrawRecord:
    issue_no: str; draw_date: str; numbers: List[int]; special_number: int
    def validate(self) -> bool:
        if not self.issue_no or not self.draw_date: return False
        if len(self.numbers) != 6: return False
        return all(n in VALID_NUMBERS for n in self.numbers + [self.special_number])

def utc_now() -> str: return datetime.now(timezone.utc).isoformat()
def connect_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path); conn.row_factory = sqlite3.Row; return conn

def init_db(conn):
    current_version = conn.execute("PRAGMA user_version").fetchone()[0]
    if current_version < 1:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS draws (issue_no TEXT PRIMARY KEY, draw_date TEXT NOT NULL,
                numbers_json TEXT NOT NULL, special_number INTEGER NOT NULL, source TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS prediction_runs (id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_no TEXT NOT NULL, strategy TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING',
                hit_count INTEGER, hit_rate REAL,
                created_at TEXT NOT NULL, reviewed_at TEXT, UNIQUE(issue_no, strategy));
            CREATE TABLE IF NOT EXISTS prediction_picks (id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL, pick_type TEXT NOT NULL DEFAULT 'MAIN',
                number INTEGER NOT NULL, rank INTEGER NOT NULL, score REAL NOT NULL, reason TEXT NOT NULL,
                UNIQUE(run_id, number), FOREIGN KEY(run_id) REFERENCES prediction_runs(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS prediction_pools (id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL, pool_size INTEGER NOT NULL, numbers_json TEXT NOT NULL,
                created_at TEXT NOT NULL, UNIQUE(run_id, pool_size),
                FOREIGN KEY(run_id) REFERENCES prediction_runs(id) ON DELETE CASCADE);
            CREATE TABLE IF NOT EXISTS model_state (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
        """)
        conn.execute("PRAGMA user_version = 1")
    if current_version < 2:
        for table, col, sql in [
            ("prediction_runs","special_hit","ALTER TABLE prediction_runs ADD COLUMN special_hit INTEGER"),
            ("prediction_runs","hit_count_10","ALTER TABLE prediction_runs ADD COLUMN hit_count_10 INTEGER"),
            ("prediction_runs","hit_rate_10","ALTER TABLE prediction_runs ADD COLUMN hit_rate_10 REAL"),
            ("prediction_runs","hit_count_14","ALTER TABLE prediction_runs ADD COLUMN hit_count_14 INTEGER"),
            ("prediction_runs","hit_rate_14","ALTER TABLE prediction_runs ADD COLUMN hit_rate_14 REAL"),
            ("prediction_runs","hit_count_20","ALTER TABLE prediction_runs ADD COLUMN hit_count_20 INTEGER"),
            ("prediction_runs","hit_rate_20","ALTER TABLE prediction_runs ADD COLUMN hit_rate_20 REAL"),
        ]:
            if not _column_exists(conn, table, col): conn.execute(sql)
        conn.execute("PRAGMA user_version = 2")
    _cleanup_stale_strategies(conn)
    conn.commit()

def _cleanup_stale_strategies(conn):
    ph = ",".join("?"*len(STRATEGY_IDS))
    stale = conn.execute(f"SELECT id FROM prediction_runs WHERE strategy NOT IN ({ph})", STRATEGY_IDS).fetchall()
    if not stale: return
    ids = [r["id"] for r in stale]; ph2 = ",".join("?"*len(ids))
    conn.execute(f"DELETE FROM prediction_picks WHERE run_id IN ({ph2})", ids)
    conn.execute(f"DELETE FROM prediction_pools WHERE run_id IN ({ph2})", ids)
    conn.execute(f"DELETE FROM prediction_runs WHERE id IN ({ph2})", ids)

def _column_exists(conn, table, col):
    return any(r["name"] == col for r in conn.execute(f"PRAGMA table_info({table})").fetchall())

def get_model_state(conn, key):
    row = conn.execute("SELECT value FROM model_state WHERE key=?", (key,)).fetchone()
    return str(row["value"]) if row else None

def set_model_state(conn, key, value):
    conn.execute("INSERT INTO model_state(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                 (key, value, utc_now()))

# ---------- 数据获取（问题#1不修改）----------
def _parse_marksix6_response(payload):
    records, errors = [], []
    hk_data = next((l for l in payload.get("lottery_data",[]) if l.get("name")=="新澳门彩"), None)
    if not hk_data:
        logger.warning("第三方数据中未找到'新澳门彩'")
        return records, 1
    try: t0 = datetime.strptime(hk_data.get("openTime",""), "%Y-%m-%d %H:%M:%S")
    except:
        logger.warning("无法解析 openTime，使用当前时间")
        t0 = datetime.now()
    for idx, item in enumerate(hk_data.get("history",[])):
        try:
            parts = item.split("期：")
            if len(parts) != 2: raise ValueError("分隔符异常")
            issue_no = parts[0].strip()
            nums = [int(n.strip()) for n in parts[1].split(",")]
            if len(nums) != 7: raise ValueError(f"号码数不为7: {len(nums)}")
            draw_date = (t0 - timedelta(days=idx)).strftime("%Y-%m-%d")
            r = DrawRecord(issue_no, draw_date, nums[:6], nums[6])
            if r.validate(): records.append(r)
            else: errors.append(f"验证失败: {item}")
        except Exception as e:
            errors.append(f"解析失败: {item[:50]}... 错误: {e}")
    if errors: logger.warning("第三方数据解析错误 %d 条: %s", len(errors), errors[:3])
    return records, 0

def _parse_official_json(payload):
    records, errors = [], []
    for item in payload:
        try:
            issue_no = str(item.get("drawNo") or item.get("issueNo") or "")
            draw_date = str(item.get("drawDate",""))[:10]
            numbers = [int(item[f"no{i}"]) for i in range(1,7)]
            special = int(item.get("specialNumber") or item.get("no7"))
            r = DrawRecord(issue_no, draw_date, numbers, special)
            if r.validate(): records.append(r)
            else: errors.append(f"验证失败: {item}")
        except Exception as e:
            errors.append(f"解析失败: {str(item)[:50]}... 错误: {e}")
    if errors: logger.warning("官方数据解析错误 %d 条", len(errors))
    return records

def fetch_online_records_with_multi_fallback(official_url, third_party_urls):
    stats = {"official_tried": False, "official_success": False, "third_party_tried": []}
    if official_url.strip():
        stats["official_tried"] = True
        try:
            req = Request(official_url, headers={"User-Agent":"Mozilla/5.0"})
            with urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8-sig"))
            records = _parse_official_json(payload)
            if records:
                stats["official_success"] = True
                return records, "official_api", official_url, stats
        except Exception as e: logger.warning("官方源失败: %s", e)
    for url in third_party_urls:
        stats["third_party_tried"].append(url)
        try:
            req = Request(url, headers={"User-Agent":"Mozilla/5.0"})
            with urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            if "marksix6.net" in url:
                records, err_flag = _parse_marksix6_response(payload)
                if records: return records, "third_party", url, stats
            else:
                records = _parse_official_json(payload)
                if records: return records, "third_party", url, stats
        except Exception as e: logger.warning("第三方源 %s 失败: %s", url, e)
    raise RuntimeError("所有新澳门数据源均无法获取数据。")

def upsert_draw(conn, record, source):
    now = utc_now()
    existing = conn.execute("SELECT numbers_json,special_number FROM draws WHERE issue_no=?", (record.issue_no,)).fetchone()
    if existing:
        if existing["numbers_json"] == json.dumps(record.numbers) and existing["special_number"] == record.special_number:
            return "unchanged"
        conn.execute("UPDATE draws SET numbers_json=?,special_number=?,source=?,updated_at=? WHERE issue_no=?",
                     (json.dumps(record.numbers), record.special_number, source, now, record.issue_no))
        return "updated"
    conn.execute("INSERT INTO draws VALUES(?,?,?,?,?,?,?)",
                 (record.issue_no, record.draw_date, json.dumps(record.numbers), record.special_number, source, now, now))
    return "inserted"

def sync_from_records(conn, records, source):
    ins = upd = 0
    for r in records:
        res = upsert_draw(conn, r, source)
        if res == "inserted": ins += 1
        elif res == "updated": upd += 1
    conn.commit(); return len(records), ins, upd

def next_issue(issue_no: str) -> str:
    if "/" in issue_no:
        prefix, last = issue_no.rsplit("/", 1)
        digits = "".join(c for c in last if c.isdigit())
        if not digits: return issue_no
        return f"{prefix}/{int(digits)+1:0{len(digits)}d}"
    import re
    parts = re.split(r'(\d+)', issue_no)
    last_digit_idx = None
    for idx in range(len(parts)-1, -1, -1):
        if parts[idx].isdigit():
            last_digit_idx = idx
            break
    if last_digit_idx is None:
        return issue_no
    orig = parts[last_digit_idx]
    parts[last_digit_idx] = str(int(orig) + 1).zfill(len(orig))
    return "".join(parts)

# ---------- 核心策略 ----------
def _normalize(m):
    vals = list(m.values()); mn, mx = min(vals), max(vals)
    if mx == mn: return {k:0.0 for k in m}
    return {k:(v-mn)/(mx-mn) for k,v in m.items()}

def _freq_map(draws):
    freq = {n:0.0 for n in ALL_NUMBERS}
    for draw in draws:
        for n in draw: freq[n] += 1.0
    return freq

def _omission_map(draws):
    omit = {n:float(len(draws)+1) for n in ALL_NUMBERS}
    for i, draw in enumerate(draws):
        for n in draw: omit[n] = min(omit[n], float(i+1))
    return omit

def _momentum_map(draws):
    m = {n:0.0 for n in ALL_NUMBERS}
    for i, draw in enumerate(draws):
        w = 1.0/(1.0+i)
        for n in draw: m[n] += w
    return m

def _pair_affinity_map(draws, window=200):
    pc = {}
    for draw in draws[:window]:
        s = sorted(draw)
        for i in range(len(s)):
            for j in range(i+1,len(s)):
                k=(s[i],s[j]); pc[k]=pc.get(k,0)+1
    social = {n:0.0 for n in ALL_NUMBERS}
    for (a,b),c in pc.items(): social[a]+=c; social[b]+=c
    return social

def _zone_heat_map(draws, window=80):
    zc = [0.0]*5
    for draw in draws[:window]:
        for n in draw: zc[min(4,(n-1)//10)] += 1.0
    if not draws[:window]: return {n:0.0 for n in ALL_NUMBERS}
    expected = 6.0*len(draws[:window])/5.0
    zs = [expected-c for c in zc]
    return {n:zs[min(4,(n-1)//10)] for n in ALL_NUMBERS}

def _number_clustering(draws, window=100):
    if not draws or len(draws) < 10: return {n:0.0 for n in ALL_NUMBERS}
    co = {}
    for draw in draws[:window]:
        s = sorted(draw)
        for i in range(len(s)):
            for j in range(i+1,len(s)):
                k=(min(s[i],s[j]),max(s[i],s[j])); co[k]=co.get(k,0)+1
    cl = {n:0.0 for n in ALL_NUMBERS}
    for (a,b),cnt in co.items():
        if cnt >= max(2,len(draws[:window])//20): cl[a]+=cnt*0.5; cl[b]+=cnt*0.5
    return cl

def _interval_pattern(draws):
    if not draws or len(draws) < 20: return {n:0.0 for n in ALL_NUMBERS}
    intervals = {n:[] for n in ALL_NUMBERS}; last_pos = {n:-1 for n in ALL_NUMBERS}
    for pos, draw in enumerate(draws):
        for n in draw:
            if last_pos[n] != -1: intervals[n].append(pos-last_pos[n])
            last_pos[n] = pos
    score = {n:0.0 for n in ALL_NUMBERS}
    for n in ALL_NUMBERS:
        if not intervals[n]: continue
        avg = sum(intervals[n])/len(intervals[n])
        if intervals[n][-1] < avg: score[n] += (avg-intervals[n][-1])/avg
    return score

def _position_weight_map(draws, window=100):
    if not draws: return {n:0.0 for n in ALL_NUMBERS}
    pd = {pos:{n:0 for n in ALL_NUMBERS} for pos in range(6)}
    for draw in draws[:window]:
        for pos,num in enumerate(sorted(draw)): pd[pos][num] += 1
    pw = {n:0.0 for n in ALL_NUMBERS}
    for n in ALL_NUMBERS:
        for pos in range(6):
            cnt = pd[pos].get(n,0)
            if cnt: pw[n] += cnt*(1.0-pos*0.1 if n<=25 else 0.4+pos*0.1)
    return pw

def _consensus_boost(score_maps, top_n=15):
    consensus = {n:0 for n in ALL_NUMBERS}
    for sm in score_maps:
        for n,_ in sorted(sm.items(), key=lambda x:x[1], reverse=True)[:top_n]:
            consensus[n] += 1
    return {n:consensus[n]/len(score_maps) for n in ALL_NUMBERS}

def _pick_top_six(scores, reason):
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    picked = []

    def _zone(n):
        return min(4, (n - 1) // 10)

    def _tail(n):
        return n % 10

    def _count_consecutive_pairs(nums):
        s = sorted(nums)
        pairs = sum(1 for i in range(len(s) - 1) if s[i+1] - s[i] == 1)
        return pairs

    for n, s in ranked:
        if len(picked) == 6:
            break
        proposal = [pn for pn, _ in picked] + [n]

        zc = {}
        for x in proposal:
            z = _zone(x)
            zc[z] = zc.get(z, 0) + 1
        if any(c >= 4 for c in zc.values()):
            continue

        tc = {}
        for x in proposal:
            t = _tail(x)
            tc[t] = tc.get(t, 0) + 1
        if any(c >= 3 for c in tc.values()):
            continue

        if _count_consecutive_pairs(proposal) > 2:
            continue

        picked.append((n, s))

    if len(picked) < 6:
        pns = {pn for pn, _ in picked}
        for n, s in ranked:
            if n not in pns:
                picked.append((n, s))
            if len(picked) == 6:
                break

    return [(n, idx+1, s, f"{reason} score={s:.4f}") for idx, (n, s) in enumerate(picked)]

def _default_mined_config():
    return {"window":80.0,"w_freq":0.40,"w_omit":0.30,"w_mom":0.20,"w_pair":0.05,"w_zone":0.05,"special_bonus":0.10}

def _apply_weight_config(draws, config, reason):
    ws = int(config.get("window",80))
    window = draws[:max(20,ws)]
    freq=_normalize(_freq_map(window)); omit=_normalize(_omission_map(window))
    mom=_normalize(_momentum_map(window))
    pair=_normalize(_pair_affinity_map(window, window=min(200,len(window))))
    zone=_normalize(_zone_heat_map(window, window=min(80,len(window))))
    cl=_normalize(_number_clustering(window, window=min(100,len(window))))
    tm=_normalize(_interval_pattern(window))
    pos=_normalize(_position_weight_map(window, window=min(100,len(window))))
    wf=float(config.get("w_freq",0.35)); wo=float(config.get("w_omit",0.25))
    wm=float(config.get("w_mom",0.15)); wp=float(config.get("w_pair",0.05)); wz=float(config.get("w_zone",0.05))
    scores = {n: freq[n]*wf+omit[n]*wo+mom[n]*wm+pair[n]*wp+zone[n]*wz+cl[n]*0.06+tm[n]*0.06+pos[n]*0.03
              for n in ALL_NUMBERS}
    picks = _pick_top_six(scores, reason)
    main_set = {n for n,_,_,_ in picks}
    cands = [(n,s) for n,s in sorted(scores.items(),key=lambda x:x[1],reverse=True) if n not in main_set]
    if not cands: cands = sorted(scores.items(),key=lambda x:x[1],reverse=True)
    return picks, cands[0][0], cands[0][1], scores

def _ensemble_strategy(draws, mined_cfg=None):
    cfg = mined_cfg or _default_mined_config()
    subs = [
        _apply_weight_config(draws,{"window":30,"w_freq":0.80,"w_omit":0.00,"w_mom":0.20,"w_pair":0.00,"w_zone":0.00},"热号"),
        _apply_weight_config(draws,{"window":120,"w_freq":0.00,"w_omit":0.70,"w_mom":0.30,"w_pair":0.00,"w_zone":0.00},"冷号"),
        _apply_weight_config(draws,{"window":20,"w_freq":0.10,"w_omit":0.00,"w_mom":0.90,"w_pair":0.00,"w_zone":0.00},"动量"),
        _apply_weight_config(draws,{"window":80,"w_freq":0.40,"w_omit":0.30,"w_mom":0.20,"w_pair":0.05,"w_zone":0.05},"平衡"),
        _apply_weight_config(draws,cfg,"规律挖掘"),
    ]
    sw = [0.18,0.18,0.18,0.23,0.23]
    votes = {n:0.0 for n in ALL_NUMBERS}
    for (_,_,_,sm),w in zip(subs,sw):
        for rank,(n,_) in enumerate(sorted(sm.items(),key=lambda x:x[1],reverse=True)):
            votes[n] += (49-rank)*w
    consensus = _normalize(_consensus_boost([s[3] for s in subs]))
    voted = _normalize(votes)
    final = _normalize({n:voted[n]*0.70+consensus[n]*0.30 for n in ALL_NUMBERS})
    picked = _pick_top_six(final,"集成+交集")
    main_set = {n for n,_,_,_ in picked}
    cands = [(n,s) for n,s in sorted(final.items(),key=lambda x:x[1],reverse=True) if n not in main_set]
    if not cands: cands = sorted(final.items(),key=lambda x:x[1],reverse=True)
    return picked, cands[0][0], cands[0][1], final

def generate_strategy(draws, strategy, mined_cfg):
    cfgs = {
        "hot_v1":         {"window":30,"w_freq":0.80,"w_omit":0.00,"w_mom":0.20,"w_pair":0.00,"w_zone":0.00},
        "cold_rebound_v1":{"window":120,"w_freq":0.00,"w_omit":0.70,"w_mom":0.30,"w_pair":0.00,"w_zone":0.00},
        "momentum_v1":    {"window":20,"w_freq":0.10,"w_omit":0.00,"w_mom":0.90,"w_pair":0.00,"w_zone":0.00},
        "balanced_v1":    {"window":80,"w_freq":0.40,"w_omit":0.30,"w_mom":0.20,"w_pair":0.05,"w_zone":0.05},
        "pattern_mined_v1": mined_cfg or _default_mined_config(),
    }
    if strategy == "ensemble_v2": return _ensemble_strategy(draws, mined_cfg)
    return _apply_weight_config(draws, cfgs.get(strategy, _default_mined_config()),
                                 STRATEGY_LABELS.get(strategy, strategy))

def _build_candidate_pools(scores, main6):
    ranked = [n for n,_ in sorted(scores.items(),key=lambda x:x[1],reverse=True)]
    rest = [n for n in ranked if n not in main6]
    return {6:main6, 10:main6+rest[:max(0,10-len(main6))],
            14:main6+rest[:max(0,14-len(main6))], 20:main6+rest[:max(0,20-len(main6))]}

def _pool_hit_count(pool, winning):
    return sum(1 for n in pool if n in winning)

def _save_prediction_pools(conn, run_id, pools):
    conn.execute("DELETE FROM prediction_pools WHERE run_id=?", (run_id,))
    now = utc_now()
    for size, nums in pools.items():
        conn.execute("INSERT INTO prediction_pools(run_id,pool_size,numbers_json,created_at) VALUES(?,?,?,?)",
                     (run_id, size, json.dumps(nums), now))

def generate_predictions(conn, issue_no=None, mined_cfg_override=None):
    row = conn.execute("SELECT issue_no FROM draws ORDER BY draw_date DESC, issue_no DESC LIMIT 1").fetchone()
    if not row: raise RuntimeError("数据库中无开奖记录。")
    target = issue_no or next_issue(row["issue_no"])
    draws = [json.loads(r["numbers_json"]) for r in
             conn.execute("SELECT numbers_json FROM draws ORDER BY draw_date DESC, issue_no DESC LIMIT 200").fetchall()]
    if len(draws) < 20: raise RuntimeError("需要至少 20 期数据。")
    mined_cfg = mined_cfg_override or (json.loads(get_model_state(conn, MINED_CONFIG_KEY) or "null") or _default_mined_config())
    for strategy in STRATEGY_IDS:
        existing = conn.execute("SELECT id,status FROM prediction_runs WHERE issue_no=? AND strategy=?",
                                (target, strategy)).fetchone()
        if existing and existing["status"] == "REVIEWED": continue
        cur = conn.execute("INSERT OR REPLACE INTO prediction_runs(issue_no,strategy,status,created_at) VALUES(?,?,'PENDING',?)",
                          (target, strategy, utc_now()))
        run_id = cur.lastrowid
        picks, snum, sscore, scores = generate_strategy(draws, strategy, mined_cfg)
        main_numbers = [n for n,_,_,_ in picks]
        conn.executemany("INSERT OR REPLACE INTO prediction_picks(run_id,pick_type,number,rank,score,reason) VALUES(?,?,?,?,?,?)",
                         [(run_id,"MAIN",n,rank,score,reason) for n,rank,score,reason in picks] +
                         [(run_id,"SPECIAL",snum,1,sscore,"特别号")])
        _save_prediction_pools(conn, run_id, _build_candidate_pools(scores, main_numbers))
    conn.commit(); return target

def review_issue(conn, issue_no):
    draw = conn.execute("SELECT numbers_json,special_number FROM draws WHERE issue_no=?", (issue_no,)).fetchone()
    if not draw: return 0
    winning = set(json.loads(draw["numbers_json"])); ws = int(draw["special_number"])
    runs = conn.execute("SELECT id FROM prediction_runs WHERE issue_no=? AND status='PENDING'", (issue_no,)).fetchall()
    for run in runs:
        rid = run["id"]
        mains = [r["number"] for r in conn.execute("SELECT number FROM prediction_picks WHERE run_id=? AND pick_type='MAIN' ORDER BY rank",(rid,)).fetchall()]
        special = next((r["number"] for r in conn.execute("SELECT number FROM prediction_picks WHERE run_id=? AND pick_type='SPECIAL'",(rid,)).fetchall()), None)
        def gp(size):
            r = conn.execute("SELECT numbers_json FROM prediction_pools WHERE run_id=? AND pool_size=?",(rid,size)).fetchone()
            return json.loads(r["numbers_json"]) if r else mains
        hc=_pool_hit_count(mains,winning); h10=_pool_hit_count(gp(10),winning)
        h14=_pool_hit_count(gp(14),winning); h20=_pool_hit_count(gp(20),winning)
        conn.execute("""UPDATE prediction_runs SET status='REVIEWED',hit_count=?,hit_rate=?,
            hit_count_10=?,hit_rate_10=?,hit_count_14=?,hit_rate_14=?,
            hit_count_20=?,hit_rate_20=?,special_hit=?,reviewed_at=? WHERE id=?""",
            (hc,hc/6.0,h10,h10/6.0,h14,h14/6.0,h20,h20/6.0,1 if special==ws else 0,utc_now(),rid))
    conn.commit(); return len(runs)

def backfill_missing_special_picks(conn):
    patched = 0
    for run in conn.execute("SELECT id,strategy FROM prediction_runs WHERE status='PENDING'").fetchall():
        rid = run["id"]
        if conn.execute("SELECT 1 FROM prediction_picks WHERE run_id=? AND pick_type='SPECIAL'",(rid,)).fetchone(): continue
        mains = [r["number"] for r in conn.execute("SELECT number FROM prediction_picks WHERE run_id=? AND pick_type='MAIN'",(rid,)).fetchall()]
        draws = [json.loads(r["numbers_json"]) for r in conn.execute("SELECT numbers_json FROM draws ORDER BY draw_date DESC, issue_no DESC LIMIT 200").fetchall()]
        mined_cfg = json.loads(get_model_state(conn,MINED_CONFIG_KEY) or "null") or _default_mined_config()
        _, snum, sscore, scores = generate_strategy(draws, run["strategy"], mined_cfg)
        if snum in mains:
            for n,_ in sorted(scores.items(),key=lambda x:x[1],reverse=True):
                if n not in mains: snum = n; break
        conn.execute("INSERT OR REPLACE INTO prediction_picks(run_id,pick_type,number,rank,score,reason) VALUES(?,'SPECIAL',?,1,?,'补齐')",
                     (rid,snum,sscore)); patched += 1
    if patched: conn.commit()
    return patched

def auto_tune_mined_config(conn, recent_runs=20):
    old_cfg = json.loads(get_model_state(conn,MINED_CONFIG_KEY) or "null") or _default_mined_config()
    cfg = dict(old_cfg)
    rows = conn.execute("SELECT hit_count FROM prediction_runs WHERE strategy='pattern_mined_v1' AND status='REVIEWED' ORDER BY id DESC LIMIT ?",(recent_runs,)).fetchall()
    if len(rows) < 5: logger.info("复盘数据不足，跳过调优。"); return old_cfg, old_cfg
    avg = sum(r["hit_count"] for r in rows)/len(rows)
    logger.info("近期规律挖掘平均命中: %.2f", avg)
    delta = 0.03
    wf=cfg.get("w_freq",0.40); wm=cfg.get("w_mom",0.20); wo=cfg.get("w_omit",0.30)
    if avg < 1.8: wf=max(0.15,wf-delta); wm=min(0.50,wm+delta)
    elif avg > 2.5: wf=min(0.50,wf+delta); wm=max(0.10,wm-delta)
    else: logger.info("当前表现合理，不调整。"); return old_cfg, old_cfg
    wo = max(0.0, wo-(wf+wm-cfg.get("w_freq",0.40)-cfg.get("w_mom",0.20)))
    cfg.update({"w_freq":round(wf,4),"w_omit":round(wo,4),"w_mom":round(wm,4)})
    set_model_state(conn, MINED_CONFIG_KEY, json.dumps(cfg, ensure_ascii=False))
    logger.info("已更新规律挖掘权重: freq=%.3f, omit=%.3f, mom=%.3f", wf, wo, wm)
    return old_cfg, cfg

def _build_color_advice(conf_data, conf_level, mc, sc_color, ec):
    d = conf_data.get(conf_level,{})
    if not d or d["total"] < 5: return f"→ 历史样本不足（{d.get('total',0)}期），建议观望"
    mr = d["main_hit"]/d["total"]; tr = d["two_color_hit"]/d["total"]
    emoji = {"高":"🟢","中":"🟡","低":"🔴"}[conf_level]
    if mr >= 1/3+0.10: return f"→ {emoji} 建议主推 {mc}（历史命中 {mr*100:.0f}%，高于基线33%）"
    if mr <= 1/3-0.05: return f"→ {emoji} 主推 {mc} 风险较高（历史仅 {mr*100:.0f}%），建议转投 {sc_color}/{ec}"
    if tr >= 2/3+0.05: return f"→ {emoji} 建议两色 {mc}/{sc_color}，排除 {ec}（两色历史 {tr*100:.0f}%）"
    return f"→ {emoji} 各指标接近随机基线，建议观望"

def _build_bs_advice(gap_conf_data, conf_level, pred):
    """新增：大小主推建议，格式对齐 _build_color_advice。"""
    d = gap_conf_data.get(conf_level,{})
    if not d or d["total"] < 5: return f"→ 历史样本不足（{d.get('total',0)}期），建议观望"
    r = d["hit"]/d["total"]
    other = "小" if pred == "大" else "大"
    emoji = {"高":"🟢","中":"🟡","低":"🔴"}[conf_level]
    if r >= 0.5+0.10: return f"→ {emoji} 建议主推 {pred}（历史命中 {r*100:.0f}%，高于基线50%）"
    if r <= 0.5-0.05: return f"→ {emoji} 主推 {pred} 风险较高（历史仅 {r*100:.0f}%），建议转投次推 {other}"
    return f"→ {emoji} 各指标接近随机基线，建议观望"

def _build_oe_advice(gap_conf_data, conf_level, pred):
    """与 _build_bs_advice 完全对齐的单双建议。"""
    d = gap_conf_data.get(conf_level,{})
    if not d or d["total"] < 5: return f"→ 历史样本不足（{d.get('total',0)}期），建议观望"
    r = d["hit"]/d["total"]
    other = "双" if pred == "单" else "单"
    emoji = {"高":"🟢","中":"🟡","低":"🔴"}[conf_level]
    if r >= 0.5+0.10: return f"→ {emoji} 建议主推 {pred}（历史命中 {r*100:.0f}%，高于基线50%）"
    if r <= 0.5-0.05: return f"→ {emoji} 主推 {pred} 风险较高（历史仅 {r*100:.0f}%），建议转投次推 {other}"
    return f"→ {emoji} 各指标接近随机基线，建议观望"

# ---------- 仪表盘（美化版，含单双预测）----------
def print_dashboard(conn, color_window=None, color_method="weighted", backtest_limit=DEFAULT_BACKTEST_LIMIT):
    print("="*70)
    print("⚠️  免责声明：彩票开奖为独立随机事件，所有预测算法及回测数据均不代表")
    print("   真实预测能力，历史命中率不能预测未来表现，请勿用于实际下注决策。")
    print("="*70)
    backfill_missing_special_picks(conn)
    latest = conn.execute("SELECT * FROM draws ORDER BY draw_date DESC, issue_no DESC LIMIT 1").fetchone()
    if latest:
        nums = " ".join(f"{n:02d}" for n in json.loads(latest["numbers_json"]))
        print(f"最新开奖: {latest['issue_no']} | {nums} + {latest['special_number']:02d}")

    all_rows = conn.execute("SELECT special_number FROM draws ORDER BY draw_date ASC, issue_no ASC").fetchall()
    all_specials = [r["special_number"] for r in all_rows]
    train_specials = all_specials[:-1] if len(all_specials) > 1 else all_specials

    if len(train_specials) >= 30:
        cw = color_window if color_window is not None else auto_tune_color_window(train_specials)
        bs_w = auto_tune_bs_window(train_specials)
    else:
        cw = color_window if color_window is not None else 8
        bs_w = 8
    print(f"🔧 实时预测调优窗口: 波色={cw}期  大小={bs_w}期")

    pred_mc = pred_sc_color = pred_ec = None
    pred_ms = pred_ss = 0.0
    conf_level = "低"
    pred_bs = None; bs_gap = 0.0; bs_conf_str = "低"; bs_ce = ""
    pred_oe = None; oe_gap = 0.0; oe_conf_str = "低"; oe_ce = ""
    if len(train_specials) >= 20:
        pred_mc, pred_sc_color, pred_ec, pred_ms, pred_ss, _ = predict_color_ensemble(train_specials, method=color_method)
        conf_level, conf_gap_val = color_confidence_dynamic(train_specials, pred_ms, pred_ss, window=cw, method=color_method)
        pred_bs, bs_gap = predict_big_small_ensemble(train_specials)
        pred_bs, bs_ce = apply_bs_correction(train_specials, pred_bs)
        bs_conf_str = "高" if bs_gap>=BS_GAP_HIGH else "中" if bs_gap>=BS_GAP_MEDIUM else "低"
        pred_oe, oe_gap = predict_odd_even_ensemble(train_specials)
        pred_oe, oe_ce = apply_oe_correction(train_specials, pred_oe)
        oe_conf_str = "高" if oe_gap>=OE_GAP_HIGH else "中" if oe_gap>=OE_GAP_MEDIUM else "低"

    if len(train_specials) >= 20:
        risk_score, color_rate, bs_rate, oe_rate = calc_risk_score(
            train_specials, conf_level, bs_conf_str, bs_gap, pred_ms - pred_ss, oe_conf=oe_conf_str)
        r_emoji, r_level, r_msg = risk_level(risk_score)
        print(f"\n{'='*50}")
        print(f"⚖️  本期综合风险评级：{r_emoji} {r_level}")
        print(f"   {r_msg}")
        print(f"\n   各维度建议：")
        print(build_dimension_advice(conf_level, bs_conf_str, bs_ce, bs_rate,
                                      color_rate, bs_gap, pred_ms - pred_ss, bs_conf_str,
                                      oe_conf_str=oe_conf_str, oe_ce=oe_ce, oe_rate=oe_rate))
        print(f"{'='*50}")

    pending = conn.execute("SELECT id,issue_no,strategy FROM prediction_runs WHERE status='PENDING' ORDER BY strategy").fetchall()
    if pending:
        print(f"\n预测期号: {pending[0]['issue_no']}")
        for r in pending:
            mains = [str(x["number"]).zfill(2) for x in conn.execute("SELECT number FROM prediction_picks WHERE run_id=? AND pick_type='MAIN' ORDER BY rank",(r["id"],)).fetchall()]
            special_row = conn.execute("SELECT number FROM prediction_picks WHERE run_id=? AND pick_type='SPECIAL'",(r["id"],)).fetchone()
            special = str(special_row["number"]).zfill(2) if special_row else "--"
            label = STRATEGY_LABELS.get(r["strategy"], r["strategy"])
            print(f"  {label:　<8s}: {' '.join(mains)} + {special}")
            if special_row:
                a = special_attributes(special_row["number"])
                print(f"         特码属性: {a['单双']}/{a['大小']} 合{a['合单双']}/{a['合大小']} 尾{a['尾大小']} {a['色波']} {a['五行']} | {a['生肖']}属")

    # ---- 大小预测（主推/次推）----
    if len(train_specials) >= 20:
        bs_other = "小" if pred_bs == "大" else "大"
        bs_conf_emoji = "🟢高" if bs_gap>=BS_GAP_HIGH else "🟡中" if bs_gap>=BS_GAP_MEDIUM else "🔴低"
        print(f"\n🔢 特码大小预测（实时，含连错纠正）：")
        print(f"   主推: {pred_bs}   次推: {bs_other}   信心度: {bs_conf_emoji}{bs_ce}（差值 {bs_gap:.3f}）")
        if bs_conf_str == "低":
            print(f"   ⚠️ 信心度低，生肖漏斗已跳过大小筛选")

        bs_conf_data = backtest_big_small_by_confidence(conn, recent_limit=backtest_limit)
        print(f"\n📊 大小信心度分组命中率（近{backtest_limit}期，基线50%）：")
        usable = False
        for lv in ["高","中","低"]:
            d = bs_conf_data.get(lv,{})
            if not d or d["total"]==0: continue
            rate = d["hit"]/d["total"]
            flag = "✅" if rate >= 0.50 else "❌"
            emoji = {"高":"🟢","中":"🟡","低":"🔴"}[lv]
            print(f"   {emoji}{lv}信心: {d['hit']}/{d['total']} ({rate*100:.1f}%) {flag}")
            if lv == "高" and rate >= 0.50: usable = True
        if not usable:
            print(f"   ⚠️ 高信心组命中率未达50%，大小预测不建议参考")
        print(f"   {_build_bs_advice(bs_conf_data, bs_conf_str, pred_bs)}")

        bt_bs = backtest_big_small_only(conn, recent_limit=backtest_limit)
        if bt_bs and bt_bs["big_small"]["total"] > 0:
            d = bt_bs["big_small"]; t = d["total"]
            flag = "✅跑赢" if d["hit"]/t>=0.50 else "❌低于基线"
            print(f"\n📊 大小近{backtest_limit}期滚动命中率：{d['hit']}/{t} ({d['hit']/t*100:.1f}%) {flag}")
            print(f"\n   近 {min(backtest_limit,t)} 期逐期明细：")
            for p in d["periods"][-min(backtest_limit,t):]:
                mark = "▲" if p["hit"] else "✗"
                print(f"     第{p['idx']:02d}期: 大小 预{p['pred']}→实{p['actual']}({p['actual_num']:02d}) {mark}")

    # ---- 单双预测（主推/次推，新增，结构对齐大小预测）----
    if len(train_specials) >= 20:
        oe_other = "双" if pred_oe == "单" else "单"
        oe_conf_emoji = "🟢高" if oe_gap>=OE_GAP_HIGH else "🟡中" if oe_gap>=OE_GAP_MEDIUM else "🔴低"
        print(f"\n🔢 特码单双预测（实时，含连错纠正）：")
        print(f"   主推: {pred_oe}   次推: {oe_other}   信心度: {oe_conf_emoji}{oe_ce}（差值 {oe_gap:.3f}）")
        if oe_conf_str == "低":
            print(f"   ⚠️ 信心度低，本期单双信号偏弱，建议观望")

        oe_conf_data = backtest_odd_even_by_confidence(conn, recent_limit=backtest_limit)
        print(f"\n📊 单双信心度分组命中率（近{backtest_limit}期，基线50%）：")
        oe_usable = False
        for lv in ["高","中","低"]:
            d = oe_conf_data.get(lv,{})
            if not d or d["total"]==0: continue
            rate = d["hit"]/d["total"]
            flag = "✅" if rate >= 0.50 else "❌"
            emoji = {"高":"🟢","中":"🟡","低":"🔴"}[lv]
            print(f"   {emoji}{lv}信心: {d['hit']}/{d['total']} ({rate*100:.1f}%) {flag}")
            if lv == "高" and rate >= 0.50: oe_usable = True
        if not oe_usable:
            print(f"   ⚠️ 高信心组命中率未达50%，单双预测不建议参考")
        print(f"   {_build_oe_advice(oe_conf_data, oe_conf_str, pred_oe)}")

        bt_oe = backtest_odd_even_only(conn, recent_limit=backtest_limit)
        if bt_oe and bt_oe["odd_even"]["total"] > 0:
            d = bt_oe["odd_even"]; t = d["total"]
            flag = "✅跑赢" if d["hit"]/t>=0.50 else "❌低于基线"
            print(f"\n📊 单双近{backtest_limit}期滚动命中率：{d['hit']}/{t} ({d['hit']/t*100:.1f}%) {flag}")
            print(f"\n   近 {min(backtest_limit,t)} 期逐期明细：")
            for p in d["periods"][-min(backtest_limit,t):]:
                mark = "▲" if p["hit"] else "✗"
                print(f"     第{p['idx']:02d}期: 单双 预{p['pred']}→实{p['actual']}({p['actual_num']:02d}) {mark}")

    # ---- 波色预测（主推/次推/排除，原有结构）----
    if pred_mc:
        conf_data = backtest_colors_by_confidence(conn, recent_limit=backtest_limit)
        conf_level, conf_gap = color_confidence_dynamic(train_specials, pred_ms, pred_ss, window=cw, method=color_method)
        conf_emoji = {"高":"🟢","中":"🟡","低":"🔴"}[conf_level]
        print(f"\n🎨 特码波色预测（实时，窗口{cw}期）：")
        print(f"   主推: {pred_mc}   次推: {pred_sc_color}   排除: {pred_ec}")
        print(f"   信心度: {conf_emoji} {conf_level}（差值 {conf_gap:.3f}）")
        print(f"   {_build_color_advice(conf_data, conf_level, pred_mc, pred_sc_color, pred_ec)}")
        t_total,mh,sh,ah = backtest_colors(conn, recent_limit=backtest_limit)
        if t_total > 0:
            print(f"\n📊 波色滚动回测（近{backtest_limit}期）：")
            print(f"   主推命中: {mh}/{t_total} ({mh/t_total*100:.1f}%)  次推: {sh}/{t_total} ({sh/t_total*100:.1f}%)  二中一: {ah}/{t_total} ({ah/t_total*100:.1f}%)")
        if conf_data:
            print(f"\n🔍 信心度分组回测（近{backtest_limit}期）：")
            for lv in ["高","中","低"]:
                d = conf_data.get(lv,{})
                if not d or d["total"]==0: continue
                t=d["total"]; mhl=d["main_hit"]; th=d["two_color_hit"]
                diff = mhl/t-1/3
                emoji = {"高":"🟢","中":"🟡","低":"🔴"}[lv]
                print(f"   {emoji}{lv:<5} {t:<6} {mhl}/{t} ({mhl/t*100:.1f}%)  {th}/{t} ({th/t*100:.1f}%)  {'+' if diff>=0 else ''}{diff*100:.1f}%")
        specials_d = [r["special_number"] for r in conn.execute("SELECT special_number FROM draws ORDER BY draw_date ASC, issue_no ASC").fetchall()]
        detail_limit = min(backtest_limit, len(specials_d)-10)
        if detail_limit > 0:
            print(f"\n   近 {detail_limit} 期逐期明细：")
            for i in range(len(specials_d)-detail_limit, len(specials_d)):
                train = specials_d[:i]; actual_num = specials_d[i]; actual_color = get_color(actual_num)
                w = auto_tune_color_window(train) if len(train)>=30 else 8
                m,s,excl,mms,sss,_ = predict_color(train, window=w, method=color_method)
                lvl, gap = color_confidence_dynamic(train, mms, sss, window=w, method=color_method)
                mark = "▲" if m==actual_color else "△" if s==actual_color else "✗"
                two_ok = "✓排除对" if actual_color!=excl else "✗排除错"
                emoji = {"高":"🟢","中":"🟡","低":"🔴"}[lvl]
                print(f"     第{i-(len(specials_d)-detail_limit)+1:02d}期: {emoji} 推{m}/{s} 排{excl}(差{gap:.3f}) → {actual_color}({actual_num:02d}) {mark} {two_ok}")
    else:
        print("\n特码数据不足，无法预测波色。")

    if len(train_specials) >= 20:
        pred_zocs, zodiac_scores = predict_zodiac(train_specials, window=cw, big_small=pred_bs,
                                                  main_color=pred_mc, second_color=pred_sc_color,
                                                  exclude_color=pred_ec, bs_confidence=bs_conf_str)
        pred_nums, num_scores = predict_special_nums_from_zodiacs(
            train_specials, pred_zocs, big_small=pred_bs,
            main_color=pred_mc, second_color=pred_sc_color,
            exclude_color=pred_ec, bs_confidence=bs_conf_str)
        bs_filter_note = f"大小:{pred_bs}({'跳过' if bs_conf_str=='低' else '生效'})"
        print(f"\n🐎 特码生肖预测（三级漏斗 {bs_filter_note} → 波色:{pred_mc}/{pred_sc_color} → 遗漏频率）：")
        score_vals = list(zodiac_scores.values())
        if score_vals:
            sorted_scores_z = sorted(score_vals)
            nz = len(sorted_scores_z)
            hi_z = sorted_scores_z[int(nz*2/3)] if nz>=3 else sorted_scores_z[-1]
            lo_z = sorted_scores_z[int(nz*1/3)] if nz>=3 else sorted_scores_z[0]
        else:
            hi_z = lo_z = 0
        zodiac_parts = []
        for z in pred_zocs:
            z_score = zodiac_scores.get(z, 0)
            level = "高" if z_score >= hi_z else "中" if z_score >= lo_z else "低"
            emoji = {"高":"🟢","中":"🟡","低":"🔴"}[level]
            zodiac_parts.append(f"{emoji}{z}({z_score:.2f})")
        print(f"   五肖: {'  '.join(zodiac_parts)}")
        num_score_vals = [num_scores.get(n, 0) for n in pred_nums]
        if num_score_vals:
            sorted_ns = sorted(num_score_vals)
            nn = len(sorted_ns)
            hi_n = sorted_ns[int(nn*2/3)] if nn>=3 else sorted_ns[-1]
            lo_n = sorted_ns[int(nn*1/3)] if nn>=3 else sorted_ns[0]
        else:
            hi_n = lo_n = 0
        num_parts = []
        detail_parts = []
        for n in sorted(pred_nums):
            n_score = num_scores.get(n, 0)
            level = "高" if n_score >= hi_n else "中" if n_score >= lo_n else "低"
            emoji = {"高":"🟢","中":"🟡","低":"🔴"}[level]
            num_parts.append(f"{n:02d}{emoji}")
            detail_parts.append(f"{n:02d}({get_zodiac(n)}/{get_color(n)}){emoji}")
        print(f"   特别号码组(6个): {' '.join(num_parts)}")
        print(f"   号码详情: {'  '.join(detail_parts)}")

        bt_zod = backtest_zodiac_and_special_nums(conn, recent_limit=backtest_limit)
        if bt_zod:
            zd=bt_zod["zodiac"]; sn=bt_zod["special_nums"]; t_z=zd["total"]
            if t_z > 0:
                zr=zd["hit"]/t_z; nr=sn["hit"]/t_z; nb=6/49
                print(f"\n📊 生肖+特别号码回测（近{backtest_limit}期）：")
                print(f"   五肖命中: {zd['hit']}/{t_z} ({zr*100:.1f}%) {'✅跑赢基线' if zr>0.417 else '❌低于基线（理论41.7%）'}")
                print(f"   六码命中: {sn['hit']}/{t_z} ({nr*100:.1f}%) {'✅跑赢基线' if nr>nb else f'❌低于基线（理论{nb*100:.1f}%）'}  基线{nb*100:.1f}%")
                d_lim = min(backtest_limit, t_z)
                print(f"\n   近 {d_lim} 期逐期明细：")
                for zp,sp in zip(zd["periods"][-d_lim:], sn["periods"][-d_lim:]):
                    bs_tag = f"{zp['big_small']}{'↓' if zp.get('bs_conf','高')=='低' else ''}"
                    top3 = zp["pred"][:3]
                    z_sc = zp.get("zodiac_scores", {})
                    zodiac_str = " ".join(f"{z}({z_sc.get(z,0):.2f})" for z in top3)
                    n_sc = sp.get("num_scores", {})
                    nums_str = " ".join(f"{n:02d}({n_sc.get(n,0):.2f})" for n in sorted(sp["pred_nums"]))
                    zh_mark = "▲" if zp["hit"] else "✗"
                    num_mark = "▲" if sp["hit"] else "✗"
                    print(f"     第{zp['idx']:02d}期({bs_tag}/{zp['main_color']}{zp['second_color']}): "
                          f"五肖 预[{zodiac_str}]→实{zp['actual']}{zh_mark} | "
                          f"六码 [{nums_str}]→实{sp['actual_num']:02d}{num_mark}")

        full_rows = conn.execute("SELECT numbers_json, special_number FROM draws ORDER BY draw_date ASC, issue_no ASC").fetchall()
        full_draws = [json.loads(r["numbers_json"]) + [r["special_number"]] for r in full_rows]
        if len(full_draws) > 1:
            train_full = full_draws[:-1]
            tp = max(5, min(10, len(train_full)-21))
            sz_window, sz_decay = auto_tune_single_zodiac_window(train_full, test_periods=tp)
            best_weights = select_best_weight(train_full)
            single_zod, single_score = predict_single_zodiac_v2(train_full, window=sz_window, weights=best_weights, decay=sz_decay)
            print(f"\n🎯 独胆生肖预测（增强版，窗口{sz_window}期，衰减{sz_decay:.2f}）：{single_zod}（得分 {single_score:.3f}）")
            bt_sz = backtest_single_zodiac_v2(conn, recent_limit=backtest_limit)
            if bt_sz["total"] > 0:
                rate = bt_sz["hit"] / bt_sz["total"]
                baseline = 1 - (11/12)**7
                flag = "✅" if rate > baseline else "❌"
                print(f"📊 独肖回测（近{backtest_limit}期）：{bt_sz['hit']}/{bt_sz['total']} ({rate*100:.1f}%)  基线{baseline*100:.1f}% {flag}")
                scores_list = [p.get("score", 0) for p in bt_sz["periods"]]
                if scores_list:
                    sorted_scores_sz = sorted(scores_list)
                    nsz = len(sorted_scores_sz)
                    hi = sorted_scores_sz[int(nsz*2/3)] if nsz>=3 else sorted_scores_sz[-1]
                    lo = sorted_scores_sz[int(nsz*1/3)] if nsz>=3 else sorted_scores_sz[0]
                lines = []
                for p in bt_sz["periods"]:
                    p_sc = p.get("score", 0)
                    level = "高" if p_sc >= hi else "中" if p_sc >= lo else "低"
                    emoji = {"高":"🟢","中":"🟡","低":"🔴"}[level]
                    mark = "▲" if p["hit"] else "✗"
                    lines.append(f"{p['idx']:02d}:{emoji}{p['pred']}({p_sc:.2f}){mark}")
                print("   逐期：")
                for i in range(0, len(lines), 4):
                    print("      " + "  ".join(lines[i:i+4]))

    stats = conn.execute("""SELECT strategy,COUNT(*) AS cnt,ROUND(AVG(hit_count),2) AS avg_hit,
        ROUND(AVG(hit_rate)*100,1) AS hr,ROUND(AVG(COALESCE(special_hit,0))*100,1) AS sr
        FROM prediction_runs WHERE status='REVIEWED' GROUP BY strategy ORDER BY avg_hit DESC""").fetchall()
    if stats:
        print("\n历史基本策略命中统计（正码主控，随机基线 12.2%）：")
        for s in stats:
            label = STRATEGY_LABELS.get(s["strategy"], s["strategy"])
            flag = "✅" if s["hr"] and s["hr"] > 12.2 else "❌"
            print(f"  {label:　<8s}: 期数={s['cnt']}, 平均命中={s['avg_hit']}个, 命中率={s['hr']}% {flag}, 特别号命中率={s['sr']}%")
    else:
        print("\n暂无基本策略复盘数据。")

def cmd_sync(args):
    conn = connect_db(args.db)
    try:
        init_db(conn)
        records, src, url, stats = fetch_online_records_with_multi_fallback(args.official_url, args.third_party_urls)
        total, ins, upd = sync_from_records(conn, records, src)
        print(f"数据同步完成: total={total}, new={ins}, updated={upd}, source={src} ({url})")
        if stats:
            print(f"数据源统计: 官方尝试={stats.get('official_tried')} 成功={stats.get('official_success')}, 第三方尝试={len(stats.get('third_party_tried',[]))}")
        latest_issue = conn.execute("SELECT issue_no FROM draws ORDER BY draw_date DESC LIMIT 1").fetchone()["issue_no"]
        review_issue(conn, latest_issue)
        if args.with_backtest:
            for issue in [r["issue_no"] for r in conn.execute("SELECT issue_no FROM draws ORDER BY draw_date DESC LIMIT 10").fetchall()]:
                review_issue(conn, issue)
        pre_cfg, _ = auto_tune_mined_config(conn)
        issue = generate_predictions(conn, mined_cfg_override=pre_cfg)
        print(f"已生成 {issue} 期预测。")
        print_dashboard(conn, color_window=args.color_window, color_method=args.color_method, backtest_limit=args.backtest_limit)
    except Exception as e: logger.error("同步失败: %s", e)
    finally: conn.close()

def cmd_show(args):
    conn = connect_db(args.db)
    try: init_db(conn); print_dashboard(conn, color_window=args.color_window, color_method=args.color_method, backtest_limit=args.backtest_limit)
    finally: conn.close()

def main():
    p = argparse.ArgumentParser(description="新澳门六合彩预测工具（美化版 + 增强大小 + 单双）")
    p.add_argument("--db", default=DB_PATH_DEFAULT)
    p.add_argument("--official-url", default=OFFICIAL_URL_DEFAULT, help="官方数据API地址")
    p.add_argument("--third-party-urls", nargs="*", default=THIRD_PARTY_URLS_DEFAULT, help="备用第三方数据源URL列表")
    p.add_argument("--color-window", type=int, default=None)
    p.add_argument("--color-method", choices=["simple","weighted"], default="weighted")
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("sync", help="同步数据并生成预测")
    sp.add_argument("--with-backtest", action="store_true")
    sp.add_argument("--backtest-limit", type=int, default=DEFAULT_BACKTEST_LIMIT)
    sp.set_defaults(func=cmd_sync)
    sh = sub.add_parser("show", help="展示最新预测和回测")
    sh.add_argument("--backtest-limit", type=int, default=DEFAULT_BACKTEST_LIMIT)
    sh.set_defaults(func=cmd_show)
    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
