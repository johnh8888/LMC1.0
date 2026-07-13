#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门彩颜色预测系统 V8.11 DOUBLE

特点:
1. 最近30期分析
2. 固定参数
3. 输出TOP2波色
4. 每个波色独立分析半波
5. 每个波色独立分析半半波
6. 最终输出双候选组合
"""


import re
import json
import urllib.request

from collections import defaultdict


# =====================================================
# 配置
# =====================================================


CONFIG = {


    "history_limit":30,


    # 保留两个颜色

    "color_limit":2,



    # 颜色权重

    "color_recent_weight":0.4,

    "color_history_weight":0.6,



    # 半波

    "half_recent_weight":0.4,

    "half_history_weight":0.6,



    # 半半波

    "halfhalf_recent_weight":0.4,

    "halfhalf_history_weight":0.4,

    "halfhalf_missing_weight":0.2,



    "api_url":

    "https://marksix6.net/index.php?api=1"


}



REPORT_FILE="result.md"





# =====================================================
# 波色定义
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


    return (

        "大"

        if num>=25

        else

        "小"

    )





def get_odd(num):


    return (

        "单"

        if num%2

        else

        "双"

    )





def get_half(num):


    c=get_color(num)


    return [

        c+"大",

        c+"小",

        c+"单",

        c+"双"

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


    try:


        req=urllib.request.Request(

            CONFIG["api_url"],

            headers={

                "User-Agent":

                "Mozilla/5.0"

            }

        )



        data=urllib.request.urlopen(

            req,

            timeout=30

        ).read()



        data=json.loads(

            data.decode("utf-8")

        )



        target=None



        print("扫描彩种:")



        for item in data.get(

            "lottery_data",

            []

        ):


            name=item.get(

                "name",

                ""

            )



            print(name)



            if name=="新澳门彩":


                target=item


                print(

                    "锁定彩种: 新澳门彩"

                )


                break




        if not target:


            return []



        for line in target.get(

            "history",

            []

        ):


            nums=parse_numbers(line)



            if len(nums)<7:

                continue



            special=nums[-1]



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



    # 去重

    tmp={}


    for r in rows:

        tmp[r["issue"]]=r



    rows=list(tmp.values())



    rows.sort(

        key=lambda x:x["issue"],

        reverse=True

    )



    return rows[:limit]
   # =====================================================
# V8.11 双波色预测核心
# =====================================================


class DoublePredictEngine:



    def __init__(self, rows):

        self.rows = rows[:30]





    # =================================================
    # 第一层：颜色 TOP2
    # =================================================


    def color_score(self):


        score={

            "红":0,

            "蓝":0,

            "绿":0

        }



        recent=self.rows[:10]



        history=self.rows[:30]



        # 最近10期

        for i,r in enumerate(recent):


            weight=10-i



            score[r["color"]] += (

                weight *

                CONFIG[
                "color_recent_weight"
                ]

            )





        # 最近30期

        for i,r in enumerate(history):


            weight=30-i



            score[r["color"]] += (

                weight *

                CONFIG[
                "color_history_weight"
                ]

            )





        # 遗漏修正

        for c in COLORS:


            miss=0



            for r in self.rows:


                if r["color"]==c:

                    break


                miss+=1



            score[c]+=min(

                miss,

                10

            )





        total=sum(score.values())



        result=[]



        for k,v in score.items():


            result.append(

                (

                    k,

                    round(

                        v/total*100,

                        2

                    )

                )

            )



        return sorted(

            result,

            key=lambda x:x[1],

            reverse=True

        )







    # =================================================
    # 第二层：指定颜色半波
    # =================================================


    def half_score(self,color):


        score=defaultdict(float)



        recent=self.rows[:10]

        history=self.rows[:30]




        # 最近趋势

        for i,r in enumerate(recent):


            if r["color"]!=color:

                continue



            weight=10-i



            score[r["half"][0]] += (

                weight *

                CONFIG[
                "half_recent_weight"
                ]

            )


            score[r["half"][1]] += (

                weight *

                CONFIG[
                "half_recent_weight"
                ]

            )




        # 历史趋势

        for i,r in enumerate(history):


            if r["color"]!=color:

                continue



            weight=30-i



            score[r["half"][0]] += (

                weight *

                CONFIG[
                "half_history_weight"
                ]

            )


            score[r["half"][1]] += (

                weight *

                CONFIG[
                "half_history_weight"
                ]

            )





        total=sum(score.values())



        result=[]



        for k,v in score.items():


            result.append(

                (

                    k,

                    round(

                        v/total*100,

                        2

                    )

                )

            )



        return sorted(

            result,

            key=lambda x:x[1],

            reverse=True

        )







    # =================================================
    # 第三层：半半波
    # =================================================


    def halfhalf_score(self,color):


        score=defaultdict(float)



        recent=self.rows[:10]

        history=self.rows[:30]




        # 最近

        for i,r in enumerate(recent):


            if r["color"]!=color:

                continue



            weight=10-i



            score[r["halfhalf"]] += (

                weight *

                CONFIG[
                "halfhalf_recent_weight"
                ]

            )





        # 历史

        for i,r in enumerate(history):


            if r["color"]!=color:

                continue



            weight=30-i



            score[r["halfhalf"]] += (

                weight *

                CONFIG[
                "halfhalf_history_weight"
                ]

            )






        # 遗漏补偿

        candidates=[

            color+"大单",

            color+"大双",

            color+"小单",

            color+"小双"

        ]



        for c in candidates:


            miss=0



            for r in self.rows:


                if r["halfhalf"]==c:

                    break


                miss+=1




            score[c]+=(
                
                miss *

                CONFIG[
                "halfhalf_missing_weight"
                ]

            )





        total=sum(score.values())



        result=[]



        for k,v in score.items():


            result.append(

                (

                    k,

                    round(

                        v/total*100,

                        2

                    )

                )

            )



        return sorted(

            result,

            key=lambda x:x[1],

            reverse=True

        )







    # =================================================
    # 最终双组合
    # =================================================


    def predict(self):


        colors=self.color_score()



        top_colors=[

            x[0]

            for x in colors[

                :CONFIG["color_limit"]

            ]

        ]



        output={

            "colors":colors,

            "details":[]

        }



        for c in top_colors:



            half=self.half_score(c)



            hh=self.halfhalf_score(c)




            output["details"].append({


                "color":c,


                "half":half[:3],


                "halfhalf":hh[:3],



                "final":

                hh[0][0]

                if hh

                else c


            })



        return output
      # =====================================================
# 回测
# =====================================================


def backtest(rows, test=20):


    hit_color=0

    hit_final=0


    total=min(

        test,

        len(rows)-10

    )



    if total<=0:

        return {

            "color":0,

            "final":0

        }



    for i in range(total):


        history=rows[i+1:]



        engine=DoublePredictEngine(history)


        result=engine.predict()



        actual=rows[i]



        # TOP2颜色命中

        colors=[

            x[0]

            for x in result["colors"][:2]

        ]



        if actual["color"] in colors:

            hit_color+=1





        # 最终半半波命中

        finals=[

            x["final"]

            for x in result["details"]

        ]



        if actual["halfhalf"] in finals:

            hit_final+=1





    return {


        "color":

        round(

            hit_color/total*100,

            2

        ),



        "final":

        round(

            hit_final/total*100,

            2

        )


    }





# =====================================================
# 报告
# =====================================================


def save_report(result,bt):


    with open(

        REPORT_FILE,

        "w",

        encoding="utf-8"

    ) as f:


        f.write(

"""

