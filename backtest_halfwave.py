#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
三彩 V11.2.1 AI四层特码预测系统

修复:
1. fetch_lottery 数据错位
2. 特码自动识别
3. 数据完整校验

模型:
第一层:
尾数 + 余数

第二层:
大小

第三层:
单双

第四层:
颜色
"""


import re
import json
import math
import urllib.request
from datetime import datetime
from collections import Counter



# ==============================
# API
# ==============================

API_URL = "https://marksix6.net/index.php?api=1"



# ==============================
# 四层权重
# ==============================

WEIGHTS = {

    "tail":0.40,

    "size":0.25,

    "odd":0.20,

    "color":0.15

}



LOTTERIES=[

    "香港彩",

    "新澳门彩",

    "老澳门彩"

]




# ==============================
# 颜色表
# ==============================


RED = {

1,2,7,8,12,13,18,19,

23,24,29,30,34,35,40,

45,46

}



BLUE = {

3,4,9,10,14,15,20,

25,26,31,36,37,41,

42,47,48

}



GREEN={

5,6,11,16,17,21,

22,27,28,32,33,

38,39,43,44,49

}






def get_color(num):


    if num in RED:

        return "红"


    elif num in BLUE:

        return "蓝"


    else:

        return "绿"







# ==============================
# 数字提取
# ==============================


def parse_numbers(text):


    nums=re.findall(

        r"\d+",

        str(text)

    )


    result=[]


    for n in nums:


        n=int(n)


        if 1<=n<=49:


            result.append(n)


    return result






# ==============================
# 新特码识别核心
# ==============================


def extract_special(item,line):


    """
    优先读取字段
    防止把生肖/日期当特码
    """



    keys=[


        "special",

        "special_num",

        "teMa",

        "tm",

        "特码",

        "特码号码"


    ]




    # 第一优先
    for k in keys:


        if k in item:


            try:

                n=int(item[k])


                if 1<=n<=49:


                    return n

            except:

                pass






    # 第二优先
    # 从字符串寻找:
    # 特码:38
    # 特码 38


    m=re.search(

        r"(特码|特碼|tm)\s*[:： ]\s*(\d{1,2})",

        str(line),

        re.I

    )



    if m:


        n=int(m.group(2))


        if 1<=n<=49:


            return n






    return None
    # ====================================================
# 数据获取模块 V11.2.1
# ====================================================


def fetch_lottery(lottery_name, limit=500):


    print()

    print(
        f"📡 获取数据: {lottery_name}"
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


            raw=response.read().decode(

                "utf-8"

            )



        data=json.loads(raw)



    except Exception as e:


        print(

            "❌ API读取失败:",

            e

        )

        return []







    rows=[]




    lottery_block=None




    # ----------------------------
    # 找对应彩种
    # ----------------------------


    for item in data.get(

        "lottery_data",

        []

    ):



        name=str(

            item.get(

                "name",

                ""

            )

        ).strip()



        if name==lottery_name:


            lottery_block=item

            break





    if not lottery_block:


        print(

            "❌ 未找到彩种"

        )

        return []






    history=lottery_block.get(

        "history",

        []

    )





    for line in history:



        special=None



        issue=None




        # ======================
        # 1. 获取期号
        # ======================


        text=str(line)




        m=re.search(

            r"(20\d{5,8})",

            text

        )


        if m:


            raw_issue=m.group(1)



            try:


                issue=(

                    raw_issue[:4]

                    +

                    "/"

                    +

                    str(

                        int(

                            raw_issue[4:]

                        )

                    ).zfill(3)

                )



            except:


                continue




        else:


            continue





        # ======================
        # 2. 优先字段特码
        # ======================


        if isinstance(line,dict):


            special=extract_special(

                line,

                line

            )



        else:


            special=extract_special(

                lottery_block,

                line

            )





        # ======================
        # 3. 备用解析
        # ======================


        if special is None:



            nums=parse_numbers(

                text

            )



            # 查找连续6+1号码结构

            if len(nums)>=7:



                candidates=[

                    n for n in nums

                    if 1<=n<=49

                ]



                # 去掉期号年份

                candidates=[

                    n for n in candidates

                    if n<50

                ]



                # 特码通常最后一个独立号码

                if len(candidates)>=7:


                    special=candidates[-1]







        # ======================
        # 4. 最终检查
        # ======================


        if special is None:


            continue



        if not(

            1<=special<=49

        ):


            continue






        rows.append(

            {


            "issue":

            issue,


            "num":

            special,


            "color":

            get_color(special),


            "big":

            special>=25,


            "small":

            special<25,


            "odd":

            special%2==1,


            "even":

            special%2==0



            }

        )








    # ==========================
    # 去重
    # ==========================


    unique={}



    for r in rows:


        unique[r["issue"]]=r




    rows=list(

        unique.values()

    )




    rows.sort(

        key=lambda x:

        x["issue"]

    )





    rows=rows[-limit:]







    print(

        f"✅ 获取 {len(rows)} 期"

    )




    # ==========================
    # 数据检查
    # ==========================


    if rows:



        print()

        print(

            "🔍 数据校验"

        )


        print(

            "最新期:",

            rows[-1]["issue"]

        )


        print(

            "最新特码:",

            rows[-1]["num"]

        )


        print(

            "颜色:",

            rows[-1]["color"]

        )



        if 1<=rows[-1]["num"]<=49:


            print(

                "✅ 特码范围正常"

            )


        else:


            print(

                "❌ 特码异常"

            )





    return rows
    # ====================================================
# 号码属性
# ====================================================


def number_info(num):


    return {


        "num":

        num,


        "tail":

        num % 10,


        "r3":

        num % 3,


        "r5":

        num % 5,


        "r7":

        num % 7,


        "big":

        num >= 25,


        "odd":

        num % 2 == 1,


        "color":

        get_color(num)

    }





def enrich_rows(rows):


    result=[]


    for r in rows:


        result.append(

            number_info(

                r["num"]

            )

        )


    return result







# ====================================================
# 第一层
# 尾数 + 余数模型
# ====================================================


class TailRemainderModel:



    def __init__(self,rows):


        self.rows=rows





    def tail_score(self,num):


        recent=[

            x["num"]%10

            for x in self.rows[-100:]

        ]



        count=Counter(recent)



        tail=num%10



        return (

            count.get(

                tail,

                0

            )

            /

            len(recent)

            *

            100

        )







    def remainder_score(self,num):


        score=0



        recent=self.rows[-100:]



        for base in [

            3,

            5,

            7

        ]:


            values=[

                x["num"]%base

                for x in recent

            ]



            target=num%base



            score += (

                values.count(

                    target

                )

                /

                len(values)

                *

                100

            )



        return score/3







    def score(self,num):


        return (

            self.tail_score(num)

            +

            self.remainder_score(num)

        )/2







# ====================================================
# 第二层
# 大小模型
# ====================================================


class SizeModel:



    def __init__(self,rows):


        self.rows=rows





    def score(self,num):


        recent=self.rows[-50:]



        if num>=25:


            rate=sum(

                1

                for x in recent

                if x["num"]>=25

            )



        else:


            rate=sum(

                1

                for x in recent

                if x["num"]<25

            )



        return rate/len(recent)*100








# ====================================================
# 第三层
# 单双模型
# ====================================================


class OddEvenModel:



    def __init__(self,rows):


        self.rows=rows





    def score(self,num):


        recent=self.rows[-50:]



        if num%2:


            hit=sum(

                1

                for x in recent

                if x["num"]%2

            )


        else:


            hit=sum(

                1

                for x in recent

                if x["num"]%2==0

            )



        return hit/len(recent)*100







# ====================================================
# 第四层
# 颜色模型
# ====================================================


class ColorModel:



    def __init__(self,rows):


        self.rows=rows





    def score(self,num):


        recent=[

            get_color(

                x["num"]

            )

            for x in self.rows[-100:]

        ]



        c=get_color(num)



        return (

            recent.count(c)

            /

            len(recent)

            *

            100

        )
        # ====================================================
# AI融合引擎
# ====================================================


class FusionEngine:



    def __init__(self, rows):


        self.rows = rows



        self.tail = TailRemainderModel(rows)


        self.size = SizeModel(rows)


        self.odd = OddEvenModel(rows)


        self.color = ColorModel(rows)





    # ----------------------------
    # 单号码评分
    # ----------------------------


    def score_number(self,num):


        tail_score = self.tail.score(num)


        size_score = self.size.score(num)


        odd_score = self.odd.score(num)


        color_score = self.color.score(num)





        total = (


            tail_score

            *

            WEIGHTS["tail"]



            +



            size_score

            *

            WEIGHTS["size"]



            +



            odd_score

            *

            WEIGHTS["odd"]



            +



            color_score

            *

            WEIGHTS["color"]



        )





        return {


            "num":

            num,


            "tail":

            round(tail_score,2),



            "size":

            round(size_score,2),



            "odd":

            round(odd_score,2),



            "color":

            round(color_score,2),



            "score":

            round(total,2)


        }








    # ----------------------------
    # 49号码全部评分
    # ----------------------------


    def rank(self):


        result=[]



        for num in range(1,50):


            result.append(

                self.score_number(num)

            )



        result.sort(

            key=lambda x:

            x["score"],

            reverse=True

        )



        return result







# ====================================================
# 双码优化选择
# ====================================================


def best_pair(ranking):



    top=ranking[:10]



    best=None


    best_score=0





    for i in range(len(top)):



        for j in range(

            i+1,

            len(top)

        ):



            a=top[i]


            b=top[j]



            score=(


                a["score"]

                +

                b["score"]


            )





            # 同尾降低


            if a["num"]%10 == b["num"]%10:


                score*=0.85





            # 同单双降低


            if a["num"]%2 == b["num"]%2:


                score*=0.90






            # 同颜色降低


            if get_color(a["num"]) == get_color(b["num"]):


                score*=0.95






            if score > best_score:



                best_score=score



                best={


                    "pair":(

                        a["num"],

                        b["num"]

                    ),



                    "score":

                    round(

                        score,

                        2

                    )

                }




    return best







# ====================================================
# 打印TOP
# ====================================================


def print_top10(ranking):


    print()


    print(

        "🔥 TOP10号码"

    )


    print("-"*70)




    for i,x in enumerate(

        ranking[:10],

        1

    ):



        print(

            f"{i:02d}. "

            f"{x['num']:02d} "

            f"总分:{x['score']} "

            f"尾余:{x['tail']} "

            f"大小:{x['size']} "

            f"单双:{x['odd']} "

            f"颜色:{x['color']}"

        )








# ====================================================
# 预测输出
# ====================================================


def predict(name,rows):


    print()

    print("="*70)


    print(

        "🎯",

        name,

        "V11.2.1 AI预测"

    )


    print("="*70)




    print(

        "最新特码:",

        rows[-1]["num"]

    )





    engine=FusionEngine(rows)



    ranking=engine.rank()




    print_top10(

        ranking

    )





    pair=best_pair(

        ranking

    )




    print()


    print(

        "⭐ 主推双码:",

        pair["pair"]

    )



    print(

        "组合评分:",

        pair["score"]

    )





    print()


    print(

        "🛡 防守号码:",

        [

            x["num"]

            for x in ranking[2:5]

        ]

    )





    return {


        "ranking":

        ranking,


        "pair":

        pair

    }
    # ====================================================
# 历史回测
# ====================================================


class BackTester:



    def __init__(self,rows):


        self.rows=rows






    def run(self,window=100):


        total=0


        hit1=0


        hit3=0


        hit5=0



        detail=[]





        if len(self.rows)<=window:


            return None






        for i in range(

            window,

            len(self.rows)

        ):



            history=self.rows[:i]



            engine=FusionEngine(

                history

            )



            ranking=engine.rank()



            actual=self.rows[i]["num"]





            top1=ranking[0]["num"]



            top3=[

                x["num"]

                for x in ranking[:3]

            ]



            top5=[

                x["num"]

                for x in ranking[:5]

            ]




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


                    "top1":

                    top1,


                    "top3":

                    top3,


                    "top5":

                    top5



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








# ====================================================
# 双码回测
# ====================================================


def pair_backtest(rows,window=100):


    total=0


    hit=0





    for i in range(

        window,

        len(rows)

    ):



        history=rows[:i]



        ranking=FusionEngine(

            history

        ).rank()



        pair=best_pair(

            ranking

        )



        actual=rows[i]["num"]




        total+=1




        if actual in pair["pair"]:


            hit+=1





    if total==0:


        return None





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








# ====================================================
# 盈亏模拟
# ====================================================


def roi_simulation(back,bet=100):


    profit=0


    count=0





    for x in back["detail"]:



        count+=1




        if x["actual"] in x["top3"]:



            profit += (

                bet*

                4

                -

                bet

            )


        else:


            profit-=bet






    total=bet*count





    return {


        "投注":

        total,


        "盈利":

        profit,


        "ROI":

        round(

            profit/

            total*

            100,

            2

        )

    }








# ====================================================
# 分析单个彩种
# ====================================================


def analyze(name):


    rows=fetch_lottery(

        name

    )



    if len(rows)<100:


        print(

            "数据不足"

        )

        return





    result=predict(

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





    if back:



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







        roi=roi_simulation(

            back

        )



        print(

            "模拟ROI:",

            roi["ROI"],

            "%"

        )





    pair=pair_backtest(

        rows

    )



    if pair:


        print(

            "双码命中:",

            pair["rate"],

            "%"

        )









# ====================================================
# 主程序
# ====================================================


def main():



    print()


    print("="*70)


    print(

        "🚀 三彩 V11.2.1 AI四层特码预测系统启动"

    )


    print(

        datetime.now()

    )


    print("="*70)





    for name in LOTTERIES:


        try:


            analyze(name)



        except Exception as e:


            print(

                "❌",

                name,

                e

            )





    print()


    print("="*70)


    print(

        "✅ 运行完成"

    )


    print("="*70)






if __name__=="__main__":


    main()