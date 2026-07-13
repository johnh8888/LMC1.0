#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
澳门六合彩颜色 + 半波 + 半半波预测系统 V8.2

功能:
1. 颜色预测
2. 半波预测
3. 半半波预测
4. 自动调参
5. 开奖结果显示
6. 最近走势分析
7. 自动生成报告
"""


import os
import re
import json
import math
import time
import random
import argparse
import urllib.request

from collections import Counter, defaultdict
from itertools import product
from datetime import datetime


# =====================================================
# 全局配置
# =====================================================


CONFIG = {


    "color_weight":35,


    "half_weight":35,


    "halfhalf_weight":25,


    "fusion_weight":5,


    "train_len":500,


    "min_train":50,


    "search_space":{


        "color_weight":[30,35,40],


        "half_weight":[30,35,40],


        "halfhalf_weight":[20,25,30],


        "fusion_weight":[5,10]

    },


    "api_url":
    "https://marksix6.net/index.php?api=1"

}



PARAM_FILE="macau_best_params.json"

REPORT_FILE="result.md"





# =====================================================
# 颜色定义
# =====================================================


RED={
1,2,7,8,12,13,18,19,
23,24,29,30,34,35,
40,45,46
}


BLUE={
3,4,9,10,14,15,
20,25,26,31,36,
37,41,42,47,48
}


GREEN={
5,6,11,16,17,
21,22,27,28,32,
33,38,39,43,44,49
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


    if num in BLUE:

        return "蓝"


    return "绿"





def get_size(num):


    return "大" if num>=25 else "小"





def get_odd_even(num):


    return "单" if num%2 else "双"





# =====================================================
# 半波定义
# =====================================================


HALF_WAVES=[


"红大",
"红小",
"红单",
"红双",


"蓝大",
"蓝小",
"蓝单",
"蓝双",


"绿大",
"绿小",
"绿单",
"绿双"


]





def get_half(num):


    c=get_color(num)


    return [

        c+get_size(num),

        c+get_odd_even(num)

    ]





# =====================================================
# 半半波定义
# =====================================================


HALF_HALF_WAVES=[


"红大单",
"红大双",
"红小单",
"红小双",


"蓝大单",
"蓝大双",
"蓝小单",
"蓝小双",


"绿大单",
"绿大双",
"绿小单",
"绿小双"


]





def get_halfhalf(num):


    return (

        get_color(num)

        +

        get_size(num)

        +

        get_odd_even(num)

    )
    # =====================================================
# 数据获取
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





def next_issue(issue):


    try:

        y,n=issue.split("/")

        return f"{y}/{int(n)+1:03d}"

    except:

        return issue





def fetch_macau(limit=800):


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

            timeout=20

        ).read()



        data=json.loads(

            data.decode("utf-8")

        )





        for item in data.get(

            "lottery_data",

            []

        ):


            if "澳门" not in item.get(

                "name",

                ""

            ):

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



                special=nums[6]



                m=re.search(

                    r"(\d{6,7})",

                    line

                )


                if not m:

                    continue



                raw=m.group(1)



                if len(raw)==6:


                    issue=(

                        raw[:2]

                        +

                        "/"

                        +

                        str(

                            int(raw[2:])

                        ).zfill(3)

                    )



                else:


                    issue=(

                        raw[2:4]

                        +

                        "/"

                        +

                        str(

                            int(raw[4:])

                        ).zfill(3)

                    )





                rows.append({


                    "issue":

                    issue,


                    "special":

                    special,


                    "color":

                    get_color(special),


                    "size":

                    get_size(special),


                    "odd":

                    get_odd_even(special),


                    "half":

                    get_half(special),


                    "halfhalf":

                    get_halfhalf(special)

                })





    except Exception as e:


        print(

            "数据获取失败:",

            e

        )





    rows.sort(

        key=lambda x:x["issue"],

        reverse=True

    )



    print(

        f"获取澳门数据: {len(rows)}期"

    )



    return rows[:limit]
    # =====================================================
# 开奖信息显示
# =====================================================


def show_latest(rows):


    if not rows:

        return



    r=rows[0]



    print()

    print(

        "===================="

    )


    print(

        "最新开奖结果"

    )


    print(

        "期号:",

        r["issue"]

    )


    print(

        "特码:",

        r["special"]

    )


    print(

        "颜色:",

        r["color"]

    )


    print(

        "大小:",

        r["size"]

    )


    print(

        "单双:",

        r["odd"]

    )


    print(

        "半波:",

        "、".join(

            r["half"]

        )

    )


    print(

        "半半波:",

        r["halfhalf"]

    )


    print(

        "===================="

    )





def show_recent(rows,count=10):


    print()


    print(

        "最近",

        count,

        "期开奖结果"

    )


    for r in rows[:count]:


        print(

            r["issue"],

            "特码",

            r["special"],

            r["color"],

            r["halfhalf"]

        )
        # =====================================================
# 通用评分模型
# =====================================================


class ScoreEngine:


    def __init__(self,targets):


        self.targets=targets





    def predict(self,history):


        score={

            t:0

            for t in self.targets

        }





        # 最近走势权重


        for i,x in enumerate(history[:50]):


            if isinstance(x,list):

                values=x

            else:

                values=[x]



            for v in values:


                if v in score:


                    score[v]+=(

                        50-i

                    )





        # 遗漏补偿


        miss={

            t:999

            for t in self.targets

        }



        for i,x in enumerate(history):


            if isinstance(x,list):


                for v in x:


                    if v in miss:

                        miss[v]=i


            else:


                if x in miss:

                    miss[x]=i





        for k,v in miss.items():


            score[k]+=min(

                v*0.8,

                30

            )





        # 转换趋势


        if len(history)>3:


            trans=defaultdict(

                Counter

            )


            for i in range(

                len(history)-1

            ):


                a=history[i]

                b=history[i+1]



                if isinstance(a,list):

                    for aa in a:

                        trans[aa][b[0] if isinstance(b,list) else b]+=1

                else:

                    trans[a][b[0] if isinstance(b,list) else b]+=1





            last=history[0]



            if isinstance(last,list):

                last=last[0]



            if last in trans:


                total=sum(

                    trans[last].values()

                )


                for k,v in trans[last].items():


                    score[k]+=(

                        v/total*10

                    )





        return score
        # =====================================================
# 三个独立预测引擎
# =====================================================


color_engine=ScoreEngine(

    COLORS

)



half_engine=ScoreEngine(

    HALF_WAVES

)



halfhalf_engine=ScoreEngine(

    HALF_HALF_WAVES

)





# =====================================================
# 概率转换
# =====================================================


def probability(score):


    total=sum(

        max(v,0)

        for v in score.values()

    )



    if total==0:


        return {

            k:33.33

            for k in score

        }



    return {


        k:round(

            max(v,0)

            /

            total

            *

            100,

            2

        )


        for k,v in score.items()

    }





def rank(score,n=5):


    return sorted(

        score.items(),

        key=lambda x:x[1],

        reverse=True

    )[:n]
    # =====================================================
# 半波强化模型
# =====================================================


class HalfWaveEngine:



    def predict(self,rows):


        score={

            h:0

            for h in HALF_WAVES

        }





        # 最近100期半波走势


        for i,r in enumerate(rows[:100]):


            for h in r["half"]:


                if h in score:


                    score[h]+= (

                        100-i

                    )





        # 遗漏计算


        for h in HALF_WAVES:


            miss=0



            for r in rows:


                if h in r["half"]:


                    break


                miss+=1



            score[h]+=min(

                miss*1.2,

                40

            )





        # 半波转换


        if len(rows)>5:


            trans=defaultdict(

                Counter

            )



            for i in range(

                len(rows)-1

            ):


                old=rows[i]["half"]


                new=rows[i+1]["half"]



                for a in old:


                    for b in new:


                        trans[a][b]+=1





            last=rows[0]["half"]



            for a in last:


                if a in trans:


                    total=sum(

                        trans[a].values()

                    )



                    for b,v in trans[a].items():


                        score[b]+= (

                            v/total

                            *

                            8

                        )





        return score
        # =====================================================
# 半半波模型
# =====================================================


class HalfHalfEngine:



    def predict(self,rows):


        score={

            h:0

            for h in HALF_HALF_WAVES

        }



        for i,r in enumerate(rows[:120]):


            h=r["halfhalf"]


            score[h]+= (

                120-i

            )





        for h in HALF_HALF_WAVES:


            miss=0



            for r in rows:


                if r["halfhalf"]==h:


                    break


                miss+=1



            score[h]+=min(

                miss,

                25

            )





        return score





halfhalf_engine=HalfHalfEngine()
# =====================================================
# 三层融合预测
# =====================================================


def fusion_predict(rows):


    # =====================
    # 颜色历史
    # =====================


    color_history=[

        r["color"]

        for r in rows

    ]



    color_score=color_engine.predict(

        color_history

    )





    # =====================
    # 半波
    # =====================


    half_score=half_engine.predict(

        rows

    )





    # =====================
    # 半半波
    # =====================


    halfhalf_score=halfhalf_engine.predict(

        rows

    )





    final_score={

        c:0

        for c in COLORS

    }





    # ---------------------

    # 颜色贡献

    # ---------------------


    for c,v in color_score.items():


        final_score[c]+= (

            v

            *

            CONFIG["color_weight"]

            /

            100

        )





    # ---------------------

    # 半波贡献

    # ---------------------


    for h,v in half_score.items():


        c=h[0]



        final_score[c]+= (

            v

            *

            CONFIG["half_weight"]

            /

            100

        )





    # ---------------------

    # 半半波贡献

    # ---------------------


    for h,v in halfhalf_score.items():


        c=h[0]



        final_score[c]+= (

            v

            *

            CONFIG["halfhalf_weight"]

            /

            100

        )





    return {


        "color_score":

        color_score,



        "half_score":

        half_score,



        "halfhalf_score":

        halfhalf_score,



        "fusion_score":

        final_score

    }





# =====================================================
# 输出预测
# =====================================================


def predict(rows):


    result=fusion_predict(

        rows

    )



    color_rank=rank(

        result["fusion_score"],

        3

    )



    half_rank=rank(

        result["half_score"],

        5

    )



    halfhalf_rank=rank(

        result["halfhalf_score"],

        5

    )





    return {


        "color_rank":

        color_rank,



        "half_rank":

        half_rank,



        "halfhalf_rank":

        halfhalf_rank,



        "probability":

        probability(

            result["fusion_score"]

        ),



        "raw":

        result

    }
    def print_prediction(result):


    print()


    print(

        "===================="

    )


    print(

        "澳门六合彩 V8.2预测"

    )


    print()




    print(

        "颜色预测:"

    )


    for x in result["color_rank"]:


        print(

            x[0],

            round(x[1],2)

        )





    print()

    print(

        "半波预测:"

    )


    for x in result["half_rank"]:


        print(

            x[0],

            round(x[1],2)

        )





    print()

    print(

        "半半波预测:"

    )


    for x in result["halfhalf_rank"]:


        print(

            x[0],

            round(x[1],2)

        )





    print()

    print(

        "颜色概率:",

        result["probability"]

    )


    print(

        "===================="

    )
    # =====================================================
# 回测系统
# =====================================================


def backtest(rows,test_len=100):


    total=0


    color_hit=0

    half_hit=0

    halfhalf_hit=0

    fusion_hit=0





    details=[]





    test_len=min(

        test_len,

        len(rows)-CONFIG["min_train"]

    )





    for i in range(test_len):


        history=rows[i+1:]



        actual=rows[i]



        result=predict(

            history

        )





        # ----------------

        # 预测取值

        # ----------------


        predict_color=[

            x[0]

            for x in result["color_rank"][:1]

        ]



        predict_half=[

            x[0]

            for x in result["half_rank"][:3]

        ]



        predict_halfhalf=[

            x[0]

            for x in result["halfhalf_rank"][:3]

        ]





        c_ok=(

            actual["color"]

            in

            predict_color

        )



        h_ok=any(

            x in actual["half"]

            for x in predict_half

        )



        hh_ok=(

            actual["halfhalf"]

            in

            predict_halfhalf

        )





        if c_ok:

            color_hit+=1



        if h_ok:

            half_hit+=1



        if hh_ok:

            halfhalf_hit+=1





        if (

            c_ok

            and

            h_ok

            and

            hh_ok

        ):

            fusion_hit+=1





        total+=1





        if len(details)<20:


            details.append({


                "issue":

                actual["issue"],



                "special":

                actual["special"],



                "predict_color":

                predict_color,



                "predict_half":

                predict_half,



                "predict_halfhalf":

                predict_halfhalf,



                "actual":

                actual["halfhalf"]



            })





    return {


        "color_rate":

        color_hit/total if total else 0,



        "half_rate":

        half_hit/total if total else 0,



        "halfhalf_rate":

        halfhalf_hit/total if total else 0,



        "fusion_rate":

        fusion_hit/total if total else 0,



        "details":

        details

    }
    # =====================================================
# 走势统计
# =====================================================


def trend_summary(rows,count=20):


    data=rows[:count]


    color=Counter(

        r["color"]

        for r in data

    )


    half=Counter(

        r["half"][0]

        for r in data

    )


    hh=Counter(

        r["halfhalf"]

        for r in data

    )



    return {


        "color":

        color,



        "half":

        half,



        "halfhalf":

        hh

    }
    # =====================================================
# 自动调参
# =====================================================


def auto_search(rows):


    print(

        "开始V8.2自动调参..."

    )



    keys=list(

        CONFIG["search_space"].keys()

    )


    values=list(

        CONFIG["search_space"].values()

    )



    best_score=-999


    best_params=None



    total=len(

        list(

            product(*values)

        )

    )



    index=0





    for combo in product(*values):


        index+=1



        params=dict(

            zip(

                keys,

                combo

            )

        )



        for k,v in params.items():

            CONFIG[k]=v





        bt=backtest(

            rows,

            150

        )





        score=(


            bt["color_rate"]

            *

            35


            +

            bt["half_rate"]

            *

            35


            +

            bt["halfhalf_rate"]

            *

            25


            +

            bt["fusion_rate"]

            *

            5

        )





        if score>best_score:


            best_score=score


            best_params=params.copy()





        if index%20==0:


            print(

                "进度",

                index,

                "/",

                total,

                "最佳",

                round(best_score,2)

            )





    if best_params:


        with open(

            PARAM_FILE,

            "w",

            encoding="utf-8"

        ) as f:


            json.dump(

                best_params,

                f,

                ensure_ascii=False,

                indent=2

            )



        print(

            "最佳参数保存完成"

        )
        # =====================================================
# 加载参数
# =====================================================


def load_params():


    if not os.path.exists(

        PARAM_FILE

    ):

        return



    try:


        with open(

            PARAM_FILE,

            "r",

            encoding="utf-8"

        ) as f:


            params=json.load(

                f

            )



        for k,v in params.items():


            if k in CONFIG:


                CONFIG[k]=v



        print(

            "已加载最佳参数"

        )


    except:

        pass
        # =====================================================
# Markdown报告
# =====================================================


def create_report(

    rows,

    result,

    bt

):


    with open(

        REPORT_FILE,

        "w",

        encoding="utf-8"

    ) as f:



        latest=rows[0]



        f.write(

            "# 澳门六合彩 V8.2预测报告\n\n"

        )



        f.write(

            "## 最新开奖结果\n\n"

        )



        f.write(

            f"""

