#!/usr/bin/env python3
# -*- coding:utf-8 -*-

"""
========================================================
三彩 V11.1 AI量化特码预测系统

核心:

第一层:
    尾数
    余数
    遗漏

第二层:
    大小

第三层:
    单双

第四层:
    颜色


增强:

    500期滚动训练
    联合概率
    双码组合评分
    动态半波
    自动回测
    ROI模拟
    风控管理

========================================================
"""


import re
import json
import math
import random
import urllib.request
from datetime import datetime



# =====================================================
# 参数配置
# =====================================================


API_URL = (

    "https://marksix6.net/index.php?api=1"

)



LOTTERIES=[

    "香港彩",

    "新澳门彩",

    "老澳门彩"

]


HISTORY_LIMIT=500



NUMBERS=list(range(1,50))



# =====================================================
# 颜色库
# =====================================================


RED={

1,2,7,8,12,

13,18,19,23,

24,29,30,34,

35,40,45,46

}



BLUE={

3,4,9,10,14,

15,20,25,26,

31,36,37,41,

42,47

}



GREEN={

5,6,11,16,17,

21,22,27,28,

32,33,38,39,

43,44,48,49

}





def get_color(num):


    if num in RED:

        return "红"


    if num in BLUE:

        return "蓝"


    return "绿"







# =====================================================
# 基础属性
# =====================================================


def is_big(num):


    return num>=25




def is_odd(num):


    return num%2==1




def get_tail(num):


    return num%10




def get_remainder(num):


    return (

        num%3,

        num%5,

        num%7

    )







# =====================================================
# 数据解析
# =====================================================


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







def fetch_lottery(name):


    print(

        "📡 获取:",

        name

    )


    try:


        req=urllib.request.Request(

            API_URL,

            headers={

                "User-Agent":

                "Mozilla/5.0"

            }

        )



        with urllib.request.urlopen(

            req,

            timeout=15

        ) as r:


            data=json.loads(

                r.read()

                .decode("utf-8")

            )




        rows=[]




        for item in data.get(

            "lottery_data",

            []

        ):


            if item.get(

                "name"

            ) != name:


                continue




            for line in item.get(

                "history",

                []

            ):



                nums=parse_numbers(line)



                if len(nums)<7:

                    continue



                n=nums[-1]



                rows.append({

                    "num":

                    n,


                    "tail":

                    get_tail(n),


                    "remainder":

                    get_remainder(n),


                    "big":

                    is_big(n),


                    "odd":

                    is_odd(n),


                    "color":

                    get_color(n)

                })



            break




        rows=rows[-HISTORY_LIMIT:]



        print(

            "✅ 数据:",

            len(rows),

            "期"

        )


        return rows



    except Exception as e:


        print(

            "数据错误:",

            e

        )


        return []







# =====================================================
# 基础统计
# =====================================================



def count_number(rows,num,window=50):


    data=rows[-window:]


    return sum(

        1

        for x in data

        if x["num"]==num

    )







def missing(rows,num):


    gap=0



    for x in reversed(rows):


        if x["num"]==num:

            return gap


        gap+=1



    return gap
    # =====================================================
# 第一层
# 尾数模型
# =====================================================


class TailModel:


    def score(self,rows,num):


        tail=get_tail(num)


        recent=rows[-100:]


        total=len(recent)


        if total==0:

            return 0



        hit=sum(

            1

            for x in recent

            if x["tail"]==tail

        )


        rate=hit/total



        return round(

            rate*100,

            2

        )







# =====================================================
# 第一层
# 余数模型
# =====================================================


class RemainderModel:



    def score(self,rows,num):


        r=get_remainder(num)



        recent=rows[-100:]



        score=0



        for x in recent:



            if x["remainder"]==r:

                score+=1



        return round(

            score/

            max(

                len(recent),

                1

            )

            *

            100,

            2

        )








# =====================================================
# 第一层
# 遗漏模型
# =====================================================



