# ============================================================
# 三彩 V11.3 AI四层特码预测系统 (数据源已修复)
# 第一部分：
# 配置 + 数据获取模块 fetch_lottery
#
# 【本次修复说明】
# 原代码把接口返回的 lottery_data 列表(每个元素其实是"一个彩种"
# 的完整信息)误当成"每期开奖记录"去逐条解析,导致找不到
# tm/teMa/special 等字段,数据要么为空要么错乱。
#
# 真实接口结构 (https://marksix6.net/index.php?api=1):
# {
#   "lottery_data": [
#       {"name":"香港彩", "expect":"2026077",
#        "numbers":[7个号码,最后一个是特码],
#        "history":["2026077 期：18,30,26,21,44,32,27", ...]},
#       {"name":"新澳门彩", ...},
#       {"name":"老澳门彩", ...},
#       ...
#   ]
# }
#
# 修复思路:
# 1. 请求一次,拿到 lottery_data
# 2. 按 name 字段找到目标彩种
# 3. 解析它的 history 里的文本行 "期号 期：n1,n2,...,n7"
#    取最后一个数字作为特码
# ============================================================

import requests
import re
import json
import datetime
import time
import random


# ============================================================
# 基础配置
# ============================================================

VERSION = "V11.3-fixed"

# 三个彩种共用同一个接口地址,name 必须和接口里的 "name" 字段完全一致
LOTTERY_CONFIG = {

    "香港彩": {
        "url": "https://marksix6.net/index.php?api=1",
        "name": "香港彩"
    },

    "新澳门彩": {
        "url": "https://marksix6.net/index.php?api=1",
        "name": "新澳门彩"
    },

    "老澳门彩": {
        "url": "https://marksix6.net/index.php?api=1",
        "name": "老澳门彩"
    }

}


# 历史数量

HISTORY_LIMIT = 500



# ============================================================
# 请求头
# ============================================================

HEADERS={

    "User-Agent":
    "Mozilla/5.0",

    "Accept":
    "application/json,text/plain,*/*"

}



# ============================================================
# 颜色数据库
# ============================================================

RED = {
1,2,7,8,12,13,18,19,
23,24,29,30,34,35,40,
45,46
}


BLUE = {
3,4,9,10,14,15,20,25,
26,31,36,37,41,42,47,48
}


GREEN = {
5,6,11,16,17,21,22,27,
28,32,33,38,39,43,44,49
}



def get_color(num):

    num=int(num)

    if num in RED:
        return "红"

    elif num in BLUE:
        return "蓝"

    elif num in GREEN:
        return "绿"

    else:
        return "未知"



# ============================================================
# 数字属性
# ============================================================

def number_feature(num):

    num=int(num)

    return {

        "num":num,


        # 尾数
        "tail":
        num%10,


        # 大小
        # 1-24 小
        # 25-49 大

        "big":
        True if num>=25 else False,


        # 单双

        "odd":
        True if num%2==1 else False,


        # 余数

        "r3":
        num%3,


        "r5":
        num%5,


        "r7":
        num%7,


        # 颜色

        "color":
        get_color(num)

    }




# ============================================================
# 解析 history 里的单行文本
# 格式例: "2026077 期：18,30,26,21,44,32,27"
# 返回 (issue, special_num) 或 None
# ============================================================

def parse_history_line(line):

    if not line:
        return None

    try:
        # 兼容全角/半角冒号
        parts = re.split(r"期[:：]", line, maxsplit=1)

        if len(parts) != 2:
            return None

        issue = parts[0].strip()
        nums_part = parts[1].strip()

        nums = [
            n.strip()
            for n in re.split(r"[,，]", nums_part)
            if n.strip() != ""
        ]

        if len(nums) < 7:
            return None

        # 最后一个数字是特码
        special = int(nums[-1])

        if not (1 <= special <= 49):
            return None

        return issue, special

    except Exception:
        return None




