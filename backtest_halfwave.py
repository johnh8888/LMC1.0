# =====================================================
# 三彩 V11.4.1 AI四层特码预测系统
# 数据模块修复版
# =====================================================

import requests
import json
import datetime
import time
import random
from collections import Counter


# =====================================================
# API配置
# =====================================================

API_CONFIG = {

    "香港彩":
        "https://marksix6.net/index.php?api=1",

    "新澳门彩":
        "https://marksix6.net/index.php?api=1",

    "老澳门彩":
        "https://marksix6.net/index.php?api=1"

}


# =====================================================
# 基础配置
# =====================================================

CONFIG = {

    "history_limit":500,

    "timeout":15

}


# =====================================================
# 请求数据
# =====================================================

def request_api(url):

    try:

        headers={
            "User-Agent":
            "Mozilla/5.0"
        }


        r=requests.get(
            url,
            headers=headers,
            timeout=CONFIG["timeout"]
        )


        r.encoding="utf-8"


        return r.text


    except Exception as e:

        print(
            "API请求失败:",
            e
        )

        return None



# =====================================================
# 解析特码
# =====================================================

def parse_number(value):

    try:

        if isinstance(value,int):

            return value


        s=str(value)


        nums=[]

        temp=""

        for c in s:

            if c.isdigit():

                temp+=c

            else:

                if temp:

                    nums.append(
                        int(temp)
                    )

                    temp=""


        if temp:

            nums.append(
                int(temp)
            )


        for n in nums:

            if 1<=n<=49:

                return n


    except:

        pass


    return None



# =====================================================
# 数据解析
# =====================================================

def parse_history(raw):


    result=[]


    try:


        data=json.loads(raw)



    except:


        print(
            "JSON解析失败"
        )

        return []



    # 兼容不同返回格式

    if isinstance(data,dict):

        for key in [
            "data",
            "result",
            "list",
            "history"
        ]:

            if key in data:

                data=data[key]

                break



    if not isinstance(data,list):

        return []



    for item in data:


        if not isinstance(item,dict):

            continue



        issue=""

        number=None



        # 期号

        for k in [
            "issue",
            "expect",
            "period",
            "qihao",
            "term"
        ]:

            if k in item:

                issue=str(
                    item[k]
                )

                break



        # 特码

        for k in [
            "tm",
            "special",
            "number",
            "teMa",
            "code",
            "open"
        ]:


            if k in item:

                number=parse_number(
                    item[k]
                )

                if number:

                    break



        if number is None:


            # 尝试所有字段搜索

            for v in item.values():

                number=parse_number(v)

                if number:

                    break



        if number:


            result.append({

                "issue":issue,

                "number":number

            })



    return result[:CONFIG["history_limit"]]



# =====================================================
# 获取彩票数据
# =====================================================

def fetch_lottery(name):


    print()

    print(
        "📡 获取数据:",
        name
    )


    url=API_CONFIG.get(name)



    if not url:


        print(
            "❌ API地址未配置:",
            name
        )

        return []



    raw=request_api(url)



    if not raw:


        return []



    history=parse_history(
        raw
    )



    print(
        "✅ 获取",
        len(history),
        "期"
    )



    return history
    # =====================================================
# V11.4.1
# 数据校验 + 特码属性模块
# =====================================================


# =====================================================
# 数据校验
# =====================================================

def check_history(history):

    print()
    print("🔍 数据校验")


    if not history:

        print("❌ 无数据")

        return False



    print(
        "数据数量:",
        len(history)
    )


    latest = history[0]


    print(
        "最新期:",
        latest.get("issue")
    )


    print(
        "最新特码:",
        latest.get("number")
    )


    num = latest.get("number")


    if not isinstance(num,int):

        print(
            "❌ 特码格式错误"
        )

        return False



    if num < 1 or num >49:

        print(
            "❌ 特码范围错误"
        )

        return False



    print(
        "颜色:",
        get_color(num)
    )


    print(
        "✅ 数据正常"
    )


    return True



# =====================================================
# 颜色计算
# =====================================================

RED = {

1,2,7,8,12,13,18,19,
23,24,29,30,34,35,
40,45,46

}


BLUE={

3,4,9,10,14,15,
20,25,26,31,36,
37,41,42,47,48

}


GREEN={

5,6,11,16,17,
21,22,27,28,
32,33,38,39,
43,44,49

}



