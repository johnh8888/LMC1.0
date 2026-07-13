#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门彩短周期预测系统 V8.5

特点:
1. 只读取新澳门彩
2. 最近100期分析
3. 最近20期重点权重
4. 短趋势预测
5. 冷热平衡
6. 遗漏补偿
7. 半波/半半波融合
8. 下一期预测优化
"""

import os
import re
import json
import argparse
import urllib.request

from collections import defaultdict
from itertools import product


# =====================================================
# 配置
# =====================================================

CONFIG = {

    # 权重
    "trend_weight":40,

    "half_weight":35,

    "halfhalf_weight":20,

    "transition_weight":5,


    # 数据量
    "history_limit":100,


    # 数据接口

    "api_url":
    "https://marksix6.net/index.php?api=1"

}


REPORT_FILE="result.md"



# =====================================================
# 颜色表
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
28,32,33,
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
        text
    )

    return [
        int(x)
        for x in nums
        if 1<=int(x)<=49
    ]



def fetch_macau(limit=100):

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



                m=re.search(
                    r"(20\d{5,7})",
                    line
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
            "数据错误:",
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
# 短周期趋势模型
# =====================================================


def trend_score(rows):

    score={

        "红":0,

        "蓝":0,

        "绿":0

    }


    # 最近20期重点

    weights=[

        10,9,8,7,6,

        5,5,4,4,3,

        3,2,2,2,1,

        1,1,1,1,1

    ]


    for i,r in enumerate(rows[:20]):


        score[r["color"]] += weights[i]



    return score





# =====================================================
# 颜色转换模型
# =====================================================


def transition_score(rows):


    result={

        "红":0,

        "蓝":0,

        "绿":0

    }


    if len(rows)<2:

        return result



    last=rows[0]["color"]



    for i in range(len(rows)-1):


        if rows[i]["color"]==last:


            nxt=rows[i+1]["color"]


            result[nxt]+=1



    return result





# =====================================================
# 冷热平衡
# =====================================================


def hot_cold_score(rows):


    score={

        "红":0,

        "蓝":0,

        "绿":0

    }



    count={

        "红":0,

        "蓝":0,

        "绿":0

    }



    for r in rows[:50]:

        count[r["color"]]+=1



    avg=sum(count.values())/3



    for c in COLORS:


        # 热降低

        if count[c]>avg:

            score[c]-=(count[c]-avg)*0.8


        # 冷补偿

        else:

            score[c]+=(avg-count[c])*1.2



    return score





# =====================================================
# 遗漏模型
# =====================================================


def miss_score(rows):


    score={

        "红":0,

        "蓝":0,

        "绿":0

    }



    for c in COLORS:


        miss=0


        for r in rows:


            if r["color"]==c:

                break


            miss+=1



        score[c]=min(

            miss*1.5,

            20

        )



    return score





# =====================================================
# 连续惩罚
# =====================================================


def repeat_penalty(rows):


    score={

        "红":0,

        "蓝":0,

        "绿":0

    }



    if not rows:

        return score



    last=rows[0]["color"]


    count=0


    for r in rows:


        if r["color"]==last:

            count+=1

        else:

            break



    if count>=2:

        score[last]-=3



    if count>=3:

        score[last]-=6



    if count>=4:

        score[last]-=10



    return score





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



def half_score(rows):


    score={

        h:0

        for h in HALF_WAVES

    }



    for i,r in enumerate(rows[:50]):


        w=max(

            50-i,

            1

        )


        for h in r["half"]:

            score[h]+=w



    return score





# =====================================================
# 半半波模型
# =====================================================


def halfhalf_score(rows):


    score=defaultdict(float)



    for i,r in enumerate(rows[:50]):


        score[

            r["halfhalf"]

        ]+=50-i



    return dict(score)





# =====================================================
# 最终融合
# =====================================================


def predict(rows):


    final={

        "红":0,

        "蓝":0,

        "绿":0

    }


    t=trend_score(rows)

    h=hot_cold_score(rows)

    m=miss_score(rows)

    tr=transition_score(rows)

    rp=repeat_penalty(rows)



    for c in COLORS:


        final[c]+=t[c]*1.5


        final[c]+=h[c]


        final[c]+=m[c]


        final[c]+=tr[c]*0.5


        final[c]+=rp[c]



    color_rank=sorted(

        final.items(),

        key=lambda x:x[1],

        reverse=True

    )



    return {


        "color":

        color_rank,


        "half":

        sorted(

            half_score(rows).items(),

            key=lambda x:x[1],

            reverse=True

        )[:5],


        "halfhalf":

        sorted(

            halfhalf_score(rows).items(),

            key=lambda x:x[1],

            reverse=True

        )[:5],


        "prob":

        probability(final)

    }





# =====================================================
# 概率
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
    # =====================================================
# 显示最新开奖结果
# =====================================================


def show_latest(rows):

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




# =====================================================
# 最近走势
# =====================================================


def show_recent(rows,count=10):

    print()

    print(
        "最近",
        count,
        "期开奖结果"
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


def backtest(rows,limit=100):


    total=0


    color_hit=0

    half_hit=0

    halfhalf_hit=0



    limit=min(

        limit,

        len(rows)-30

    )



    for i in range(limit):


        history=rows[i+1:]


        actual=rows[i]



        result=predict(history)



        # 第一颜色

        color=result["color"][0][0]



        if color==actual["color"]:

            color_hit+=1



        # 半波前三

        half=[

            x[0]

            for x in result["half"][:3]

        ]



        if any(

            x in actual["half"]

            for x in half

        ):

            half_hit+=1



        # 半半波前三

        hh=[

            x[0]

            for x in result["halfhalf"][:3]

        ]



        if actual["halfhalf"] in hh:

            halfhalf_hit+=1



        total+=1



    return {


        "color":

        color_hit/total,


        "half":

        half_hit/total,


        "halfhalf":

        halfhalf_hit/total

    }




# =====================================================
# 输出预测
# =====================================================


def print_prediction(result):


    print()

    print("====================")

    print(
        "新澳门彩 V8.5预测"
    )


    print()


    print(
        "颜色TOP:"
    )


    for k,v in result["color"]:


        print(

            k,

            round(v,2)

        )



    print()


    print(
        "半波TOP:"
    )


    for k,v in result["half"]:


        print(

            k,

            round(v,2)

        )



    print()


    print(
        "半半波TOP:"
    )


    for k,v in result["halfhalf"]:


        print(

            k,

            round(v,2)

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

            "# 新澳门彩 V8.5预测报告\n\n"

        )


        f.write(

            "最新开奖:\n\n"

        )


        r=rows[0]


        f.write(

            f"""