# ============================================================
# 核心 fetch_lottery (已修复)
# ============================================================


def fetch_lottery(name):


    print()

    print(
    "📡 获取数据:",
    name
    )


    cfg=LOTTERY_CONFIG[name]


    try:


        r=requests.get(

            cfg["url"],

            headers=HEADERS,

            timeout=10

        )


        data=r.json()



    except Exception as e:


        print(
        "❌接口失败:",
        e
        )


        return []


    lottery_list = data.get("lottery_data")

    if not isinstance(lottery_list, list) or len(lottery_list) == 0:

        print(
        "❌没有找到开奖列表(lottery_data 为空)"
        )

        return []


    # ==================================================
    # 按 name 找到目标彩种
    # ==================================================

    target = None

    for item in lottery_list:

        if isinstance(item, dict) and item.get("name") == name:

            target = item

            break


    if target is None:

        available = [
            x.get("name")
            for x in lottery_list
            if isinstance(x, dict)
        ]

        print(
        "❌未在接口中找到彩种:",
        name,
        " 可用彩种:",
        available
        )

        return []


    records = []

    seen_issues = set()


    # ==================================================
    # 先加入最新一期(expect + numbers)
    # 防止 history 更新有延迟,漏掉最新一期
    # ==================================================

    latest_issue = target.get("expect")

    latest_numbers = target.get("numbers")


    if latest_issue and isinstance(latest_numbers, list) and len(latest_numbers) >= 7:

        try:

            special = int(latest_numbers[-1])

            if 1 <= special <= 49:

                records.append({

                    "issue": latest_issue,

                    "num": special,

                    "feature": number_feature(special)

                })

                seen_issues.add(latest_issue)

        except Exception:

            pass



    # ==================================================
    # 解析历史文本行
    # ==================================================

    history_lines = target.get("history", [])


    for line in history_lines:


        parsed = parse_history_line(line)


        if parsed is None:

            continue


        issue, special = parsed


        if issue in seen_issues:

            continue


        records.append({

            "issue": issue,

            "num": special,

            "feature": number_feature(special)

        })


        seen_issues.add(issue)



    result = records[:HISTORY_LIMIT]


    print(
    "✅ 获取",
    len(result),
    "期"
    )


    return result




# ============================================================
# 数据校验 (逻辑不变)
# ============================================================


def check_data(data):


    print()

    print(
    "🔍 数据校验"
    )


    if len(data)==0:

        print(
        "❌ 无数据"
        )

        return False



    latest=data[0]



    print(

    "最新期:",

    latest["issue"]

    )


    print(

    "最新特码:",

    latest["num"]

    )



    print(

    "颜色:",

    latest["feature"]["color"]

    )



    if 1<=latest["num"]<=49:


        print(
        "✅特码范围正常"
        )


        return True


    else:


        print(
        "❌特码异常"
        )

        return False


def check_data_silent(data):
    """不打印任何内容,仅返回数据是否有效"""
    if len(data) == 0:
        return False
    return 1 <= data[0]["num"] <= 49



# ============================================================
# 三彩 V11.3
# 第二部分：
# 四层漏斗预测核心
# ============================================================


import math
from collections import Counter



# ============================================================
# 参数
# ============================================================


TAIL_WEIGHT = 0.45

REMAIN_WEIGHT = 0.55



# ============================================================
# 第一层
# 尾数 + 余数分析
# ============================================================


def tail_remainder_score(history):


    """
    第一层核心

    分析:
    1.尾数热度
    2.尾数遗漏
    3.余数周期

    """


    nums=[

        x["num"]

        for x in history

    ]



    tail_count=Counter(

        n%10

        for n in nums

    )



    r3_count=Counter(

        n%3

        for n in nums

    )


    r5_count=Counter(

        n%5

        for n in nums

    )


    scores={}



    for n in range(1,50):


        tail=n%10


        r3=n%3

        r5=n%5



        score=0



        # ---------------------
        # 尾数热度
        # ---------------------

        score += (

            tail_count[tail]

            *

            TAIL_WEIGHT

        )



        # ---------------------
        # 余数周期
        # ---------------------

        score += (

            r3_count[r3]

            *

            0.3

        )


        score += (

            r5_count[r5]

            *

            0.25

        )



        # ---------------------
        # 遗漏补偿
        # ---------------------

        miss=0


        for i,x in enumerate(history):

            if x["num"]==n:

                miss=i

                break


        score += min(
            miss*0.15,
            10
        )



        scores[n]=score



    return scores




