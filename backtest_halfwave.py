#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门六合彩 - 3注半半波策略回测 + 最近10期查看
功能：
1. 拉取历史数据回测（默认636期）
2. 显示最近10期命中情况
3. 生成回测报告
"""

import re
import json
import urllib.request
from collections import defaultdict
from datetime import datetime
import sys
import os

# =====================================================
# 配置
# =====================================================

CONFIG = {
    "api_url": "https://marksix6.net/index.php?api=1",
    "history_limit": 730,
    "bet_per_note": 100,
    "bets": [
        {"name": "蓝小单", "odds": 15.76, "numbers": [3, 9, 15, 21]},
        {"name": "绿大单", "odds": 11.82, "numbers": [27, 33, 39, 43, 49]},
        {"name": "蓝大双", "odds": 11.82, "numbers": [26, 36, 42, 47, 48]},
    ]
}

# 官方号码表
RED = {1,2,7,8,12,13,18,19,23,24,29,30,34,35,40,45,46}
BLUE = {3,4,9,10,14,15,20,25,26,31,36,37,41,42,47,48}
GREEN = {5,6,11,16,17,21,22,27,28,32,33,38,39,43,44,49}


def get_color(n):
    if n in RED: return "红"
    if n in BLUE: return "蓝"
    return "绿"


def get_size(n):
    return "大" if n >= 25 else "小"


def get_odd(n):
    return "单" if n % 2 else "双"


def get_halfhalf(n):
    return get_color(n) + get_size(n) + get_odd(n)


def get_hit_bet(n):
    """检查命中了哪个玩法"""
    for bet in CONFIG["bets"]:
        if n in bet["numbers"]:
            return bet["name"]
    return None


# =====================================================
# 获取数据
# =====================================================

def fetch_data(limit=730, cache_file="history_cache.json"):
    """获取历史数据（带缓存）"""
    
    # 1. 尝试从缓存读取
    if os.path.exists(cache_file):
        print(f"📂 从缓存读取数据: {cache_file}")
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                rows = json.load(f)
            if len(rows) >= limit:
                print(f"✅ 缓存数据充足: {len(rows)}期")
                return rows[:limit]
            else:
                print(f"⚠️ 缓存数据不足 ({len(rows)}期)，重新拉取...")
        except Exception as e:
            print(f"⚠️ 缓存读取失败: {e}")

    # 2. 从API拉取
    print(f"📡 正在从API获取数据（最多{limit}期）...")
    rows = []
    try:
        req = urllib.request.Request(
            CONFIG["api_url"],
            headers={"User-Agent": "Mozilla/5.0"}
        )
        data = urllib.request.urlopen(req, timeout=60).read()
        data = json.loads(data.decode("utf-8"))

        target = None
        for item in data.get("lottery_data", []):
            if item.get("name", "").strip() == "新澳门彩":
                target = item
                break

        if not target:
            print("❌ 未找到新澳门彩数据")
            return []

        for line in target.get("history", []):
            nums = re.findall(r"\d+", line)
            nums = [int(x) for x in nums if 1 <= int(x) <= 49]
            if len(nums) < 7:
                continue
            special = nums[-1]
            m = re.search(r"(20\d{5,8})", line)
            if not m:
                continue
            raw = m.group(1)
            issue = raw[:4] + "/" + str(int(raw[4:])).zfill(3)
            rows.append({
                "issue": issue,
                "special": special,
                "halfhalf": get_halfhalf(special)
            })

    except Exception as e:
        print(f"❌ 获取失败: {e}")
        return []

    # 去重并排序
    cache = {}
    for r in rows:
        cache[r["issue"]] = r
    rows = list(cache.values())
    rows.sort(key=lambda x: x["issue"])
    
    # 保存缓存
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        print(f"💾 缓存已保存: {cache_file} ({len(rows)}期)")
    except Exception as e:
        print(f"⚠️ 缓存保存失败: {e}")
    
    return rows[-limit:]


# =====================================================
# 最近10期命中查看
# =====================================================

def show_recent_hits(rows, show_count=10):
    """显示最近N期命中情况"""
    if len(rows) < show_count:
        print(f"⚠️ 数据不足，仅获取到 {len(rows)} 期")
        show_count = len(rows)

    # 取最近的期数（rows已经是倒序）
    recent = rows[:show_count]

    print("\n" + "=" * 70)
    print(f"📊 最近{show_count}期开奖明细")
    print("=" * 70)
    print(f"{'期号':<12} {'特码':<6} {'半半波':<12} {'命中':<10} {'中奖玩法':<12}")
    print("-" * 70)

    hit_count = 0
    hit_details = []
    consecutive_miss = 0

    for r in recent:
        hit_bet = get_hit_bet(r["special"])
        is_hit = hit_bet is not None

        if is_hit:
            hit_count += 1
            hit_icon = "✅ 中"
            hit_details.append({
                "issue": r["issue"],
                "number": r["special"],
                "bet": hit_bet,
                "halfhalf": r["halfhalf"],
            })
            consecutive_miss = 0
        else:
            hit_icon = "❌ 未中"
            consecutive_miss += 1

        print(f"{r['issue']:<12} {r['special']:<6} {r['halfhalf']:<12} {hit_icon:<10} {hit_bet or '-':<12}")

    # 汇总统计
    print("-" * 70)
    
    total_numbers = sum(len(bet["numbers"]) for bet in CONFIG["bets"])
    theoretical = total_numbers / 49 * show_count
    
    print(f"\n📊 最近{show_count}期汇总:")
    print(f"  命中: {hit_count}/{show_count} ({hit_count/show_count*100:.1f}%)")
    print(f"  理论预期: {theoretical:.1f}次")
    print(f"  偏差: {hit_count - theoretical:+.1f}次")

    if hit_count > theoretical:
        print(f"  ✅ 最近表现优于理论预期！")
    elif hit_count < theoretical:
        print(f"  ⚠️ 最近表现低于理论预期，属正常波动")
    else:
        print(f"  ℹ️ 最近表现与理论预期一致")

    # 命中详情
    if hit_details:
        print(f"\n🎯 命中详情:")
        for h in hit_details:
            print(f"  {h['issue']} 开{h['number']:02d} → 中{h['bet']} ({h['halfhalf']})")
    else:
        print(f"\n❌ 最近{show_count}期未命中任何号码")

    # 连续未中提醒
    if consecutive_miss > 0:
        print(f"\n⚠️ 当前已连续 {consecutive_miss} 期未中")
        if consecutive_miss >= 10:
            print(f"  🔴 连续未中已达 {consecutive_miss} 期，请注意风险！")
    else:
        print(f"\n✅ 最近一期命中！")

    # 盈亏估算
    total_bet = show_count * 300
    total_win = 0
    for h in hit_details:
        for bet in CONFIG["bets"]:
            if bet["name"] == h["bet"]:
                total_win += bet["odds"] * 100
                break

    profit = total_win - total_bet
    print(f"\n💰 盈亏估算（最近{show_count}期，每期300元）:")
    print(f"  总投注: {total_bet:,.0f}元")
    print(f"  总中奖: {total_win:,.0f}元")
    print(f"  净盈亏: {profit:+,.0f}元")

    return {
        "hit_count": hit_count,
        "total": show_count,
        "hit_rate": hit_count / show_count * 100,
        "profit": profit,
        "consecutive_miss": consecutive_miss,
        "hit_details": hit_details,
    }


# =====================================================
# 回测引擎
# =====================================================

def run_backtest(rows):
    """执行回测"""
    bets = CONFIG["bets"]
    bet_per_period = CONFIG["bet_per_note"] * len(bets)

    total_numbers = sum(len(bet["numbers"]) for bet in bets)

    print("\n" + "=" * 70)
    print("📊 回测配置")
    print("=" * 70)
    print(f"  策略: 3注半半波策略")
    print(f"  每注: {CONFIG['bet_per_note']}元")
    print(f"  每期投入: {bet_per_period}元")
    print(f"  回测期数: {len(rows)}期")
    print(f"  覆盖号码: {total_numbers}个/49个 ({total_numbers/49*100:.1f}%)")

    results = []
    balance = 0
    hit_count = 0
    max_drawdown = 0
    max_balance = 0
    consecutive_loss = 0
    max_consecutive_loss = 0
    hit_stats = defaultdict(int)

    # 按月统计
    monthly = defaultdict(list)
    
    for r in rows:
        hit = None
        for bet in bets:
            if r["special"] in bet["numbers"]:
                hit = bet
                break

        if hit:
            hit_count += 1
            hit_stats[hit["name"]] += 1
            balance += hit["odds"] * CONFIG["bet_per_note"] - bet_per_period
            consecutive_loss = 0
        else:
            balance -= bet_per_period
            consecutive_loss += 1
            max_consecutive_loss = max(max_consecutive_loss, consecutive_loss)

        if balance > max_balance:
            max_balance = balance
        max_drawdown = max(max_drawdown, max_balance - balance)

        # 按月统计
        month = r["issue"][:7]
        monthly[month].append(balance)
        
        results.append({
            "issue": r["issue"],
            "number": r["special"],
            "actual": r["halfhalf"],
            "hit": hit["name"] if hit else None,
            "balance": balance,
        })

    total = len(results)
    hit_rate = hit_count / total * 100 if total > 0 else 0
    roi = balance / (total * bet_per_period) * 100 if total > 0 else 0

    # =====================================================
    # 输出结果
    # =====================================================
    print("\n" + "=" * 70)
    print("📊 回测结果")
    print("=" * 70)
    print(f"  📅 回测期数: {total}期")
    print(f"  🎯 命中次数: {hit_count}次")
    print(f"  📈 命中率: {hit_rate:.2f}%")
    print(f"  💰 总投注: {total * bet_per_period:,.0f}元")
    print(f"  📊 最终盈亏: {balance:+,.0f}元")
    print(f"  📉 最大回撤: {max_drawdown:,.0f}元")
    print(f"  🔥 最长连续未中: {max_consecutive_loss}期")
    print(f"  📊 ROI: {roi:+.2f}%")

    # =====================================================
    # 各玩法命中统计
    # =====================================================
    print("\n🎯 各玩法命中统计:")
    for bet in bets:
        count = hit_stats.get(bet["name"], 0)
        pct = count / hit_count * 100 if hit_count > 0 else 0
        print(f"  {bet['name']}: {count}次 ({pct:.1f}%)")

    # =====================================================
    # 年度对比
    # =====================================================
    if len(results) >= 365:
        year1 = results[:365]
        year2 = results[365:730] if len(results) >= 730 else results[365:]
        
        y1_balance = year1[-1]["balance"] if year1 else 0
        y2_balance = year2[-1]["balance"] - y1_balance if year2 else 0
        
        print("\n📅 年度对比:")
        print(f"  第一年 (365期): {y1_balance:+,.0f}元")
        if len(results) >= 730:
            print(f"  第二年 (365期): {y2_balance:+,.0f}元")
            print(f"  两年合计: {y1_balance + y2_balance:+,.0f}元")

    # =====================================================
    # 生成报告
    # =====================================================
    report = f"""# 新澳门六合彩 - 3注半半波策略回测报告

