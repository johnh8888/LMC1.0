#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三彩大/单置信度下注建议 - 完整修复版
"""

import re
import json
import math
import urllib.request
import random
from datetime import datetime, timedelta

API_URL = "https://marksix6.net/index.php?api=1"

CONFIG = {
    "z_threshold": 1.96,
    "windows": [30, 50, 100],
    "min_agree_windows": 2,
    "min_data_required": 100,
    "per_bet_amount": 200,
}

LOTTERIES = [
    {"name": "香港彩", "label": "香港彩"},
    {"name": "新澳门彩", "label": "新澳门彩"},
    {"name": "老澳门彩", "label": "老澳门彩"},
]

THEORY_P = 25 / 49


def parse_numbers(text):
    nums = re.findall(r"\d+", text)
    return [int(x) for x in nums if 1 <= int(x) <= 49]


def fetch_lottery(lottery_name, limit=200):
    print(f"📡 正在获取 {lottery_name} 数据...")
    try:
        req = urllib.request.Request(API_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))

        rows = []
        for item in data.get("lottery_data", []):
            if item.get("name", "").strip() == lottery_name:
                for line in item.get("history", []):
                    nums = parse_numbers(line)
                    if len(nums) < 7: continue
                    special = nums[-1]
                    m = re.search(r"(20\d{5,8})", line)
                    if not m: continue
                    raw = m.group(1)
                    issue = raw[:4] + "/" + str(int(raw[4:])).zfill(3)
                    rows.append({
                        "issue": issue,
                        "special": special,
                        "is_big": special >= 25,
                        "is_odd": special % 2 == 1,
                    })
                break

        unique_rows = {r["issue"]: r for r in rows}
        rows = list(unique_rows.values())
        rows.sort(key=lambda x: x["issue"], reverse=True)
        rows = rows[:limit]
        rows.sort(key=lambda x: x["issue"])
        print(f"✅ 获取 {len(rows)} 期数据")
        return rows
    except Exception as e:
        print(f"❌ 获取失败: {e}")
        return []


def multi_window_decision(rows):
    if len(rows) < CONFIG["min_data_required"]:
        return None
    
    results = {}
    for w in CONFIG["windows"]:
        if len(rows) >= w:
            recent = rows[-w:]
            n = len(recent)
            z_big = (sum(1 for r in recent if r["is_big"]) / n - THEORY_P) / math.sqrt(THEORY_P*(1-THEORY_P)/n)
            z_odd = (sum(1 for r in recent if r["is_odd"]) / n - THEORY_P) / math.sqrt(THEORY_P*(1-THEORY_P)/n)
            
            results[w] = {
                "大": {"z": round(z_big, 3), "action": "下注" if z_big >= CONFIG["z_threshold"] else "观望"},
                "单": {"z": round(z_odd, 3), "action": "下注" if z_odd >= CONFIG["z_threshold"] else "观望"},
            }
    
    if len(results) < CONFIG["min_agree_windows"]:
        return None

    final = {}
    for dir_name in ["大", "单"]:
        votes = sum(1 for d in results.values() if d[dir_name]["action"] == "下注")
        avg_z = sum(d[dir_name]["z"] for d in results.values()) / len(results)
        final[dir_name] = {
            "action": "下注" if votes >= CONFIG["min_agree_windows"] else "观望",
            "votes": votes,
            "total": len(results),
            "avg_z": round(avg_z, 2)
        }
    return final


def main():
    print("=" * 80)
    print("🎯 三彩大/单置信度下注建议 - 完整修复版")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    for lot in LOTTERIES:
        rows = fetch_lottery(lot["name"], limit=200)
        if len(rows) < CONFIG["min_data_required"]:
            continue
        
        print(f"\n📊 {lot['label']}:")
        decision = multi_window_decision(rows)
        if decision:
            for d_name in ["大", "单"]:
                d = decision[d_name]
                if d["action"] == "下注":
                    print(f"  ✅ {d_name} 信号 | avg z = {d['avg_z']} | {d['votes']}/{d['total']}窗口")
                else:
                    print(f"  ⏸️ {d_name} 观望")
        else:
            print("  ⏸️ 无有效信号")

    print("\n⚠️ 完成运行")


if __name__ == "__main__":
    main()