def get_color(num):


    if num in RED:

        return "红"


    elif num in BLUE:

        return "蓝"


    elif num in GREEN:

        return "绿"


    return "未知"



# =====================================================
# 大小
# =====================================================

def get_size(num):


    if num>=25:

        return "大"


    return "小"



# =====================================================
# 单双
# =====================================================

def get_odd_even(num):


    if num%2==0:

        return "双"


    return "单"



# =====================================================
# 尾数
# =====================================================

def get_tail(num):


    return num%10



# =====================================================
# 余数
# =====================================================

def get_remainder(num):


    return num%3



# =====================================================
# 历史统计
# =====================================================

def analyze_history(history):


    nums=[

        x["number"]

        for x in history

        if x.get("number")

    ]



    data={

        "color":Counter(),

        "size":Counter(),

        "odd":Counter(),

        "tail":Counter(),

        "remainder":Counter()

    }



    for n in nums:


        data["color"][
            get_color(n)
        ]+=1



        data["size"][
            get_size(n)
        ]+=1



        data["odd"][
            get_odd_even(n)
        ]+=1



        data["tail"][
            get_tail(n)
        ]+=1



        data["remainder"][
            get_remainder(n)
        ]+=1



    return data



# =====================================================
# 单个号码属性
# =====================================================

def number_feature(num):


    return {

        "number":num,

        "tail":
        get_tail(num),

        "remainder":
        get_remainder(num),

        "size":
        get_size(num),

        "odd":
        get_odd_even(num),

        "color":
        get_color(num)

    }



# =====================================================
# 49码属性池
# =====================================================

def build_number_pool():


    pool=[]


    for n in range(1,50):


        pool.append(

            number_feature(n)

        )


    return pool
    # =====================================================
# V11.4.1
# AI四层特码评分模型
# 尾数余数 → 大小 → 单双 → 颜色 → 双码组合
# =====================================================


# =====================================================
# 时间衰减权重
# =====================================================

def time_weight(index):

    """
    越新的数据权重越高
    """

    return 1 / (1 + index * 0.015)



# =====================================================
# 号码基础评分
# =====================================================

def calculate_number_score(
        num,
        history
):


    score = 0


    features = number_feature(num)



    # ---------------------------------
    # 1. 尾数模型
    # ---------------------------------

    tail_score = 0


    for i,item in enumerate(history):


        if get_tail(
            item["number"]
        ) == features["tail"]:


            tail_score += time_weight(i)



    # ---------------------------------
    # 2. 余数模型
    # ---------------------------------

    remainder_score = 0


    for i,item in enumerate(history):


        if get_remainder(
            item["number"]
        ) == features["remainder"]:


            remainder_score += time_weight(i)



    # ---------------------------------
    # 3. 大小模型
    # ---------------------------------

    size_score = 0


    for i,item in enumerate(history):


        if get_size(
            item["number"]
        ) == features["size"]:


            size_score += time_weight(i)



    # ---------------------------------
    # 4. 单双模型
    # ---------------------------------

    odd_score = 0


    for i,item in enumerate(history):


        if get_odd_even(
            item["number"]
        ) == features["odd"]:


            odd_score += time_weight(i)



    # ---------------------------------
    # 5. 颜色模型
    # ---------------------------------

    color_score = 0


    for i,item in enumerate(history):


        if get_color(
            item["number"]
        ) == features["color"]:


            color_score += time_weight(i)




    # 归一化

    total_history=len(history)


    if total_history:


        tail_score = tail_score / total_history *100

        remainder_score = remainder_score / total_history *100

        size_score = size_score / total_history *100

        odd_score = odd_score / total_history *100

        color_score = color_score / total_history *100




    # =====================================================
    # 四层融合
    # =====================================================


    final_score=(

        tail_score *0.25

        +

        remainder_score *0.15

        +

        size_score *0.20

        +

        odd_score *0.20

        +

        color_score *0.20

    )


    return {

        "number":num,

        "score":
        round(final_score,2),

        "tail":
        round(tail_score,2),

        "remainder":
        round(remainder_score,2),

        "size":
        round(size_score,2),

        "odd":
        round(odd_score,2),

        "color":
        round(color_score,2)

    }



# =====================================================
# TOP号码排序
# =====================================================

def rank_numbers(history):


    result=[]


    for n in range(1,50):


        result.append(

            calculate_number_score(
                n,
                history
            )

        )


    result.sort(

        key=lambda x:x["score"],

        reverse=True

    )


    return result