**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**数据**: 最近{total}期

## 回测结果

| 指标 | 数值 |
|------|------|
| 回测期数 | {total}期 |
| 命中次数 | {hit_count}次 |
| 命中率 | {hit_rate:.2f}% |
| 总投注 | {total * bet_per_period:,.0f}元 |
| 总盈亏 | {balance:+,.0f}元 |
| 最大回撤 | {max_drawdown:,.0f}元 |
| 最长连续未中 | {max_consecutive_loss}期 |
| ROI | {roi:+.2f}% |

## 下注明细

| 玩法 | 赔率 | 号码 | 数量 | 命中 |
|------|------|------|------|------|
"""

    for bet in bets:
        nums = ", ".join([f"{n:02d}" for n in bet["numbers"]])
        count = hit_stats.get(bet["name"], 0)
        report += f"| {bet['name']} | {bet['odds']} | {nums} | {len(bet['numbers'])}个 | {count}次 |\n"

    report += f"""

## 结论

{"✅ 策略可行！" if balance > 0 and roi > 0 else "❌ 策略需谨慎"}

建议启动资金: {max(10000, int(abs(max_drawdown) * 1.5)):,}元
"""

    with open("backtest_result.md", "w", encoding="utf-8") as f:
        f.write(report)

    return {
        "total": total,
        "hit_count": hit_count,
        "hit_rate": hit_rate,
        "balance": balance,
        "max_drawdown": max_drawdown,
        "max_consecutive_loss": max_consecutive_loss,
        "roi": roi,
        "year1": y1_balance if len(results) >= 365 else None,
        "year2": y2_balance if len(results) >= 730 else None,
    }


# =====================================================
# 主程序
# =====================================================

def main():
    print("=" * 70)
    print("🎯 新澳门六合彩 - 3注半半波策略回测 + 最近10期查看")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 获取数据
    rows = fetch_data(CONFIG["history_limit"])

    if len(rows) < 30:
        print("❌ 数据不足")
        sys.exit(1)

    print(f"✅ 获取 {len(rows)} 期数据")
    print(f"📅 数据范围: {rows[-1]['issue']} ~ {rows[0]['issue']}")

    # =====================================================
    # 1. 显示最近10期命中
    # =====================================================
    show_recent_hits(rows, show_count=10)

    # =====================================================
    # 2. 执行回测
    # =====================================================
    result = run_backtest(rows)

    # =====================================================
    # 3. 最终结论
    # =====================================================
    print("\n" + "=" * 70)
    print("📋 最终结论")
    print("=" * 70)

    if result["balance"] > 0 and result["roi"] > 0:
        print(f"""
✅ 策略可行！

关键数据:
  回测期数: {result['total']}期
  命中率: {result['hit_rate']:.2f}%
  总盈亏: {result['balance']:+,.0f}元
  ROI: {result['roi']:+.2f}%
  最大回撤: {result['max_drawdown']:.0f}元
  最长连续未中: {result['max_consecutive_loss']}期

建议:
  启动资金: {int(abs(result['max_drawdown']) * 1.5):,}元
  每期投入: 300元 (3注×100元)
  严格执行: 不倍投、不追号
""")
    else:
        print("""
❌ 策略需谨慎，建议继续观察
""")

    print(f"📄 详细报告已生成: backtest_result.md")


if __name__ == "__main__":
    main()