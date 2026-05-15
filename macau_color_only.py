#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
澳门彩 · 特二色预测（纯预测，无调参/无冗长回测）
- 只获取澳门彩（非新澳门）历史数据
- 基于波色映射预测下一期特码二色（红/蓝/绿）
- 输出：期号 + 预测二色
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
    if n in RED:
        return "红"
    if n in BLUE:
        return "蓝"
    if n in GREEN:
        return "绿"
    return "红"  # fallback


def next_issue(issue_no: str) -> str:
    """期号递增（格式：YY/XXX）"""
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


def fetch_macau_records(limit: int = 300) -> list:
    """从API获取澳门彩历史数据（只取澳门，不取新澳门）"""
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
                    # 只取澳门彩（排除新澳门）
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


def predict_two_colors(train_colors: list) -> list:
    """
    核心预测：给定历史特码颜色列表（从早到晚），返回预测的两个颜色（优先级从高到低）
    策略（简化自 color_two.py 的职业量化版）：
    - 多窗口加权计数（短、中、长）
    - 遗漏加分
    - 转移矩阵
    - 连空保护（若上期未中，奖励冷色）
    """
    if not train_colors:
        return ["红", "蓝"]

    # 参数（固定经验值，不调参）
    windows = [(12, 3.2), (30, 1.4), (60, 0.8)]  # (窗口大小, 权重)
    omission_weight = 0.65
    omission_cap = 6.0
    transition_weight = 4.5
    miss_streak_bonus = 4.0

    # 1. 热冷分数
    score = Counter()
    for w, wgt in windows:
        recent = train_colors[:w]
        for c in recent:
            score[c] += wgt

    # 2. 遗漏加分
    omission = {}
    for c in COLORS:
        miss = 0
        for x in train_colors:
            if x == c:
                break
            miss += 1
        omission[c] = miss
        score[c] += min(miss * omission_weight, omission_cap)

    # 3. 转移矩阵（基于上一期颜色）
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
                score[c] += (v / total) * transition_weight

    # 4. 连空保护（这里模拟 miss_streak=1 时的处理，实际调用时可传入）
    # 本简化版假设 miss_streak=0，不加额外奖励

    # 5. 取最热两色作为预测（双色）
    ranked = [c for c, _ in score.most_common()]
    return ranked[:2]


def main():
    print("正在获取澳门彩最新数据...")
    rows = fetch_macau_records(300)
    if not rows:
        print("获取数据失败，请检查网络或API可用性")
        return

    # 提取特码颜色历史（从早到晚）
    color_history = [get_color(r["special_number"]) for r in rows]  # rows[0]最新，但预测需要从早到晚，所以这里直接使用
    # 注意：fetch_macau_records 返回的是最新在前，因此预测函数需要逆序为从早到晚
    train_colors = list(reversed(color_history))

    # 预测
    pred = predict_two_colors(train_colors)

    latest_issue = rows[0]["issue_no"]
    pred_issue = next_issue(latest_issue)

    print("\n========== 澳门彩 · 特二色预测 ==========")
    print(f"预测期号：{pred_issue}")
    print(f"预测二色：{'、'.join(pred)}")
    print("=========================================")


if __name__ == "__main__":
    main()
