#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门彩预测系统 V8.16 BALANCE

升级:

1. 冷热颜色平衡
2. 防连续追色
3. 大小模型增强
4. 半半波融合
5. TOP1 + TOP3盲测
6. 多窗口优化

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

    "api_url":
    "https://marksix6.net/index.php?api=1",

    "weights":{

        "color":0.25,

        "size":0.30,

        "odd":0.25,

        "halfhalf":0.20

    }

}


REPORT_FILE="result_v816.md"





# =====================================================
# 波色定义
# =====================================================


RED={
1,2,7,8,
12,13,18,19,
23,24,29,30,
34,35,40,45,46
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
# 获取数据
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

            timeout=20

        ).read()



        data=json.loads(

            data.decode("utf-8")

        )



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

                r"(20\d{5,8})",

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

                "color":
                get_color(special),

                "size":
                get_size(special),

                "odd":
                get_odd(special),

                "halfhalf":
                get_halfhalf(special)

            })




    except Exception as e:


        print(

            "获取失败:",

            e

        )


        return []




    cache={}



    for r in rows:

        cache[r["issue"]]=r



    rows=list(cache.values())



    rows.sort(

        key=lambda x:x["issue"],

        reverse=True

    )



    return rows[:limit]





# =====================================================
# 基础统计模型
# =====================================================


class AttributeModel:


    def __init__(self,rows):

        self.rows=rows[:30]



    def window_score(self,attr):


        score=defaultdict(float)



        for size,weight in [

            (10,0.5),

            (20,0.3),

            (30,0.2)

        ]:


            for i,r in enumerate(

                self.rows[:size]

            ):


                score[r[attr]] += (

                    size-i

                )*weight



        return score
        # =====================================================
# V8.16 冷热平衡模型
# =====================================================


    def miss_score(self,attr,values):


        result=defaultdict(float)



        for v in values:


            miss=0



            for r in self.rows:


                if r[attr]==v:

                    break


                miss+=1



            # 遗漏补偿

            result[v]=min(

                miss*1.5,

                15

            )



        return result






    # =================================================
    # 连续趋势修正
    # =================================================


    def trend_balance(self,attr,score):


        recent=[

            r[attr]

            for r in self.rows[:5]

        ]



        count={

            x:recent.count(x)

            for x in set(recent)

        }




        for k,v in count.items():


            # 连续过热降低

            if v>=3:


                score[k]-=v*3




        return score






    # =================================================
    # 通用属性预测
    # =================================================


    def predict(self,attr,values):


        score=self.window_score(

            attr

        )



        miss=self.miss_score(

            attr,

            values

        )



        for k in values:


            score[k]+=miss[k]



        score=self.trend_balance(

            attr,

            score

        )



        total=sum(score.values())



        if total<=0:

            total=1



        return {


            k:round(

                max(score[k],0)

                /

                total

                *

                100,

                2

            )

            for k in values

        }






    # =================================================
    # 颜色
    # =================================================


    def color(self):


        return self.predict(

            "color",

            [

                "红",

                "蓝",

                "绿"

            ]

        )






    # =================================================
    # 大小
    # =================================================


    def size(self):


        return self.predict(

            "size",

            [

                "大",

                "小"

            ]

        )






    # =================================================
    # 单双
    # =================================================


    def odd(self):


        return self.predict(

            "odd",

            [

                "单",

                "双"

            ]

        )







    # =================================================
    # 半半波
    # =================================================


    def halfhalf(self,color=None):


        score=defaultdict(float)



        for size,weight in [

            (10,0.5),

            (20,0.3),

            (30,0.2)

        ]:


            for i,r in enumerate(

                self.rows[:size]

            ):


                hh=r["halfhalf"]



                if color:


                    if not hh.startswith(color):

                        continue



                score[hh]+= (

                    size-i

                )*weight




        # 半半波遗漏

        for k in list(score.keys()):


            miss=0



            for r in self.rows:


                if r["halfhalf"]==k:

                    break


                miss+=1



            score[k]+=min(

                miss,

                10

            )



        total=sum(score.values())



        if total==0:

            return {}



        return {


            k:round(

                v/total*100,

                2

            )

            for k,v in sorted(

                score.items(),

                key=lambda x:x[1],

                reverse=True

            )

        }






# =====================================================
# V8.16 最终融合
# =====================================================