# 新澳门彩 V8.11 DOUBLE预测


## 颜色TOP2


"""

        )



        for c,p in result["colors"]:


            f.write(

                f"{c}: {p}%\n"

            )



        f.write(

"""

--------------------


## 双波色分析


"""

        )



        for item in result["details"]:



            f.write(

f"""

颜色:

{item["color"]}


半波:

{item["half"]}


半半波:

{item["halfhalf"]}


最终:

{item["final"]}


--------------------

"""

            )



        f.write(

f"""

## 回测


颜色TOP2:

{bt["color"]}%


最终半半波:

{bt["final"]}%


"""

        )







# =====================================================
# 主程序
# =====================================================


def main():


    print(

        "正在获取新澳门彩..."

    )



    rows=fetch_new_macau(

        CONFIG["history_limit"]

    )



    if not rows:


        print(

            "无数据"

        )

        return





    print(

        "\n最近30期开奖结果"

    )



    print(

        "--------------------"

    )



    for r in rows:


        print(

            r["issue"],

            "特码",

            r["special"],

            r["color"],

            r["halfhalf"]

        )





    engine=DoublePredictEngine(rows)



    result=engine.predict()




    print(

        "\n===================="

    )

    print(

        "V8.11 DOUBLE预测"

    )

    print(

        "===================="

    )





    print(

        "\n颜色TOP2:"

    )



    for c,p in result["colors"]:


        print(

            c,

            p,

            "%"

        )





    print(

        "\n保留波色:"

    )



    for item in result["details"]:


        print(

            "\n颜色:",

            item["color"]

        )


        print(

            "半波TOP:",

            item["half"]

        )


        print(

            "半半波TOP:",

            item["halfhalf"]

        )


        print(

            "最终:",

            item["final"]

        )





    bt=backtest(rows)



    print(

        "\n===================="

    )


    print(

        "最近回测"

    )



    print(

        "颜色TOP2:",

        bt["color"],

        "%"

    )



    print(

        "最终半半波:",

        bt["final"],

        "%"

    )





    save_report(

        result,

        bt

    )



    print(

        "\n报告生成:",

        REPORT_FILE

    )







if __name__=="__main__":

    main()