class MissingModel:



    def score(self,rows,num):


        gap=missing(

            rows,

            num

        )



        # 30期以内遗漏最佳

        if gap<=5:


            return 90



        elif gap<=15:


            return 75



        elif gap<=30:


            return 60



        else:


            return 40








# =====================================================
# 第二层
# 大小模型
# =====================================================


class BigSmallModel:



    def score(self,rows,num):


        target=is_big(num)



        recent=rows[-100:]



        if not recent:

            return 0



        hit=sum(

            1

            for x in recent

            if x["big"]==target

        )



        return round(

            hit/

            len(recent)

            *

            100,

            2

        )









# =====================================================
# 第三层
# 单双模型
# =====================================================



class OddEvenModel:



    def score(self,rows,num):


        target=is_odd(num)



        recent=rows[-100:]



        hit=sum(

            1

            for x in recent

            if x["odd"]==target

        )



        return round(

            hit/

            max(

                len(recent),

                1

            )

            *

            100,

            2

        )









# =====================================================
# 第四层
# 颜色模型
# =====================================================



class ColorModel:



    def score(self,rows,num):


        color=get_color(num)



        recent=rows[-100:]



        hit=sum(

            1

            for x in recent

            if x["color"]==color

        )



        return round(

            hit/

            max(

                len(recent),

                1

            )

            *

            100,

            2

        )









# =====================================================
# 热冷趋势模型
# =====================================================



class TrendModel:



    def score(self,rows,num):


        recent30=rows[-30:]

        recent100=rows[-100:]



        c30=count_number(

            recent30,

            num,

            30

        )


        c100=count_number(

            recent100,

            num,

            100

        )



        value=(

            c30*0.7

            +

            c100*0.3

        )



        return round(

            value*20,

            2

        )
        # =====================================================
# 四属性联合概率模型
# 尾数 + 颜色 + 大小 + 单双
# =====================================================


class JointProbability:



    def score(self,rows,num):


        tail=get_tail(num)

        color=get_color(num)

        big=is_big(num)

        odd=is_odd(num)



        recent=rows[-300:]



        hit=0



        for x in recent:


            if (

                x["tail"]==tail

                and

                x["color"]==color

                and

                x["big"]==big

                and

                x["odd"]==odd

            ):

                hit+=1




        if not recent:

            return 0



        rate=(

            hit/

            len(recent)

        )



        return round(

            rate*1000,

            2

        )









# =====================================================
# 双码组合评分
# =====================================================


class PairModel:



    def score(self,a,b):


        score=100



        # 同尾风险


        if get_tail(a)==get_tail(b):


            score-=20




        # 同颜色


        if get_color(a)==get_color(b):


            score-=15




        # 同大小


        if is_big(a)==is_big(b):


            score-=8




        # 同单双


        if is_odd(a)==is_odd(b):


            score-=5




        # 距离太近


        if abs(a-b)<=3:


            score-=10




        return max(

            score,

            0

        )









# =====================================================
# 动态半波选择
# =====================================================


class HalfWaveSelector:



    def select(self,numbers):


        result=[]



        for x in numbers:


            color=get_color(

                x["num"]

            )



            result.append(

                {

                "num":

                x["num"],


                "color":

                color,


                "score":

                x["score"]

                }

            )




        # 强制颜色分散


        final=[]


        used=set()



        for x in result:


            if (

                x["color"]

                not in used

                or

                len(final)<2

            ):


                final.append(x)

                used.add(

                    x["color"]

                )



            if len(final)>=5:

                break



        return final









# =====================================================
# AI融合引擎
# =====================================================



