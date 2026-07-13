#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门彩颜色预测系统 V8.9

三阶段决策模型：

第一阶段:
    预测颜色

第二阶段:
    根据颜色预测半波

第三阶段:
    根据半波预测半半波


特点:
1. 最近10期分析
2. 不混合权重
3. 颜色优先
4. 半波二次筛选
5. 半半波最终细化
"""


import json
import re
import urllib.request
import time

from collections import Counter, defaultdict



# =====================================================
# 配置
# =====================================================


CONFIG = {


    # 只分析最近10期

    "history_limit":10,


    # API

    "api_url":
    "https://marksix6.net/index.php?api=1",


    # 请求

    "timeout":15,


}



REPORT_FILE="result.md"





# =====================================================
# 颜色定义
# =====================================================


RED={

1,2,7,8,
12,13,
18,19,
23,24,
29,30,
34,35,
40,45,46

}



BLUE={

3,4,
9,10,
14,15,
20,25,26,
31,36,37,
41,42,
47,48

}



GREEN={

5,6,
11,
16,17,
21,22,
27,28,
32,33,
38,39,
43,44,49

}



COLORS=[

"红",
"蓝",
"绿"

]





# =====================================================
# 基础属性
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


def fetch_new_macau(limit=10):


    rows=[]


    headers={

        "User-Agent":
        "Mozilla/5.0"

    }



    try:


        req=urllib.request.Request(

            CONFIG["api_url"],

            headers=headers

        )


        raw=urllib.request.urlopen(

            req,

            timeout=CONFIG["timeout"]

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



            if not 1<=special<=49:

                continue





            m=re.search(

                r"(20\d{5,7})",

                line

            )


            if not m:

                continue



            raw_issue=m.group(1)



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

    result={}


    for r in rows:

        result[r["issue"]]=r




    rows=list(

        result.values()

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
# V8.9 三阶段预测核心
# =====================================================


class PredictEngine:


    def __init__(self, rows):

        self.rows = rows[:10]





    # =================================================
    # 第一阶段
    # 颜色预测
    # =================================================


    def predict_color(self):


        score={

            "红":0,

            "蓝":0,

            "绿":0

        }



        # 趋势权重
        # 越近权重越高


        for index,r in enumerate(self.rows):


            weight=10-index


            score[r["color"]] += weight





        # 频率


        counter=Counter(

            r["color"]

            for r in self.rows

        )



        for c in COLORS:


            score[c]+=counter[c]*2





        # 遗漏补偿


        for c in COLORS:


            miss=0


            for r in self.rows:


                if r["color"]==c:

                    break


                miss+=1



            score[c]+=miss*1.5





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
    # 第二阶段
    # 指定颜色预测半波
    # =================================================


    def predict_half(self,color):



        score=defaultdict(float)



        targets=[

            color+"大",

            color+"小",

            color+"单",

            color+"双"

        ]



        for index,r in enumerate(self.rows):


            weight=10-index



            for h in r["half"]:


                if h in targets:


                    score[h]+=weight





        # 遗漏


        for h in targets:


            miss=0


            for r in self.rows:


                if h in r["half"]:

                    break


                miss+=1



            score[h]+=miss*1.2





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
    # 第三阶段
    # 指定颜色+半波预测半半波
    # =================================================


    def predict_halfhalf(self,color,half):



        score=defaultdict(float)



        for index,r in enumerate(self.rows):


            weight=10-index



            if r["halfhalf"].startswith(color):


                if r["halfhalf"].startswith(

                    half[:1]

                ):


                    score[

                        r["halfhalf"]

                    ]+=weight





        # 只保留对应组合


        candidates=[]


        for size in ["大","小"]:


            for odd in ["单","双"]:


                name=(

                    color

                    +

                    size

                    +

                    odd

                )


                candidates.append(name)





        for c in candidates:


            if c not in score:


                score[c]=0





        total=sum(score.values())



        if total==0:


            total=1





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
    # 总预测
    # =================================================


    def predict(self):


        # 第一层

        color_list=self.predict_color()


        color=color_list[0][0]



        # 第二层


        half_list=self.predict_half(color)



        half=half_list[0][0]



        # 第三层


        halfhalf_list=self.predict_halfhalf(

            color,

            half

        )




        return {


            "color":

            color_list,



            "select_color":

            color,



            "half":

            half_list,



            "select_half":

            half,



            "halfhalf":

            halfhalf_list[:5],



            "select_halfhalf":

            halfhalf_list[0][0]

        }
        # =====================================================
# V8.9 回测
# =====================================================


def backtest(rows):


    if len(rows)<5:

        return None



    hit_color=0

    hit_half=0

    hit_halfhalf=0



    total=0



    # 从旧到新测试

    for i in range(

        len(rows)-1,

        0,

        -1

    ):



        history=rows[i:]



        if len(history)<5:

            continue



        engine=PredictEngine(history)



        result=engine.predict()



        actual=rows[i-1]



        total+=1



        if (

            result["select_color"]

            ==

            actual["color"]

        ):

            hit_color+=1




        if (

            result["select_half"]

            in actual["half"]

        ):

            hit_half+=1




        if (

            result["select_halfhalf"]

            ==

            actual["halfhalf"]

        ):

            hit_halfhalf+=1





    if total==0:

        return None



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


def save_report(text):


    with open(

        REPORT_FILE,

        "w",

        encoding="utf-8"

    ) as f:


        f.write(text)







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





    print()

    print(

        "最近10期开奖结果"

    )

    print(

        "-"*30

    )



    for r in rows:



        print(

            r["issue"],

            "特码",

            r["special"],

            r["color"],

            r["halfhalf"]

        )



    print()

    print(

        "="*20

    )



    engine=PredictEngine(rows)



    result=engine.predict()



    print(

        "新澳门彩 V8.9预测"

    )



    print()

    print(

        "第一层 颜色 TOP:"

    )



    for x in result["color"]:


        print(

            x[0],

            x[1],

            "%"

        )




    print()

    print(

        "锁定颜色:",

        result["select_color"]

    )



    print()

    print(

        "第二层 半波 TOP:"

    )



    for x in result["half"]:


        print(

            x[0],

            x[1],

            "%"

        )



    print()

    print(

        "锁定半波:",

        result["select_half"]

    )



    print()

    print(

        "第三层 半半波 TOP:"

    )



    for x in result["halfhalf"]:


        print(

            x[0],

            x[1],

            "%"

        )



    print()

    print(

        "最终预测"

    )



    print(

        "颜色:",

        result["select_color"]

    )



    print(

        "半波:",

        result["select_half"]

    )


    print(

        "半半波:",

        result["select_halfhalf"]

    )





    print()

    print(

        "="*20

    )



    bt=backtest(rows)



    if bt:


        print(

            "最近回测"

        )


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





    report=f"""

# 新澳门彩 V8.9预测报告


分析期数:

{len(rows)}期


## 第一层

颜色:

{result["select_color"]}


## 第二层

半波:

{result["select_half"]}


## 第三层

半半波:

{result["select_halfhalf"]}


"""


    save_report(report)



    print()

    print(

        "报告生成:",

        REPORT_FILE

    )








if __name__=="__main__":

    main()