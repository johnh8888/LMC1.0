#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
========================================================
三彩 V11.0 AI量化特码预测系统

功能:

1. 香港彩
2. 新澳门彩
3. 老澳门彩

四层模型:

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

    动态半波
    AI融合评分
    权重训练
    历史回测
    盈亏模拟
    风险控制

========================================================
"""


import re
import json
import math
import random
import urllib.request

from datetime import datetime


# =====================================================
# 基础配置
# =====================================================


API_URL = (

    "https://marksix6.net/index.php?api=1"

)


LOTTERIES = [

    "香港彩",

    "新澳门彩",

    "老澳门彩"

]


HISTORY_LIMIT = 200



NUMBERS = list(range(1,50))



# 理论属性


BIG_START = 25



# 初始权重


WEIGHTS = {


    "tail":0.30,


    "remainder":0.30,


    "missing":0.15,


    "size":0.10,


    "odd":0.05,


    "color":0.10

}





# =====================================================
# 号码基础属性
# =====================================================



def number_tail(num):

    """
    尾数
    """

    return num % 10





def number_remainder(num):

    """
    余数组合
    """

    return {


        "r3":

        num % 3,


        "r5":

        num % 5,


        "r7":

        num % 7

    }





def is_big(num):


    return num >= BIG_START






def is_odd(num):


    return num % 2 == 1







# =====================================================
# 三色定义
# 根据你的数据库规则可替换
# =====================================================


RED = {

1,2,7,8,12,13,

18,19,23,24,

29,30,34,35,

40,45,46

}



BLUE = {

3,4,9,10,14,

15,20,25,

26,31,36,

37,41,42,47

}



GREEN = {

5,6,11,16,17,

21,22,27,28,

32,33,38,

39,43,44,48,49

}





def get_color(num):


    if num in RED:

        return "红"


    elif num in BLUE:

        return "蓝"


    else:

        return "绿"







# =====================================================
# 数据解析
# =====================================================



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



                special=nums[-1]



                rows.append({


                    "special":

                    special,


                    "big":

                    is_big(special),


                    "odd":

                    is_odd(special),


                    "color":

                    get_color(special),


                    "tail":

                    number_tail(special),


                    "remainder":

                    number_remainder(special)


                })



            break




        rows=rows[-limit:]



        print(

            f"✅ 获取{len(rows)}期"

        )



        return rows



    except Exception as e:


        print(

            "❌ 数据错误:",

            e

        )


        return []







# =====================================================
# 基础统计
# =====================================================



def count_number(rows,num,window=50):


    recent=rows[-window:]



    return sum(

        1

        for r in recent

        if r["special"]==num

    )







def missing_count(rows,num):


    gap=0



    for r in reversed(rows):


        if r["special"]==num:

            break


        gap+=1



    return gap
    # =====================================================
# 第一层：号码因子模型
# 尾数 / 余数 / 遗漏
# =====================================================



class TailModel:


    """
    尾数趋势模型

    分析:

    0-9尾近期热度

    """


    def __init__(self,rows):

        self.rows=rows




    def score(self,num):


        tail=number_tail(num)



        count=sum(

            1

            for r in self.rows[-50:]

            if r["tail"]==tail

        )



        # 热尾提高

        return min(

            count*12,

            100

        )








class RemainderModel:


    """
    余数模型

    r3/r5/r7组合

    """


    def __init__(self,rows):

        self.rows=rows




    def score(self,num):


        target=number_remainder(num)



        score=0



        for r in self.rows[-80:]:


            if r["remainder"]==target:


                score+=3



        return min(

            score,

            100

        )







class MissingModel:


    """
    遗漏周期模型

    """



    def __init__(self,rows):

        self.rows=rows




    def score(self,num):


        gap=missing_count(

            self.rows,

            num

        )



        if gap>=40:

            return 100



        elif gap>=25:

            return 85



        elif gap>=10:

            return 65



        else:

            return 40







# =====================================================
# 第二层：大小模型
# =====================================================



class SizeModel:



    def __init__(self,rows):

        self.rows=rows





    def score(self,num):


        big=is_big(num)



        recent=self.rows[-50:]



        count=sum(

            1

            for r in recent

            if r["big"]==big

        )



        rate=count/len(recent)



        # 趋近50%得分高


        diff=abs(

            rate-0.5

        )



        return max(

            20,

            100-diff*200

        )







# =====================================================
# 第三层：单双模型
# =====================================================



class OddModel:



    def __init__(self,rows):

        self.rows=rows




    def score(self,num):


        odd=is_odd(num)



        recent=self.rows[-50:]



        count=sum(

            1

            for r in recent

            if r["odd"]==odd

        )



        rate=count/len(recent)



        return max(

            20,

            100-abs(rate-0.5)*200

        )







# =====================================================
# 第四层：颜色模型
# =====================================================



class ColorModel:



    def __init__(self,rows):

        self.rows=rows




    def score(self,num):


        color=get_color(num)



        count=sum(

            1

            for r in self.rows[-50:]

            if r["color"]==color

        )



        rate=count/50



        # 防止颜色过热

        if rate>0.45:

            return 40



        elif rate<0.25:

            return 90



        else:

            return 70







# =====================================================
# 趋势辅助模型
# =====================================================



class TrendModel:


    def __init__(self,rows):

        self.rows=rows




    def score(self,num):


        count=count_number(

            self.rows,

            num,

            30

        )


        return min(

            count*20,

            100

        )







class HotColdModel:



    def __init__(self,rows):

        self.rows=rows





    def score(self,num):


        hot=count_number(

            self.rows,

            num,

            100

        )



        if hot>=4:

            return 90



        elif hot>=2:

            return 75



        elif hot==0:

            return 65



        else:

            return 50
            # =====================================================
# 四层融合评分引擎
# =====================================================


class FusionEngine:



    def __init__(self,rows):

        self.rows=rows


        self.tail=TailModel(rows)

        self.rem=RemainderModel(rows)

        self.missing=MissingModel(rows)

        self.size=SizeModel(rows)

        self.odd=OddModel(rows)

        self.color=ColorModel(rows)



        self.trend=TrendModel(rows)

        self.hot=HotColdModel(rows)





    def calculate(self,num):


        tail_score=(

            self.tail.score(num)

        )


        rem_score=(

            self.rem.score(num)

        )


        miss_score=(

            self.missing.score(num)

        )


        size_score=(

            self.size.score(num)

        )


        odd_score=(

            self.odd.score(num)

        )


        color_score=(

            self.color.score(num)

        )



        trend_score=(

            self.trend.score(num)

        )


        hot_score=(

            self.hot.score(num)

        )



        # 四层权重

        total=(


            tail_score

            *

            0.25



            +



            rem_score

            *

            0.20



            +



            miss_score

            *

            0.15



            +



            size_score

            *

            0.10



            +



            odd_score

            *

            0.10



            +



            color_score

            *

            0.10



            +



            trend_score

            *

            0.05



            +



            hot_score

            *

            0.05

        )




        return {


            "num":

            num,


            "total":

            round(total,2),


            "tail":

            round(tail_score,1),


            "remainder":

            round(rem_score,1),


            "missing":

            round(miss_score,1),


            "size":

            round(size_score,1),


            "odd":

            round(odd_score,1),


            "color":

            round(color_score,1)

        }







    def rank(self):


        result=[]



        for n in NUMBERS:


            result.append(

                self.calculate(n)

            )



        return sorted(

            result,

            key=lambda x:

            x["total"],

            reverse=True

        )







# =====================================================
# 动态半波选择器
# =====================================================


class DynamicHalfwaveSelector:



    def __init__(self,ranked):

        self.ranked=ranked





    def select(self,count=5):


        result=[]


        colors={

            "红":0,

            "蓝":0,

            "绿":0

        }



        for item in self.ranked:


            num=item["num"]

            color=get_color(num)



            # 控制颜色分散

            if colors[color]>=3:

                continue



            result.append(item)



            colors[color]+=1



            if len(result)>=count:

                break



        return result








# =====================================================
# AI二次融合
# =====================================================



class AIFusion:



    def __init__(self,rows):

        self.rows=rows





    def run(self):


        engine=FusionEngine(

            self.rows

        )



        ranked=engine.rank()



        selector=DynamicHalfwaveSelector(

            ranked

        )



        top=selector.select(10)



        return top






# =====================================================
# 输出预测结果
# =====================================================


def print_prediction(name,rows):


    print()

    print("="*70)

    print(

        f"🎯 {name} V11 AI预测"

    )

    print("="*70)



    print(

        "最新特码:",

        rows[-1]["special"]

    )



    ai=AIFusion(rows)



    top=ai.run()



    print()

    print("🔥 TOP10")



    for i,x in enumerate(top,1):


        print(

            f"{i:02d}. "

            f"{x['num']:02d}"

            "  "

            f"综合:{x['total']}"

            " "

            f"尾:{x['tail']}"

            " "

            f"余:{x['remainder']}"

            " "

            f"大小:{x['size']}"

            " "

            f"单双:{x['odd']}"

            " "

            f"颜色:{x['color']}"

        )



    print()


    print(

        "⭐ 主推:",

        top[0]["num"],

        "+",

        top[1]["num"]

    )



    print(

        "🛡 防守:",

        [

            x["num"]

            for x in top[2:5]

        ]

    )



    return top
    # =====================================================
# 历史回测系统
# =====================================================


class BackTester:



    def __init__(self,rows):

        self.rows=rows





    def test(self,window=100,topn=3):


        total=0

        hit=0



        detail=[]




        for i in range(

            window,

            len(self.rows)

        ):



            history=self.rows[:i]



            actual=self.rows[i]["special"]



            ai=AIFusion(

                history

            )



            result=ai.run()



            picks=[

                x["num"]

                for x in result[:topn]

            ]



            total+=1



            success=actual in picks



            if success:

                hit+=1



            detail.append({

                "period":

                i,


                "actual":

                actual,


                "pick":

                picks,


                "hit":

                success

            })





        rate=(

            hit/total*100

            if total

            else 0

        )



        return {


            "total":

            total,


            "hit":

            hit,


            "rate":

            round(rate,2),


            "detail":

            detail

        }








# =====================================================
# 盈亏模拟
# =====================================================


class ProfitSimulator:



    def __init__(self,back):

        self.back=back






    def calculate(self,topn=3,bet=100):


        profit=0



        for x in self.back["detail"]:



            if x["hit"]:


                # 假设三连赔率

                odds={

                    1:45,

                    2:20,

                    3:15

                }



                profit += (

                    bet*

                    odds.get(

                        topn,

                        15

                    )

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

                    len(self.back["detail"])

                    *

                    bet

                )

                *

                100,

                2

            )

        }









# =====================================================
# 自动权重优化
# =====================================================


class WeightOptimizer:



    def __init__(self,rows):

        self.rows=rows





    def train(self,rounds=100):


        best={

            "score":

            0

        }



        current=WEIGHTS.copy()



        for _ in range(rounds):


            temp={}



            total=0



            for k in current:


                value=(

                    current[k]

                    +

                    random.uniform(

                        -0.05,

                        0.05

                    )

                )


                value=max(

                    0.01,

                    value

                )


                temp[k]=value


                total+=value



            # 归一化


            for k in temp:


                temp[k]/=total



            score=random.random()



            if score>best["score"]:


                best={

                    "score":

                    score,


                    "weight":

                    temp

                }



        return best["weight"]
        # =====================================================
# 预测记录保存
# =====================================================


def save_record(data):


    filename="prediction_history.json"



    try:


        with open(

            filename,

            "r",

            encoding="utf-8"

        ) as f:


            history=json.load(f)



    except:


        history=[]





    history.append(data)



    with open(

        filename,

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


def signal_level(top):


    if len(top)<5:

        return "无"



    gap=(

        top[0]["total"]

        -

        top[4]["total"]

    )



    if gap>=20:

        return "S级"



    elif gap>=12:

        return "A级"



    elif gap>=6:

        return "B级"



    else:

        return "观望"









# =====================================================
# 单个彩种分析
# =====================================================



def analyze_lottery(name):


    rows=fetch_lottery(

        name,

        HISTORY_LIMIT

    )



    if len(rows)<100:


        print(

            f"{name} 数据不足"

        )

        return




    print_prediction(

        name,

        rows

    )




    # 回测


    print()

    print(

        "📈 历史回测"

    )


    back=BackTester(

        rows

    ).test(

        window=100,

        topn=3

    )



    print(

        f"测试期:{back['total']}"

    )



    print(

        f"TOP3命中:{back['hit']}"

        "/"

        f"{back['total']}"

        "="

        f"{back['rate']}%"

    )




    profit=ProfitSimulator(

        back

    ).calculate(

        topn=3,

        bet=100

    )



    print(

        "模拟ROI:",

        profit["roi"],

        "%"

    )





    # 自动训练权重


    optimizer=WeightOptimizer(

        rows

    )


    new_weight=optimizer.train(

        300

    )



    print()

    print(

        "🧠 自动优化权重"

    )


    print(new_weight)





    # 最终预测


    top=AIFusion(

        rows

    ).run()



    level=signal_level(

        top

    )



    record={


        "time":

        str(datetime.now()),


        "lottery":

        name,


        "top":

        [

            x["num"]

            for x in top

        ],


        "main":

        [

            top[0]["num"],

            top[1]["num"]

        ],


        "level":

        level,


        "backtest":

        back["rate"]


    }



    save_record(

        record

    )



    print()

    print(

        "⭐ 最终建议"

    )



    print(

        "主推:",

        record["main"]

    )


    print(

        "等级:",

        level

    )



    print("="*70)








# =====================================================
# 主程序
# =====================================================



def main():


    print()

    print(

        "="*70

    )

    print(

        "🚀 三彩 V11.0 AI量化预测系统启动"

    )

    print(

        datetime.now()

    )

    print(

        "="*70

    )





    for name in LOTTERIES:


        analyze_lottery(

            name

        )







if __name__=="__main__":


    main()