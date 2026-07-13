#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
澳门新彩六合彩预测系统 V8.4 PRO

升级:
1. 新澳门彩专用提取
2. 多周期趋势
3. 颜色转移矩阵
4. 冷热平衡
5. 半波动态模型
6. 半半波状态模型
7. 动态融合评分
8. 滚动回测
9. 自动调参
"""


import os
import re
import json
import argparse
import urllib.request

from collections import Counter, defaultdict
from itertools import product


# =====================================================
# 配置
# =====================================================

CONFIG = {

    "color_weight":40,

    "half_weight":35,

    "halfhalf_weight":25,


    "api_url":
    "https://marksix6.net/index.php?api=1",


    "search_space":{

        "color_weight":[35,40,45],

        "half_weight":[30,35,40],

        "halfhalf_weight":[20,25,30]

    }

}


PARAM_FILE="macau_v84_params.json"

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
31,36,37,
41,42,47,48

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
# 属性
# =====================================================


def get_color(n):

    if n in RED:

        return "红"

    if n in BLUE:

        return "蓝"

    return "绿"



def get_size(n):

    return "大" if n>=25 else "小"



def get_odd(n):

    return "单" if n%2 else "双"




# =====================================================
# 半波
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



def get_half(n):

    c=get_color(n)

    return [

        c+get_size(n),

        c+get_odd(n)

    ]




# =====================================================
# 半半波
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



def get_halfhalf(n):

    return (

        get_color(n)

        +

        get_size(n)

        +

        get_odd(n)

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
# 新澳门彩获取
# =====================================================


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



        print("扫描彩种:")



        for item in data.get(

            "lottery_data",

            []

        ):


            name=item.get(

                "name",

                ""

            ).strip()



            print(name)



            # 只锁定新澳门彩

            if name!="新澳门彩":

                continue



            print(

                "锁定彩种:",

                name

            )



            for line in item.get(

                "history",

                []

            ):



                nums=parse_numbers(line)



                if len(nums)<7:

                    continue



                special=nums[-1]



                if not 1<=special<=49:

                    continue



                # 提取期号

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


                    "issue":

                    issue,


                    "special":

                    special,


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



    # 去重复期

    cache={}


    for r in rows:


        cache[r["issue"]]=r



    rows=list(cache.values())



    rows.sort(

        key=lambda x:x["issue"],

        reverse=True

    )


    print(

        "获取新澳门彩:",

        len(rows),

        "期"

    )


    return rows[:limit]
    # =====================================================
# V8.4 多周期趋势模型
# =====================================================


def window_score(history, target):

    """
    多周期走势评分
    """

    score=0


    windows=[

        (20,0.4),

        (50,0.3),

        (100,0.2),

        (300,0.1)

    ]



    for size,weight in windows:


        data=history[:size]


        if not data:

            continue



        count=data.count(target)


        score += (

            count /

            len(data)

            *

            weight

            *

            100

        )


    return score




# =====================================================
# 颜色转移矩阵
# =====================================================


def color_transition(rows):


    matrix=defaultdict(

        Counter

    )


    colors=[

        r["color"]

        for r in rows

    ]



    for i in range(

        len(colors)-1

    ):


        now=colors[i]

        nxt=colors[i+1]


        matrix[now][nxt]+=1



    return matrix




def transition_score(rows):


    score={

        c:0

        for c in COLORS

    }



    if len(rows)<2:

        return score



    matrix=color_transition(rows)



    last=rows[0]["color"]



    if last in matrix:


        total=sum(

            matrix[last].values()

        )


        for c,v in matrix[last].items():

            score[c]=(

                v/

                total

                *

                100

            )


    return score




# =====================================================
# 冷热平衡模型
# =====================================================


def cold_hot_score(rows):


    result={

        c:0

        for c in COLORS

    }



    colors=[

        r["color"]

        for r in rows

    ]



    for c in COLORS:


        hot=colors[:50].count(c)

        medium=colors[:100].count(c)


        miss=0


        for x in colors:

            if x==c:

                break

            miss+=1



        result[c]=(

            hot*0.6

            +

            medium*0.3

            +

            min(miss,30)*0.1

        )



    return result





# =====================================================
# 颜色预测核心
# =====================================================


def color_predict(rows):


    score={

        c:0

        for c in COLORS

    }



    trend={

        c:window_score(

            [

                r["color"]

                for r in rows

            ],

            c

        )

        for c in COLORS

    }



    trans=transition_score(rows)



    cold=cold_hot_score(rows)



    for c in COLORS:


        score[c]=(

            trend[c]*0.5

            +

            trans[c]*0.3

            +

            cold[c]*0.2

        )



    return score




# =====================================================
# 半波动态模型
# =====================================================


def half_predict(rows):


    score={

        h:0

        for h in HALF_WAVES

    }



    for h in HALF_WAVES:


        history=[

            r["half"]

            for r in rows

        ]


        count=0


        for i,x in enumerate(history[:100]):


            if h in x:

                count+=100-i



        miss=0


        for r in rows:


            if h in r["half"]:

                break

            miss+=1



        score[h]=(

            count*0.7

            +

            min(miss,50)*0.3

        )



    return score




# =====================================================
# 半半波状态模型
# =====================================================


def halfhalf_transition(rows):


    matrix=defaultdict(

        Counter

    )


    data=[

        r["halfhalf"]

        for r in rows

    ]



    for i in range(

        len(data)-1

    ):


        matrix[data[i]][data[i+1]]+=1



    return matrix




def halfhalf_predict(rows):


    score={

        h:0

        for h in HALF_HALF_WAVES

    }



    data=[

        r["halfhalf"]

        for r in rows

    ]



    for i,h in enumerate(data[:120]):


        score[h]+=120-i



    matrix=halfhalf_transition(rows)



    last=data[0]



    if last in matrix:


        total=sum(

            matrix[last].values()

        )



        for h,v in matrix[last].items():


            score[h]+= (

                v/

                total

                *

                80

            )



    return score




# =====================================================
# 综合融合模型
# =====================================================


def normalize(score):


    total=sum(score.values())


    if total==0:

        return score



    return {

        k:

        v/total*100

        for k,v in score.items()

    }




def rank(score,n=5):


    return sorted(

        score.items(),

        key=lambda x:x[1],

        reverse=True

    )[:n]




def fusion_predict(rows):


    color=color_predict(rows)


    half=half_predict(rows)


    halfhalf=halfhalf_predict(rows)



    final={

        c:0

        for c in COLORS

    }



    for c,v in color.items():

        final[c]+= (

            v

            *

            CONFIG["color_weight"]

            /

            100

        )



    for h,v in half.items():

        final[h[0]]+=(

            v

            *

            CONFIG["half_weight"]

            /

            100

        )



    for h,v in halfhalf.items():

        final[h[0]]+=(

            v

            *

            CONFIG["halfhalf_weight"]

            /

            100

        )



    return {


        "color":

        color,


        "half":

        half,


        "halfhalf":

        halfhalf,


        "fusion":

        final

    }




def predict(rows):


    result=fusion_predict(rows)



    return {


        "color_rank":

        rank(

            result["fusion"],

            3

        ),



        "half_rank":

        rank(

            result["half"],

            5

        ),



        "halfhalf_rank":

        rank(

            result["halfhalf"],

            5

        ),



        "probability":

        normalize(

            result["fusion"]

        ),



        "raw":

        result

    }
    # =====================================================
# 开奖显示
# =====================================================


def show_latest(rows):

    if not rows:

        return


    r=rows[0]


    print()

    print("====================")

    print("最新新澳门彩开奖结果")


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

        "半半波:",

        r["halfhalf"]

    )


    print("====================")





def show_recent(rows,count=10):


    print()


    print(

        f"最近{count}期开奖结果"

    )


    print("--------------------")


    for r in rows[:count]:


        print(

            r["issue"],

            "特码",

            r["special"],

            r["color"],

            r["halfhalf"]

        )


    print("--------------------")





# =====================================================
# V8.4 回测
# =====================================================


def backtest(rows,test_len=100):


    result={

        "color1":0,

        "color3":0,

        "half3":0,

        "halfhalf3":0,

        "fusion1":0,

        "fusion3":0,

        "total":0

    }



    test_len=min(

        test_len,

        len(rows)-100

    )



    for i in range(test_len):


        history=rows[i+1:]


        actual=rows[i]



        pred=predict(history)



        color_rank=[

            x[0]

            for x in pred["color_rank"]

        ]



        half_rank=[

            x[0]

            for x in pred["half_rank"][:3]

        ]



        hh_rank=[

            x[0]

            for x in pred["halfhalf_rank"][:3]

        ]



        if actual["color"]==color_rank[0]:

            result["color1"]+=1



        if actual["color"] in color_rank[:3]:

            result["color3"]+=1



        if any(

            x in actual["half"]

            for x in half_rank

        ):

            result["half3"]+=1



        if actual["halfhalf"] in hh_rank:

            result["halfhalf3"]+=1



        if (

            actual["color"]==color_rank[0]

            and

            actual["halfhalf"] in hh_rank

        ):

            result["fusion1"]+=1



        if (

            actual["color"] in color_rank[:3]

            and

            actual["halfhalf"] in hh_rank

        ):

            result["fusion3"]+=1



        result["total"]+=1



    t=result["total"]



    return {


        k:

        (

            v/t

            if t

            else 0

        )

        for k,v in result.items()

        if k!="total"

    }




# =====================================================
# 自动调参
# =====================================================


def auto_search(rows):


    print(

        "开始V8.4自动调参..."

    )


    keys=list(

        CONFIG["search_space"].keys()

    )


    values=list(

        CONFIG["search_space"].values()

    )


    best_score=-1

    best=None



    for index,combo in enumerate(

        product(*values),

        1

    ):


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

            100

        )


        score=(

            bt["color1"]*40

            +

            bt["half3"]*35

            +

            bt["halfhalf3"]*25

        )



        if score>best_score:


            best_score=score

            best=params.copy()



        print(

            "参数",

            index,

            "得分",

            round(score,2)

        )



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

            "最佳参数保存"

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

            encoding="utf-8"

        ) as f:


            data=json.load(f)



        for k,v in data.items():

            if k in CONFIG:

                CONFIG[k]=v



        print(

            "加载V8.4参数"

        )


    except:

        pass





# =====================================================
# 预测输出
# =====================================================


def print_prediction(result):


    print()


    print("====================")

    print("新澳门彩 V8.4预测")


    print()


    print("颜色TOP:")


    for x in result["color_rank"]:


        print(

            x[0],

            round(x[1],2)

        )



    print()


    print("半波TOP:")


    for x in result["half_rank"]:


        print(

            x[0],

            round(x[1],2)

        )



    print()


    print("半半波TOP:")


    for x in result["halfhalf_rank"]:


        print(

            x[0],

            round(x[1],2)

        )


    print()


    print(

        "综合概率:",

        result["probability"]

    )


    print("====================")





# =====================================================
# 报告
# =====================================================


def create_report(rows,pred,bt):


    with open(

        REPORT_FILE,

        "w",

        encoding="utf-8"

    ) as f:


        r=rows[0]


        f.write(

            "# 新澳门彩 V8.4预测报告\n\n"

        )


        f.write(

f"""
最新开奖:

