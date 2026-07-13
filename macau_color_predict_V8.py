#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
新澳门彩颜色预测系统 V8.6 FINAL

核心:
1. 只分析最近30期
2. 锁定新澳门彩
3. 趋势+频率+遗漏融合
4. 针对下一期预测
5. 自动生成报告
"""


import os
import re
import json
import time
import urllib.request


from collections import defaultdict
from itertools import product



# =====================================================
# 配置
# =====================================================


CONFIG = {


    # 分析期数

    "history_limit":30,


    # 权重

    "trend_weight":45,

    "frequency_weight":25,

    "missing_weight":20,

    "pattern_weight":10,


    # 自动优化范围

    "search_space":{


        "trend_weight":[40,45,50],

        "frequency_weight":[25],

        "missing_weight":[15,20],

        "pattern_weight":[10]


    },


    "api_url":

    "https://marksix6.net/index.php?api=1"


}



PARAM_FILE="macau_v86_params.json"


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


    headers={

        "User-Agent":

        "Mozilla/5.0"

    }



    for retry in range(3):


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


            break



        except Exception as e:


            print(

                "获取失败",

                retry+1,

                e

            )


            time.sleep(2)



    else:


        return []




    print(

        "扫描彩种:"

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



        if not 1<=special<=49:

            continue



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


            "halfhalf":get_halfhalf(special)


        })




    # 去重

    unique={}



    for r in rows:


        unique[r["issue"]]=r



    rows=list(unique.values())



    rows.sort(

        key=lambda x:x["issue"],

        reverse=True

    )



    rows=rows[:limit]



    print(

        f"获取新澳门彩:{len(rows)}期"

    )



    return rows
    # =====================================================
# V8.6 预测核心
# =====================================================


class PredictEngine:


    def __init__(self, rows):


        self.rows = rows[:CONFIG["history_limit"]]




    # =================================================
    # 颜色评分
    # =================================================


    def color_score(self):


        score={

            "红":0,

            "蓝":0,

            "绿":0

        }



        # 趋势

        for i,r in enumerate(self.rows):


            weight=30-i


            score[r["color"]]+=weight




        # 频率

        counter={

            c:0 for c in COLORS

        }


        for r in self.rows:


            counter[r["color"]]+=1



        for c in COLORS:


            score[c]+=counter[c]*2





        # 遗漏

        for c in COLORS:


            miss=0


            for r in self.rows:


                if r["color"]==c:

                    break


                miss+=1



            score[c]+=min(

                miss*2,

                20

            )



        return score






    # =================================================
    # 半波评分
    # =================================================


    def half_score(self):


        score=defaultdict(float)



        for i,r in enumerate(self.rows):


            weight=30-i



            for h in r["half"]:


                score[h]+=weight




        for h in HALF_WAVES:


            miss=0


            for r in self.rows:


                if h in r["half"]:

                    break


                miss+=1



            score[h]+=min(

                miss*1.5,

                20

            )



        return dict(score)







    # =================================================
    # 半半波评分
    # =================================================


    def halfhalf_score(self):


        score=defaultdict(float)



        for i,r in enumerate(self.rows):


            weight=30-i



            score[r["halfhalf"]]+=weight




        for h in HALF_HALF_WAVES:


            miss=0


            for r in self.rows:


                if r["halfhalf"]==h:

                    break


                miss+=1



            score[h]+=min(

                miss*1.5,

                20

            )



        return dict(score)






    # =================================================
    # 综合融合
    # =================================================


    def predict(self):


        color=self.color_score()


        half=self.half_score()


        halfhalf=self.halfhalf_score()



        final={

            "红":0,

            "蓝":0,

            "绿":0

        }




        # 颜色贡献

        for k,v in color.items():


            final[k]+=v*0.45




        # 半波贡献

        for k,v in half.items():


            final[k[0]]+=v*0.35




        # 半半波贡献

        for k,v in halfhalf.items():


            final[k[0]]+=v*0.20





        return {


            "color":

            sorted(

                color.items(),

                key=lambda x:x[1],

                reverse=True

            ),



            "half":

            sorted(

                half.items(),

                key=lambda x:x[1],

                reverse=True

            )[:5],




            "halfhalf":

            sorted(

                halfhalf.items(),

                key=lambda x:x[1],

                reverse=True

            )[:5],




            "final":

            sorted(

                final.items(),

                key=lambda x:x[1],

                reverse=True

            )


        }








# =====================================================
# 回测
# =====================================================


def backtest(rows):


    hit_color=0

    hit_half=0

    hit_halfhalf=0



    total=min(

        20,

        len(rows)-5

    )



    if total<=0:


        return {


            "color":0,

            "half":0,

            "halfhalf":0

        }





    for i in range(total):



        history=rows[i+1:]



        result=PredictEngine(

            history

        ).predict()



        actual=rows[i]





        # 颜色TOP1


        if result["final"][0][0]==actual["color"]:


            hit_color+=1





        # 半波TOP3


        half=[

            x[0]

            for x in result["half"][:3]

        ]



        if any(

            x in actual["half"]

            for x in half

        ):


            hit_half+=1





        # 半半波TOP3


        hh=[

            x[0]

            for x in result["halfhalf"][:3]

        ]



        if actual["halfhalf"] in hh:


            hit_halfhalf+=1





    return {


        "color":

        round(

            hit_color/total*100,

            2

        ),



        "half":

        round(

            hit_half/total*100,

            2

        ),



        "halfhalf":

        round(

            hit_halfhalf/total*100,

            2

        )


    }
    # =====================================================
# 自动调参
# =====================================================


def auto_search(rows):


    print(

        "开始V8.6自动优化..."

    )



    keys=list(

        CONFIG["search_space"].keys()

    )



    values=list(

        CONFIG["search_space"].values()

    )



    best_score=-1

    best=None



    combos=list(

        product(*values)

    )



    for index,combo in enumerate(combos,1):


        params=dict(

            zip(

                keys,

                combo

            )

        )



        for k,v in params.items():


            CONFIG[k]=v




        bt=backtest(rows)



        score=(

            bt["color"]*0.45

            +

            bt["half"]*0.35

            +

            bt["halfhalf"]*0.20

        )




        print(

            "参数",

            index,

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


    if not os.path.exists(PARAM_FILE):

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

            "加载V8.6参数"

        )



    except:


        pass







# =====================================================
# 显示走势
# =====================================================


def show_recent(rows):


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








# =====================================================
# 输出预测
# =====================================================


def print_prediction(result):


    print()

    print(

        "="*20

    )

    print(

        "新澳门彩 V8.6预测"

    )



    print()


    print(

        "颜色TOP:"

    )


    for x in result["final"]:


        print(

            x[0],

            round(x[1],2)

        )



    print()


    print(

        "半波TOP:"

    )



    for x in result["half"]:


        print(

            x[0],

            round(x[1],2)

        )



    print()


    print(

        "半半波TOP:"

    )



    for x in result["halfhalf"]:


        print(

            x[0],

            round(x[1],2)

        )



    print(

        "="*20

    )







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



        latest=rows[0]



        f.write(

f"""
最新开奖:

期号:{latest['issue']}

特码:{latest['special']}

颜色:{latest['color']}

半半波:{latest['halfhalf']}



##预测

颜色:

{result['final']}


半波:

{result['half']}


半半波:

{result['halfhalf']}



##回测

颜色:

{bt['color']}%


半波:

{bt['half']}%


半半波:

{bt['halfhalf']}%

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





    show_recent(rows)




    # 自动优化

    if not os.path.exists(PARAM_FILE):


        auto_search(rows)



    load_params()




    result=PredictEngine(

        rows

    ).predict()



    print_prediction(result)




    bt=backtest(rows)



    print()


    print(

        "最近回测"

    )



    print(

        "颜色:",

        bt["color"],

        "%"

    )


    print(

        "半波:",

        bt["half"],

        "%"

    )



    print(

        "半半波:",

        bt["halfhalf"],

        "%"

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