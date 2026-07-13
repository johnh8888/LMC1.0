#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
澳门六合彩颜色 + 半波 + 半半波预测 V8.1

新增:
1. 颜色预测
2. 半波预测
3. 半半波预测
4. 三层融合模型
5. 独立回测统计
6. 自动调参
7. GitHub Actions兼容
"""

import os
import re
import json
import math
import time
import random
import copy
import gzip
import urllib.request
import argparse

from collections import Counter, defaultdict
from itertools import product
from datetime import datetime


# =====================================================
# 配置
# =====================================================

CONFIG = {


    # 三层融合权重

    "color_weight": 0.35,

    "half_weight": 0.35,

    "halfhalf_weight": 0.30,



    # 最近走势

    "recent_weight": 8.0,

    "medium_weight": 3.0,

    "long_weight": 1.0,



    # 遗漏

    "omission_weight": 1.2,



    # 转换

    "transition_weight": 6.0,



    # 半波

    "half_recent_weight": 6.0,

    "half_transition_weight": 5.0,



    # 半半波

    "halfhalf_recent_weight": 7.0,

    "halfhalf_transition_weight": 6.0,



    # 数据

    "api_url":

    "https://marksix6.net/index.php?api=1",


    "max_retry":6,


    "timeout":30,


    "min_train":30,


    "bankroll":10000,



    # 自动搜索

    "search_space":{


        "color_weight":[

            0.25,

            0.35,

            0.45,

            0.55

        ],


        "half_weight":[

            0.20,

            0.30,

            0.35,

            0.45

        ],


        "halfhalf_weight":[

            0.15,

            0.25,

            0.30,

            0.40

        ]


    }

}



PARAM_FILE="macau_best_params.json"

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

3,4,9,10,

14,15,20,25,

26,31,36,37,

41,42,47,48

}


GREEN={

5,6,11,16,

17,21,22,27,

28,32,33,38,

39,43,44,49

}


COLORS=[

"红",

"蓝",

"绿"

]



# =====================================================
# 半波定义
# =====================================================


HALF_WAVES=[]


for c in COLORS:


    for size in [

        "大",

        "小"

    ]:


        HALF_WAVES.append(

            c+size

        )


    for oe in [

        "单",

        "双"

    ]:


        HALF_WAVES.append(

            c+oe

        )



# =====================================================
# 半半波定义
# =====================================================


HALF_HALF_WAVES=[]


for c in COLORS:


    for size in [

        "大",

        "小"

    ]:


        for oe in [

            "单",

            "双"

        ]:


            HALF_HALF_WAVES.append(

                c+size+oe

            )



# =====================================================
# 基础函数
# =====================================================


def get_color(num):

    if num in RED:

        return "红"


    if num in BLUE:

        return "蓝"


    if num in GREEN:

        return "绿"


    return "红"




def get_size(num):

    return (

        "小"

        if num<=24

        else

        "大"

    )




def get_oe(num):

    return (

        "单"

        if num%2

        else

        "双"

    )




def get_half(num):

    return (

        get_color(num)

        +

        get_size(num)

    )




def get_halfhalf(num):

    return (

        get_color(num)

        +

        get_size(num)

        +

        get_oe(num)

    )
    # =====================================================
# 数据获取
# =====================================================


def parse_nums(value):


    return [

        int(x)

        for x in re.findall(

            r"\d+",

            value

        )

        if 1 <= int(x) <= 49

    ]





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

            ) as resp:


                raw=resp.read()



                if (

                    "gzip"

                    in

                    resp.headers.get(

                        "Content-Encoding",

                        ""

                    )

                ):


                    raw=gzip.decompress(

                        raw

                    )



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



                    for line in item.get(

                        "history",

                        []

                    ):



                        nums=parse_nums(

                            line

                        )



                        if len(nums)<7:

                            continue



                        rows.append({


                            "issue":

                            str(

                                line[:8]

                            ),



                            "numbers":

                            nums[:6],



                            "special":

                            nums[6],



                            "color":

                            get_color(

                                nums[6]

                            )

                        })



                if rows:


                    rows=rows[:limit]



                    print(

                        "获取澳门数据:",

                        len(rows),

                        "期"

                    )


                    return rows



        except Exception as e:


            print(

                "获取失败",

                e

            )


            time.sleep(

                retry+1

            )



    return []





# =====================================================
# 属性统计
# =====================================================


class AttributeCounter:



    def count_recent(

        self,

        history,

        attrs,

        weight=1

    ):


        result={

            a:0

            for a in attrs

        }



        for i,x in enumerate(

            history[:50]

        ):


            if x in result:


                result[x]+= (

                    weight

                    *

                    (1-i/50)

                )



        return result





    def omission(

        self,

        history,

        attrs

    ):


        result={}



        for a in attrs:


            miss=0



            for x in history:


                if x==a:

                    break


                miss+=1



            result[a]=miss



        return result





attribute_counter=AttributeCounter()
# =====================================================
# 颜色预测引擎
# =====================================================


class ColorEngine:



    def predict(

        self,

        colors

    ):



        score={

            c:0

            for c in COLORS

        }




        # 最近50期趋势


        for i,c in enumerate(

            colors[:50]

        ):


            score[c]+= (

                CONFIG["recent_weight"]

                *

                (1-i/50)

            )





        # 最近150期趋势


        for i,c in enumerate(

            colors[:150]

        ):


            score[c]+= (

                CONFIG["medium_weight"]

                *

                (1-i/150)

            )





        # 遗漏补偿


        miss=attribute_counter.omission(

            colors,

            COLORS

        )



        for c,v in miss.items():

            score[c]+= (

                v

                *

                CONFIG["omission_weight"]

            )





        # 转换关系


        if len(colors)>5:



            trans=defaultdict(

                Counter

            )



            for i in range(

                len(colors)-1

            ):


                trans[

                    colors[i]

                ][

                    colors[i+1]

                ]+=1





            last=colors[0]



            if last in trans:



                total=sum(

                    trans[last].values()

                )



                for c,v in trans[last].items():

                    score[c]+= (

                        v/total

                        *

                        CONFIG["transition_weight"]

                    )




        return score





color_engine=ColorEngine()





# =====================================================
# 半波预测引擎
# =====================================================


class HalfWaveEngine:



    def predict(

        self,

        history

    ):



        score={

            h:0

            for h in HALF_WAVES

        }





        recent=attribute_counter.count_recent(

            history,

            HALF_WAVES,

            CONFIG["half_recent_weight"]

        )



        for h,v in recent.items():

            score[h]+=v





        miss=attribute_counter.omission(

            history,

            HALF_WAVES

        )



        for h,v in miss.items():

            score[h]+= (

                v

                *

                0.8

            )





        # 半波转换


        if len(history)>5:



            trans=defaultdict(

                Counter

            )



            for i in range(

                len(history)-1

            ):


                trans[

                    history[i]

                ][

                    history[i+1]

                ]+=1





            last=history[0]



            if last in trans:



                total=sum(

                    trans[last].values()

                )



                for h,v in trans[last].items():

                    score[h]+= (

                        v/total

                        *

                        CONFIG["half_transition_weight"]

                    )





        return score





half_engine=HalfWaveEngine()
# =====================================================
# 半半波预测引擎
# =====================================================


class HalfHalfWaveEngine:



    def predict(

        self,

        history

    ):



        score={

            h:0

            for h in HALF_HALF_WAVES

        }





        # 最近走势


        recent=attribute_counter.count_recent(

            history,

            HALF_HALF_WAVES,

            CONFIG["halfhalf_recent_weight"]

        )



        for h,v in recent.items():

            score[h]+=v





        # 遗漏


        miss=attribute_counter.omission(

            history,

            HALF_HALF_WAVES

        )



        for h,v in miss.items():

            score[h]+= (

                v

                *

                0.8

            )







        # 转换链


        if len(history)>5:



            trans=defaultdict(

                Counter

            )



            for i in range(

                len(history)-1

            ):


                trans[

                    history[i]

                ][

                    history[i+1]

                ]+=1





            last=history[0]



            if last in trans:


                total=sum(

                    trans[last].values()

                )



                for h,v in trans[last].items():


                    score[h]+= (

                        v/total

                        *

                        CONFIG["halfhalf_transition_weight"]

                    )



        return score





halfhalf_engine=HalfHalfWaveEngine()





# =====================================================
# 三层融合模型
# =====================================================


class FusionEngine:



    def merge(

        self,

        color_score,

        half_score,

        halfhalf_score

    ):



        result={

            c:0

            for c in COLORS

        }



        # 颜色层


        for c,v in color_score.items():

            result[c]+= (

                v

                *

                CONFIG["color_weight"]

            )





        # 半波层


        for h,v in half_score.items():


            c=h[0]



            if c in result:


                result[c]+= (

                    v

                    *

                    CONFIG["half_weight"]

                )





        # 半半波层


        for h,v in halfhalf_score.items():


            c=h[0]



            if c in result:


                result[c]+= (

                    v

                    *

                    CONFIG["halfhalf_weight"]

                )



        return result





fusion_engine=FusionEngine()
# =====================================================
# 概率计算
# =====================================================


def calc_probability(score):


    total=sum(

        max(v,0)

        for v in score.values()

    )



    if total<=0:


        return {


            k:33.33

            for k in score.keys()

        }



    return {


        k:

        round(

            max(v,0)

            /

            total

            *

            100,

            2

        )


        for k,v in score.items()

    }





# =====================================================
# 排名工具
# =====================================================


def ranking(score,limit=5):


    return sorted(

        score.items(),

        key=lambda x:x[1],

        reverse=True

    )[:limit]





# =====================================================
# 核心预测
# =====================================================


def predict_v81(rows):


    colors=[]

    half_history=[]

    halfhalf_history=[]



    for r in rows:


        num=r["special"]



        colors.append(

            r["color"]

        )


        half_history.append(

            get_half(num)

        )


        halfhalf_history.append(

            get_halfhalf(num)

        )





    # 三层计算


    color_score=color_engine.predict(

        colors

    )



    half_score=half_engine.predict(

        half_history

    )



    halfhalf_score=halfhalf_engine.predict(

        halfhalf_history

    )




    fusion_score=fusion_engine.merge(

        color_score,

        half_score,

        halfhalf_score

    )





    color_probability=calc_probability(

        fusion_score

    )



    half_probability=calc_probability(

        half_score

    )



    halfhalf_probability=calc_probability(

        halfhalf_score

    )





    color_rank=ranking(

        fusion_score,

        3

    )



    half_rank=ranking(

        half_score,

        5

    )



    halfhalf_rank=ranking(

        halfhalf_score,

        8

    )





    return {


        "color_rank":

        color_rank,



        "half_rank":

        half_rank,



        "halfhalf_rank":

        halfhalf_rank,



        "color_probability":

        color_probability,



        "half_probability":

        half_probability,



        "halfhalf_probability":

        halfhalf_probability,



        "fusion_score":

        fusion_score

    }
    # =====================================================
# 半波命中判断
# =====================================================


def check_half_hit(

    predict_list,

    num

):


    target=get_half(num)


    return target in predict_list





# =====================================================
# 半半波命中判断
# =====================================================


def check_halfhalf_hit(

    predict_list,

    num

):


    target=get_halfhalf(num)


    return target in predict_list





# =====================================================
# 三层回测
# =====================================================


def backtest_v81(

    rows,

    test_count=100

):


    color_hit=0

    half_hit=0

    halfhalf_hit=0

    fusion_hit=0



    total=0



    details=[]



    max_test=min(

        test_count,

        len(rows)-CONFIG["min_train"]

    )





    for i in range(max_test):


        history=rows[i+1:]



        result=predict_v81(

            history

        )



        actual=rows[i]



        actual_color=actual["color"]



        actual_num=actual["special"]





        # 颜色TOP1


        color_predict=[

            x[0]

            for x in result["color_rank"][:1]

        ]



        # 半波TOP2


        half_predict=[

            x[0]

            for x in result["half_rank"][:2]

        ]



        # 半半波TOP3


        halfhalf_predict=[

            x[0]

            for x in result["halfhalf_rank"][:3]

        ]





        c_ok=(

            actual_color

            in

            color_predict

        )



        h_ok=check_half_hit(

            half_predict,

            actual_num

        )



        hh_ok=check_halfhalf_hit(

            halfhalf_predict,

            actual_num

        )





        if c_ok:

            color_hit+=1



        if h_ok:

            half_hit+=1



        if hh_ok:

            halfhalf_hit+=1





        # 融合命中

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



                "color":

                color_predict,



                "half":

                half_predict,



                "halfhalf":

                halfhalf_predict,



                "actual":

                actual_color,



                "special":

                actual_num,



                "color_hit":

                c_ok,



                "half_hit":

                h_ok,



                "halfhalf_hit":

                hh_ok

            })





    if total==0:


        return {}




    return {


        "color_rate":

        color_hit/total,



        "half_rate":

        half_hit/total,



        "halfhalf_rate":

        halfhalf_hit/total,



        "fusion_rate":

        fusion_hit/total,



        "details":

        details

    }
    # =====================================================
# 自动调参
# =====================================================


def auto_search(rows):


    print(

        "开始V8.1自动调参..."

    )



    keys=list(

        CONFIG["search_space"].keys()

    )


    values=list(

        CONFIG["search_space"].values()

    )



    best_score=-999

    best_params=None



    original=copy.deepcopy(

        CONFIG

    )




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





        result=backtest_v81(

            rows,

            150

        )



        if not result:

            continue





        score=(


            result["fusion_rate"]

            *

            50


            +

            result["color_rate"]

            *

            30


            +

            result["half_rate"]

            *

            15


            +

            result["halfhalf_rate"]

            *

            5

        )





        if score>best_score:


            best_score=score


            best_params=params.copy()



        if index%20==0:


            print(

                "搜索进度",

                index,

                "/",

                total,

                "最佳:",

                round(best_score,2)

            )





    CONFIG.update(

        original

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



    return best_params





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

            "加载最佳参数"

        )



    except Exception:


        pass
        # =====================================================
# 报告生成
# =====================================================


def create_report(

    rows,

    result,

    backtest

):


    with open(

        REPORT_FILE,

        "w",

        encoding="utf-8"

    ) as f:



        f.write(

            "# 澳门六合彩 V8.1 三层预测报告\n\n"

        )



        f.write(

            "## 当前预测\n\n"

        )



        f.write(

            "颜色预测:\n\n"

        )


        for x in result["color_rank"]:

            f.write(

                f"{x[0]} : {x[1]:.2f}\n"

            )



        f.write(

            "\n半波预测:\n\n"

        )


        for x in result["half_rank"]:

            f.write(

                f"{x[0]} : {x[1]:.2f}\n"

            )



        f.write(

            "\n半半波预测:\n\n"

        )


        for x in result["halfhalf_rank"]:

            f.write(

                f"{x[0]} : {x[1]:.2f}\n"

            )



        f.write(

            "\n## 概率\n\n"

        )



        f.write(

            "颜色概率:\n"

        )



        f.write(

            str(

                result["color_probability"]

            )

        )



        f.write(

            "\n\n半波概率:\n"

        )



        f.write(

            str(

                result["half_probability"]

            )

        )



        f.write(

            "\n\n半半波概率:\n"

        )



        f.write(

            str(

                result["halfhalf_probability"]

            )

        )




        f.write(

            "\n\n## 回测\n\n"

        )



        f.write(

            f"颜色命中率: {backtest['color_rate']:.2%}\n"

        )


        f.write(

            f"半波命中率: {backtest['half_rate']:.2%}\n"

        )


        f.write(

            f"半半波命中率: {backtest['halfhalf_rate']:.2%}\n"

        )


        f.write(

            f"融合命中率: {backtest['fusion_rate']:.2%}\n"

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



    rows=fetch_macau(

        800

    )



    if not rows:


        print(

            "没有数据"

        )


        return





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





    result=predict_v81(

        rows

    )



    bt=backtest_v81(

        rows,

        100

    )





    print(

        "\n===================="

    )


    print(

        "澳门六合彩 V8.1"

    )


    print(

        "颜色预测:",

        result["color_rank"][:3]

    )


    print(

        "半波预测:",

        result["half_rank"][:5]

    )


    print(

        "半半波预测:",

        result["halfhalf_rank"][:5]

    )



    print(

        "\n回测:"

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