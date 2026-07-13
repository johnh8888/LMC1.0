#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
澳门颜色趋势分析 V8

功能：
- 历史数据获取
- 特征评分
- 自动参数搜索
- 滚动回测
- 自动生成报告

"""

import argparse
import copy
import json
import os
import random
import re
import time
import urllib.request

from collections import Counter, defaultdict
from itertools import product
from datetime import datetime


# =====================================================
# 配置
# =====================================================

CONFIG = {

    "api_url":
    "https://marksix6.net/index.php?api=1",

    "timeout":30,

    "max_retry":5,


    "min_train":50,

    "train_length":420,


    # 特征权重

    "recent_weight":8.0,

    "medium_weight":3.0,

    "long_weight":1.0,

    "omission_weight":1.2,

    "transition_weight":8.0,


    # 自动搜索范围

    "search_space":{

        "recent_weight":[6,8,10],

        "medium_weight":[2,3,4],

        "transition_weight":[6,8,10],

        "omission_weight":[0.8,1.2,1.5]

    }

}


PARAM_FILE="macau_v8_best.json"



# =====================================================
# 颜色定义
# =====================================================


RED={
1,2,7,8,
12,13,18,19,
23,24,29,30,
34,35,40,45,46
}


BLUE={
3,4,9,10,
14,15,20,
25,26,31,
36,37,41,
42,47,48
}


GREEN={
5,6,11,
16,17,21,22,
27,28,32,33,
38,39,43,44,49
}


COLORS=[
"红",
"蓝",
"绿"
]



def get_color(num):

    if num in RED:
        return "红"

    if num in BLUE:
        return "蓝"

    if num in GREEN:
        return "绿"

    return "红"



# =====================================================
# 数据解析
# =====================================================


def parse_numbers(text):

    nums=[]

    for x in re.findall(
        r"\d+",
        text
    ):

        n=int(x)

        if 1<=n<=49:
            nums.append(n)


    return nums



# =====================================================
# 获取澳门数据
# =====================================================


def fetch_macau(limit=800):


    headers={

        "User-Agent":
        "Mozilla/5.0"

    }


    for retry in range(
        CONFIG["max_retry"]
    ):


        try:

            req=urllib.request.Request(
                CONFIG["api_url"],
                headers=headers
            )


            with urllib.request.urlopen(
                req,
                timeout=CONFIG["timeout"]
            ) as response:


                raw=response.read()



            data=json.loads(
                raw.decode(
                    "utf-8"
                )
            )



            rows=[]



            for item in data.get(
                "lottery_data",
                []
            ):


                name=item.get(
                    "name",
                    ""
                )


                if "澳门" not in name:
                    continue


                if "新澳门" in name:
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



                    rows.append({

                        "issue":
                        line[:7],

                        "normal":
                        nums[:6],

                        "special":
                        nums[6],

                        "color":
                        get_color(
                            nums[6]
                        )

                    })



            if rows:


                rows.sort(
                    key=lambda x:x["issue"],
                    reverse=True
                )


                print(
                    "成功获取数据:",
                    len(rows),
                    "期"
                )


                return rows[:limit]



        except Exception as e:


            print(
                "获取失败:",
                e
            )


            time.sleep(
                2
            )



    return []
    # =====================================================
# V8 特征评分模型
# =====================================================


class FeatureEngine:


    def __init__(self):

        self.colors=COLORS



    # ---------------------------------
    # 遗漏计算
    # ---------------------------------

    def omission_score(
        self,
        colors
    ):

        score={
            c:0
            for c in COLORS
        }


        for c in COLORS:


            miss=0


            for x in colors:

                if x==c:
                    break

                miss+=1



            score[c]=min(
                miss *
                CONFIG["omission_weight"],
                15
            )


        return score



    # ---------------------------------
    # 最近趋势
    # ---------------------------------

    def recent_score(
        self,
        colors
    ):


        score={
            c:0
            for c in COLORS
        }


        for i,c in enumerate(
            colors[:30]
        ):


            score[c]+=(
                CONFIG["recent_weight"]
                *
                (1-i/40)
            )


        return score



    # ---------------------------------
    # 中长期平衡
    # ---------------------------------

    def balance_score(
        self,
        colors
    ):


        score={
            c:0
            for c in COLORS
        }



        sample=colors[:200]


        if len(sample)==0:

            return score



        avg=len(sample)/3



        for c in COLORS:

            diff=avg-sample.count(c)


            if diff>0:

                score[c]+=diff



        return score



    # ---------------------------------
    # 转换关系
    # ---------------------------------

    def transition_score(
        self,
        colors
    ):


        score={
            c:0
            for c in COLORS
        }


        if len(colors)<3:

            return score



        table=defaultdict(
            Counter
        )


        for i in range(
            len(colors)-1
        ):

            table[
                colors[i]
            ][
                colors[i+1]
            ]+=1



        last=colors[0]


        if last in table:


            total=sum(
                table[last].values()
            )


            for c,v in table[last].items():

                score[c]+=(
                    v/total
                    *
                    CONFIG[
                        "transition_weight"
                    ]
                )


        return score




    # ---------------------------------
    # 综合评分
    # ---------------------------------

    def calculate(
        self,
        colors
    ):


        score={
            c:0
            for c in COLORS
        }



        models=[

            self.recent_score(colors),

            self.omission_score(colors),

            self.balance_score(colors),

            self.transition_score(colors)

        ]



        for model in models:

            for c,v in model.items():

                score[c]+=v



        return score



feature_engine=FeatureEngine()



# =====================================================
# 稳定性模拟
# =====================================================


class StabilityAnalyzer:



    def simulate(
        self,
        scores,
        times=3000
    ):


        result={
            c:0
            for c in COLORS
        }


        total=sum(
            max(v,0)
            for v in scores.values()
        )


        if total<=0:

            return {
                c:33.33
                for c in COLORS
            }



        probability={

            c:
            max(
                scores[c],
                0
            )
            /
            total

            for c in COLORS

        }



        for _ in range(times):


            r=random.random()


            acc=0



            for c,p in probability.items():


                acc+=p


                if r<=acc:

                    result[c]+=1

                    break



        return {

            c:
            round(
                result[c]/times*100,
                2
            )

            for c in COLORS

        }




stability_analyzer=StabilityAnalyzer()
# =====================================================
# V8 核心预测模块
# =====================================================


def normalize_probability(scores):


    total=sum(
        max(v,0)
        for v in scores.values()
    )


    if total<=0:

        return {
            c:33.33
            for c in COLORS
        }



    return {

        c:
        round(
            max(scores[c],0)
            /
            total
            *
            100,
            2
        )

        for c in COLORS

    }



def anti_streak(
    scores,
    colors
):


    if len(colors)<5:

        return scores



    last=colors[0]

    streak=0



    for c in colors:


        if c==last:

            streak+=1

        else:

            break



    # 连续过热修正

    if streak>=4:

        scores[last]-=(
            streak-3
        )*2.5



    return scores




def predict(
    colors
):


    if len(colors)<CONFIG["min_train"]:


        return {

            "predict":
            ["红","蓝"],

            "score":
            {},

            "probability":
            {},

            "confidence":
            50

        }



    scores=feature_engine.calculate(
        colors
    )



    scores=anti_streak(
        scores,
        colors
    )



    probability=normalize_probability(
        scores
    )


    stability=stability_analyzer.simulate(
        scores
    )



    ranking=sorted(

        scores.items(),

        key=lambda x:x[1],

        reverse=True

    )



    first=ranking[0][0]

    second=ranking[1][0]



    # 自动双色判断

    diff=(

        ranking[0][1]

        -

        ranking[1][1]

    )



    if diff<3:

        prediction=[

            first,

            second

        ]

    else:

        prediction=[

            first

        ]



    confidence=max(
        stability.values()
    )



    return {


        "predict":
        prediction,


        "score":
        scores,


        "probability":
        probability,


        "stability":
        stability,


        "confidence":
        round(
            confidence,
            2
        )

    }




# =====================================================
# 回测系统
# =====================================================


def backtest(
    rows,
    periods=100
):


    colors=[

        x["color"]

        for x in rows

    ]



    total=0

    hit=0



    details=[]



    max_test=min(
        periods,
        len(colors)-CONFIG["min_train"]
    )



    for i in range(
        max_test
    ):


        history=colors[i+1:]



        result=predict(
            history
        )



        actual=colors[i]


        ok=actual in result["predict"]



        total+=1



        if ok:

            hit+=1



        details.append({

            "actual":
            actual,


            "predict":
            result["predict"],


            "confidence":
            result["confidence"],


            "hit":
            ok

        })



    rate=(

        hit/total

        if total

        else 0

    )


    return rate,details
    # =====================================================
# 自动调参搜索
# =====================================================


def search_parameters(rows):


    print(
        "\n开始自动参数优化..."
    )


    keys=list(
        CONFIG["search_space"].keys()
    )


    values=list(
        CONFIG["search_space"].values()
    )


    combinations=list(
        product(*values)
    )



    best_rate=0

    best=None



    backup=copy.deepcopy(
        CONFIG
    )



    for index,combo in enumerate(
        combinations,
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



        rate,_=backtest(
            rows,
            150
        )



        print(

            f"{index}/{len(combinations)}",

            "命中率:",

            f"{rate:.2%}"

        )



        if rate>best_rate:

            best_rate=rate

            best=params.copy()



    CONFIG.update(
        backup
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
            "\n最佳参数:"
        )

        print(
            best
        )

        print(
            "测试命中率:",
            f"{best_rate:.2%}"
        )



    return best




# =====================================================
# 加载参数
# =====================================================


def load_parameters():


    if not os.path.exists(
        PARAM_FILE
    ):

        return False



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
            "加载历史最佳参数成功"
        )


        return True



    except:


        return False




# =====================================================
# 生成 Markdown 报告
# =====================================================


def create_report(
    issue,
    result,
    rate
):


    with open(
        "result.md",
        "w",
        encoding="utf-8"
    ) as f:



        f.write(
            "# 澳门颜色趋势分析 V8\n\n"
        )



        f.write(

            "预测期号："

            +

            str(issue)

            +

            "\n\n"

        )



        f.write(
            "## 推荐颜色\n\n"
        )


        f.write(

            "、".join(
                result["predict"]
            )

            +

            "\n\n"

        )



        f.write(
            "## 概率分析\n\n"
        )


        for c,p in result["probability"].items():

            f.write(

                f"{c}: {p}%\n"

            )



        f.write(
            "\n## 稳定检测\n\n"
        )


        for c,p in result["stability"].items():

            f.write(

                f"{c}: {p}%\n"

            )



        f.write(

            "\n## 历史回测\n\n"

        )


        f.write(

            f"近150期测试命中率: {rate:.2%}\n"

        )
        # =====================================================
# 主程序
# =====================================================


def main():


    parser=argparse.ArgumentParser(

        description=
        "澳门颜色趋势分析 V8"

    )


    parser.add_argument(

        "--search",

        action="store_true",

        help="强制重新搜索参数"

    )


    args=parser.parse_args()



    print(
        "正在获取澳门历史数据..."
    )



    rows=fetch_macau(
        800
    )



    if not rows:


        print(
            "没有获取到数据"
        )


        return




    # 自动搜索参数


    if (

        args.search

        or

        not os.path.exists(
            PARAM_FILE
        )

    ):


        search_parameters(
            rows
        )



    load_parameters()



    colors=[

        x["color"]

        for x in rows

    ]



    result=predict(
        colors
    )



    rate,_=backtest(

        rows,

        150

    )



    latest=rows[0]["issue"]



    print("\n====================")

    print(

        "预测期:",

        latest

    )


    print(

        "推荐颜色:",

        "、".join(
            result["predict"]
        )

    )


    print(

        "概率:",

        result["probability"]

    )


    print(

        "稳定度:",

        result["stability"]

    )


    print(

        "历史测试:",

        f"{rate:.2%}"

    )


    print("====================\n")




    create_report(

        latest,

        result,

        rate

    )



    print(
        "报告已生成 result.md"
    )





if __name__=="__main__":

    main()