class FusionEngine:



    def __init__(self,rows):


        self.rows=rows


        self.tail=TailModel()

        self.rem=RemainderModel()

        self.miss=MissingModel()

        self.size=BigSmallModel()

        self.odd=OddEvenModel()

        self.color=ColorModel()

        self.trend=TrendModel()

        self.joint=JointProbability()




    def score_number(self,num):


        tail=self.tail.score(

            self.rows,

            num

        )


        rem=self.rem.score(

            self.rows,

            num

        )


        miss=self.miss.score(

            self.rows,

            num

        )


        size=self.size.score(

            self.rows,

            num

        )


        odd=self.odd.score(

            self.rows,

            num

        )


        color=self.color.score(

            self.rows,

            num

        )


        trend=self.trend.score(

            self.rows,

            num

        )


        joint=self.joint.score(

            self.rows,

            num

        )




        # 四层权重


        total=(


            tail*0.20


            +

            rem*0.15


            +

            miss*0.10


            +

            size*0.10


            +

            odd*0.10


            +

            color*0.10


            +

            trend*0.10


            +

            joint*0.15


        )




        return round(

            total,

            2

        )






    def rank(self):


        result=[]



        for num in NUMBERS:


            result.append(

                {


                "num":

                num,


                "score":

                self.score_number(

                    num

                )


                }

            )



        return sorted(

            result,

            key=lambda x:

            x["score"],

            reverse=True

        )









# =====================================================
# 最佳双码搜索
# =====================================================


def find_best_pair(ranked):


    pair_model=PairModel()



    best=None

    best_score=0



    top=ranked[:10]



    for i in range(len(top)):


        for j in range(

            i+1,

            len(top)

        ):



            a=top[i]["num"]

            b=top[j]["num"]



            score=(


                top[i]["score"]

                +

                top[j]["score"]

                +

                pair_model.score(

                    a,

                    b

                )

            )



            if score>best_score:


                best_score=score


                best=(

                    a,

                    b

                )




    return {


        "pair":

        best,


        "score":

        round(

            best_score,

            2

        )

    }
    # =====================================================
# 500期滚动训练
# =====================================================


class RollingTrainer:



    def __init__(self,rows):

        self.rows=rows





    def get_windows(self):


        return {


            "short":

            self.rows[-30:],



            "middle":

            self.rows[-100:],



            "long":

            self.rows[-500:]

            if len(self.rows)>=500

            else self.rows

        }






    def get_weights(self):


        return {


            "short":

            0.40,


            "middle":

            0.35,


            "long":

            0.25

        }








# =====================================================
# 因子自动优化
# =====================================================


class FactorOptimizer:



    def adjust(self,rate):


        if rate>=0.30:


            return 1.30



        elif rate>=0.20:


            return 1.10



        elif rate>=0.10:


            return 0.90



        else:


            return 0.60







# =====================================================
# 回测系统
# =====================================================


class BackTester:



    def __init__(self,rows):


        self.rows=rows






    def run(self,window=100):


        total=0


        hit1=0


        hit3=0


        hit5=0



        detail=[]





        for i in range(

            window,

            len(self.rows)

        ):



            history=self.rows[:i]



            ai=FusionEngine(

                history

            )



            ranking=ai.rank()



            top1=ranking[0]["num"]



            top3=[

                x["num"]

                for x in ranking[:3]

            ]



            top5=[

                x["num"]

                for x in ranking[:5]

            ]



            actual=self.rows[i]["num"]



            total+=1




            if actual==top1:


                hit1+=1



            if actual in top3:


                hit3+=1



            if actual in top5:


                hit5+=1





            detail.append(

                {


                "actual":

                actual,


                "top3":

                top3,


                "hit":

                actual in top3


                }

            )






        return {


            "total":

            total,


            "top1":

            round(

                hit1/

                total*

                100,

                2

            ),



            "top3":

            round(

                hit3/

                total*

                100,

                2

            ),



            "top5":

            round(

                hit5/

                total*

                100,

                2

            ),



            "detail":

            detail

        }









# =====================================================
# 双码回测
# =====================================================


class PairBackTester:



    def __init__(self,rows):


        self.rows=rows





    def run(self,window=100):


        total=0


        hit=0




        for i in range(

            window,

            len(self.rows)

        ):



            history=self.rows[:i]



            ranking=FusionEngine(

                history

            ).rank()



            pair=find_best_pair(

                ranking

            )



            actual=self.rows[i]["num"]



            total+=1




            if actual in pair["pair"]:


                hit+=1






        return {


            "total":

            total,


            "hit":

            hit,


            "rate":

            round(

                hit/

                total*

                100,

                2

            )

        }