期号:
{latest['issue']}


特码:
{latest['special']}


颜色:
{latest['color']}


大小:
{latest['size']}


单双:
{latest['odd']}


半波:
{latest['half']}


半半波:
{latest['halfhalf']}


"""

        )



        f.write(

            "## 当前预测\n\n"

        )



        f.write(

            "颜色:\n"

        )


        f.write(

            str(result["color_rank"])

        )



        f.write(

            "\n\n半波:\n"

        )


        f.write(

            str(result["half_rank"])

        )



        f.write(

            "\n\n半半波:\n"

        )


        f.write(

            str(result["halfhalf_rank"])

        )




        f.write(

            "\n\n## 回测\n\n"

        )


        f.write(

            f"""

颜色命中:
{bt['color_rate']:.2%}


半波命中:
{bt['half_rate']:.2%}


半半波命中:
{bt['halfhalf_rate']:.2%}


融合命中:
{bt['fusion_rate']:.2%}

"""

        )
        # =====================================================
# 主程序
# =====================================================


def main():


    parser=argparse.ArgumentParser()


    parser.add_argument(

        "--search",

        action="store_true",

        help="强制自动调参"

    )


    args=parser.parse_args()





    print(

        "正在获取澳门数据..."

    )



    rows=fetch_macau(

        800

    )



    if not rows:


        print(

            "没有获取到数据"

        )

        return





    # 显示最新开奖


    show_latest(

        rows

    )



    show_recent(

        rows,

        10

    )





    # 自动调参


    if (

        args.search

        or

        not os.path.exists(

            PARAM_FILE

        )

    ):


        auto_search(

            rows

        )





    load_params()





    # 当前预测


    result=predict(

        rows

    )





    print_prediction(

        result

    )





    # 回测


    bt=backtest(

        rows,

        100

    )





    print()


    print(

        "===================="

    )


    print(

        "最近100期回测"

    )


    print(

        "颜色:",

        f"{bt['color_rate']:.2%}"

    )


    print(

        "半波:",

        f"{bt['half_rate']:.2%}"

    )


    print(

        "半半波:",

        f"{bt['halfhalf_rate']:.2%}"

    )


    print(

        "融合:",

        f"{bt['fusion_rate']:.2%}"

    )


    print(

        "===================="

    )





    # 生成报告


    create_report(

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