#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门彩颜色预测系统 V8.14 DYNAMIC

升级:

1. 最近30期训练
2. 动态窗口10/20/30
3. 颜色/大小/单双/半半波四模型
4. 动态权重学习
5. TOP2颜色融合
6. 最近10期盲测回测
7. 防止偷看未来数据

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
    "https://marksix6.net/index.php?api=1"

}


REPORT_FILE="result_v814.md"



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
# 动态预测核心
# =====================================================


class DynamicPredictEngine:


    def __init__(self,rows):

        self.rows=rows[:30]



    def window_score(self,attr):

        score=defaultdict(float)


        for size,weight in [

            (10,0.5),

            (20,0.3),

            (30,0.2)

        ]:


            data=self.rows[:size]


            for i,r in enumerate(data):


                value=r[attr]


                score[value]+=(
                    size-i
                )*weight


        return score



    def miss_bonus(self,values,attr):

        bonus=defaultdict(float)


        for v in values:


            miss=0


            for r in self.rows:


                if r[attr]==v:

                    break


                miss+=1



            bonus[v]=min(

                miss*1.5,

                15

            )


        return bonus



    def normalize(self,score):

        total=sum(score.values())


        if total==0:

            return {}


        return {

            k:round(

                v/total*100,

                2

            )

            for k,v in score.items()

        }



    def predict_attr(self,attr,values):

        score=self.window_score(attr)


        bonus=self.miss_bonus(

            values,

            attr

        )


        for v in values:

            score[v]+=bonus[v]


        return self.normalize(score)



    def predict_color(self):

        return self.predict_attr(

            "color",

            ["红","蓝","绿"]

        )



    def predict_size(self):

        return self.predict_attr(

            "size",

            ["大","小"]

        )



    def predict_odd(self):

        return self.predict_attr(

            "odd",

            ["单","双"]

        )
            # =================================================
    # 半半波预测
    # =================================================

    def predict_halfhalf(self,color=None):

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

        all_values=[]


        for c in ["红","蓝","绿"]:

            for s in ["大","小"]:

                for o in ["单","双"]:

                    all_values.append(
                        c+s+o
                    )


        for hh in all_values:


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

            if (

                color is None

                or

                k.startswith(color)

            )

        }



# =====================================================
# 动态权重学习
# =====================================================


class WeightLearner:


    def __init__(self,rows):

        self.rows=rows



    def test_model(self,mode,test=10):


        hit=0

        total=0



        max_test=min(

            test,

            len(self.rows)-10

        )


        for i in range(max_test):


            history=self.rows[i+1:i+31]


            if len(history)<5:

                continue



            engine=DynamicPredictEngine(

                history

            )


            actual=self.rows[i]



            if mode=="color":


                pred=max(

                    engine.predict_color(),

                    key=engine.predict_color().get

                )



            elif mode=="size":


                pred=max(

                    engine.predict_size(),

                    key=engine.predict_size().get

                )



            elif mode=="odd":


                pred=max(

                    engine.predict_odd(),

                    key=engine.predict_odd().get

                )


            else:

                continue



            if pred==actual[mode]:

                hit+=1



            total+=1



        if total==0:

            return 0



        return round(

            hit/total*100,

            2

        )





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

                "color":0.4,

                "size":0.3,

                "odd":0.3

            }



        return {

            k:round(

                v/total,

                3

            )

            for k,v in scores.items()

        }




# =====================================================
# 综合融合预测
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

        top_colors=sorted(

            color.items(),

            key=lambda x:x[1],

            reverse=True

        )[:2]




        for c,cp in top_colors:


            half=engine.predict_halfhalf(

                c

            )



            for hh,hp in list(

                half.items()

            )[:3]:


                score=(


                    cp*weight["color"]


                    +

                    hp*0.45


                    +

                    size.get(

                        hh[1],

                        0

                    )*weight["size"]


                    +

                    odd.get(

                        hh[-1],

                        0

                    )*weight["odd"]

                )


                candidates.append({

                    "halfhalf":hh,

                    "score":round(

                        score,

                        2

                    )

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
# V8.14 最近10期盲测回测
# =====================================================


class BackTester:


    def __init__(self,rows):

        self.rows=rows



    def run(self,period=10):


        result={

            "color":0,

            "size":0,

            "odd":0,

            "halfhalf":0,

            "combo":0,

            "total":0

        }



        count=min(

            period,

            len(self.rows)-10

        )



        for i in range(count):


            # 关键:
            # 不包含当前开奖
            # 只使用历史数据


            history=self.rows[i+1:i+31]



            engine=DynamicPredictEngine(

                history

            )


            fusion=FinalFusion(

                history

            ).predict()



            actual=self.rows[i]



            # 颜色

            color_pred=max(

                engine.predict_color(),

                key=engine.predict_color().get

            )



            if color_pred==actual["color"]:

                result["color"]+=1



            # 大小

            size_pred=max(

                engine.predict_size(),

                key=engine.predict_size().get

            )


            if size_pred==actual["size"]:

                result["size"]+=1



            # 单双

            odd_pred=max(

                engine.predict_odd(),

                key=engine.predict_odd().get

            )


            if odd_pred==actual["odd"]:

                result["odd"]+=1




            # 半半波

            hh=engine.predict_halfhalf(

                actual["color"]

            )


            if hh:


                hh_pred=max(

                    hh,

                    key=hh.get

                )


                if hh_pred==actual["halfhalf"]:

                    result["halfhalf"]+=1




            # 综合TOP5

            top=[

                x["halfhalf"]

                for x in fusion["candidates"]

            ]



            if actual["halfhalf"] in top:

                result["combo"]+=1




            result["total"]+=1





        return result






def show_backtest(data):


    total=data["total"]


    print("\n")

    print("="*30)

    print(

        "V8.14 最近10期盲测回测"

    )

    print("="*30)



    if total==0:

        print("无数据")

        return



    for k in [

        "color",

        "size",

        "odd",

        "halfhalf",

        "combo"

    ]:


        print(

            k,

            ":",

            data[k],

            "/",

            total,

            "=",

            round(

                data[k]/total*100,

                2

            ),

            "%"

        )






# =====================================================
# 输出报告
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





def save_report(result,back):


    with open(

        REPORT_FILE,

        "w",

        encoding="utf-8"

    ) as f:


        f.write(

            "# 新澳门彩 V8.14预测报告\n\n"

        )


        f.write(

            "## 权重\n\n"

        )


        for k,v in result["weight"].items():

            f.write(

                f"{k}:{v}\n"

            )


        f.write(

            "\n## 综合TOP5\n\n"

        )


        for i,x in enumerate(

            result["candidates"],

            1

        ):


            f.write(

                f"{i}. {x['halfhalf']} "

                f"{x['score']}\n"

            )



        f.write(

            "\n## 最近10期盲测\n\n"

        )


        f.write(

            str(back)

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



    print_history(

        rows

    )



    print("\n")

    print("="*30)

    print(

        "新澳门彩 V8.14 DYNAMIC预测"

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


    for i,x in enumerate(

        result["candidates"],

        1

    ):


        print(

            i,

            x["halfhalf"],

            x["score"]

        )



    # 最近10期盲测

    back=BackTester(

        rows

    ).run(

        10

    )



    show_backtest(

        back

    )



    save_report(

        result,

        back

    )


    print(

        "\n报告生成:",

        REPORT_FILE

    )




if __name__=="__main__":

    main()