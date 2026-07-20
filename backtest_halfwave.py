#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
三彩 V10.1 四层特码量化预测系统

核心:

第一层:
    尾数热度
    尾数遗漏
    余数组合
    特码遗漏

第二层:
    大小趋势

第三层:
    单双趋势

第四层:
    颜色确认


输出:

TOP1
TOP3
TOP5

历史回测

"""

import re
import json
import math
import urllib.request

from collections import Counter
from datetime import datetime



# ==============================
# 配置
# ==============================


API_URL = (
    "https://marksix6.net/index.php?api=1"
)


LOTTERIES=[

    "香港彩",

    "新澳门彩",

    "老澳门彩"

]



NUMBERS=list(range(1,50))



# ==============================
# 颜色库
# ==============================


RED=set([

1,2,7,8,12,13,18,19,23,24,
29,30,34,35,40,45,46

])


BLUE=set([

3,4,9,10,14,15,20,25,
26,31,36,37,41,42,47,48

])


GREEN=set([

5,6,11,16,17,21,22,27,
28,32,33,38,39,43,44,49

])



def get_color(num):


    if num in RED:

        return "红"


    if num in BLUE:

        return "蓝"


    return "绿"





# ==============================
# 号码基础属性
# ==============================


def number_info(num):


    return {

        "num":num,

        "tail":
            num%10,


        "big":
            num>=25,


        "odd":
            num%2==1,


        "r3":
            num%3,


        "r5":
            num%5,


        "r7":
            num%7,


        "color":
            get_color(num)

    }





NUMBER_INFO={

    n:number_info(n)

    for n in NUMBERS

}





# ==============================
# 数据解析
# ==============================


def parse_numbers(text):


    nums=re.findall(
        r"\d+",
        text
    )


    return [

        int(x)

        for x in nums

        if 1<=int(x)<=49

    ]





# ==============================
# 获取历史数据
# ==============================


def fetch_lottery(name,limit=200):


    print(
        f"📡 获取{name}数据..."
    )


    try:


        req=urllib.request.Request(

            API_URL,

            headers={

                "User-Agent":
                "Mozilla/5.0"

            }

        )


        response=urllib.request.urlopen(

            req,

            timeout=15

        )


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


                nums=parse_numbers(
                    line
                )


                if len(nums)<7:

                    continue



                special=nums[-1]



                issue=re.search(

                    r"(20\d{5,8})",

                    line

                )


                if not issue:

                    continue



                code=issue.group(1)



                rows.append({

                    "issue":

                    code,


                    "special":

                    special,


                    "tail":

                    special%10,


                    "big":

                    special>=25,


                    "odd":

                    special%2==1,


                    "color":

                    get_color(
                        special
                    )

                })


            break




        # 去重

        temp={}


        for r in rows:

            temp[
                r["issue"]
            ]=r



        rows=list(
            temp.values()
        )


        rows.sort(

            key=lambda x:
            x["issue"]

        )


        rows=rows[-limit:]



        print(

            f"✅ {name}"
            f" 获取{len(rows)}期"

        )


        return rows




    except Exception as e:


        print(
            "❌ 数据错误:",
            e
        )


        return []





# ==============================
# 测试基础数据
# ==============================


if __name__=="__main__":


    print(
        "三彩 V10.1 启动"
    )


    for i in range(1,6):

        print(
            NUMBER_INFO[i]
        )
        # ==============================
# 第一层：尾数强化模型
# ==============================


class TailModel:

    """
    尾数:
    
    热度70%
    遗漏30%

    """

    def __init__(self, rows):

        self.rows = rows


        self.tails = [

            r["special"] % 10

            for r in rows

        ]



    def analyze(self):


        counter = Counter(
            self.tails
        )


        total=len(
            self.tails
        )


        result={}



        for tail in range(10):


            count = counter.get(
                tail,
                0
            )


            miss=999


            for i,t in enumerate(
                reversed(self.tails)
            ):


                if t==tail:

                    miss=i

                    break



            # 热度

            hot=(

                count /
                total
                *
                100

            ) if total else 0



            # 遗漏

            miss_score=min(
                miss,
                20
            )



            score=(

                hot*0.7

                +

                miss_score*0.3

            )


            result[tail]={

                "count":
                count,


                "miss":
                miss,


                "score":
                score

            }


        return result





    def score(self,num):


        data=self.analyze()


        tail=num%10


        return data[tail]["score"]





# ==============================
# 第二部分：余数组合模型
# ==============================


class RemainderPatternModel:


    """
    余数组合:

    除3
    除5
    除7

    形成:

    a-b-c

    """


    def __init__(self,rows):


        self.patterns=[]


        for r in rows:


            n=r["special"]


            self.patterns.append(

                (

                n%3,

                n%5,

                n%7

                )

            )




    def analyze(self):


        return Counter(
            self.patterns
        )




    def score(self,num):


        pattern=(

            num%3,

            num%5,

            num%7

        )


        data=self.analyze()


        hit=data.get(

            pattern,

            0

        )


        total=sum(
            data.values()
        )


        if total==0:

            return 0



        # 放大差异


        return (

            hit /

            total

            *

            1000

        )





# ==============================
# 第三部分：号码遗漏模型
# ==============================


class NumberMissingModel:


    """

    特码遗漏

    刚出的降低

    长期未出的增加


    """



    def __init__(self,rows):

        self.rows=rows





    def score(self,num):


        miss=999



        for i,r in enumerate(

            reversed(
                self.rows
            )

        ):


            if r["special"]==num:

                miss=i

                break




        if miss==999:

            return 100




        # 最近出现

        if miss<=3:

            return 20




        # 长遗漏


        if miss>=20:

            return 100



        return miss*5






# ==============================
# 第二层：大小模型
# ==============================


class SizeModel:


    def __init__(self,rows):

        self.rows=rows




    def score(self,num):


        total=len(
            self.rows
        )


        if total==0:

            return 0



        big=sum(

            1

            for r in self.rows

            if r["big"]

        )



        rate=big/total



        if num>=25:


            return rate*100


        else:


            return (

                1-rate

            )*100







# ==============================
# 第三层：单双模型
# ==============================


class OddModel:


    def __init__(self,rows):

        self.rows=rows




    def score(self,num):


        total=len(
            self.rows
        )


        if total==0:

            return 0



        odd=sum(

            1

            for r in self.rows

            if r["odd"]

        )


        rate=odd/total



        if num%2==1:


            return rate*100


        else:


            return (

                1-rate

            )*100






# ==============================
# 第四层：颜色模型
# ==============================


class ColorModel:


    def __init__(self,rows):

        self.rows=rows




    def score(self,num):


        total=len(
            self.rows
        )


        if total==0:

            return 0



        colors=Counter(

            r["color"]

            for r in self.rows

        )


        rate=(

            colors[
                get_color(num)
            ]

            /

            total

        )



        return rate*100
        # ==============================
# 四层融合评分引擎
# ==============================


class FusionEngine:


    def __init__(self,rows):

        self.rows=rows


        # 第一层

        self.tail_model=TailModel(
            rows
        )


        self.pattern_model=RemainderPatternModel(
            rows
        )


        self.missing_model=NumberMissingModel(
            rows
        )



        # 第二层

        self.size_model=SizeModel(
            rows
        )



        # 第三层

        self.odd_model=OddModel(
            rows
        )



        # 第四层

        self.color_model=ColorModel(
            rows
        )





    def normalize(self,value,max_value):


        if max_value==0:

            return 0


        return (

            value /

            max_value

            *

            100

        )





    def score(self,num):


        # 第一层

        tail_score=(

            self.tail_model
            .score(num)

        )



        pattern_score=(

            self.pattern_model
            .score(num)

        )


        missing_score=(

            self.missing_model
            .score(num)

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



        # 余数组合压缩

        pattern_score=min(

            pattern_score,

            100

        )



        total=(


            tail_score
            *
            0.25



            +

            pattern_score
            *
            0.30



            +

            missing_score
            *
            0.15



            +

            size_score
            *
            0.10



            +

            odd_score
            *
            0.05



            +

            color_score
            *
            0.05



            +

            tail_score
            *
            0.10

        )



        return {


            "number":

            num,


            "tail":

            tail_score,


            "pattern":

            pattern_score,


            "missing":

            missing_score,


            "size":

            size_score,


            "odd":

            odd_score,


            "color":

            color_score,


            "total":

            total

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





    def top10(self):


        return self.rank()[:10]





    def confidence(self):


        data=self.rank()


        gap=(

            data[0]["total"]

            -

            data[4]["total"]

        )



        if gap>=20:

            return "★★★★★"


        elif gap>=10:

            return "★★★★"


        elif gap>=5:

            return "★★★"


        else:

            return "★★"







# ==============================
# 推荐输出
# ==============================


def print_prediction(
        lottery,
        rows
):


    print("\n")
    print("="*70)

    print(
        f"🎯 {lottery} V10.1预测"
    )

    print("="*70)



    latest=rows[-1]["special"]


    print(
        f"最新特码: {latest}"
    )



    engine=FusionEngine(
        rows[-200:]
    )



    result=engine.rank()



    print("\n🔥 TOP10号码")



    for i,item in enumerate(

        result[:10],

        1

    ):


        print(

            f"{i:02d}. "

            f"{item['number']:02d}"

            f" "

            f"总分:{item['total']:.2f}"

            f" "

            f"尾:{item['tail']:.1f}"

            f" "

            f"余:{item['pattern']:.1f}"

            f" "

            f"漏:{item['missing']:.1f}"

        )




    print("\n⭐ 主推:")


    print(

        result[0]["number"],

        "+",

        result[1]["number"]

    )



    print(
        "\n🛡 防守:"
    )


    print(

        [

            x["number"]

            for x in result[2:5]

        ]

    )



    print(

        "\n信心:",

        engine.confidence()

    )
    # ==============================
# 回测系统
# ==============================


class BacktestEngine:


    def __init__(self,rows):

        self.rows=rows




    def run(self,window=100):


        if len(self.rows)<=window:

            print(
                "数据不足回测"
            )

            return



        total=0


        hit1=0

        hit3=0

        hit5=0


        hit2=0

        hit3group=0



        for i in range(

            window,

            len(self.rows)

        ):


            history=self.rows[:i]


            target=(

                self.rows[i]
                ["special"]

            )



            engine=FusionEngine(

                history[-200:]

            )



            rank=engine.rank()



            nums=[

                x["number"]

                for x in rank

            ]



            total+=1



            # TOP1

            if target==nums[0]:

                hit1+=1



            # TOP3

            if target in nums[:3]:

                hit3+=1



            # TOP5

            if target in nums[:5]:

                hit5+=1



            # 两码

            if target in nums[:2]:

                hit2+=1



            # 三码

            if target in nums[:3]:

                hit3group+=1






        print("\n")
        print("="*70)

        print(
            "📈 V10.1历史滚动回测"
        )

        print("="*70)


        print(
            f"测试期数:{total}"
        )


        print(
            f"TOP1:"
            f"{hit1}/{total}"
            f" "
            f"{hit1/total*100:.2f}%"
        )


        print(
            f"TOP3:"
            f"{hit3}/{total}"
            f" "
            f"{hit3/total*100:.2f}%"
        )


        print(
            f"TOP5:"
            f"{hit5}/{total}"
            f" "
            f"{hit5/total*100:.2f}%"
        )


        print("\n下注覆盖:")


        print(

            f"2码:"
            f"{hit2/total*100:.2f}%"

        )


        print(

            f"3码:"
            f"{hit3group/total*100:.2f}%"

        )







# ==============================
# 主程序
# ==============================


def main():


    print("="*70)

    print(

        "🚀 三彩 V10.1 四层特码量化系统启动"

    )

    print("="*70)



    print(

        datetime.now()

    )




    for lottery in LOTTERIES:



        rows=fetch_lottery(

            lottery,

            200

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

            window=100

        )





# ==============================
# 启动
# ==============================


if __name__=="__main__":

    main()