# ============================================================
# 第一层筛选12码
# ============================================================


def layer_one(history):


    scores=tail_remainder_score(history)


    result=sorted(

        scores.items(),

        key=lambda x:x[1],

        reverse=True

    )


    return result[:16]





# ============================================================
# 第二层
# 大小过滤
# ============================================================



def size_filter(candidates,history):


    nums=[

        x["num"]

        for x in history

    ]



    big=sum(

        1

        for n in nums

        if n>=25

    )


    small=len(nums)-big



    big_rate=big/len(nums)



    result=[]



    for num,score in candidates:


        bonus=0


        if big_rate>0.52:


            if num>=25:

                bonus+=8


        else:


            if num<25:

                bonus+=8



        result.append(

            (
            num,

            score+bonus

            )

        )



    result.sort(

        key=lambda x:x[1],

        reverse=True

    )


    return result[:12]





# ============================================================
# 第三层
# 单双过滤
# ============================================================


def odd_even_filter(candidates,history):


    nums=[

        x["num"]

        for x in history

    ]



    odd=sum(

        1

        for n in nums

        if n%2

    )


    odd_rate=odd/len(nums)



    result=[]



    for num,score in candidates:



        bonus=0



        if odd_rate>0.55:


            if num%2==1:

                bonus+=7



        elif odd_rate<0.45:


            if num%2==0:

                bonus+=7



        else:


            bonus+=3



        result.append(

            (
            num,

            score+bonus

            )

        )



    result.sort(

        key=lambda x:x[1],

        reverse=True

    )


    return result[:10]





# ============================================================
# 第四层
# 颜色确认
# ============================================================



def color_filter(candidates):


    result=[]


    color_count=Counter()



    for num,score in candidates:


        color=get_color(num)


        result.append(

            {

            "num":num,

            "score":score,

            "color":color

            }

        )



    # 颜色分散

    result.sort(

        key=lambda x:x["score"],

        reverse=True

    )


    return result




# ============================================================
# 最终预测
# ============================================================



def base_candidates(history):
    """
    三层模式起点:不再用尾数+余数打分,
    直接从全部49个号码出发,只给一个很轻的历史出现频率作基础分
    (纯粹为了让后面大小/单双加分时不是完全同分,不引入尾数余数逻辑)
    """

    nums = [x["num"] for x in history]

    freq = Counter(nums)

    return [
        (n, freq.get(n, 0) * 0.1)
        for n in range(1, 50)
    ]


def predict_v113(history, verbose=False):

    # 起点：全部49码 + 轻量频率基础分
    base = base_candidates(history)

    # 第一层：大小过滤 49 -> 12
    l1 = size_filter(base, history)

    # 第二层：单双过滤 12 -> 10
    l2 = odd_even_filter(l1, history)

    # 第三层：颜色确认(排序+展示)
    final = color_filter(l2)

    if verbose:
        print()
        print("第一层 大小过滤:", [x[0] for x in l1])
        print("第二层 单双过滤:", [x[0] for x in l2])
        print("第三层 颜色确认:")
        for x in final:
            print(x["num"], x["color"], round(x["score"], 2))

    main = [x["num"] for x in final[:5]]
    guard = [x["num"] for x in final[5:10]]

    return {
        "main": main,
        "guard": guard,
        "detail": final
    }
    # ============================================================
# 三彩 V11.3
# 第三部分：
# 滚动回测 + ROI模块
# ============================================================


