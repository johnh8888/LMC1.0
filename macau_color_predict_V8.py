#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门彩属性分离预测系统 V8.12 MULTI

核心:

1. 颜色独立预测
2. 大小独立预测
3. 单双独立预测
4. 半半波独立预测
5. 最后综合评分

数据:
最近30期
"""

import re
import json
import urllib.request

from collections import defaultdict, Counter



# =====================================================
# 配置
# =====================================================


CONFIG = {

    "history_limit":30,


    "weights":{

        "color":0.40,

        "size":0.20,

        "odd":0.20,

        "halfhalf":0.20

    },


    "api_url":

    "https://marksix6.net/index.php?api=1"


}



REPORT_FILE="result.md"





# =====================================================
# 颜色
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



SIZES=[
"大",
"小"
]


ODDS=[
"单",
"双"
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


    if num>=25:

        return "大"


    return "小"






def get_odd(num):


    if num%2:

        return "单"


    return "双"







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


        data=urllib.request.urlopen(

            req,

            timeout=40

        ).read()



        data=json.loads(

            data.decode("utf-8")

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





        for line in target.get(

            "history",

            []

        ):



            nums=parse_numbers(line)



            if len(nums)<7:

                continue




            special=nums[-1]



            if not 1<=special<=49:

                continue




            issue_match=re.search(

                r"(20\d{5,7})",

                line

            )



            if not issue_match:

                continue



            raw=issue_match.group(1)



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
# V8.12 MULTI 预测核心
# =====================================================


class MultiPredictEngine:


    def __init__(self, rows):

        self.rows = rows[:CONFIG["history_limit"]]




    # =================================================
    # 通用趋势评分
    # =================================================


    def trend_score(self, key, values):


        score=defaultdict(float)



        total=len(self.rows)



        for i,r in enumerate(self.rows):


            weight=total-i



            value=r[key]



            score[value]+=weight




        return score






    # =================================================
    # 遗漏补偿
    # =================================================


    def missing_bonus(self,key,score,values):


        for v in values:


            miss=0


            for r in self.rows:


                if r[key]==v:

                    break


                miss+=1



            score[v]+=min(

                miss*1.5,

                15

            )


        return score






    # =================================================
    # 颜色预测
    # =================================================


    def predict_color(self):


        score=self.trend_score(

            "color",

            COLORS

        )


        score=self.missing_bonus(

            "color",

            score,

            COLORS

        )


        return sorted(

            score.items(),

            key=lambda x:x[1],

            reverse=True

        )






    # =================================================
    # 大小预测
    # =================================================


    def predict_size(self):


        score=self.trend_score(

            "size",

            SIZES

        )


        score=self.missing_bonus(

            "size",

            score,

            SIZES

        )


        return sorted(

            score.items(),

            key=lambda x:x[1],

            reverse=True

        )







    # =================================================
    # 单双预测
    # =================================================


    def predict_odd(self):


        score=self.trend_score(

            "odd",

            ODDS

        )


        score=self.missing_bonus(

            "odd",

            score,

            ODDS

        )


        return sorted(

            score.items(),

            key=lambda x:x[1],

            reverse=True

        )






    # =================================================
    # 半半波预测
    # =================================================


    def predict_halfhalf(self):


        waves=[]


        for c in COLORS:

            for s in SIZES:

                for o in ODDS:


                    waves.append(

                        c+s+o

                    )




        score=defaultdict(float)



        total=len(self.rows)



        for i,r in enumerate(self.rows):


            weight=total-i



            score[r["halfhalf"]]+=weight






        for w in waves:


            miss=0


            for r in self.rows:


                if r["halfhalf"]==w:

                    break


                miss+=1



            score[w]+=min(

                miss*1.2,

                15

            )




        return sorted(

            score.items(),

            key=lambda x:x[1],

            reverse=True

        )









    # =================================================
    # 综合组合
    # =================================================


    def final_predict(self):


        colors=self.predict_color()


        sizes=self.predict_size()


        odds=self.predict_odd()


        halfhalf=self.predict_halfhalf()




        result=[]




        for c in colors[:2]:


            for s in sizes[:2]:


                for o in odds[:2]:


                    name=(

                        c[0]

                        +

                        s[0]

                        +

                        o[0]

                    )


                    score=(

                        c[1]
                        *
                        CONFIG["weights"]["color"]

                        +

                        s[1]
                        *
                        CONFIG["weights"]["size"]

                        +

                        o[1]
                        *
                        CONFIG["weights"]["odd"]

                    )



                    # 半半波增强


                    for h in halfhalf[:10]:


                        if h[0]==name:


                            score+=h[1]*CONFIG["weights"]["halfhalf"]



                    result.append(

                        (

                            name,

                            round(score,2)

                        )

                    )





        result.sort(

            key=lambda x:x[1],

            reverse=True

        )


        return {


            "color":

            colors,


            "size":

            sizes,


            "odd":

            odds,


            "halfhalf":

            halfhalf[:10],


            "final":

            result[:5]

        }
        # =====================================================
# 回测
# =====================================================


def backtest(rows, test=10):


    hit_color=0

    hit_size=0

    hit_odd=0

    hit_halfhalf=0



    total=min(

        test,

        len(rows)-5

    )



    if total<=0:

        return {}





    for i in range(total):


        history=rows[i+1:]


        engine=MultiPredictEngine(

            history

        )


        result=engine.final_predict()



        actual=rows[i]



        # 颜色


        color_top=[

            x[0]

            for x in result["color"][:1]

        ]



        if actual["color"] in color_top:

            hit_color+=1




        # 大小


        size_top=[

            x[0]

            for x in result["size"][:1]

        ]



        if actual["size"] in size_top:

            hit_size+=1




        # 单双


        odd_top=[

            x[0]

            for x in result["odd"][:1]

        ]



        if actual["odd"] in odd_top:

            hit_odd+=1




        # 半半波


        hh_top=[

            x[0]

            for x in result["halfhalf"][:3]

        ]



        if actual["halfhalf"] in hh_top:

            hit_halfhalf+=1







    return {


        "颜色":

        round(hit_color/total*100,2),


        "大小":

        round(hit_size/total*100,2),


        "单双":

        round(hit_odd/total*100,2),


        "半半波TOP3":

        round(hit_halfhalf/total*100,2)


    }









# =====================================================
# 输出
# =====================================================


def show_result(rows,result):


    print()

    print("="*35)

    print(

        "新澳门彩 V8.12 MULTI预测"

    )

    print("="*35)



    print()


    print("第一层 颜色预测:")



    for x in result["color"][:3]:


        print(

            x[0],

            round(x[1],2)

        )





    print()


    print("第二层 大小预测:")



    for x in result["size"]:


        print(

            x[0],

            round(x[1],2)

        )





    print()


    print("第三层 单双预测:")



    for x in result["odd"]:


        print(

            x[0],

            round(x[1],2)

        )





    print()


    print("半半波TOP10:")



    for x in result["halfhalf"]:


        print(

            x[0],

            round(x[1],2)

        )






    print()


    print("="*35)

    print("最终组合TOP5")

    print("="*35)



    for x in result["final"]:


        print(

            x[0],

            x[1]

        )







# =====================================================
# 保存报告
# =====================================================


def save_report(result,bt):


    with open(

        REPORT_FILE,

        "w",

        encoding="utf-8"

    ) as f:



        f.write(

            "# 新澳门彩 V8.12 MULTI预测\n\n"

        )



        f.write(

            "## 最终组合\n\n"

        )


        for x in result["final"]:


            f.write(

                f"- {x[0]} : {x[1]}\n"

            )



        f.write(

            "\n## 回测\n\n"

        )



        for k,v in bt.items():


            f.write(

                f"- {k}: {v}%\n"

            )









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

        "最近数据"

    )


    print("-"*30)



    for r in rows:


        print(

            r["issue"],

            "特码",

            r["special"],

            r["halfhalf"]

        )





    engine=MultiPredictEngine(

        rows

    )


    result=engine.final_predict()



    show_result(

        rows,

        result

    )



    bt=backtest(

        rows,

        10

    )


    print()


    print("="*35)

    print("最近回测")

    print("="*35)



    for k,v in bt.items():

        print(

            k,

            ":",

            v,

            "%"

        )



    save_report(

        result,

        bt

    )



    print()

    print(

        "报告生成:",

        REPORT_FILE

    )





if __name__=="__main__":


    main()