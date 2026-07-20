# ============================================================
# 三彩 V11.3 AI四层特码预测系统
# 第一部分：
# 配置 + 数据获取模块 fetch_lottery
# ============================================================

import requests
import json
import datetime
import time
import random


# ============================================================
# 基础配置
# ============================================================

VERSION = "V11.3"

LOTTERY_CONFIG = {

    "香港彩":{
        "url":
        "https://marksix6.net/index.php?api=1",

        "name":"香港彩"
    },


    "新澳门彩":{
        "url":
        "https://marksix6.net/index.php?api=1",

        "name":"新澳门彩"
    },


    "老澳门彩":{
        "url":
        "https://marksix6.net/index.php?api=1",

        "name":"老澳门彩"
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
# 数据清洗
# ============================================================


def clean_number(x):

    """
    提取特码数字
    """

    if x is None:
        return None


    try:

        # 数字

        if isinstance(x,int):

            if 1<=x<=49:
                return x



        # 字符

        s=str(x)


        nums=[]

        for i in s:

            if i.isdigit():

                nums.append(i)



        if len(nums)>0:

            n=int(
                "".join(nums)
            )

            if 1<=n<=49:

                return n


    except:

        pass



    return None




# ============================================================
# 核心 fetch_lottery
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



    records=[]



    # ==================================================
    # 自动寻找列表
    # ==================================================

    raw=None


    if isinstance(data,list):

        raw=data


    elif isinstance(data,dict):


        for k,v in data.items():

            if isinstance(v,list):

                raw=v

                break



    if raw is None:

        print(
        "❌没有找到开奖列表"
        )

        return []




    # ==================================================
    # 解析每一期
    # ==================================================


    for item in raw:


        if not isinstance(item,dict):

            continue



        issue=None

        num=None



        # -------------------------
        # 期号字段
        # -------------------------


        for key in [

            "expect",
            "issue",
            "period",
            "qihao",
            "term",
            "no"

        ]:

            if key in item:

                issue=item[key]

                break




        # -------------------------
        # 特码字段优先级
        # -------------------------


        possible=[


            "tm",

            "teMa",

            "tema",

            "special",

            "special_num",

            "specialNumber",

            "sx",

            "zodiac"

        ]



        for key in possible:


            if key in item:


                num=clean_number(
                    item[key]
                )


                if num:

                    break



        # ==================================================
        # 如果没有特码字段
        # 尝试所有字段寻找49以内数字
        # ==================================================


        if num is None:


            for k,v in item.items():


                n=clean_number(v)


                if n:


                    num=n

                    break




        # ==================================================
        # 最终校验
        # ==================================================

        if num is None:

            continue



        if not(
            1<=num<=49
        ):

            continue



        records.append({

            "issue":issue,

            "num":num,

            "feature":
            number_feature(num)

        })




    # 去重

    result=[]

    seen=set()


    for x in records:


        if x["num"] not in seen:

            result.append(x)

            seen.add(
                x["num"]
            )



    # 最新在前

    result=result[:HISTORY_LIMIT]



    print(
    "✅ 获取",
    len(result),
    "期"
    )


    return result




# ============================================================
# 数据校验
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



# ============================================================
# 测试
# ============================================================


if __name__=="__main__":


    print("="*70)

    print(
    "三彩",
    VERSION,
    "数据模块测试"
    )

    print("="*70)



    for name in LOTTERY_CONFIG:


        data=fetch_lottery(name)


        check_data(data)
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


    return result[:12]





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


    return result[:8]





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


    return result[:5]





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



def predict_v113(history):


    print()

    print("="*70)

    print("🎯 V11.3 四层漏斗预测")

    print("="*70)



    # 第一层

    l1=layer_one(history)



    print()

    print("第一层 尾余TOP12:")

    print(

        [
            x[0]

            for x in l1

        ]

    )



    # 第二层


    l2=size_filter(

        l1,

        history

    )


    print()

    print("第二层 大小过滤:")

    print(

        [
            x[0]

            for x in l2

        ]

    )




    # 第三层


    l3=odd_even_filter(

        l2,

        history

    )


    print()

    print("第三层 单双过滤:")

    print(

        [
            x[0]

            for x in l3

        ]

    )





    # 第四层


    final=color_filter(l3)



    print()

    print("第四层 颜色确认:")


    for x in final:

        print(

            x["num"],

            x["color"],

            round(
                x["score"],
                2
            )

        )



    main=[

        x["num"]

        for x in final[:2]

    ]



    guard=[

        x["num"]

        for x in final[2:]

    ]



    print()

    print(
    "⭐ 主推双码:",
    tuple(main)
    )


    print(

    "🛡 防守号码:",

    guard

    )


    return {

        "main":main,

        "guard":guard,

        "detail":final

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


def backtest_v113(history):


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





        # TOP统计


        if target==main[0]:

            top1+=1



        if target in detail[:3]:

            top3+=1



        if target in detail[:5]:

            top5+=1




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

        return





    print()

    print(

    "测试期:",

    test_count

    )


    print(

    "TOP1:",

    round(

        top1/test_count*100,

        2

    ),

    "%"

    )


    print(

    "TOP3:",

    round(

        top3/test_count*100,

        2

    ),

    "%"

    )


    print(

    "TOP5:",

    round(

        top5/test_count*100,

        2

    ),

    "%"

    )



    print()

    print(

    "双码命中:",

    round(

        double_hit/test_count*100,

        2

    ),

    "%"

    )



    roi=(

        profit

        /

        (

        test_count*

        BET_AMOUNT

        )

        *

        100

    )



    double_roi=(

        double_profit

        /

        (

        test_count*

        BET_AMOUNT

        )

        *

        100

    )



    print()

    print(

    "单码ROI:",

    round(

        roi,

        2

    ),

    "%"

    )



    print(

    "双码ROI:",

    round(

        double_roi,

        2

    ),

    "%"

    )




    return {


        "top1":

        top1/test_count,


        "top3":

        top3/test_count,


        "top5":

        top5/test_count,


        "double":

        double_hit/test_count,


        "roi":

        roi,


        "double_roi":

        double_roi


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


def run_lottery(name):


    print()

    print("="*70)

    print(
        "📡 获取数据:",
        name
    )

    print("="*70)



    # 获取数据

    history = fetch_lottery(name)



    if not history:


        print(
            "❌ 数据为空:",
            name
        )

        return



    # 数据检查


    if not check_data(history):


        print(
            "❌ 数据异常"
        )

        return




    print()

    print("="*70)

    print(

        "🎯",

        name,

        "V11.3预测"

    )

    print("="*70)



    # 当前最新号码

    print(

        "最新特码:",

        history[0]["num"]

    )




    # =========================
    # 四层预测
    # =========================


    result=predict_v113(

        history

    )




    print()

    print("="*70)

    print("⭐ 最终推荐")

    print("="*70)



    print(

        "主推双码:",

        result["main"]

    )


    print(

        "防守号码:",

        result["guard"]

    )




    print()

    print(

        "颜色分布:"
    )


    for x in result["detail"]:


        print(

            x["num"],

            x["color"],

            round(

                x["score"],

                2

            )

        )




    # =========================
    # 回测
    # =========================


    if len(history)>100:


        backtest_v113(

            history

        )





# ============================================================
# 总运行
# ============================================================



def main():


    print()

    print("="*70)

    print(

    "🚀 三彩 V11.3 AI四层特码预测系统启动"

    )

    print(

    datetime.datetime.now()

    )

    print("="*70)



    print()

    print(

    "模型结构:"
    )

    print(

    "尾数+余数 → 大小 → 单双 → 颜色"

    )





    for name in [

        "香港彩",

        "新澳门彩",

        "老澳门彩"

    ]:


        try:


            run_lottery(

                name

            )


        except Exception as e:


            print()

            print(

            "❌运行错误:",

            name

            )

            print(e)




    print()

    print("="*70)

    print(

    "✅ V11.3运行完成"

    )

    print("="*70)





# ============================================================
# 启动
# ============================================================


if __name__=="__main__":


    main()