import statistics



# ============================================================
# 回测配置
# ============================================================


BACKTEST_PERIOD = 100


BET_AMOUNT = 10


# 单码赔率(示例)

ODDS_SINGLE = 47



# 双码赔率(示例)

ODDS_DOUBLE = 18





# ============================================================
# 单次收益计算
# ============================================================


def calc_profit(hit,bet):


    if hit:

        return bet*ODDS_SINGLE-bet


    else:

        return -bet





# ============================================================
# 双码收益
# ============================================================


def calc_double_profit(hit,bet):


    if hit:

        return bet*ODDS_DOUBLE-bet


    else:

        return -bet






# ============================================================
# 滚动回测
# ============================================================


def backtest_v113(history, verbose=True):

    if verbose:
        print()
        print("="*70)
        print("📈 V11.3 历史滚动回测")
        print("="*70)

    total=len(history)



    if total < BACKTEST_PERIOD+50:


        test_count=total-50


    else:

        test_count=BACKTEST_PERIOD




    top1=0

    top3=0

    top5=0

    top10=0


    double_hit=0



    profit=0



    double_profit=0



    records=[]




    # 注意:

    # history[0] 最新

    # 从旧到新预测


    for i in range(

        test_count,

        0,

        -1

    ):



        train=history[i:]



        target=history[i-1]["num"]




        try:


            result=predict_v113(

                train

            )


        except:


            continue




        main=result["main"]



        detail=[

            x["num"]

            for x in result["detail"]

        ]

        pool = [x["num"] for x in result["detail"]]





        # TOP统计


        if target==main[0]:

            top1+=1



        if target in detail[:3]:

            top3+=1



        if target in detail[:5]:

            top5+=1


        if target in pool[:10]:

            top10+=1




        # 双码


        if target in main:


            double_hit+=1



            double_profit += calc_double_profit(

                True,

                BET_AMOUNT

            )


        else:


            double_profit += calc_double_profit(

                False,

                BET_AMOUNT

            )





        # 单码

        hit=target in main


        profit += calc_profit(

            hit,

            BET_AMOUNT

        )



        records.append({

            "target":

            target,


            "predict":

            main,


            "hit":

            hit

        })





    if test_count==0:

        return None

    roi = profit / (test_count * BET_AMOUNT) * 100
    double_roi = double_profit / (test_count * BET_AMOUNT) * 100

    if verbose:
        print()
        print("测试期:", test_count)
        print("TOP1:", round(top1/test_count*100, 2), "%")
        print("TOP3:", round(top3/test_count*100, 2), "%")
        print("TOP5:", round(top5/test_count*100, 2), "%")
        print("TOP10:", round(top10/test_count*100, 2), "%")
        print()
        print("双码命中:", round(double_hit/test_count*100, 2), "%")
        print()
        print("单码ROI:", round(roi, 2), "%")
        print("双码ROI:", round(double_roi, 2), "%")

    return {
        "test_count": test_count,
        "top1": top1/test_count,
        "top3": top3/test_count,
        "top5": top5/test_count,
        "top10": top10/test_count,
        "double": double_hit/test_count,
        "roi": roi,
        "double_roi": double_roi
    }
    # ============================================================
# 三彩 V11.3
# 第四部分：
# 主程序运行入口
# ============================================================


import datetime



# ============================================================
# 单个彩种运行
# ============================================================


