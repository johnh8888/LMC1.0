#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门彩颜色预测系统 V8.10-STABLE

特点:
1. 使用最近30期
2. 固定参数，不自动调参
3. 三层预测:
   颜色 -> 半波 -> 半半波
4. 半半波参与最终判断
5. 最近趋势 + 历史稳定结合
"""


import re
import json
import urllib.request

from collections import defaultdict


# =====================================================
# 配置
# =====================================================

CONFIG = {

    "history_limit":30,

    "api_url":
    "https://marksix6.net/index.php?api=1",


    # 颜色权重

    "color_recent_weight":0.5,

    "color_history_weight":0.5,


    # 半波

    "half_recent_weight":0.4,

    "half_history_weight":0.6,


    # 半半波

    "halfhalf_recent_weight":0.4,

    "halfhalf_history_weight":0.4,

    "halfhalf_missing_weight":0.2

}



REPORT_FILE="result.md"



# =====================================================
# 波色定义
# =====================================================


RED={
1,2,7,8,12,13,
18,19,23,24,
29,30,34,35,
40,45,46
}


BLUE={
3,4,9,10,14,
15,20,25,26,
31,36,37,41,
42,47,48
}


GREEN={
5,6,11,16,17,
21,22,27,28,
32,33,38,39,
43,44,49
}


COLORS=[
    "红",
    "蓝",
    "绿"
]



# =====================================================
# 属性计算
# =====================================================


def get_color(num):

    if num in RED:
        return "红"

    elif num in BLUE:
        return "蓝"

    else:
        return "绿"



def get_size(num):

    return "大" if num>=25 else "小"



def get_odd(num):

    return "单" if num%2 else "双"



def get_half(num):

    c=get_color(num)

    return [
        c+get_size(num),
        c+get_odd(num)
    ]



def get_halfhalf(num):

    return (
        get_color(num)
        +
        get_size(num)
        +
        get_odd(num)
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



# =====================================================
# 获取新澳门彩
# =====================================================


def fetch_new_macau(limit=30):


    rows=[]


    try:

        req=urllib.request.Request(

            CONFIG["api_url"],

            headers={
                "User-Agent":
                "Mozilla/5.0"
            }

        )


        raw=urllib.request.urlopen(

            req,

            timeout=30

        ).read()



        data=json.loads(

            raw.decode("utf-8")

        )


        print("扫描彩种:")


        target=None


        for item in data.get(
            "lottery_data",
            []
        ):


            name=item.get(
                "name",
                ""
            )


            print(name)


            if name=="新澳门彩":

                target=item

                print(
                    "锁定彩种: 新澳门彩"
                )

                break



        if not target:

            return []



        history=target.get(
            "history",
            []
        )


        for line in history:


            nums=parse_numbers(line)


            if len(nums)<7:

                continue



            special=nums[-1]


            if special<1 or special>49:

                continue



            issue_match=re.search(

                r"(20\d{5,8})",

                line

            )


            if not issue_match:

                continue



            raw_issue=issue_match.group(1)



            issue=(

                raw_issue[:4]

                +

                "/"

                +

                str(
                    int(raw_issue[4:])
                ).zfill(3)

            )



            rows.append({

                "issue":issue,

                "special":special,

                "color":
                get_color(special),

                "size":
                get_size(special),

                "odd":
                get_odd(special),

                "half":
                get_half(special),

                "halfhalf":
                get_halfhalf(special)

            })



    except Exception as e:

        print(
            "获取失败:",
            e
        )



    # 去重

    temp={}


    for r in rows:

        temp[r["issue"]]=r



    rows=list(temp.values())


    rows.sort(

        key=lambda x:x["issue"],

        reverse=True

    )


    rows=rows[:limit]


    print(
        f"获取新澳门彩:{len(rows)}期"
    )


    return rows
    # =====================================================
# V8.10 三层预测核心
# =====================================================


class PredictEngine:


    def __init__(self, rows):

        self.rows = rows[:30]



    # =================================================
    # 第一层：颜色预测
    # =================================================

    def color_predict(self):


        recent=self.rows[:10]

        history=self.rows[:30]


        score={

            "红":0,

            "蓝":0,

            "绿":0

        }



        # 最近10期趋势

        for i,r in enumerate(recent):


            weight=10-i


            score[r["color"]] += (

                weight *

                CONFIG[
                "color_recent_weight"
                ]

            )




        # 30期稳定

        for i,r in enumerate(history):


            weight=30-i


            score[r["color"]] += (

                weight *

                CONFIG[
                "color_history_weight"
                ]

            )




        # 遗漏补偿

        for c in COLORS:


            miss=0


            for r in self.rows:


                if r["color"]==c:

                    break


                miss+=1



            score[c]+=min(

                miss*1.5,

                15

            )



        total=sum(score.values())


        result=[]


        for k,v in score.items():


            result.append(

                (
                    k,

                    round(
                        v/total*100,
                        2
                    )

                )

            )


        return sorted(

            result,

            key=lambda x:x[1],

            reverse=True

        )




    # =================================================
    # 第二层：半波预测
    # =================================================

    def half_predict(self,color):


        recent=self.rows[:10]


        history=self.rows[:30]


        score=defaultdict(float)



        # 最近趋势

        for i,r in enumerate(recent):


            weight=10-i


            for h in r["half"]:


                if h.startswith(color):


                    score[h]+=(
                        weight *

                        CONFIG[
                        "half_recent_weight"
                        ]
                    )




        # 历史趋势

        for i,r in enumerate(history):


            weight=30-i


            for h in r["half"]:


                if h.startswith(color):


                    score[h]+=(
                        weight *

                        CONFIG[
                        "half_history_weight"
                        ]
                    )



        total=sum(score.values())


        result=[]


        for k,v in score.items():


            result.append(

                (
                    k,

                    round(
                        v/total*100,
                        2
                    )

                )

            )


        return sorted(

            result,

            key=lambda x:x[1],

            reverse=True

        )





    # =================================================
    # 第三层：半半波预测
    # =================================================

    def halfhalf_predict(self,half):


        color=half[0]


        size_or_odd=half[1:]



        recent=self.rows[:10]


        history=self.rows[:30]


        score=defaultdict(float)



        # 最近半半波

        for i,r in enumerate(recent):


            weight=10-i


            if r["halfhalf"].startswith(
                half
            ):


                score[r["halfhalf"]]+=(
                    weight *

                    CONFIG[
                    "halfhalf_recent_weight"
                    ]
                )




        # 历史半半波

        for i,r in enumerate(history):


            weight=30-i


            if r["halfhalf"].startswith(
                half
            ):


                score[r["halfhalf"]]+=(
                    weight *

                    CONFIG[
                    "halfhalf_history_weight"
                    ]
                )




        # 遗漏补偿

        candidates=[

            color+"大单",

            color+"大双",

            color+"小单",

            color+"小双"

        ]



        for c in candidates:


            miss=0


            for r in self.rows:


                if r["halfhalf"]==c:

                    break


                miss+=1



            score[c]+=(
                min(
                    miss*0.5,
                    10
                )
                *
                CONFIG[
                "halfhalf_missing_weight"
                ]
            )



        total=sum(score.values())



        result=[]


        for k,v in score.items():


            result.append(

                (

                    k,

                    round(
                        v/total*100,
                        2
                    )

                )

            )



        return sorted(

            result,

            key=lambda x:x[1],

            reverse=True

        )




    # =================================================
    # 最终预测
    # =================================================

    def predict(self):


        color=self.color_predict()


        best_color=color[0][0]



        half=self.half_predict(
            best_color
        )


        best_half=half[0][0]



        halfhalf=self.halfhalf_predict(
            best_half
        )



        return {


            "color":

            color,


            "half":

            half[:5],


            "halfhalf":

            halfhalf[:5],



            "final":

            {

                "color":
                best_color,


                "half":
                best_half,


                "halfhalf":
                halfhalf[0][0]

            }

        }
        # =====================================================
# 回测
# =====================================================


def backtest(rows, test=20):


    hit_color=0

    hit_half=0

    hit_halfhalf=0



    total=min(

        test,

        len(rows)-5

    )



    if total<=0:

        return {

            "color":0,

            "half":0,

            "halfhalf":0

        }



    for i in range(total):


        history=rows[i+1:]


        engine=PredictEngine(history)


        result=engine.predict()



        actual=rows[i]



        # 颜色

        if (

            result["final"]["color"]

            ==

            actual["color"]

        ):

            hit_color+=1



        # 半波

        if (

            result["final"]["half"]

            in

            actual["half"]

        ):

            hit_half+=1



        # 半半波

        if (

            result["final"]["halfhalf"]

            ==

            actual["halfhalf"]

        ):

            hit_halfhalf+=1




    return {


        "color":

        round(

            hit_color/total*100,

            2

        ),


        "half":

        round(

            hit_half/total*100,

            2

        ),


        "halfhalf":

        round(

            hit_halfhalf/total*100,

            2

        )


    }




# =====================================================
# 输出报告
# =====================================================


def save_report(rows,result,bt):


    with open(

        REPORT_FILE,

        "w",

        encoding="utf-8"

    ) as f:



        f.write(

f"""
# 新澳门彩 V8.10-STABLE预测报告


