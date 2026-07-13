#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
澳门颜色趋势分析 V8
自动参数优化 + 滚动回测 + 稳定性分析版

说明：
本程序用于历史数据统计分析、模型测试和趋势研究。
"""

import argparse
import copy
import gzip
import json
import math
import os
import random
import re
import time
import urllib.request

from datetime import datetime, timedelta
from collections import Counter, defaultdict
from itertools import product


# =========================================================
# 基础配置
# =========================================================

CONFIG = {

    "api_url":
    "https://marksix6.net/index.php?api=1",

    "max_retries": 6,
    "timeout": 30,

    "train_max_len": 420,
    "min_train": 40,


    # 原始权重
    "window_recent": 8.0,
    "window_middle": 3.0,
    "window_long": 1.0,

    "omission_weight": 1.2,
    "transition_weight": 8.0,


    # 输出
    "show_details":20,


    # 自动搜索
    "search_space":{

        "window_recent":[6,8,10],

        "window_middle":[2,3,4],

        "transition_weight":[6,8,10],

        "omission_weight":[0.8,1.2,1.5],

    }

}


PARAM_FILE="macau_v8_best.json"


# =========================================================
# 颜色定义
# =========================================================


RED={
1,2,7,8,12,13,18,19,
23,24,29,30,34,35,
40,45,46
}


BLUE={
3,4,9,10,14,15,
20,25,26,31,
36,37,41,42,47,48
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



def get_color(n):

    if n in RED:
        return "红"

    if n in BLUE:
        return "蓝"

    if n in GREEN:
        return "绿"

    return "红"



# =========================================================
# 数字解析
# =========================================================


def parse_nums(text):

    return [
        int(x)
        for x in re.findall(r"\d+",text)
        if 1<=int(x)<=49
    ]



def next_issue(issue):

    try:

        if "/" in issue:

            y,n=issue.split("/")

            return (
                f"{y}/"
                f"{str(int(n)+1).zfill(3)}"
            )

        return issue

    except:

        return issue



# =========================================================
# 获取历史数据
# =========================================================


def fetch_macau(limit=800):

    headers={
        "User-Agent":
        "Mozilla/5.0"
    }


    for i in range(CONFIG["max_retries"]):

        try:

            req=urllib.request.Request(
                CONFIG["api_url"],
                headers=headers
            )


            with urllib.request.urlopen(
                req,
                timeout=CONFIG["timeout"]
            ) as r:


                raw=r.read()


                if "gzip" in str(
                    r.headers
                ).lower():

                    raw=gzip.decompress(raw)



                data=json.loads(
                    raw.decode("utf-8")
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


                    m=re.search(
                        r"(\d{6,7}).*?([\d,\s，]+)",
                        line
                    )


                    if not m:
                        continue



                    nums=parse_nums(
                        m.group(2)
                    )


                    if len(nums)<7:
                        continue



                    issue=m.group(1)


                    rows.append({

                        "issue":
                        issue,

                        "normal":
                        nums[:6],

                        "special":
                        nums[6],

                        "color":
                        get_color(nums[6])

                    })



            if rows:

                rows.sort(
                    key=lambda x:x["issue"],
                    reverse=True
                )


                print(
                    "获取数据:",
                    len(rows)
                )


                return rows[:limit]



        except Exception as e:

            print(
                "获取失败:",
                e
            )

            time.sleep(2)



    return []



# =========================================================
# V8 特征稳定分析
# =========================================================


class StabilityModel:


    def monte_carlo(
        self,
        scores,
        times=3000
    ):


        total={
            c:0
            for c in COLORS
        }


        s=sum(
            max(v,0)
            for v in scores.values()
        )


        if s<=0:

            return {
                c:0
                for c in COLORS
            }



        prob={

            c:
            max(scores.get(c,0),0)
            /
            s

            for c in COLORS

        }



        for _ in range(times):

            r=random.random()

            acc=0


            for c,p in prob.items():

                acc+=p


                if r<=acc:

                    total[c]+=1

                    break



        return {

            c:
            round(
                total[c]/times*100,
                2
            )

            for c in COLORS

        }




stability=StabilityModel()
# =========================================================
# V8 连续走势修正
# =========================================================


def streak_adjust(score, colors):

    if len(colors)<5:
        return score


    last=colors[0]

    count=0

    for c in colors:

        if c==last:
            count+=1
        else:
            break


    # 连续过长，降低追涨权重

    if count>=4:

        score[last]-=(
            count-3
        )*3


    return score



# =========================================================
# V8 概率转换
# =========================================================


def score_to_probability(score):


    total=sum(
        max(v,0)
        for v in score.values()
    )


    if total<=0:

        return {
            c:33.33
            for c in COLORS
        }


    return {

        c:
        round(
            max(score[c],0)
            /
            total*100,
            2
        )

        for c in COLORS

    }



# =========================================================
# V8核心预测模型
# =========================================================


def professional_predict(
        train_colors,
        train_normals,
        train_specials
):


    if len(train_colors)<CONFIG["min_train"]:

        return (
            ["红","蓝"],
            {},
            {},
            50,
            "数据不足"
        )



    score={
        c:0
        for c in COLORS
    }



    # -----------------------------------------------------
    # 1. 最近走势
    # -----------------------------------------------------

    for i,c in enumerate(
        train_colors[:30]
    ):

        score[c]+=(
            CONFIG["window_recent"]
            *
            (1-i/40)
        )



    # -----------------------------------------------------
    # 2. 中期趋势
    # -----------------------------------------------------

    for i,c in enumerate(
        train_colors[:80]
    ):

        score[c]+=(
            CONFIG["window_middle"]
            *
            (1-i/100)
        )



    # -----------------------------------------------------
    # 3. 长周期平衡
    # -----------------------------------------------------

    for c in COLORS:

        cnt=train_colors[:200].count(c)

        avg=200/3


        if cnt<avg:

            score[c]+=
            (
                avg-cnt
            )



    # -----------------------------------------------------
    # 4. 遗漏周期
    # -----------------------------------------------------

    for c in COLORS:


        miss=0


        for x in train_colors:

            if x==c:
                break

            miss+=1


        score[c]+=(
            min(
                miss*CONFIG["omission_weight"],
                15
            )
        )



    # -----------------------------------------------------
    # 5. 转换模型
    # -----------------------------------------------------


    transition=defaultdict(
        Counter
    )


    for i in range(
        len(train_colors)-1
    ):

        now=train_colors[i]

        nxt=train_colors[i+1]


        transition[now][nxt]+=1



    last=train_colors[0]


    if last in transition:


        total=sum(
            transition[last].values()
        )


        for c,v in transition[last].items():

            score[c]+=(
                v/total
                *
                CONFIG["transition_weight"]
            )



    # -----------------------------------------------------
    # 6. 连续走势修正
    # -----------------------------------------------------

    score=streak_adjust(
        score,
        train_colors
    )



    # -----------------------------------------------------
    # 7. 蒙特卡洛稳定检测
    # -----------------------------------------------------


    probability=score_to_probability(
        score
    )


    stability_result=stability.monte_carlo(
        score
    )



    ranked=sorted(
        score.items(),
        key=lambda x:x[1],
        reverse=True
    )


    best=ranked[0][0]


    second=ranked[1][0]



    # 双色模式

    if abs(
        ranked[0][1]
        -
        ranked[1][1]
    )<3:


        predict=[
            best,
            second
        ]

    else:

        predict=[
            best
        ]



    confidence=max(
        stability_result.values()
    )


    return (

        predict,

        dict(score),

        probability,

        round(
            confidence,
            2
        ),

        stability_result

    )



# =========================================================
# 滚动回测
# =========================================================


def rolling_backtest(
        rows,
        rounds=80
):


    colors=[
        x["color"]
        for x in rows
    ]


    total=0
    hit=0


    result=[]



    max_round=min(
        rounds,
        len(colors)-50
    )


    for i in range(
        max_round
    ):


        history=colors[i+1:]


        pred,score,prob,conf,stab=professional_predict(

            history[:420],

            [],

            []

        )


        actual=colors[i]


        ok=actual in pred


        total+=1


        if ok:

            hit+=1



        result.append({

            "actual":
            actual,

            "predict":
            pred,

            "confidence":
            conf,

            "hit":
            ok

        })



    rate=(
        hit/total
        if total
        else 0
    )


    return rate,result
    # =========================================================
# V8 自动参数搜索
# =========================================================


def evaluate_config(
        rows
):

    rate,_=rolling_backtest(
        rows,
        rounds=80
    )

    return rate



def run_grid_search(
        rows
):


    print(
        "\n开始V8自动参数搜索..."
    )


    keys=list(
        CONFIG["search_space"].keys()
    )


    values=list(
        CONFIG["search_space"].values()
    )


    combos=list(
        product(*values)
    )


    best_score=-1

    best_params=None



    old=copy.deepcopy(CONFIG)



    for index,combo in enumerate(
        combos,
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



        score=evaluate_config(
            rows
        )



        if score>best_score:

            best_score=score

            best_params=params.copy()



        print(
            f"{index}/{len(combos)}",
            "命中率:",
            f"{score:.2%}"
        )



    CONFIG.update(old)



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
            "\n最佳参数:"
        )

        print(
            best_params
        )

        print(
            "历史测试:",
            f"{best_score:.2%}"
        )


        return best_params



    return None




# =========================================================
# 加载参数
# =========================================================


def load_params():


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

            data=json.load(f)



        for k,v in data.items():

            if k in CONFIG:

                CONFIG[k]=v



        print(
            "已加载最佳参数"
        )


        return True


    except:


        return False




# =========================================================
# 输出报告
# =========================================================


def save_report(
        issue,
        pred,
        prob,
        conf,
        stab,
        rate
):


    with open(
        "result.md",
        "w",
        encoding="utf-8"
    ) as f:



        f.write(
            "# 澳门颜色分析 V8\n\n"
        )


        f.write(
            f"预测期号: {issue}\n\n"
        )


        f.write(
            "## 推荐颜色\n\n"
        )


        f.write(
            "、".join(pred)
            +
            "\n\n"
        )


        f.write(
            "## 概率评分\n\n"
        )


        for c,p in prob.items():

            f.write(
                f"{c}: {p}%\n"
            )


        f.write(
            "\n## 稳定检测\n\n"
        )


        for c,p in stab.items():

            f.write(
                f"{c}: {p}%\n"
            )



        f.write(
            "\n## 回测\n\n"
        )


        f.write(
            f"滚动命中率: {rate:.2%}\n"
        )



# =========================================================
# 主程序
# =========================================================


def main():


    parser=argparse.ArgumentParser()


    parser.add_argument(
        "--search",
        action="store_true"
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
            "无数据"
        )

        return



    if args.search or not os.path.exists(
        PARAM_FILE
    ):

        run_grid_search(
            rows
        )



    load_params()



    colors=[
        x["color"]
        for x in rows
    ]



    normals=[
        x["normal"]
        for x in rows
    ]


    specials=[
        x["special"]
        for x in rows
    ]



    pred,score,prob,conf,stab=professional_predict(

        colors,

        normals,

        specials

    )



    rate,_=rolling_backtest(
        rows,
        100
    )



    latest=rows[0]["issue"]



    print("\n===================")

    print(
        "预测期:",
        next_issue(latest)
    )

    print(
        "推荐:",
        "、".join(pred)
    )

    print(
        "概率:",
        prob
    )

    print(
        "稳定度:",
        stab
    )

    print(
        "历史测试:",
        f"{rate:.2%}"
    )

    print(
        "===================\n"
    )



    save_report(

        next_issue(latest),

        pred,

        prob,

        conf,

        stab,

        rate

    )



if __name__=="__main__":

    main()