# =====================================================
# 双码组合评分
# =====================================================

def pair_score(
        a,
        b,
        history
):


    score=0



    # 基础分

    score += a["score"]

    score += b["score"]



    # ---------------------------------
    # 避免同尾
    # ---------------------------------

    if a["tail"]==b["tail"]:

        score-=8



    # ---------------------------------
    # 避免同大小过度集中
    # ---------------------------------

    if a["size"]==b["size"]:

        score-=3



    # ---------------------------------
    # 颜色分散
    # ---------------------------------

    if a["color"]!=b["color"]:

        score+=5



    # ---------------------------------
    # 单双平衡
    # ---------------------------------

    if a["odd"]!=b["odd"]:

        score+=3



    return round(score,2)



# =====================================================
# 获取最佳双码
# =====================================================

def get_best_pair(ranking):


    best=None

    best_score=-999



    top=ranking[:15]



    for i in range(len(top)):

        for j in range(i+1,len(top)):


            s=pair_score(
                top[i],
                top[j],
                ranking
            )


            if s>best_score:


                best_score=s


                best=(

                    top[i]["number"],

                    top[j]["number"]

                )



    return best,best_score



# =====================================================
# 防守号码
# =====================================================

def get_defense(ranking):


    return [

        x["number"]

        for x in ranking[2:5]

    ]
    # =====================================================
# V11.4.1
# 输出 + 回测 + 主程序
# =====================================================


# =====================================================
# TOP10输出
# =====================================================

def print_prediction(
        name,
        history
):


    print()
    print("="*70)

    print(
        "🎯",
        name,
        "V11.4.1 AI预测"
    )

    print("="*70)



    ranking=rank_numbers(
        history
    )


    latest=history[0]["number"]


    print()

    print(
        "最新特码:",
        latest
    )


    print()

    print("🔥 TOP10号码")

    print("-"*70)



    for i,item in enumerate(
        ranking[:10],
        1
    ):


        print(

            f"{i:02d}. "

            f"{item['number']:02d} "

            f"总分:{item['score']} "

            f"尾:{item['tail']} "

            f"余:{item['remainder']} "

            f"大小:{item['size']} "

            f"单双:{item['odd']} "

            f"颜色:{item['color']}"

        )



    pair,score=get_best_pair(
        ranking
    )


    print()

    print(
        "⭐ 主推双码:",
        pair
    )


    print(
        "组合评分:",
        score
    )



    print()

    print(
        "🛡 防守号码:",
        get_defense(ranking)
    )



    return ranking



# =====================================================
# 简易回测
# =====================================================

def backtest(history):


    if len(history)<100:

        return



    win=0

    lose=0



    total=len(history)-50



    for i in range(
        50,
        len(history)
    ):



        train=history[i:]


        target=history[i-1]["number"]



        ranking=rank_numbers(
            train
        )



        top5=[

            x["number"]

            for x in ranking[:5]

        ]



        if target in top5:

            win+=1

        else:

            lose+=1



    rate=round(

        win/(win+lose)*100,

        2

    )



    print()

    print("📈 历史回测")

    print("-"*70)

    print(
        "TOP5命中:",
        rate,
        "%"
    )

    print(
        "胜:",
        win,
        "负:",
        lose
    )



# =====================================================
# 三彩分析
# =====================================================

def analyze_lottery(name):


    print()

    print("="*70)

    print(
        "📡 获取数据:",
        name
    )

    print("="*70)



    history=fetch_lottery(
        name
    )



    if not check_history(
        history
    ):


        print(
            "❌ 数据为空:",
            name
        )

        return



    ranking=print_prediction(

        name,

        history

    )



    backtest(
        history
    )





# =====================================================
# 主入口
# =====================================================

def main():


    print("="*70)

    print(
        "🚀 三彩 V11.4.1 AI四层特码预测系统启动"
    )

    print(
        datetime.datetime.now()
    )

    print("="*70)



    print()

    print(
        "模型结构:"
    )

    print(
        "尾数余数 → 大小 → 单双 → 颜色 → 双码组合"
    )



    for name in [

        "香港彩",

        "新澳门彩",

        "老澳门彩"

    ]:


        analyze_lottery(
            name
        )



    print()

    print("="*70)

    print(
        "✅ V11.4.1运行完成"
    )

    print("="*70)





if __name__=="__main__":

    main()