## 数据

分析期数:

{len(rows)}期



最新:

{rows[0]["issue"]}

特码:

{rows[0]["special"]}

颜色:

{rows[0]["color"]}



--------------------


## 第一层 颜色预测


"""
        )



        for x in result["color"]:

            f.write(

                f"{x[0]} : {x[1]}%\n"

            )



        f.write(

"""

--------------------


## 第二层 半波预测


"""

        )



        for x in result["half"]:

            f.write(

                f"{x[0]} : {x[1]}%\n"

            )



        f.write(

"""

--------------------


## 第三层 半半波预测


"""

        )



        for x in result["halfhalf"]:

            f.write(

                f"{x[0]} : {x[1]}%\n"

            )



        f.write(

"""

--------------------


## 最终预测


颜色:

"""

+result["final"]["color"]+

"""



半波:

"""

+result["final"]["half"]+

"""



半半波:

"""

+result["final"]["halfhalf"]+



"""



--------------------


## 最近回测


颜色:

"""

+str(bt["color"])+

"%\n\n半波:"

+str(bt["half"])+

"%\n\n半半波:"

+str(bt["halfhalf"])+

"%\n"


        )





# =====================================================
# 主程序
# =====================================================


def main():


    print(
        "正在获取新澳门彩..."
    )


    rows=fetch_new_macau(

        CONFIG[
        "history_limit"
        ]

    )



    if not rows:


        print(
            "无数据"
        )

        return



    print("\n最近数据")

    print("--------------------")



    for r in rows:


        print(

            r["issue"],

            "特码",

            r["special"],

            r["color"],

            r["halfhalf"]

        )



    print("\n====================")

    print(
        "新澳门彩 V8.10-STABLE预测"
    )

    print(
        "===================="
    )



    engine=PredictEngine(rows)


    result=engine.predict()



    print("\n第一层 颜色 TOP:")



    for x in result["color"]:


        print(

            x[0],

            x[1],

            "%"

        )



    print(

        "\n锁定颜色:",

        result["final"]["color"]

    )



    print("\n第二层 半波 TOP:")



    for x in result["half"]:


        print(

            x[0],

            x[1],

            "%"

        )



    print(

        "\n锁定半波:",

        result["final"]["half"]

    )



    print("\n第三层 半半波 TOP:")



    for x in result["halfhalf"]:


        print(

            x[0],

            x[1],

            "%"

        )



    print("\n最终预测")

    print(

        "颜色:",

        result["final"]["color"]

    )

    print(

        "半波:",

        result["final"]["half"]

    )

    print(

        "半半波:",

        result["final"]["halfhalf"]

    )



    bt=backtest(rows)



    print("\n====================")

    print("最近回测")

    print(

        "颜色:",

        bt["color"],

        "%"

    )

    print(

        "半波:",

        bt["half"],

        "%"

    )

    print(

        "半半波:",

        bt["halfhalf"],

        "%"

    )



    save_report(

        rows,

        result,

        bt

    )


    print(

        "\n报告生成:",

        REPORT_FILE

    )





if __name__=="__main__":

    main()