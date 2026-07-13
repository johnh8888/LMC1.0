#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
澳门六合彩颜色 + 半波 + 半半波预测系统 V8.3 PRO

功能:
1. 颜色预测
2. 半波预测
3. 半半波预测
4. 自动调参
5. 开奖结果显示
6. 最近走势分析
7. 自动生成报告
8. GitHub Actions自动运行
"""


import os
import re
import json
import math
import argparse
import urllib.request

from collections import Counter, defaultdict
from itertools import product


# =====================================================
# 配置
# =====================================================


CONFIG = {

    "color_weight":35,

    "half_weight":35,

    "halfhalf_weight":25,

    "fusion_weight":5,


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



# =====================================================
# 属性
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



def get_half(num):

    c=get_color(num)

    return [

        c+get_size(num),

        c+get_odd_even(num)

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



def get_halfhalf(num):

    return (

        get_color(num)
        +
        get_size(num)
        +
        get_odd_even(num)

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

    print(
        "发现彩种:",
        item.get("name","")
    )


    name=item.get(
        "name",
        ""
    ).strip()


            if name not in [

                "新澳门六合彩",

                "新澳门六合彩特码",

                "澳门六合彩"

            ]:

                continue



            for line in item.get(

                "history",

                []

            ):


                nums=parse_numbers(line)



                # 必须有特码

                if len(nums)<7:

                    continue



                special=nums[-1]



                if not 1<=special<=49:

                    continue



                # =============================
                # 提取期号
                # =============================

                m=re.search(

                    r"(20\d{5,7})",

                    line

                )



                if m:


                    raw=m.group(1)



                    year=raw[:4]


                    num=raw[4:]



                    issue=(

                        year

                        +

                        "/"

                        +

                        str(

                            int(num)

                        ).zfill(3)

                    )


                else:


                    # 备用格式

                    m=re.search(

                        r"(\d{2})(\d{3})",

                        line

                    )


                    if not m:

                        continue



                    issue=(

                        "20"

                        +

                        m.group(1)

                        +

                        "/"

                        +

                        m.group(2)

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



    # =============================
    # 去除重复期号
    # =============================


    unique={}


    for r in rows:


        if r["issue"] not in unique:


            unique[r["issue"]]=r



    rows=list(

        unique.values()

    )



    # 最新在前

    rows.sort(

        key=lambda x:x["issue"],

        reverse=True

    )



    print(

        f"获取新澳门六合彩: {len(rows)}期"

    )


    return rows[:limit]
    # =====================================================
# 评分引擎
# =====================================================


class ScoreEngine:


    def __init__(self,targets):

        self.targets=targets



    def predict(self,history):


        score={

            t:0

            for t in self.targets

        }


        # 最近走势

        for i,x in enumerate(history[:80]):


            if isinstance(x,list):

                arr=x

            else:

                arr=[x]



            for v in arr:


                if v in score:

                    score[v]+=80-i



        # 遗漏补偿

        for t in self.targets:


            miss=0


            for x in history:


                if isinstance(x,list):

                    if t in x:

                        break

                else:

                    if t==x:

                        break


                miss+=1



            score[t]+=min(

                miss*1.2,

                40

            )



        return score





color_engine=ScoreEngine(

    COLORS

)





# =====================================================
# 半波强化模型
# =====================================================


class HalfWaveEngine:



    def predict(self,rows):


        score={

            h:0

            for h in HALF_WAVES

        }



        # 近期半波走势

        for i,r in enumerate(rows[:100]):


            for h in r["half"]:


                score[h]+=(
                    100-i
                )



        # 遗漏增强


        for h in HALF_WAVES:


            miss=0


            for r in rows:


                if h in r["half"]:

                    break


                miss+=1



            score[h]+=min(

                miss*1.8,

                50

            )



        # 降低同时出现偏差

        avg=sum(score.values())/len(score)



        for h in score:


            score[h]+=(
                score[h]-avg
            )*0.3



        return score





half_engine=HalfWaveEngine()





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


            score[h]+=(
                120-i
            )*1.5



        # 遗漏

        for h in HALF_HALF_WAVES:


            miss=0


            for r in rows:


                if r["halfhalf"]==h:

                    break


                miss+=1



            score[h]+=min(

                miss*1.8,

                45

            )



        return score





halfhalf_engine=HalfHalfEngine()





# =====================================================
# 融合预测
# =====================================================


def fusion_predict(rows):


    color_history=[

        r["color"]

        for r in rows

    ]



    color_score=color_engine.predict(

        color_history

    )



    half_score=half_engine.predict(

        rows

    )



    halfhalf_score=halfhalf_engine.predict(

        rows

    )



    final={

        c:0

        for c in COLORS

    }



    # 颜色权重

    for c,v in color_score.items():


        final[c]+=(
            v*
            CONFIG["color_weight"]
            /
            100
        )



    # 半波颜色贡献

    for h,v in half_score.items():


        c=h[0]


        final[c]+=(
            v*
            CONFIG["half_weight"]
            /
            100
        )



    # 半半波贡献

    for h,v in halfhalf_score.items():


        c=h[0]


        final[c]+=(
            v*
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


        "fusion":

        final

    }





# =====================================================
# 概率
# =====================================================


def probability(score):


    total=sum(

        max(value,0)

        for value in score.values()

    )



    if total<=0:


        return {

            k:33.33

            for k in score

        }



    return {


        k:round(

            max(value,0)
            /
            total
            *
            100,

            2

        )


        for k,value in score.items()

    }





def rank(score,n=5):


    return sorted(

        score.items(),

        key=lambda x:x[1],

        reverse=True

    )[:n]





# =====================================================
# 最终预测
# =====================================================


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
            result["half_score"],
            5
        ),


        "halfhalf_rank":

        rank(
            result["halfhalf_score"],
            5
        ),


        "probability":

        probability(
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

    print("最新开奖结果")

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
        "、".join(r["half"])
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
# 回测
# =====================================================


def backtest(rows,test_len=100):


    total=0


    color_hit=0

    half_hit=0

    halfhalf_hit=0

    fusion_hit=0



    test_len=min(

        test_len,

        len(rows)-50

    )



    for i in range(test_len):


        history=rows[i+1:]


        actual=rows[i]



        result=predict(history)



        color=result["color_rank"][0][0]


        half=[

            x[0]

            for x in result["half_rank"][:3]

        ]


        halfhalf=[

            x[0]

            for x in result["halfhalf_rank"][:3]

        ]



        c_ok=(

            color==actual["color"]

        )


        h_ok=any(

            x in actual["half"]

            for x in half

        )


        hh_ok=(

            actual["halfhalf"]

            in

            halfhalf

        )



        if c_ok:

            color_hit+=1


        if h_ok:

            half_hit+=1


        if hh_ok:

            halfhalf_hit+=1


        if c_ok and h_ok and hh_ok:

            fusion_hit+=1



        total+=1



    return {


        "color_rate":

        color_hit/total if total else 0,


        "half_rate":

        half_hit/total if total else 0,


        "halfhalf_rate":

        halfhalf_hit/total if total else 0,


        "fusion_rate":

        fusion_hit/total if total else 0

    }





# =====================================================
# 自动调参
# =====================================================


def auto_search(rows):


    print(
        "开始V8.3自动调参..."
    )



    keys=list(
        CONFIG["search_space"].keys()
    )


    values=list(
        CONFIG["search_space"].values()
    )



    best_score=-1


    best=None



    combos=list(

        product(*values)

    )


    total=len(combos)



    for index,combo in enumerate(combos,1):


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

            bt["color_rate"]*35

            +

            bt["half_rate"]*35

            +

            bt["halfhalf_rate"]*25

            +

            bt["fusion_rate"]*5

        )



        if score>best_score:


            best_score=score

            best=params.copy()



        if index%20==0:


            print(

                "搜索进度",

                index,

                "/",

                total,

                "最佳",

                round(best_score,2)

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
            "最佳参数保存完成"
        )





# =====================================================
# 加载参数
# =====================================================


def load_params():


    if not os.path.exists(PARAM_FILE):

        return



    try:


        with open(

            PARAM_FILE,

            "r",

            encoding="utf-8"

        ) as f:


            params=json.load(f)



        for k,v in params.items():

            if k in CONFIG:

                CONFIG[k]=v



        print(
            "已加载最佳参数"
        )


    except Exception:

        pass
        # =====================================================
# 预测打印
# =====================================================


def print_prediction(result):


    print()

    print("====================")

    print("澳门六合彩 V8.3 PRO预测")


    print()

    print("颜色预测:")


    for name,score in result["color_rank"]:


        print(

            name,

            round(score,2)

        )


    print()


    print("半波预测:")


    for name,score in result["half_rank"]:


        print(

            name,

            round(score,2)

        )


    print()


    print("半半波预测:")


    for name,score in result["halfhalf_rank"]:


        print(

            name,

            round(score,2)

        )



    print()


    print(

        "颜色概率:",

        result["probability"]

    )


    print("====================")





# =====================================================
# 生成报告
# =====================================================


def create_report(rows,result,bt):


    latest=rows[0]



    with open(

        REPORT_FILE,

        "w",

        encoding="utf-8"

    ) as f:


        f.write(

            "# 澳门六合彩 V8.3 PRO预测报告\n\n"

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
{'、'.join(latest['half'])}

半半波:
{latest['halfhalf']}

---

"""

        )



        f.write(

            "## 最近10期开奖\n\n"

        )


        for r in rows[:10]:


            f.write(

f"""
{r['issue']} 特码:{r['special']} {r['color']} {r['halfhalf']}

"""

            )



        f.write(

            "\n## 当前预测\n\n"

        )


        f.write(

            "### 颜色预测\n\n"

        )


        f.write(

            str(
                result["color_rank"]
            )

        )



        f.write(

            "\n\n### 半波预测\n\n"

        )


        f.write(

            str(
                result["half_rank"]
            )

        )


        f.write(

            "\n\n### 半半波预测\n\n"

        )


        f.write(

            str(
                result["halfhalf_rank"]
            )

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

        action="store_true"

    )


    args=parser.parse_args()



    print(

        "正在获取澳门数据..."

    )



    rows=fetch_macau(800)



    if not rows:


        print(

            "数据为空"

        )

        return





    # 最新开奖结果


    show_latest(rows)


    show_recent(

        rows,

        10

    )





    # 自动调参


    if (

        args.search

        or

        not os.path.exists(PARAM_FILE)

    ):


        auto_search(rows)





    load_params()



    # 预测


    result=predict(rows)



    print_prediction(result)




    # 回测


    bt=backtest(

        rows,

        100

    )



    print()


    print("====================")


    print("最近100期回测")


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


    print("====================")





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
    