期号:
{r['issue']}

特码:
{r['special']}

颜色:
{r['color']}

半半波:
{r['halfhalf']}


## 当前预测

颜色:
{pred['color_rank']}


半波:
{pred['half_rank']}


半半波:
{pred['halfhalf_rank']}


## 回测

颜色TOP1:
{bt['color1']:.2%}


颜色TOP3:
{bt['color3']:.2%}


半波TOP3:
{bt['half3']:.2%}


半半波TOP3:
{bt['halfhalf3']:.2%}


综合TOP1:
{bt['fusion1']:.2%}


综合TOP3:
{bt['fusion3']:.2%}

"""

        )





# =====================================================
# 主程序
# =====================================================


def main():


    parser=argparse.ArgumentParser()


    parser.add_argument(

        "--search",

        action="store_true"

    )


    args=parser.parse_args()



    print(

        "正在获取新澳门彩..."

    )


    rows=fetch_macau(800)



    if not rows:


        print(

            "没有数据"

        )

        return



    show_latest(rows)


    show_recent(rows,10)



    if (

        args.search

        or

        not os.path.exists(PARAM_FILE)

    ):


        auto_search(rows)



    load_params()



    pred=predict(rows)


    print_prediction(pred)



    bt=backtest(rows,100)



    print()


    print("====================")

    print("V8.4最近100期回测")


    for k,v in bt.items():

        print(

            k,

            f"{v:.2%}"

        )


    print("====================")



    create_report(

        rows,

        pred,

        bt

    )


    print(

        "报告生成:",

        REPORT_FILE

    )





if __name__=="__main__":

    main()