# =====================================================
# 盈亏模拟
# =====================================================


class ProfitSimulator:



    def __init__(self,result):


        self.result=result






    def calculate(self,bet=100):


        profit=0



        for x in self.result["detail"]:



            if x["hit"]:


                # 假设TOP3命中赔率

                profit += (

                    bet*

                    15

                    -

                    bet

                )


            else:


                profit-=bet





        return {


            "profit":

            profit,


            "roi":

            round(

                profit/

                (

                len(

                self.result["detail"]

                )

                *

                bet

                )

                *

                100,

                2

            )

        }
        # =====================================================
# 保存预测记录
# =====================================================


def save_prediction(data):


    file="prediction_history.json"



    try:

        with open(

            file,

            "r",

            encoding="utf-8"

        ) as f:


            history=json.load(f)


    except:


        history=[]




    history.append(data)



    with open(

        file,

        "w",

        encoding="utf-8"

    ) as f:


        json.dump(

            history,

            f,

            ensure_ascii=False,

            indent=2

        )









# =====================================================
# 信号等级
# =====================================================


def get_signal(score):


    if score>=180:


        return "S级"



    elif score>=150:


        return "A级"



    elif score>=120:


        return "B级"



    else:


        return "观望"









# =====================================================
# 打印预测
# =====================================================


def print_prediction(name,rows):


    print()

    print("="*70)

    print(

        "🎯",

        name,

        "V11.1 AI预测"

    )

    print("="*70)




    latest=rows[-1]



    print(

        "最新特码:",

        latest["num"]

    )





    engine=FusionEngine(

        rows

    )



    ranking=engine.rank()



    print()

    print("🔥 TOP10")



    for i,x in enumerate(

        ranking[:10],

        1

    ):


        print(

            f"{i:02d}.",

            x["num"],

            "评分:",

            x["score"]

        )






    pair=find_best_pair(

        ranking

    )



    print()

    print(

        "⭐ 最佳组合"

    )



    print(

        pair["pair"]

    )


    print(

        "组合分:",

        pair["score"]

    )





    print()

    print(

        "🛡 防守号码"

    )


    print(

        [

            x["num"]

            for x in ranking[2:5]

        ]

    )




    signal=get_signal(

        pair["score"]

    )



    print()

    print(

        "信号等级:",

        signal

    )





    # 保存


    save_prediction(

        {


        "time":

        str(datetime.now()),


        "lottery":

        name,


        "top10":

        [

            x["num"]

            for x in ranking[:10]

        ],



        "main":

        pair["pair"],



        "score":

        pair["score"],



        "signal":

        signal


        }

    )



    return ranking








# =====================================================
# 单彩分析
# =====================================================


def analyze(name):


    rows=fetch_lottery(

        name

    )



    if len(rows)<100:


        print(

            "数据不足"

        )

        return




    ranking=print_prediction(

        name,

        rows

    )



    print()

    print(

        "📈 历史回测"

    )



    back=BackTester(

        rows

    ).run()



    print(

        "TOP1:",

        back["top1"],

        "%"

    )


    print(

        "TOP3:",

        back["top3"],

        "%"

    )


    print(

        "TOP5:",

        back["top5"],

        "%"

    )




    pairback=PairBackTester(

        rows

    ).run()



    print()

    print(

        "双码命中:",

        pairback["rate"],

        "%"

    )





    profit=ProfitSimulator(

        back

    ).calculate()



    print(

        "模拟ROI:",

        profit["roi"],

        "%"

    )






# =====================================================
# 主程序
# =====================================================


def main():


    print()

    print("="*70)

    print(

        "🚀 三彩 V11.1 AI量化特码预测系统启动"

    )

    print(

        datetime.now()

    )

    print("="*70)




    for name in LOTTERIES:


        analyze(

            name

        )



    print()

    print("="*70)

    print(

        "运行完成"

    )

    print("="*70)







if __name__=="__main__":


    main()