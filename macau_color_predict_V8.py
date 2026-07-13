#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门彩颜色预测系统 V8.7

核心优化:
1. 只分析最近30期
2. 最近10期短趋势权重70%
3. 最近30期长趋势权重30%
4. 避免单一颜色锁死
5. 输出颜色TOP3
6. 输出半波TOP5
7. 输出半半波TOP5
8. 回测同步预测逻辑
"""

import os
import re
import json
import math
import urllib.request

from collections import Counter, defaultdict


# =====================================================
# 配置
# =====================================================

CONFIG = {

    # 获取历史数量
    "history_limit":30,

    # 短趋势
    "short_window":10,

    # 权重
    "short_weight":0.7,
    "long_weight":0.3,

    # API
    "api_url":
    "https://marksix6.net/index.php?api=1"

}


REPORT_FILE="result.md"


# =====================================================
# 颜色定义
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

    if num in BLUE:
        return "蓝"

    return "绿"



def get_size(num):

    if num >= 25:
        return "大"

    return "小"



def get_odd(num):

    if num % 2:
        return "单"

    return "双"



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
# 固定组合
# =====================================================


HALF_WAVES=[]


for c in COLORS:

    for s in ["大","小"]:

        HALF_WAVES.append(
            c+s
        )

    for o in ["单","双"]:

        HALF_WAVES.append(
            c+o
        )



HALF_HALF_WAVES=[]


for c in COLORS:

    for s in ["大","小"]:

        for o in ["单","双"]:

            HALF_HALF_WAVES.append(
                c+s+o
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

        if 1 <= int(x) <= 49

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


        data=urllib.request.urlopen(

            req,

            timeout=30

        ).read()



        data=json.loads(

            data.decode(
                "utf-8"
            )

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
            ).strip()


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



            m=re.search(

                r"(20\d{5,7})",

                line

            )


            if not m:

                continue



            raw=m.group(1)



            issue=(

                raw[:4]

                +

                "/"

                +

                str(
                    int(raw[4:])
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



    rows=list(
        temp.values()
    )


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
# V8.7预测核心
# =====================================================


class PredictEngine:


    def __init__(self, rows):

        # 最新在前
        self.rows = rows[:30]



    # =================================================
    # 趋势计算
    # =================================================


    def trend_score(self, data):

        score={

            "红":0,
            "蓝":0,
            "绿":0

        }


        for i,r in enumerate(data):


            # 越新的权重越高

            weight=len(data)-i


            score[r["color"]] += weight



        return score




    # =================================================
    # 颜色融合
    # =================================================


    def color_score(self):


        short=self.rows[
            :CONFIG["short_window"]
        ]


        long=self.rows



        short_score=self.trend_score(
            short
        )


        long_score=self.trend_score(
            long
        )



        final={

            "红":0,

            "蓝":0,

            "绿":0

        }



        for c in COLORS:


            final[c] = (

                short_score[c]
                *
                CONFIG["short_weight"]

                +

                long_score[c]
                *
                CONFIG["long_weight"]

            )



        # 遗漏修正

        for c in COLORS:


            miss=0


            for r in self.rows:


                if r["color"]==c:

                    break


                miss+=1



            final[c]+=min(

                miss*1.5,

                15

            )



        return final




    # =================================================
    # 半波计算
    # =================================================


    def half_score(self):


        score=defaultdict(float)



        short=self.rows[
            :CONFIG["short_window"]
        ]


        long=self.rows



        for i,r in enumerate(short):


            weight=(

                len(short)-i

            )


            for h in r["half"]:

                score[h]+=(
                    weight*0.7
                )



        for i,r in enumerate(long):


            weight=(

                len(long)-i

            )


            for h in r["half"]:

                score[h]+=(
                    weight*0.3
                )



        return dict(score)




    # =================================================
    # 半半波计算
    # =================================================


    def halfhalf_score(self):


        score=defaultdict(float)



        short=self.rows[
            :CONFIG["short_window"]
        ]


        long=self.rows



        for i,r in enumerate(short):


            weight=len(short)-i


            score[
                r["halfhalf"]
            ] += weight*0.7




        for i,r in enumerate(long):


            weight=len(long)-i


            score[
                r["halfhalf"]
            ] += weight*0.3



        return dict(score)




    # =================================================
    # 综合预测
    # =================================================


    def predict(self):


        color=self.color_score()


        half=self.half_score()


        halfhalf=self.halfhalf_score()



        return {


            "color":

            sorted(

                color.items(),

                key=lambda x:x[1],

                reverse=True

            ),



            "half":

            sorted(

                half.items(),

                key=lambda x:x[1],

                reverse=True

            )[:5],



            "halfhalf":

            sorted(

                halfhalf.items(),

                key=lambda x:x[1],

                reverse=True

            )[:5]

        }




# =====================================================
# 概率转换
# =====================================================


def normalize(scores):


    total=sum(

        x[1]

        for x in scores

    )


    if total<=0:

        return scores



    return [

        (

            k,

            round(

                v/total*100,

                2

            )

        )

        for k,v in scores

    ]



# =====================================================
# 回测
# =====================================================


def backtest(rows):


    hit_color=0

    hit_half=0

    hit_halfhalf=0


    total=len(rows)-10



    if total<=0:

        return {}



    for i in range(total):


        history=rows[i+1:]



        if len(history)<10:

            continue



        engine=PredictEngine(
            history
        )


        result=engine.predict()



        actual=rows[i]



        # 颜色TOP1

        if (

            result["color"][0][0]

            ==
            actual["color"]

        ):

            hit_color+=1



        # 半波TOP3

        top_half=[

            x[0]

            for x in result["half"][:3]

        ]



        if any(

            h in actual["half"]

            for h in top_half

        ):

            hit_half+=1




        top_hh=[

            x[0]

            for x in result["halfhalf"][:3]

        ]



        if actual["halfhalf"] in top_hh:

            hit_halfhalf+=1



    return {


        "颜色":

        round(

            hit_color/total*100,

            2

        ),


        "半波":

        round(

            hit_half/total*100,

            2

        ),


        "半半波":

        round(

            hit_halfhalf/total*100,

            2

        )

    }
    # =====================================================
# 输出报告
# =====================================================


def save_report(result, rows, back):


    with open(

        REPORT_FILE,

        "w",

        encoding="utf-8"

    ) as f:


        f.write("# 新澳门彩 V8.7预测报告\n\n")



        f.write(

            f"分析数据: 最近{len(rows)}期\n\n"

        )



        f.write("## 颜色预测\n\n")


        for k,v in result["color"]:


            f.write(

                f"{k}: {v:.2f}\n"

            )



        f.write("\n## 半波预测\n\n")


        for k,v in result["half"]:


            f.write(

                f"{k}: {v:.2f}\n"

            )



        f.write("\n## 半半波预测\n\n")


        for k,v in result["halfhalf"]:


            f.write(

                f"{k}: {v:.2f}\n"

            )



        f.write("\n## 最近回测\n\n")


        for k,v in back.items():


            f.write(

                f"{k}: {v}%\n"

            )





# =====================================================
# 打印结果
# =====================================================


def print_result(result, rows, back):


    print("\n====================")

    print("新澳门彩 V8.7预测")

    print("====================")



    print("\n颜色TOP:")



    color_prob=normalize(

        result["color"]

    )



    for k,v in color_prob:


        print(

            k,

            v,

            "%"

        )



    print("\n半波TOP:")


    for k,v in result["half"]:


        print(

            k,

            round(v,2)

        )



    print("\n半半波TOP:")


    for k,v in result["halfhalf"]:


        print(

            k,

            round(v,2)

        )



    print("\n====================")

    print("最近回测")



    for k,v in back.items():


        print(

            k,

            ":",

            v,

            "%"

        )



    print("====================")





# =====================================================
# 主程序
# =====================================================


def main():


    print(
        "正在获取新澳门彩..."
    )



    rows=fetch_new_macau(

        CONFIG["history_limit"]

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




    # 预测

    engine=PredictEngine(rows)



    result=engine.predict()



    # 回测

    back=backtest(rows)



    print_result(

        result,

        rows,

        back

    )



    save_report(

        result,

        rows,

        back

    )



    print(

        "报告生成:",

        REPORT_FILE

    )






# =====================================================
# 启动
# =====================================================


if __name__=="__main__":


    main()