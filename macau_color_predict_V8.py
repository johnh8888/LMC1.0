#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门彩颜色预测系统 V8.13 DYNAMIC

升级:

1. 最近30期主分析
2. 最近10/20/30期动态窗口
3. 颜色/大小/单双/半半波四模型
4. 自动动态权重
5. 滚动回测调整权重
6. 最终组合预测

"""

import re
import json
import urllib.request
import math

from collections import defaultdict, Counter



# =====================================================
# 配置
# =====================================================


CONFIG = {


    # 主数据量

    "history_limit":30,


    # 动态窗口

    "windows":[

        10,

        20,

        30

    ],



    # 初始权重

    "weights":{


        "color":0.35,

        "size":0.20,

        "odd":0.25,

        "halfhalf":0.20


    },



    "api_url":

    "https://marksix6.net/index.php?api=1"



}



REPORT_FILE="result_v813.md"






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
# 解析数据
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






        history=target.get(

            "history",

            []

        )





        for line in history:



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





    # 去重


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
# V8.13 四维预测引擎
# =====================================================


class DynamicPredictEngine:


    def __init__(self, rows):


        self.rows = rows[:30]



    # -------------------------------------------------
    # 动态窗口
    # -------------------------------------------------


    def window_score(self, attr):


        result = defaultdict(float)



        windows = [

            (10,0.5),

            (20,0.3),

            (30,0.2)

        ]



        for size,weight in windows:


            data=self.rows[:size]



            for i,r in enumerate(data):


                value=r[attr]


                # 越近权重越高

                w=(size-i)*weight


                result[value]+=w



        return result






    # -------------------------------------------------
    # 遗漏修正
    # -------------------------------------------------


    def miss_bonus(self, values, attr):


        bonus=defaultdict(float)



        for v in values:


            miss=0



            for r in self.rows:


                if r[attr]==v:

                    break


                miss+=1



            bonus[v]=min(

                miss*1.8,

                15

            )



        return bonus






    # =================================================
    # 颜色模型
    # =================================================


    def predict_color(self):


        values=[

            "红",

            "蓝",

            "绿"

        ]



        score=self.window_score(

            "color"

        )



        bonus=self.miss_bonus(

            values,

            "color"

        )



        for k in values:


            score[k]+=bonus[k]



        total=sum(score.values())



        return {


            k:round(

                score[k]/total*100,

                2

            )

            for k in score

        }








    # =================================================
    # 大小模型
    # =================================================


    def predict_size(self):


        values=[

            "大",

            "小"

        ]



        score=self.window_score(

            "size"

        )


        bonus=self.miss_bonus(

            values,

            "size"

        )



        for k in values:


            score[k]+=bonus[k]



        total=sum(score.values())



        return {


            k:round(

                score[k]/total*100,

                2

            )

            for k in score

        }








    # =================================================
    # 单双模型
    # =================================================


    def predict_odd(self):


        values=[

            "单",

            "双"

        ]



        score=self.window_score(

            "odd"

        )



        bonus=self.miss_bonus(

            values,

            "odd"

        )



        for k in values:


            score[k]+=bonus[k]



        total=sum(score.values())



        return {


            k:round(

                score[k]/total*100,

                2

            )

            for k in score

        }







    # =================================================
    # 半半波模型
    # =================================================


    def predict_halfhalf(self, color=None):


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



                score[hh]+=(size-i)*weight





        # 遗漏增强


        for hh in list(score.keys()):


            miss=0


            for r in self.rows:


                if r["halfhalf"]==hh:

                    break


                miss+=1



            score[hh]+=min(

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






    # =================================================
    # 综合评分
    # =================================================


    def final_predict(self):


        color=self.predict_color()


        size=self.predict_size()


        odd=self.predict_odd()



        # 第一层锁定颜色TOP2


        colors=sorted(

            color.items(),

            key=lambda x:x[1],

            reverse=True

        )



        top_colors=[

            x[0]

            for x in colors[:2]

        ]




        results=[]




        for c in top_colors:



            hh=self.predict_halfhalf(c)



            top_hh=list(

                hh.items()

            )[:3]



            for item,prob in top_hh:


                results.append({


                    "color":c,


                    "halfhalf":item,


                    "prob":prob



                })



        return {


            "color":color,


            "size":size,


            "odd":odd,


            "colors":top_colors,


            "results":results


        }
        # =====================================================
# V8.13 动态权重学习系统
# =====================================================


class WeightLearner:


    def __init__(self, rows):

        self.rows=rows




    # -------------------------------------------------
    # 单模型回测
    # -------------------------------------------------


    def test_model(self, mode, test=20):


        hit=0

        total=0



        for i in range(

            min(test,len(self.rows)-11)

        ):



            history=self.rows[i+1:]



            engine=DynamicPredictEngine(

                history

            )



            result=None



            actual=self.rows[i]



            if mode=="color":


                result=engine.predict_color()


                pred=max(

                    result,

                    key=result.get

                )


                if pred==actual["color"]:

                    hit+=1




            elif mode=="size":


                result=engine.predict_size()


                pred=max(

                    result,

                    key=result.get

                )


                if pred==actual["size"]:

                    hit+=1





            elif mode=="odd":


                result=engine.predict_odd()


                pred=max(

                    result,

                    key=result.get

                )


                if pred==actual["odd"]:

                    hit+=1





            total+=1




        if total==0:

            return 0



        return round(

            hit/total*100,

            2

        )







    # -------------------------------------------------
    # 获取动态权重
    # -------------------------------------------------


    def learn(self):


        scores={}



        for m in [

            "color",

            "size",

            "odd"

        ]:


            scores[m]=self.test_model(

                m

            )



        total=sum(

            scores.values()

        )



        if total==0:


            return {


                "color":0.5,

                "size":0.3,

                "odd":0.2

            }



        return {


            k:round(

                v/total,

                3

            )

            for k,v in scores.items()

        }









# =====================================================
# 最终融合预测
# =====================================================


class FinalFusion:


    def __init__(self,rows):


        self.rows=rows




    def predict(self):


        engine=DynamicPredictEngine(

            self.rows

        )


        learner=WeightLearner(

            self.rows

        )


        weight=learner.learn()




        color=engine.predict_color()


        size=engine.predict_size()


        odd=engine.predict_odd()




        candidates=[]



        # 颜色TOP2


        colors=sorted(

            color.items(),

            key=lambda x:x[1],

            reverse=True

        )[:2]





        for c,cp in colors:



            hh=engine.predict_halfhalf(

                c

            )



            for h,hp in list(

                hh.items()

            )[:3]:


                score=(

                    cp*weight["color"]

                    +

                    hp*0.5

                    +

                    size.get(

                        h[1],

                        0

                    )*weight["size"]

                    +

                    odd.get(

                        h[-1],

                        0

                    )*weight["odd"]

                )



                candidates.append({


                    "color":c,


                    "halfhalf":h,


                    "score":

                    round(score,2)



                })




        candidates.sort(

            key=lambda x:x["score"],

            reverse=True

        )



        return {


            "weight":weight,


            "color":color,


            "size":size,


            "odd":odd,


            "candidates":candidates[:5]

        }
        # =====================================================
# 主程序
# =====================================================


def print_history(rows):


    print("\n最近30期开奖结果")

    print("-"*30)



    for r in rows:


        print(

            r["issue"],

            "特码",

            r["special"],

            r["color"],

            r["halfhalf"]

        )







def save_report(result):


    with open(

        "result.md",

        "w",

        encoding="utf-8"

    ) as f:



        f.write(

            "# 新澳门彩 V8.13 动态预测报告\n\n"

        )



        f.write(

            "## 模型权重\n\n"

        )



        for k,v in result["weight"].items():

            f.write(

                f"- {k}: {v}\n"

            )



        f.write(

            "\n## 颜色预测\n\n"

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

            "\n## 最终综合TOP5\n\n"

        )



        for i,c in enumerate(

            result["candidates"],

            1

        ):


            f.write(

                f"{i}. "

                f"{c['halfhalf']} "

                f"评分:{c['score']}\n"

            )





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





    print_history(

        rows

    )





    print("\n")

    print("="*30)

    print(

        "新澳门彩 V8.13 DYNAMIC预测"

    )

    print("="*30)





    model=FinalFusion(

        rows

    )



    result=model.predict()




    print("\n动态权重:")



    for k,v in result["weight"].items():


        print(

            k,

            v

        )





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




    save_report(

        result

    )



    print(

        "\n报告生成: result.md"

    )







if __name__=="__main__":


    main()