期号:{r['issue']}

特码:{r['special']}

颜色:{r['color']}

半半波:{r['halfhalf']}


---

"""

        )


        f.write(

            "颜色预测:\n\n"

        )


        f.write(

            str(
                result["color"]
            )

        )


        f.write(

            "\n\n半波预测:\n\n"

        )


        f.write(

            str(
                result["half"]
            )

        )


        f.write(

            "\n\n半半波预测:\n\n"

        )


        f.write(

            str(
                result["halfhalf"]
            )

        )


        f.write(

            "\n\n回测:\n\n"

        )


        f.write(

            str(bt)

        )




# =====================================================
# 主程序
# =====================================================


def main():


    parser=argparse.ArgumentParser()


    args=parser.parse_args()



    print(

        "正在获取新澳门彩..."

    )



    rows=fetch_macau(

        CONFIG["history_limit"]

    )



    if not rows:


        print(

            "没有数据"

        )

        return



    show_latest(rows)


    show_recent(rows)



    result=predict(rows)



    print_prediction(result)



    bt=backtest(

        rows,

        100

    )


    print()

    print("====================")

    print(
        "V8.5最近100期回测"
    )


    print(

        "颜色第一:",

        f"{bt['color']:.2%}"

    )


    print(

        "半波前三:",

        f"{bt['half']:.2%}"

    )


    print(

        "半半波前三:",

        f"{bt['halfhalf']:.2%}"

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