#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门彩颜色预测系统 V8.6-30

优化:
1. 只分析最近30期
2. 锁定新澳门彩
3. 减少旧数据干扰
4. 最近走势权重增强
5. 适合预测下一期
"""


import os
import re
import json
import math
import argparse
import urllib.request

from itertools import product
from collections import Counter



# =====================================================
# 配置
# =====================================================


CONFIG = {

    # 最近分析期数
    "history_limit":30,

    # 权重
    "trend_weight":45,
    "frequency_weight":25,
    "missing_weight":20,
    "pattern_weight":10,


    # 自动调参范围

    "search_space":{

        "trend_weight":[40,45,50],

        "frequency_weight":[20,25,30],

        "missing_weight":[15,20,25],

        "pattern_weight":[5,10]

    },


    "api_url":
    "https://marksix6.net/index.php?api=1"

}



PARAM_FILE="macau_v86_params.json"

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

    if num>=25:
        return "大"

    return "小"




def get_odd(num):

    if num%2:
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


    headers={

        "User-Agent":
        "Mozilla/5.0"

    }



    try:


        req=urllib.request.Request(

            CONFIG["api_url"],

            headers=headers

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
            ).strip()



            print(name)



            if name=="新澳门彩":

                target=item

                print(
                    "锁定彩种: 新澳门彩"
                )

                break




        if not target:

            print(
                "没有找到新澳门彩"
            )

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




            # 期号

            m=re.search(

                r"(20\d{5,7})",

                line

            )



            if m:


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


            else:

                continue




            rows.append({

                "issue":issue,

                "special":special,

                "color":get_color(special),

                "size":get_size(special),

                "odd":get_odd(special),

                "half":get_half(special),

                "halfhalf":
                get_halfhalf(special)

            })





    except Exception as e:


        print(
            "获取失败:",
            e
        )




    # 去重复


    result={}


    for r in rows:


        result[r["issue"]]=r



    rows=list(

        result.values()

    )



    # 最新排序


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
# V8.6 预测核心
# =====================================================


class PredictEngine:


    def __init__(self, rows):

        self.rows = rows[:30]


    # -----------------------------
    # 颜色趋势
    # -----------------------------

    def color_score(self):

        score = {
            "红":0,
            "蓝":0,
            "绿":0
        }


        for i,r in enumerate(self.rows):

            weight = 30-i

            score[r["color"]] += weight



        # 遗漏补偿

        for c in score:

            miss = 0

            for r in self.rows:

                if r["color"] == c:

                    break

                miss += 1


            score[c] += min(
                miss*2,
                20
            )


        return score



    # -----------------------------
    # 半波
    # -----------------------------

    def half_score(self):

        score = defaultdict(float)


        for i,r in enumerate(self.rows):

            weight = 30-i


            for h in r["half"]:

                score[h]+=weight



        for h in HALF_WAVES:

            miss=0

            for r in self.rows:

                if h in r["half"]:
                    break

                miss+=1


            score[h]+=min(
                miss*1.5,
                20
            )


        return dict(score)



    # -----------------------------
    # 半半波
    # -----------------------------

    def halfhalf_score(self):

        score = defaultdict(float)


        for i,r in enumerate(self.rows):

            weight = 30-i

            score[r["halfhalf"]] += weight



        for h in HALF_HALF_WAVES:

            miss=0

            for r in self.rows:

                if r["halfhalf"]==h:
                    break

                miss+=1


            score[h]+=min(
                miss*1.5,
                20
            )


        return dict(score)




    # -----------------------------
    # 综合
    # -----------------------------

    def predict(self):


        color=self.color_score()

        half=self.half_score()

        halfhalf=self.halfhalf_score()



        final={

            "红":0,
            "蓝":0,
            "绿":0

        }



        # 颜色权重

        for k,v in color.items():

            final[k]+=v*0.45



        # 半波贡献

        for k,v in half.items():

            final[k[0]]+=v*0.35



        # 半半波贡献

        for k,v in halfhalf.items():

            final[k[0]]+=v*0.20



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
                )[:5],


            "final":

                sorted(
                    final.items(),
                    key=lambda x:x[1],
                    reverse=True
                )

        }





# =====================================================
# 回测 V8.6
# =====================================================


def backtest_v86(rows, test=50):


    hit_color=0

    hit_half=0

    hit_halfhalf=0


    total=min(
        test,
        len(rows)-31
    )



    for i in range(total):


        history=rows[i+1:]


        engine=PredictEngine(history)


        result=engine.predict()



        actual=rows[i]



        # 颜色TOP1

        if result["final"][0][0]==actual["color"]:

            hit_color+=1



        # 半波TOP3

        half_list=[

            x[0]

            for x in result["half"][:3]

        ]


        if any(

            h in actual["half"]

            for h in half_list

        ):

            hit_half+=1




        hh=[

            x[0]

            for x in result["halfhalf"][:3]

        ]


        if actual["halfhalf"] in hh:

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
# 参数自动优化 V8.6
# =====================================================


def auto_search_v86(rows):

    print()
    print("开始V8.6自动调参...")


    best_score=-1

    best=None



    search=list(product(

        CONFIG["search_space"]["trend_weight"],

        CONFIG["search_space"]["frequency_weight"],

        CONFIG["search_space"]["missing_weight"],

        CONFIG["search_space"]["pattern_weight"]

    ))



    for index,p in enumerate(search,1):


        score=0


        CONFIG["trend_weight"]=p[0]
        CONFIG["frequency_weight"]=p[1]
        CONFIG["missing_weight"]=p[2]
        CONFIG["pattern_weight"]=p[3]



        bt=backtest_v86(
            rows,
            min(20,len(rows)-1)
        )



        score=(

            bt["color"]*0.45

            +

            bt["half"]*0.35

            +

            bt["halfhalf"]*0.20

        )



        print(
            "参数",
            index,
            "得分",
            round(score,2)
        )



        if score>best_score:

            best_score=score

            best={

                "trend_weight":p[0],

                "frequency_weight":p[1],

                "missing_weight":p[2],

                "pattern_weight":p[3]

            }




    if best:


        with open(

            PARAM_FILE,

            "w",

            encoding="utf-8"

        ) as f:


            json.dump(

                best,

                f,

                ensure_ascii=False,

                indent=2

            )


        print(
            "V8.6最佳参数保存"
        )





# =====================================================
# 加载参数
# =====================================================


def load_v86_params():


    if not os.path.exists(PARAM_FILE):

        return



    try:

        with open(

            PARAM_FILE,

            "r",

            encoding="utf-8"

        ) as f:


            data=json.load(f)



        for k,v in data.items():

            if k in CONFIG:

                CONFIG[k]=v



        print(
            "加载V8.6参数"
        )



    except:

        pass





# =====================================================
# 显示预测
# =====================================================


def show_prediction(result):


    print()

    print("====================")

    print(
        "新澳门彩 V8.6预测"
    )


    print()

    print(
        "颜色TOP:"
    )


    for x in result["final"]:

        print(
            x[0],
            round(x[1],2)
        )



    print()

    print(
        "半波TOP:"
    )


    for x in result["half"]:

        print(
            x[0],
            round(x[1],2)
        )



    print()

    print(
        "半半波TOP:"
    )


    for x in result["halfhalf"]:

        print(
            x[0],
            round(x[1],2)
        )


    print("====================")





# =====================================================
# 最近走势
# =====================================================


def show_recent(rows):


    print()

    print(
        "最近30期开奖结果"
    )

    print("--------------------")


    for r in rows[:30]:


        print(

            r["issue"],

            "特码",

            r["special"],

            r["color"],

            r["halfhalf"]

        )


    print("--------------------")





# =====================================================
# 报告
# =====================================================


def create_report_v86(rows,result,bt):


    with open(

        REPORT_FILE,

        "w",

        encoding="utf-8"

    ) as f:



        f.write(
            "# 新澳门彩 V8.6预测报告\n\n"
        )


        f.write(
            "## 最新开奖\n\n"
        )


        r=rows[0]


        f.write(

f"""
期号:
{r['issue']}

特码:
{r['special']}

颜色:
{r['color']}

半半波:
{r['halfhalf']}


"""

        )



        f.write(
            "\n## 下一期预测\n\n"
        )


        f.write(
            str(result["final"])
        )


        f.write(
            "\n\n## 回测\n"
        )


        f.write(

f"""
颜色:
{bt['color']}%

半波:
{bt['half']}%

半半波:
{bt['halfhalf']}%

"""

        )





# =====================================================
# 主程序
# =====================================================


def main():


    print(
        "正在获取新澳门彩..."
    )


    rows=fetch_new_macau(30)



    if len(rows)<10:

        print(
            "数据不足"
        )

        return



    show_recent(rows)



    if not os.path.exists(PARAM_FILE):

        auto_search_v86(rows)



    load_v86_params()



    engine=PredictEngine(rows)


    result=engine.predict()



    show_prediction(result)



    bt=backtest_v86(
        rows,
        20
    )



    print()

    print("====================")

    print(
        "V8.6最近回测"
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


    print("====================")



    create_report_v86(
        rows,
        result,
        bt
    )


    print(
        "报告生成:",
        REPORT_FILE
    )





if __name__=="__main__":

    main()