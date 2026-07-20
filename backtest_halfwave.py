#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
====================================================
三彩 V10.0 四层特码量化预测系统
====================================================

核心：

第一层：
    尾数 + 余数
    ↓
    49号码初筛

第二层：
    大小分析

第三层：
    单双分析

第四层：
    颜色分析

最终:
    TOP5特码推荐

====================================================
"""

import re
import json
import math
import urllib.request
from datetime import datetime
from collections import Counter, defaultdict


# ==============================
# 基础配置
# ==============================


API_URL = "https://marksix6.net/index.php?api=1"


LOTTERIES = [
    "香港彩",
    "新澳门彩",
    "老澳门彩"
]


# 历史数据长度

HISTORY_LIMIT = 200


# 号码评分权重

WEIGHTS = {

    "tail":25,        # 尾数

    "remain":25,      # 余数

    "size":20,        # 大小

    "odd":15,         # 单双

    "color":15        # 颜色
}



# ==============================
# 49号码基础库
# ==============================


NUMBERS = list(range(1,50))


# ==============================
# 颜色数据库
# ==============================

# 香港六合彩颜色表

RED = {
1,2,7,8,12,13,18,19,
23,24,29,30,34,35,
40,45,46
}


BLUE = {
3,4,9,10,14,15,
20,25,26,31,36,
37,41,42,47,48
}


GREEN = {
5,6,11,16,17,
21,22,27,28,
32,33,38,39,
43,44,49
}



def get_color(num):

    if num in RED:
        return "红"

    elif num in BLUE:
        return "蓝"

    else:
        return "绿"



# ==============================
# 号码属性
# ==============================


def number_info(num):

    return {

        "num":num,

        # 尾数

        "tail":num % 10,


        # 大小

        "big":num >= 25,


        # 单双

        "odd":num % 2 == 1,


        # 余数

        "r3":num % 3,

        "r5":num % 5,

        "r7":num % 7,


        # 颜色

        "color":get_color(num)

    }



NUMBER_INFO = {

    n:number_info(n)

    for n in NUMBERS

}




# ==============================
# 数据解析
# ==============================


def parse_numbers(text):

    nums = re.findall(
        r"\d+",
        text
    )

    return [

        int(x)

        for x in nums

        if 1 <= int(x) <=49

    ]




def fetch_lottery(name):

    """
    获取历史数据
    """

    print(
        f"📡 获取{name}数据..."
    )


    try:

        req = urllib.request.Request(

            API_URL,

            headers={
                "User-Agent":
                "Mozilla/5.0"
            }

        )


        with urllib.request.urlopen(
            req,
            timeout=15
        ) as response:


            data=json.loads(

                response.read()
                .decode("utf-8")

            )


        rows=[]


        for item in data.get(
            "lottery_data",
            []
        ):


            if item.get(
                "name",
                ""
            ).strip()!=name:

                continue



            for line in item.get(
                "history",
                []
            ):


                nums=parse_numbers(line)


                if len(nums)<7:

                    continue



                special=nums[-1]


                rows.append({

                    "special":special

                })



            break



        rows=rows[-HISTORY_LIMIT:]


        print(
            f"✅ {name} 获取{len(rows)}期"
        )


        return rows



    except Exception as e:


        print(
            "数据错误:",
            e
        )


        return []



# ==============================
# 测试
# ==============================


if __name__=="__main__":


    print(
        "三彩 V10 启动"
    )


    for n in NUMBERS:

        print(
            NUMBER_INFO[n]
        )

        if n>=5:
            break
            # ==============================
# 第一层模型
# 尾数 + 余数分析
# ==============================


class TailModel:
    """
    尾数分析模型

    分析:
    0~9尾

    评分:
    热度
    遗漏
    周期
    """

    def __init__(self, rows):

        self.rows = rows


        self.tails = [

            r["special"] % 10

            for r in rows

        ]



    def analyze(self):

        if not self.rows:

            return {}



        counter = Counter(
            self.tails
        )


        total=len(self.rows)



        result={}



        for tail in range(10):


            count=counter.get(
                tail,
                0
            )


            # 出现比例

            rate=count/total



            # 最近遗漏

            miss=999


            for i,t in enumerate(
                reversed(self.tails)
            ):


                if t==tail:

                    miss=i

                    break



            # 热度评分

            hot_score = rate*70



            # 遗漏评分

            miss_score = min(
                miss,
                20
            )



            score=(
                hot_score
                +
                miss_score
            )


            result[tail]={

                "count":count,

                "miss":miss,

                "score":score

            }


        return result




    def top_tails(self,n=3):


        data=self.analyze()


        return [

            x[0]

            for x in sorted(

                data.items(),

                key=lambda x:
                x[1]["score"],

                reverse=True

            )[:n]

        ]





# ==============================
# 余数模型
# ==============================


class RemainderModel:

    """
    余数分析

    除3
    除5
    除7

    """

    def __init__(self,rows):

        self.rows=rows



    def get_values(self):


        nums=[

            r["special"]

            for r in self.rows

        ]


        result={

            "r3":Counter(),

            "r5":Counter(),

            "r7":Counter()

        }


        for n in nums:


            result["r3"][
                n%3
            ]+=1


            result["r5"][
                n%5
            ]+=1


            result["r7"][
                n%7
            ]+=1



        return result





    def score_number(self,num):


        data=self.get_values()


        score=0



        # 除3

        r3=num%3

        total3=sum(
            data["r3"].values()
        )

        if total3:

            score += (

                data["r3"][r3]
                /
                total3
                *
                30

            )



        # 除5

        r5=num%5

        total5=sum(
            data["r5"].values()
        )


        if total5:

            score += (

                data["r5"][r5]
                /
                total5
                *
                30

            )



        # 除7


        r7=num%7

        total7=sum(
            data["r7"].values()
        )


        if total7:

            score += (

                data["r7"][r7]
                /
                total7
                *
                40

            )


        return score





# ==============================
# 49号码评分引擎
# ==============================


class NumberScoreEngine:


    def __init__(self,rows):

        self.rows=rows


        self.tail_model=TailModel(
            rows
        )


        self.remain_model=RemainderModel(
            rows
        )




    def tail_score(self,num):


        top=self.tail_model.analyze()


        tail=num%10


        if tail not in top:

            return 0



        max_score=max(

            x["score"]

            for x in top.values()

        )



        if max_score==0:

            return 0



        return (

            top[tail]["score"]

            /
            max_score

            *
            100

        )




    def remain_score(self,num):


        return self.remain_model.score_number(
            num
        )




    def first_layer_score(self,num):


        t=self.tail_score(num)


        r=self.remain_score(num)



        score=(

            t*0.5

            +

            r*0.5

        )


        return score




    def rank_numbers(self):


        result=[]



        for num in NUMBERS:


            score=self.first_layer_score(
                num
            )


            result.append({

                "number":num,

                "tail":num%10,

                "score":score

            })



        result.sort(

            key=lambda x:
            x["score"],

            reverse=True

        )


        return result




    def top15(self):


        return self.rank_numbers()[:15]
      # ==============================
# 第二层：大小模型
# ==============================


class SizeModel:
    """
    大小走势分析

    大:
    25-49

    小:
    1-24

    """

    def __init__(self, rows):

        self.rows = rows



    def analyze(self):

        total=len(self.rows)

        if total==0:
            return {
                "big":0,
                "small":0
            }


        big=sum(

            1

            for r in self.rows

            if r["special"]>=25

        )


        small=total-big



        return {

            "big_rate":
                big/total,

            "small_rate":
                small/total

        }



    def score(self,num):


        data=self.analyze()


        if num>=25:

            return data["big_rate"]*100

        else:

            return data["small_rate"]*100





# ==============================
# 第三层：单双模型
# ==============================


class OddModel:


    def __init__(self,rows):

        self.rows=rows



    def analyze(self):


        total=len(self.rows)


        if total==0:

            return {
                "odd":0,
                "even":0
            }



        odd=sum(

            1

            for r in self.rows

            if r["special"]%2==1

        )


        even=total-odd



        return {

            "odd_rate":
                odd/total,

            "even_rate":
                even/total

        }




    def score(self,num):


        data=self.analyze()



        if num%2==1:

            return data["odd_rate"]*100


        else:

            return data["even_rate"]*100





# ==============================
# 第四层：颜色模型
# ==============================


class ColorModel:


    def __init__(self,rows):

        self.rows=rows



    def analyze(self):


        colors=[]


        for r in self.rows:

            colors.append(

                get_color(
                    r["special"]
                )

            )


        counter=Counter(
            colors
        )


        total=len(colors)



        return {

            "红":
            counter["红"]/total if total else 0,

            "蓝":
            counter["蓝"]/total if total else 0,

            "绿":
            counter["绿"]/total if total else 0

        }




    def score(self,num):


        data=self.analyze()


        return (

            data[
                get_color(num)
            ]

            *
            100

        )






# ==============================
# 综合融合评分
# ==============================


class FusionEngine:


    def __init__(self,rows):


        self.rows=rows


        self.number_engine=NumberScoreEngine(
            rows
        )


        self.size_model=SizeModel(
            rows
        )


        self.odd_model=OddModel(
            rows
        )


        self.color_model=ColorModel(
            rows
        )





    def score(self,num):


        # 第一层
        number_score = (

            self.number_engine
            .first_layer_score(num)

        )


        # 第二层

        size_score=(

            self.size_model
            .score(num)

        )


        # 第三层

        odd_score=(

            self.odd_model
            .score(num)

        )


        # 第四层

        color_score=(

            self.color_model
            .score(num)

        )



        final=(


            number_score
            *
            0.50


            +

            size_score
            *
            0.20


            +

            odd_score
            *
            0.15


            +

            color_score
            *
            0.15

        )


        return {


            "number":num,


            "tail_remain":
                number_score,


            "size":
                size_score,


            "odd":
                odd_score,


            "color":
                color_score,


            "total":
                final

        }




    def rank(self):


        result=[]


        for n in NUMBERS:


            result.append(

                self.score(n)

            )



        result.sort(

            key=lambda x:
            x["total"],

            reverse=True

        )


        return result




    def top5(self):

        return self.rank()[:5]
      # ==============================
# 第五部分
# 回测系统
# ==============================


class BacktestEngine:
    """
    TOP号码历史回测

    测试:
    TOP1
    TOP3
    TOP5

    """

    def __init__(self, rows):

        self.rows = rows



    def run(self, start_window=100):

        if len(self.rows) <= start_window:

            print(
                "⚠️ 数据不足无法回测"
            )

            return



        top1 = 0
        top3 = 0
        top5 = 0

        total = 0



        for i in range(
            start_window,
            len(self.rows)
        ):


            history = self.rows[:i]


            target = self.rows[i]["special"]



            model = FusionEngine(
                history[-200:]
            )


            result=model.rank()



            numbers=[

                x["number"]

                for x in result

            ]



            total += 1


            if target == numbers[0]:

                top1 += 1


            if target in numbers[:3]:

                top3 += 1


            if target in numbers[:5]:

                top5 += 1





        print("\n")
        print("="*60)
        print("📈 V10历史回测")
        print("="*60)


        print(
            f"测试期数:{total}"
        )


        print(
            f"TOP1命中:"
            f"{top1}/{total}"
            f" = {top1/total*100:.2f}%"
        )


        print(
            f"TOP3命中:"
            f"{top3}/{total}"
            f" = {top3/total*100:.2f}%"
        )


        print(
            f"TOP5命中:"
            f"{top5}/{total}"
            f" = {top5/total*100:.2f}%"
        )



# ==============================
# 推荐输出
# ==============================


def print_prediction(name,rows):


    print("\n")
    print("="*70)

    print(
        f"🎯 {name} V10四层特码预测"
    )

    print("="*70)



    latest=rows[-1]["special"]


    print(
        f"最新特码:{latest}"
    )



    engine=FusionEngine(
        rows[-200:]
    )



    result=engine.rank()



    print("\n")
    print("🔥 TOP10号码")


    for i,item in enumerate(
        result[:10],
        1
    ):


        print(

            f"{i:02d}. "

            f"{item['number']:02d}"

            f"  "

            f"总分:"
            f"{item['total']:.2f}"

            f"  "

            f"尾余:"
            f"{item['tail_remain']:.1f}"

            f"  "

            f"大小:"
            f"{item['size']:.1f}"

            f"  "

            f"单双:"
            f"{item['odd']:.1f}"

            f"  "

            f"颜色:"
            f"{item['color']:.1f}"

        )




    print("\n")

    print(
        "⭐ 主推:"
    )


    print(

        result[0]["number"],

        "+",

        result[1]["number"]

    )



    print(
        "🛡 防守:"
    )


    print(

        [

            x["number"]

            for x in result[2:5]

        ]

    )





# ==============================
# 每周资金管理
# ==============================


class MoneyManager:


    def __init__(self):


        self.bankroll=50000

        self.bet=200



    def recommend(self,score):


        if score>=85:

            return self.bet


        elif score>=75:

            return int(
                self.bet*0.5
            )


        else:

            return 0






# ==============================
# 主程序
# ==============================


def main():


    print("="*70)

    print(
        "🚀 三彩 V10.0 四层特码量化预测系统启动"
    )

    print("="*70)



    for lottery in LOTTERIES:


        rows=fetch_lottery(
            lottery
        )


        if len(rows)<100:

            print(
                f"{lottery}数据不足"
            )

            continue



        # 当前预测

        print_prediction(

            lottery,

            rows

        )



        # 回测

        backtest=BacktestEngine(
            rows
        )


        backtest.run(
            start_window=100
        )





if __name__=="__main__":

    main()