class FusionV816:


    def __init__(self,rows):

        self.rows=rows

        self.model=AttributeModel(

            rows

        )




    def predict(self):


        color=self.model.color()


        size=self.model.size()


        odd=self.model.odd()



        candidates=[]




        top_colors=sorted(

            color.items(),

            key=lambda x:x[1],

            reverse=True

        )[:2]





        for c,cp in top_colors:



            hh=self.model.halfhalf(

                c

            )



            for h,hp in list(

                hh.items()

            )[:5]:



                s=h[1]

                o=h[2]



                score=(


                    cp*CONFIG["weights"]["color"]

                    +

                    size.get(

                        s,

                        0

                    )

                    *

                    CONFIG["weights"]["size"]


                    +

                    odd.get(

                        o,

                        0

                    )

                    *

                    CONFIG["weights"]["odd"]


                    +

                    hp

                    *

                    CONFIG["weights"]["halfhalf"]

                )



                candidates.append({


                    "halfhalf":h,


                    "score":

                    round(score,2)


                })




        candidates.sort(

            key=lambda x:x["score"],

            reverse=True

        )



        return {


            "color":color,

            "size":size,

            "odd":odd,

            "candidates":

            candidates[:5]

        }
        # =====================================================
# V8.16 盲测回测系统
# =====================================================


class BackTest816:


    def __init__(self,rows):

        self.rows=rows




    def run(self):


        result={

            "color":[0,0],

            "size":[0,0],

            "odd":[0,0],

            "halfhalf":[0,0],

            "top1":[0,0],

            "top3":[0,0]

        }




        # 最近10期盲测

        total=min(

            10,

            len(self.rows)-10

        )




        for i in range(total):


            # 关键:
            # 不使用当前及未来数据

            history=self.rows[i+1:]



            actual=self.rows[i]



            model=FusionV816(

                history

            )



            pred=model.predict()



            result["color"][1]+=1

            result["size"][1]+=1

            result["odd"][1]+=1

            result["halfhalf"][1]+=1

            result["top1"][1]+=1

            result["top3"][1]+=1




            if max(

                pred["color"],

                key=pred["color"].get

            )==actual["color"]:

                result["color"][0]+=1




            if max(

                pred["size"],

                key=pred["size"].get

            )==actual["size"]:

                result["size"][0]+=1




            if max(

                pred["odd"],

                key=pred["odd"].get

            )==actual["odd"]:

                result["odd"][0]+=1




            hlist=[

                x["halfhalf"]

                for x in pred["candidates"]

            ]



            if actual["halfhalf"] in hlist:

                result["halfhalf"][0]+=1





            if (

                pred["candidates"]

                and

                pred["candidates"][0]["halfhalf"]

                ==actual["halfhalf"]

            ):

                result["top1"][0]+=1





            if actual["halfhalf"] in [

                x["halfhalf"]

                for x in pred["candidates"][:3]

            ]:

                result["top3"][0]+=1



        return result






    def print_result(self):


        r=self.run()



        print()

        print("="*35)

        print(

            "V8.16 最近10期盲测"

        )

        print("="*35)



        for k,v in r.items():


            print(

                k,

                ":",

                v[0],

                "/",

                v[1],

                "=",

                round(

                    v[0]/v[1]*100,

                    2

                ),

                "%"

            )



        return r






# =====================================================
# 报告
# =====================================================


def save_report(result):


    with open(

        REPORT_FILE,

        "w",

        encoding="utf-8"

    ) as f:



        f.write(

            "# 新澳门彩 V8.16 BALANCE\n\n"

        )



        f.write(

            "## 颜色预测\n\n"

        )


        for k,v in sorted(

            result["color"].items(),

            key=lambda x:x[1],

            reverse=True

        ):


            f.write(

                f"{k}: {v}%\n"

            )



        f.write(

            "\n## 最终TOP5\n\n"

        )



        for i,c in enumerate(

            result["candidates"],

            1

        ):


            f.write(

                f"{i}. {c['halfhalf']} "

                f"{c['score']}\n"

            )






# =====================================================
# 主程序
# =====================================================


def main():



    print(

        "正在获取新澳门彩..."

    )



    rows=fetch_new_macau(

        30

    )



    if len(rows)<10:


        print(

            "数据不足"

        )

        return





    print()

    print(

        "最近30期开奖结果"

    )

    print("-"*30)



    for r in rows:


        print(

            r["issue"],

            "特码",

            r["special"],

            r["color"],

            r["halfhalf"]

        )




    print()

    print("="*35)

    print(

        "新澳门彩 V8.16 BALANCE预测"

    )

    print("="*35)



    model=FusionV816(

        rows

    )



    result=model.predict()



    print()

    print("颜色预测:")



    for k,v in sorted(

        result["color"].items(),

        key=lambda x:x[1],

        reverse=True

    ):


        print(

            k,

            v,

            "%"

        )





    print()

    print("大小预测:")


    for k,v in result["size"].items():

        print(

            k,

            v,

            "%"

        )





    print()

    print("单双预测:")


    for k,v in result["odd"].items():

        print(

            k,

            v,

            "%"

        )




    print()

    print("最终TOP5:")



    for i,c in enumerate(

        result["candidates"],

        1

    ):


        print(

            i,

            c["halfhalf"],

            c["score"]

        )





    BackTest816(

        rows

    ).print_result()




    save_report(

        result

    )



    print()

    print(

        "报告生成:",

        REPORT_FILE

    )






if __name__=="__main__":

    main()