def random_baseline_test(hit_rate, test_count, k=10, total=49):
    """
    把模型的命中率,和"纯随机选k个号码"的理论基准做 z 检验。

    原理:如果开奖真的是独立随机的,那不管模型怎么设计,
    命中率的期望值都应该是 k/total(比如10个候选/49个号码≈20.4%)。
    这里用二项分布的正态近似算 z 值和双尾 p 值,
    判断模型的实际命中率是不是"看起来比瞎猜准",
    还是只是样本量小导致的正常波动。
    """

    p0 = k / total

    if test_count <= 0:
        return None

    se = math.sqrt(p0 * (1 - p0) / test_count)

    if se == 0:
        return None

    z = (hit_rate - p0) / se

    # 双尾 p 值(正态近似)
    p_value = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))

    if abs(z) >= 1.96:
        verdict = "显著(可能有信号,但注意多重比较)"
    elif abs(z) >= 1.0:
        verdict = "有点偏离,但不算显著"
    else:
        verdict = "和瞎猜没有区别"

    return {
        "p0": p0,
        "z": z,
        "p_value": p_value,
        "verdict": verdict
    }


def backtest_hitrate(history, period):
    """
    三层模型(大小→单双→颜色)的滚动回测。
    统计两件事:
    1. 最终命中率 = 目标特码是否落在本期预测的10个最终候选
       (主推5 + 防守5)里
    2. 这个命中率和"纯随机选10个号码"的理论基准(10/49)
       相比,是不是统计显著

    period: 回测最近多少期(如果数据不够,会自动缩到可用的最大期数)
    """

    total = len(history)

    # 至少留一部分数据当"训练历史",这里简单地保证 train 不为空
    max_possible = total - 1

    test_count = min(period, max_possible)

    if test_count <= 0:
        return None

    hit = 0

    for i in range(test_count, 0, -1):

        train = history[i:]

        if len(train) == 0:
            continue

        target = history[i - 1]["num"]

        try:
            result = predict_v113(train)
        except Exception:
            continue

        final_nums = result["main"] + result["guard"]

        if target in final_nums:
            hit += 1

    hit_rate = hit / test_count

    test = random_baseline_test(hit_rate, test_count, k=10, total=49)

    return {
        "period": period,
        "test_count": test_count,
        "hit_rate": hit_rate,
        "test": test
    }


def format_num_tag(item):
    """把一个候选号码格式化成 '12(小单红)' 这种简短标签"""
    num = item["num"]
    feat = number_feature(num)
    size_tag = "大" if feat["big"] else "小"
    odd_tag = "单" if feat["odd"] else "双"
    color_tag = feat["color"]
    return f"{num}({size_tag}{odd_tag}{color_tag})"


def run_lottery(name):

    history = fetch_lottery(name)

    if not history:
        print(f"❌ {name}: 数据为空")
        return

    if not check_data_silent(history):
        print(f"❌ {name}: 数据异常")
        return

    result = predict_v113(history)

    main_tags = [format_num_tag(x) for x in result["detail"][:5]]
    guard_tags = [format_num_tag(x) for x in result["detail"][5:10]]

    print()
    print(f"【{name}】最新特码: {history[0]['num']}")
    print(f"⭐ 主推: {'  '.join(main_tags)}")
    print(f"🛡 防守: {'  '.join(guard_tags)}")

    lines = []

    for p in [100, 50, 30, 10]:

        stat = backtest_hitrate(history, p)

        if stat and stat["test"]:
            t = stat["test"]
            lines.append(
                f"{stat['period']}期: 命中{stat['hit_rate']*100:.1f}% "
                f"vs基准{t['p0']*100:.1f}% "
                f"(z={t['z']:.2f}, {t['verdict']})"
            )
        elif stat:
            lines.append(
                f"{stat['period']}期: 命中{stat['hit_rate']*100:.1f}%(样本太小,无法检验)"
            )

    if lines:
        print("   " + "\n   ".join(lines))





# ============================================================
# 总运行
# ============================================================



def main():

    print(f"🚀 三彩 V11.3 预测  {datetime.datetime.now():%Y-%m-%d %H:%M}")
    print("-"*50)

    for name in ["香港彩", "新澳门彩", "老澳门彩"]:
        try:
            run_lottery(name)
        except Exception as e:
            print(f"❌ {name} 运行错误: {e}")
        print("-"*50)





# ============================================================
# 启动
# ============================================================


if __name__=="__main__":


    main()
