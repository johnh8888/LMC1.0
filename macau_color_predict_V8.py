#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
澳门六合彩 V8 PRO

功能：
1. 特码颜色预测
2. 半波预测
3. 半半波预测
4. 正码辅助分析
5. 自动调参
6. 滚动回测
7. GitHub Actions兼容

"""

import argparse
import copy
import json
import math
import os
import random
import re
import time
import urllib.request

from collections import Counter, defaultdict
from itertools import product
from datetime import datetime



# =====================================================
# 全局配置
# =====================================================


CONFIG = {


    "api_url":
    "https://marksix6.net/index.php?api=1",


    "timeout":30,


    "retry":5,


    # 数据

    "train_length":420,

    "min_train":50,


    # 综合权重

    "color_weight":0.45,

    "half_weight":0.30,

    "half_half_weight":0.25,



    # 颜色模型

    "recent_weight":8.0,

    "medium_weight":3.0,

    "long_weight":1.0,

    "omission_weight":1.2,

    "transition_weight":8.0,



    # 半波模型

    "half_recent_weight":6.0,

    "half_transition_weight":5.0,



    # 半半波模型

    "halfhalf_recent_weight":6.0,

    "halfhalf_transition_weight":5.0,



    # 自动搜索

    "search_space":{


        "color_weight":[

            0.35,

            0.45,

            0.55

        ],


        "half_weight":[

            0.20,

            0.30,

            0.35

        ],


        "half_half_weight":[

            0.15,

            0.25,

            0.30

        ]

    }

}



PARAM_FILE = "macau_v8_pro_params.json"

REPORT_FILE = "result.md"




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





# =====================================================
# 基础属性
# =====================================================


def get_color(num):


    if num in RED:

        return "红"


    elif num in BLUE:

        return "蓝"


    elif num in GREEN:

        return "绿"


    return "红"





def get_size(num):


    if num>=25:

        return "大"


    return "小"





def get_odd_even(num):


    if num%2==0:

        return "双"


    return "单"





# =====================================================
# 半波
# 颜色 + 大小/单双
# =====================================================


def get_half_wave(num):


    color=get_color(num)


    size=get_size(num)


    odd=get_odd_even(num)



    return [

        color+"大",

        color+"小",

        color+"单",

        color+"双"

    ]





# =====================================================
# 半半波
# 颜色 + 大小 + 单双
# =====================================================


def get_half_half_wave(num):


    return (

        get_color(num)

        +

        get_size(num)

        +

        get_odd_even(num)

    )





# =====================================================
# 特码完整属性
# =====================================================


def get_attributes(num):


    return {


        "color":

        get_color(num),



        "half_half":

        get_half_half_wave(num),



        "size":

        get_size(num),



        "odd_even":

        get_odd_even(num)

    }
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
# 获取澳门历史数据
# =====================================================


def fetch_macau(limit=800):


    headers={

        "User-Agent":
        "Mozilla/5.0"

    }



    for retry in range(
        CONFIG["retry"]
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


                data=response.read()



            json_data=json.loads(

                data.decode(
                    "utf-8"
                )

            )



            rows=[]



            for item in json_data.get(

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

                        line[:10],



                        "normal":

                        nums[:6],



                        "special":

                        nums[6],



                        "color":

                        get_color(nums[6]),



                        "half_half":

                        get_half_half_wave(nums[6])


                    })




            if rows:


                rows.sort(

                    key=lambda x:x["issue"],

                    reverse=True

                )


                print(

                    "获取澳门数据:",

                    len(rows),

                    "期"

                )



                return rows[:limit]



        except Exception as e:


            print(

                "数据获取失败",

                e

            )


            time.sleep(2)



    return []





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





# =====================================================
# 属性统计基础类
# =====================================================


class AttributeCounter:



    def count_recent(

        self,

        values,

        target_list,

        weight=1

    ):


        score={

            x:0

            for x in target_list

        }



        for i,v in enumerate(

            values[:50]

        ):



            if v in score:


                score[v]+= (

                    weight

                    *

                    (1-i/60)

                )



        return score




    def omission(

        self,

        values,

        target_list

    ):


        score={

            x:0

            for x in target_list

        }



        for t in target_list:


            miss=0



            for v in values:


                if v==t:

                    break


                miss+=1



            score[t]=min(

                miss*1.2,

                15

            )



        return score





attribute_counter=AttributeCounter()
# =====================================================
# 颜色趋势模型
# =====================================================


class ColorEngine:


    def predict(self, colors):


        score={

            c:0

            for c in COLORS

        }



        # 最近走势

        for i,c in enumerate(

            colors[:50]

        ):


            score[c]+= (

                CONFIG["recent_weight"]

                *

                (1-i/60)

            )



        # 中期走势

        for i,c in enumerate(

            colors[:150]

        ):


            score[c]+= (

                CONFIG["medium_weight"]

                *

                (1-i/180)

            )



        # 长期平衡

        for c in COLORS:


            count=colors[:400].count(c)


            diff=(

                len(colors[:400])/3

                -

                count

            )


            if diff>0:

                score[c]+=diff*CONFIG["long_weight"]




        # 遗漏

        miss=attribute_counter.omission(

            colors,

            COLORS

        )


        for c,v in miss.items():

            score[c]+=v*CONFIG["omission_weight"]




        # 转换

        if len(colors)>5:


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


                    score[c]+= (

                        v/total

                        *

                        CONFIG["transition_weight"]

                    )



        return score





color_engine=ColorEngine()





# =====================================================
# 半波模型
# =====================================================


class HalfWaveEngine:



    def predict(

        self,

        half_history

    ):


        score={

            h:0

            for h in HALF_WAVES

        }



        # 最近半波走势


        recent=attribute_counter.count_recent(

            half_history,

            HALF_WAVES,

            CONFIG["half_recent_weight"]

        )



        for h,v in recent.items():

            score[h]+=v



        # 半波遗漏


        miss=attribute_counter.omission(

            half_history,

            HALF_WAVES

        )



        for h,v in miss.items():

            score[h]+=v




        # 半波转换


        if len(half_history)>5:


            trans=defaultdict(

                Counter

            )



            for i in range(

                len(half_history)-1

            ):


                trans[

                    half_history[i]

                ][

                    half_history[i+1]

                ]+=1



            last=half_history[0]



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
# 半半波模型
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




        # 遗漏补偿


        miss=attribute_counter.omission(

            history,

            HALF_HALF_WAVES

        )



        for h,v in miss.items():

            score[h]+=v





        # 转换链


        if len(history)>5:


            table=defaultdict(

                Counter

            )



            for i in range(

                len(history)-1

            ):


                table[

                    history[i]

                ][

                    history[i+1]

                ]+=1




            last=history[0]



            if last in table:


                total=sum(

                    table[last].values()

                )



                for h,v in table[last].items():

                    score[h]+= (

                        v/total

                        *

                        CONFIG["halfhalf_transition_weight"]

                    )



        return score





halfhalf_engine=HalfHalfWaveEngine()





# =====================================================
# 综合融合模型
# =====================================================


class FusionEngine:



    def merge(

        self,

        color_score,

        half_score,

        halfhalf_score

    ):



        final={

            "红":0,

            "蓝":0,

            "绿":0

        }



        # 颜色直接贡献


        for c,v in color_score.items():

            final[c]+= (

                v

                *

                CONFIG["color_weight"]

            )




        # 半波贡献转换到颜色


        for h,v in half_score.items():


            color=h[0]


            if color in final:

                final[color]+= (

                    v

                    *

                    CONFIG["half_weight"]

                )





        # 半半波贡献


        for h,v in halfhalf_score.items():


            color=h[0]


            if color in final:

                final[color]+= (

                    v

                    *

                    CONFIG["half_half_weight"]

                )



        return final





fusion_engine=FusionEngine()





# =====================================================
# 概率计算
# =====================================================


def probability(score):


    total = sum(

        max(value,0)

        for value in score.values()

    )


    if total <= 0:

        return {

            c:33.33

            for c in COLORS

        }



    return {


        c:

        round(

            max(score.get(c,0),0)

            /

            total

            *

            100,

            2

        )


        for c in COLORS

    }



    return {


        c:

        round(

            max(v,0)

            /

            total

            *

            100,

            2

        )


        for c in COLORS

    }
    # =====================================================
# V8 PRO 核心预测
# =====================================================


def predict_v8(rows):


    colors=[

        x["color"]

        for x in rows

    ]


    half_history=[]

    halfhalf_history=[]



    for x in rows:


        num=x["special"]


        attrs=get_attributes(num)



        # 半波展开

        half_history.append(

            attrs["color"]

            +

            attrs["size"]

        )



        halfhalf_history.append(

            attrs["half_half"]

        )




    color_score=color_engine.predict(

        colors

    )



    half_score=half_engine.predict(

        half_history

    )



    halfhalf_score=halfhalf_engine.predict(

        halfhalf_history

    )




    final_score=fusion_engine.merge(

        color_score,

        half_score,

        halfhalf_score

    )



    probs=probability(

        final_score

    )



    ranking=sorted(

        final_score.items(),

        key=lambda x:x[1],

        reverse=True

    )



    # 默认取最高颜色

    recommend=[

        ranking[0][0]

    ]



    # 分差小自动双色

    if len(ranking)>1:


        diff=(

            ranking[0][1]

            -

            ranking[1][1]

        )


        if diff<5:


            recommend.append(

                ranking[1][0]

            )




    return {


        "color":

        recommend,


        "color_score":

        final_score,


        "probability":

        probs,


        "half":

        sorted(

            half_score.items(),

            key=lambda x:x[1],

            reverse=True

        )[:3],


        "half_half":

        sorted(

            halfhalf_score.items(),

            key=lambda x:x[1],

            reverse=True

        )[:5]

    }





# =====================================================
# 回测
# =====================================================


def backtest(

    rows,

    test_count=100

):


    hit=0

    total=0



    details=[]



    max_test=min(

        test_count,

        len(rows)-CONFIG["min_train"]

    )




    for i in range(max_test):



        history=rows[i+1:]



        result=predict_v8(

            history

        )



        actual=rows[i]["color"]



        ok=(

            actual

            in

            result["color"]

        )



        total+=1



        if ok:

            hit+=1




        details.append({


            "issue":

            rows[i]["issue"],



            "predict":

            result["color"],



            "actual":

            actual,



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
# 参数自动搜索
# =====================================================


def auto_search(rows):


    print(

        "开始V8 PRO自动调参..."

    )



    keys=list(

        CONFIG["search_space"].keys()

    )



    values=list(

        CONFIG["search_space"].values()

    )



    best_rate=0

    best=None



    old=copy.deepcopy(

        CONFIG

    )



    for combo in product(*values):



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



        if rate>best_rate:


            best_rate=rate

            best=params.copy()




    CONFIG.update(old)



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

        "最佳命中率:",

        f"{best_rate:.2%}"

    )


    return best
    # =====================================================
# 参数加载
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


            params=json.load(f)



        for k,v in params.items():

            if k in CONFIG:

                CONFIG[k]=v



        print(

            "已加载最佳参数"

        )


    except:


        pass





# =====================================================
# 生成报告
# =====================================================


def create_report(

    issue,

    result,

    rate

):


    with open(

        REPORT_FILE,

        "w",

        encoding="utf-8"

    ) as f:



        f.write(

            "# 澳门六合彩 V8 PRO预测报告\n\n"

        )



        f.write(

            "预测期号："

            +

            str(issue)

            +

            "\n\n"

        )



        f.write(

            "## 颜色预测\n\n"

        )


        f.write(

            "、".join(

                result["color"]

            )

            +

            "\n\n"

        )



        f.write(

            "## 颜色评分\n\n"

        )


        for c,v in result["color_score"].items():

            f.write(

                f"{c}: {v:.2f}\n"

            )



        f.write(

            "\n## 颜色概率\n\n"

        )


        for c,v in result["probability"].items():

            f.write(

                f"{c}: {v}%\n"

            )



        f.write(

            "\n## 半波预测\n\n"

        )



        for h,v in result["half"]:


            f.write(

                f"{h}: {v:.2f}\n"

            )



        f.write(

            "\n## 半半波预测\n\n"

        )



        for h,v in result["half_half"]:


            f.write(

                f"{h}: {v:.2f}\n"

            )



        f.write(

            "\n## 历史回测\n\n"

        )


        f.write(

            f"近100期命中率: {rate:.2%}\n"

        )





# =====================================================
# 主程序
# =====================================================


def main():


    parser=argparse.ArgumentParser(

        description=

        "澳门六合彩 V8 PRO"

    )


    parser.add_argument(

        "--search",

        action="store_true",

        help="重新搜索参数"

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

            "数据获取失败"

        )


        return



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



    result=predict_v8(

        rows

    )



    rate,_=backtest(

        rows,

        100

    )




    print(

        "\n===================="

    )


    print(

        "澳门六合彩 V8 PRO"

    )


    print(

        "预测颜色:",

        "、".join(

            result["color"]

        )

    )



    print(

        "半波:",

        result["half"][0][0]

    )



    print(

        "半半波:",

        result["half_half"][0][0]

    )



    print(

        "概率:",

        result["probability"]

    )



    print(

        "回测:",

        f"{rate:.2%}"

    )



    print(

        "===================="

    )



    create_report(

        rows[0]["issue"],

        result,

        rate

    )



    print(

        "报告生成完成:",

        REPORT_FILE

    )





if __name__=="__main__":

    main()