#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门彩短周期预测系统 V8.6 PRO

升级:
1. 只针对新澳门彩
2. 短周期窗口预测
3. 自动选择最佳历史窗口
4. 增加冷热转换
5. 增加遗漏补偿
6. 半波/半半波独立评分
7. 滚动回测
8. GitHub Actions兼容
"""

import os
import re
import json
import math
import argparse
import urllib.request

from itertools import product
from collections import defaultdict


# =====================================================
# 参数
# =====================================================

CONFIG = {

    # 短周期窗口
    "windows":[20,30,50],

    # 最近权重
    "recent_weight":{

        "5":0.5,
        "15":0.3,
        "30":0.2

    },

    # 模型权重

    "color_weight":40,

    "half_weight":30,

    "halfhalf_weight":30,


    # 自动搜索

    "search_space":{

        "color_weight":[35,40,45],

        "half_weight":[25,30,35],

        "halfhalf_weight":[25,30,35]

    },


    # 新澳门彩接口

    "api_url":
    "https://marksix6.net/index.php?api=1"

}


PARAM_FILE="macau_v86_params.json"

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
3,4,9,10,
14,15,
20,25,26,
31,36,37,
41,42,47,48
}


GREEN={
5,6,11,
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
        str(text)
    )

    return [

        int(x)

        for x in nums

        if 1<=int(x)<=49

    ]



# =====================================================
# 获取新澳门彩
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


        raw=urllib.request.urlopen(

            req,

            timeout=20

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

            print(
                "未找到新澳门彩"
            )

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



            # 期号

            m=re.search(

                r"(20\d{5,7})",

                str(line)

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

                "color":get_color(special),

                "size":get_size(special),

                "odd":get_odd(special),

                "half":get_half(special),

                "halfhalf":get_halfhalf(special)

            })



    except Exception as e:


        print(
            "获取失败:",
            e
        )



    # 去重

    cache={}


    for r in rows:

        cache[r["issue"]]=r



    rows=list(
        cache.values()
    )


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
# 短周期权重
# =====================================================

def recent_weight(index):

    if index < 5:

        return 0.5

    elif index < 15:

        return 0.3

    else:

        return 0.2



# =====================================================
# 颜色短周期模型
# =====================================================

class ColorEngine:


    def predict(self,rows,window):


        data=rows[:window]


        score={

            c:0

            for c in COLORS

        }


        # 最近趋势

        for i,r in enumerate(data):


            w=recent_weight(i)


            score[r["color"]] += (

                (window-i)

                *

                w

            )



        # 遗漏补偿

        for c in COLORS:


            miss=0


            for r in data:


                if r["color"]==c:

                    break


                miss+=1



            score[c]+=min(

                miss*2,

                20

            )



        # 连续惩罚

        if len(data)>=3:


            last=[

                x["color"]

                for x in data[:3]

            ]


            if len(set(last))==1:


                score[last[0]]*=0.75



        # 平衡修正

        avg=sum(score.values())/3


        for c in COLORS:

            score[c]+=(
                score[c]-avg
            )*0.3


        return score



color_engine=ColorEngine()



# =====================================================
# 半波模型
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



class HalfEngine:


    def predict(self,rows,window):


        score={

            h:0

            for h in HALF_WAVES

        }



        data=rows[:window]


        for i,r in enumerate(data):


            for h in r["half"]:


                score[h]+=(
                    window-i
                )*recent_weight(i)



        # 遗漏

        for h in HALF_WAVES:


            miss=0


            for r in data:


                if h in r["half"]:

                    break


                miss+=1



            score[h]+=min(

                miss*1.5,

                15

            )


        return score



half_engine=HalfEngine()



# =====================================================
# 半半波模型
# =====================================================

HALF_HALF=[

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



class HalfHalfEngine:


    def predict(self,rows,window):


        score={

            h:0

            for h in HALF_HALF

        }



        data=rows[:window]



        for i,r in enumerate(data):


            h=r["halfhalf"]


            score[h]+=(
                window-i
            )*recent_weight(i)



        # 组合遗漏

        for h in HALF_HALF:


            miss=0


            for r in data:


                if r["halfhalf"]==h:

                    break


                miss+=1



            score[h]+=min(

                miss*2,

                20

            )



        return score



halfhalf_engine=HalfHalfEngine()



# =====================================================
# 综合预测
# =====================================================

def predict_window(rows,window):


    color=color_engine.predict(

        rows,

        window

    )


    half=half_engine.predict(

        rows,

        window

    )


    halfhalf=halfhalf_engine.predict(

        rows,

        window

    )



    final={

        c:0

        for c in COLORS

    }



    for c,v in color.items():


        final[c]+=(
            v*
            CONFIG["color_weight"]
            /
            100
        )



    for h,v in half.items():


        final[h[0]]+=(
            v*
            CONFIG["half_weight"]
            /
            100
        )



    for h,v in halfhalf.items():


        final[h[0]]+=(
            v*
            CONFIG["halfhalf_weight"]
            /
            100
        )



    return {

        "window":window,

        "color":color,

        "half":half,

        "halfhalf":halfhalf,

        "final":final

    }



# =====================================================
# 自动选择窗口
# =====================================================

def choose_window(rows):


    best=None

    best_score=-1



    for w in CONFIG["windows"]:


        if len(rows)<=w+10:

            continue



        result=predict_window(

            rows[w:],

            w

        )


        score=max(

            result["final"].values()

        )



        if score>best_score:


            best_score=score

            best=w



    return best or 30




# =====================================================
# 排序
# =====================================================

def rank(score,n=5):


    return sorted(

        score.items(),

        key=lambda x:x[1],

        reverse=True

    )[:n]



def probability(score):


    total=sum(score.values())


    return {

        k:round(

            v/total*100,

            2

        )

        for k,v in score.items()

    }



# =====================================================
# 最终预测
# =====================================================

def predict(rows):


    window=choose_window(rows)


    result=predict_window(

        rows,

        window

    )


    return {


        "window":window,


        "color":

        rank(
            result["final"],
            3
        ),


        "half":

        rank(
            result["half"],
            5
        ),


        "halfhalf":

        rank(
            result["halfhalf"],
            5
        ),


        "prob":

        probability(
            result["final"]
        ),


        "raw":result

    }
    # =====================================================
# 回测
# =====================================================

def backtest(rows,limit=100):


    total=0

    color_hit=0

    half_hit=0

    halfhalf_hit=0



    limit=min(

        limit,

        len(rows)-60

    )



    for i in range(limit):


        history=rows[i+1:]


        actual=rows[i]



        result=predict(history)



        # 颜色TOP1

        if result["color"][0][0]==actual["color"]:

            color_hit+=1



        # 半波TOP3

        half_list=[

            x[0]

            for x in result["half"][:3]

        ]


        if any(

            x in actual["half"]

            for x in half_list

        ):

            half_hit+=1



        # 半半波TOP3

        hh_list=[

            x[0]

            for x in result["halfhalf"][:3]

        ]



        if actual["halfhalf"] in hh_list:

            halfhalf_hit+=1



        total+=1



    return {


        "color":

        round(

            color_hit/total*100,

            2

        ),


        "half":

        round(

            half_hit/total*100,

            2

        ),


        "halfhalf":

        round(

            halfhalf_hit/total*100,

            2

        )

    }





# =====================================================
# 自动调参
# =====================================================

def auto_search(rows):


    print(

        "开始V8.6自动调参..."

    )



    keys=list(

        CONFIG["search_space"]

        .keys()

    )



    values=list(

        CONFIG["search_space"]

        .values()

    )



    best_score=-1

    best=None



    for idx,combo in enumerate(

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

            80

        )



        score=(

            bt["color"]*0.4

            +

            bt["half"]*0.3

            +

            bt["halfhalf"]*0.3

        )



        print(

            "参数",

            idx,

            "得分",

            round(score,2)

        )



        if score>best_score:


            best_score=score

            best=params.copy()



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
# 显示
# =====================================================

def show_latest(rows):


    r=rows[0]


    print()

    print("====================")

    print(

        "最新新澳门彩开奖结果"

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

        "半半波:",

        r["halfhalf"]

    )


    print("====================")





def show_recent(rows,n=10):


    print()

    print(

        "最近",

        n,

        "期开奖结果"

    )


    print("--------------------")


    for r in rows[:n]:

        print(

            r["issue"],

            "特码",

            r["special"],

            r["color"],

            r["halfhalf"]

        )


    print("--------------------")





def print_prediction(result):


    print()

    print("====================")

    print(

        "新澳门彩 V8.6预测"

    )


    print()

    print(

        "使用窗口:",

        result["window"]

    )


    print()

    print("颜色TOP:")


    for x in result["color"]:

        print(

            x[0],

            round(x[1],2)

        )



    print()

    print("半波TOP:")


    for x in result["half"]:

        print(

            x[0],

            round(x[1],2)

        )



    print()

    print("半半波TOP:")


    for x in result["halfhalf"]:

        print(

            x[0],

            round(x[1],2)

        )


    print()

    print(

        "综合概率:",

        result["prob"]

    )


    print("====================")





# =====================================================
# 报告
# =====================================================

def create_report(rows,result,bt):


    with open(

        REPORT_FILE,

        "w",

        encoding="utf-8"

    ) as f:


        f.write(

            "# 新澳门彩 V8.6预测报告\n\n"

        )


        f.write(

            "预测窗口:\n"

            +

            str(result["window"])

            +

            "\n\n"

        )


        f.write(

            "颜色:\n"

            +

            str(result["color"])

            +

            "\n\n"

        )


        f.write(

            "半波:\n"

            +

            str(result["half"])

            +

            "\n\n"

        )


        f.write(

            "半半波:\n"

            +

            str(result["halfhalf"])

            +

            "\n\n"

        )


        f.write(

            "回测:\n"

            +

            str(bt)

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


    rows=fetch_macau()



    if not rows:

        print(

            "无数据"

        )

        return



    show_latest(rows)


    show_recent(rows)



    if (

        args.search

        or

        not os.path.exists(PARAM_FILE)

    ):

        auto_search(rows)



    load_params()



    result=predict(rows)



    print_prediction(result)



    bt=backtest(rows)



    print()

    print("====================")

    print(

        "V8.6回测"

    )


    print(bt)


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