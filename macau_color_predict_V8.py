#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门彩预测系统 V8.15 DYNAMIC BALANCE

升级:

1. 颜色/大小/单双/半半波四模型
2. 最近10/20/30窗口
3. 动态权重平衡
4. 热冷平衡
5. 连续颜色防追
6. 半半波参与最终评分
7. 最近10/20/30盲测
8. 严格禁止偷看未来数据

"""


import re
import json
import urllib.request

from collections import defaultdict



# =====================================================
# 配置
# =====================================================


CONFIG={

    "history_limit":30,

    "api_url":
    "https://marksix6.net/index.php?api=1"

}



REPORT_FILE="result_v815.md"




# =====================================================
# 波色
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
# 属性计算
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

                "color":get_color(special),

                "size":get_size(special),

                "odd":get_odd(special),

                "halfhalf":get_halfhalf(special)


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
# 基础预测引擎
# =====================================================


class PredictEngine:


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



    def miss_score(self,values,attr):


        bonus=defaultdict(float)



        for v in values:


            miss=0


            for r in self.rows:


                if r[attr]==v:

                    break


                miss+=1



            bonus[v]=min(

                miss*1.5,

                10

            )



        return bonus
        # =====================================================
# V8.15 属性预测
# =====================================================


    def predict_attr(self,attr,values):


        score=self.window_score(attr)


        miss=self.miss_score(

            values,

            attr

        )



        for v in values:

            score[v]+=miss[v]



        # ==========================
        # 连续趋势修正
        # ==========================


        recent=[

            r[attr]

            for r in self.rows[:5]

        ]



        count={

            v:recent.count(v)

            for v in values

        }



        for v,c in count.items():


            if c>=3:

                # 连续追热降低

                score[v]-=c*2




        total=sum(score.values())



        if total<=0:

            total=1



        return {


            k:round(

                score[k]/total*100,

                2

            )

            for k in values

        }





    # =================================================
    # 颜色
    # =================================================


    def color(self):


        return self.predict_attr(

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


        return self.predict_attr(

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


        return self.predict_attr(

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



                score[hh]+=(

                    size-i

                )*weight




        # 遗漏补偿


        for k in list(score.keys()):


            miss=0


            for r in self.rows:


                if r["halfhalf"]==k:

                    break


                miss+=1



            score[k]+=min(

                miss,

                8

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
# V8.15 综合融合
# =====================================================


class FusionPredict:



    def __init__(self,rows):


        self.rows=rows



        self.engine=PredictEngine(

            rows

        )





    def predict(self):



        color=self.engine.color()


        size=self.engine.size()


        odd=self.engine.odd()



        candidates=[]



        # 颜色TOP2

        top_colors=sorted(

            color.items(),

            key=lambda x:x[1],

            reverse=True

        )[:2]





        for c,cp in top_colors:



            hh=self.engine.halfhalf(

                c

            )



            for h,hp in list(

                hh.items()

            )[:5]:



                # --------------------------
                # 半半波拆分
                # --------------------------


                h_size=h[1]

                h_odd=h[2]



                score=(


                    cp*0.35


                    +

                    size.get(

                        h_size,

                        0

                    )*0.25



                    +

                    odd.get(

                        h_odd,

                        0

                    )*0.25



                    +

                    hp*0.15


                )



                candidates.append({


                    "halfhalf":h,


                    "color":c,


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


            "candidates":candidates[:5]

        }
        # =====================================================
# V8.15 盲测回测
# =====================================================


class BackTest:



    def __init__(self,rows):

        self.rows=rows




    def test_window(self,window):


        result={

            "color":0,

            "size":0,

            "odd":0,

            "halfhalf":0,

            "combo":0,

            "total":0

        }



        # 禁止偷看未来
        # 使用历史之后的数据预测当前期


        max_test=min(

            10,

            len(self.rows)-window

        )



        for i in range(max_test):


            history=self.rows[i+1:]

            actual=self.rows[i]



            engine=FusionPredict(

                history

            )



            pred=engine.predict()



            result["total"]+=1




            # 颜色

            if max(

                pred["color"],

                key=pred["color"].get

            )==actual["color"]:

                result["color"]+=1




            # 大小

            if max(

                pred["size"],

                key=pred["size"].get

            )==actual["size"]:

                result["size"]+=1





            # 单双

            if max(

                pred["odd"],

                key=pred["odd"].get

            )==actual["odd"]:

                result["odd"]+=1





            # 半半波

            top=[

                x["halfhalf"]

                for x in pred["candidates"]

            ]



            if actual["halfhalf"] in top:

                result["halfhalf"]+=1




            # 综合第一名

            if pred["candidates"][0]["halfhalf"]==actual["halfhalf"]:

                result["combo"]+=1




        return result





    def report(self):


        print("\n")

        print("="*30)

        print(

            "V8.15 多窗口盲测"

        )

        print("="*30)



        for w in [

            10,

            20,

            30

        ]:


            r=self.test_window(w)



            print()

            print(

                "窗口",

                w

            )



            for k in [

                "color",

                "size",

                "odd",

                "halfhalf",

                "combo"

            ]:


                if r["total"]:


                    print(

                        k,

                        ":",

                        r[k],

                        "/",

                        r["total"],

                        "=",

                        round(

                            r[k]/r["total"]*100,

                            2

                        ),

                        "%"

                    )








# =====================================================
# 输出报告
# =====================================================


def save_report(result):


    with open(

        REPORT_FILE,

        "w",

        encoding="utf-8"

    ) as f:



        f.write(

            "# 新澳门彩 V8.15 DYNAMIC BALANCE\n\n"

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

                f"- {k}: {v}%\n"

            )




        f.write(

            "\n## 大小预测\n\n"

        )


        for k,v in result["size"].items():

            f.write(

                f"- {k}: {v}%\n"

            )




        f.write(

            "\n## 单双预测\n\n"

        )



        for k,v in result["odd"].items():

            f.write(

                f"- {k}: {v}%\n"

            )




        f.write(

            "\n## 最终TOP5\n\n"

        )


        for i,c in enumerate(

            result["candidates"],

            1

        ):


            f.write(

                f"{i}. "

                f"{c['halfhalf']} "

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

    print(

        "-"*30

    )



    for r in rows:


        print(

            r["issue"],

            "特码",

            r["special"],

            r["color"],

            r["halfhalf"]

        )




    print()

    print("="*30)

    print(

        "新澳门彩 V8.15 DYNAMIC BALANCE"

    )

    print("="*30)



    model=FusionPredict(

        rows

    )



    result=model.predict()




    print("\n颜色预测:")


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





    print("\n大小预测:")


    for k,v in result["size"].items():

        print(

            k,

            v,

            "%"

        )





    print("\n单双预测:")


    for k,v in result["odd"].items():

        print(

            k,

            v,

            "%"

        )




    print("\n最终综合TOP5:")



    for i,c in enumerate(

        result["candidates"],

        1

    ):


        print(

            i,

            c["halfhalf"],

            c["score"]

        )




    BackTest(

        rows

    ).report()



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