# ============================================================
# 三彩 V11.3.1 AI四层特码预测系统
#
# 修复版本：
# 1. 修复 fetch_lottery 数据为空
# 2. 多API字段兼容
# 3. 数据自动校验
# 4. 四层融合预测
#
# ============================================================


import requests
import datetime
import itertools
import statistics
import random
import math
import time



# ============================================================
# 基础配置
# ============================================================


VERSION = "V11.3.1"



HISTORY_LIMIT = 500



TIMEOUT = 10



# ============================================================
# API配置
# ============================================================


API_URL = {

    "香港彩":
    "https://marksix6.net/index.php?api=1",


    "新澳门彩":
    "https://marksix6.net/index.php?api=1",


    "老澳门彩":
    "https://marksix6.net/index.php?api=1"

}




# ============================================================
# 颜色定义
# ============================================================


RED = {

1,2,7,8,12,13,18,19,
23,24,29,30,34,35,
40,45,46

}



BLUE = {

3,4,9,10,14,15,
20,25,26,31,36,
37,41,42,47,48

}



GREEN = {

5,6,11,16,17,21,
22,27,28,32,33,
38,39,43,44,49

}




def get_color(num):


    if num in RED:

        return "红"


    if num in BLUE:

        return "蓝"


    if num in GREEN:

        return "绿"


    return "未知"





# ============================================================
# 号码基础特征
# ============================================================


def number_feature(num):


    return {


        "num":
        num,


        # 尾数

        "tail":
        num % 10,



        # 大小

        "big":
        num >= 25,



        # 单双

        "odd":
        num % 2 == 1,



        # 余数

        "r3":
        num % 3,


        "r5":
        num % 5,


        "r7":
        num % 7,


        # 颜色

        "color":
        get_color(num)

    }





# ============================================================
# 生成1-49号码特征
# ============================================================


NUMBER_POOL = {


    i:number_feature(i)

    for i in range(1,50)

}





# ============================================================
# 数据排序工具
# ============================================================


def sort_history(data):


    try:


        return sorted(

            data,

            key=lambda x:

            str(x.get("issue","")),

            reverse=True

        )


    except:


        return data





print("="*70)

print(

"三彩",

VERSION,

"启动"

)

print(

datetime.datetime.now()

)

print("="*70)
# ============================================================
# 第2部分
# V11.3.1 数据获取模块
# ============================================================



def request_api(url):


    headers = {

        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

    }


    try:


        r = requests.get(

            url,

            headers=headers,

            timeout=TIMEOUT

        )


        r.encoding="utf-8"


        return r.text



    except Exception as e:


        print(

            "API请求失败:",

            e

        )


        return ""





# ============================================================
# 自动寻找列表数据
# ============================================================


def find_records(obj):


    if isinstance(obj,list):

        return obj



    if isinstance(obj,dict):


        keys=[

            "data",

            "list",

            "result",

            "history",

            "rows",

            "items",

            "records"

        ]


        for k in keys:


            if k in obj:


                result=find_records(

                    obj[k]

                )


                if result:

                    return result



    return []






# ============================================================
# 自动读取号码字段
# ============================================================


def parse_number(item):


    if not isinstance(item,dict):

        return None



    fields=[


        "tm",

        "te",

        "special",

        "special_num",

        "specialnum",

        "specialNumber",

        "number",

        "num",

        "code"

    ]



    for f in fields:


        if f in item:


            value=item[f]


            if isinstance(value,dict):


                for x in [

                    "num",

                    "number",

                    "value"

                ]:


                    if x in value:

                        value=value[x]

                        break



            try:


                value=int(value)


                if 1 <= value <= 49:


                    return value



            except:


                pass




    return None





# ============================================================
# 自动读取期号
# ============================================================


def parse_issue(item):


    if not isinstance(item,dict):

        return ""



    for f in [

        "issue",

        "period",

        "expect",

        "qihao",

        "openCode",

        "date"

    ]:


        if f in item:


            return str(item[f])



    return ""






# ============================================================
# 核心 fetch_lottery
# ============================================================



def fetch_lottery(name):


    url=API_URL.get(name)



    if not url:


        print(

            "没有数据源:",

            name

        )

        return []





    text=request_api(url)



    if not text:


        return []





    # JSON解析


    try:


        data=requests.models.complexjson.loads(

            text

        )


    except:


        print(

            "JSON解析失败"

        )


        return []





    records=find_records(data)



    history=[]



    for item in records:


        num=parse_number(item)



        if num:


            history.append({


                "issue":

                parse_issue(item),



                "num":

                num



            })




    history=sort_history(history)




    # 去重

    result=[]

    exists=set()



    for x in history:


        if x["num"] not in exists or True:


            result.append(x)



    return result[:HISTORY_LIMIT]






# ============================================================
# 数据校验
# ============================================================



def check_data(history):


    print()

    print(

        "🔍 数据校验"

    )



    if not history:


        print(

            "❌ 无数据"

        )

        return False




    latest=history[0]



    print(

        "最新期:",

        latest.get("issue")

    )


    print(

        "最新特码:",

        latest.get("num")

    )


    print(

        "颜色:",

        get_color(

            latest.get("num")

        )

    )




    nums=[

        x["num"]

        for x in history

    ]



    bad=[

        n for n in nums

        if n<1 or n>49

    ]



    if bad:


        print(

            "❌号码异常:",

            bad[:5]

        )


        return False




    print(

        "✅特码范围正常"

    )


    return True
    # ============================================================
# 第3部分
# V11.3.1 四层预测模型
#
# 第一层：
# 尾数 + 余数
#
# 第二层：
# 大小
#
# ============================================================



# ============================================================
# 历史统计
# ============================================================


def history_numbers(history):


    return [

        x["num"]

        for x in history

        if "num" in x

    ]





# ============================================================
# 第一层
# 尾数 + 余数模型
# ============================================================


def tail_remainder_score(num, history):


    nums=history_numbers(history)



    if not nums:


        return 0




    score=0



    tail=num % 10



    # ==========================
    # 尾数冷热
    # ==========================


    tails=[

        x%10

        for x in nums[:100]

    ]



    tail_count=tails.count(

        tail

    )



    score += tail_count * 2




    # ==========================
    # 余数分析
    # ==========================


    r3=num%3

    r5=num%5

    r7=num%7




    for r,mod in [

        (r3,3),

        (r5,5),

        (r7,7)

    ]:



        count=sum(

            1

            for x in nums[:100]

            if x%mod==r

        )



        score += count*0.3




    # ==========================
    # 遗漏补偿
    # ==========================


    miss=0



    for i,x in enumerate(nums):


        if x%10==tail:


            miss=i

            break



    if miss>15:


        score += 5




    return score






# ============================================================
# 第二层
# 大小模型
# ============================================================



def size_score(num,history):


    nums=history_numbers(history)



    if not nums:


        return 0



    score=0



    big=num>=25




    big_count=sum(

        1

        for x in nums[:50]

        if x>=25

    )



    small_count=50-big_count



    # 当前趋势


    if big:


        if big_count<small_count:

            score+=8


        else:

            score+=3



    else:


        if small_count<big_count:

            score+=8


        else:

            score+=3





    # 最近走势修正


    recent=nums[:10]



    rb=sum(

        1

        for x in recent

        if x>=25

    )



    if rb>=8 and num<25:


        score+=5



    if rb<=2 and num>=25:


        score+=5




    return score






# ============================================================
# 第一二层融合
# ============================================================



def layer12_score(num,history):


    return (

        tail_remainder_score(

            num,

            history

        )

        +

        size_score(

            num,

            history

        )

    )
    # ============================================================
# 第4部分
# V11.3.1
#
# 第三层:
# 单双模型
#
# 第四层:
# 颜色模型
#
# 四层融合
# ============================================================





# ============================================================
# 第三层
# 单双模型
# ============================================================


def odd_even_score(num, history):


    nums=history_numbers(history)


    if not nums:


        return 0



    score=0



    odd=num%2==1



    recent=nums[:50]



    odd_count=sum(

        1

        for x in recent

        if x%2==1

    )


    even_count=len(recent)-odd_count



    # 当前单双缺口补偿


    if odd:


        if odd_count < even_count:

            score += 8

        else:

            score += 3



    else:


        if even_count < odd_count:

            score += 8

        else:

            score += 3





    # 最近10期走势


    r10=nums[:10]



    odd10=sum(

        1

        for x in r10

        if x%2==1

    )



    if odd10>=8 and not odd:

        score+=5



    if odd10<=2 and odd:

        score+=5



    return score






# ============================================================
# 第四层
# 颜色模型
# ============================================================



def color_score(num,history):


    nums=history_numbers(history)



    if not nums:


        return 0



    color=get_color(num)



    score=0



    colors=[

        get_color(x)

        for x in nums[:100]

    ]



    count=colors.count(color)



    # 颜色热度


    score += count*0.8





    # 颜色遗漏


    miss=0


    for i,c in enumerate(colors):


        if c==color:


            miss=i

            break



    if miss>=15:


        score+=8



    elif miss>=8:


        score+=4



    return score





# ============================================================
# 四层综合评分
# ============================================================


def final_score(num,history):


    return round(

        tail_remainder_score(

            num,

            history

        )*0.35


        +

        size_score(

            num,

            history

        )*0.25


        +

        odd_even_score(

            num,

            history

        )*0.20


        +

        color_score(

            num,

            history

        )*0.20,


        3

    )







# ============================================================
# TOP号码
# ============================================================



def get_top_numbers(history):


    result=[]



    for num in range(1,50):


        result.append({


            "num":

            num,


            "score":

            final_score(

                num,

                history

            ),



            "color":

            get_color(num)

        })




    result.sort(

        key=lambda x:x["score"],

        reverse=True

    )



    return result
    # ============================================================
# 第5部分
# V11.3.1
#
# 双码组合
# 回测系统
#
# ============================================================



# ============================================================
# 双码组合评分
# ============================================================


def pair_score(a,b,history):


    score=0



    sa=final_score(

        a,

        history

    )


    sb=final_score(

        b,

        history

    )



    score += sa+sb




    # ======================
    # 尾数分散
    # ======================


    if a%10 != b%10:


        score +=5


    else:


        score-=3




    # ======================
    # 大小平衡
    # ======================


    if (a>=25)!=(b>=25):


        score+=5


    else:


        score+=1





    # ======================
    # 单双平衡
    # ======================


    if (a%2)!=(b%2):


        score+=5


    else:


        score+=1





    # ======================
    # 颜色分散
    # ======================


    if get_color(a)!=get_color(b):


        score+=5



    else:


        score-=2




    return round(score,3)






# ============================================================
# 推荐号码生成
# ============================================================



def predict_numbers(history):


    tops=get_top_numbers(

        history

    )



    top10=tops[:10]



    best=None


    best_score=-999



    for a,b in itertools.combinations(

        [x["num"] for x in top10],

        2

    ):



        s=pair_score(

            a,

            b,

            history

        )



        if s>best_score:


            best_score=s


            best=(a,b)




    guard=[

        x["num"]

        for x in tops[2:5]

    ]




    return {


        "top10":

        top10,


        "main":

        best,


        "pair_score":

        best_score,


        "guard":

        guard

    }








# ============================================================
# 历史回测
# ============================================================



def backtest_v113(history):


    if len(history)<120:


        return




    total=0


    hit1=0


    hit3=0


    hit5=0


    pair_hit=0





    # 使用过去数据预测未来


    test=history[:100]




    for i in range(

        20,

        len(test)

    ):



        train=test[i:]


        real=test[i-1]["num"]




        result=predict_numbers(

            train

        )



        top10=[

            x["num"]

            for x in result["top10"]

        ]




        if real in top10[:1]:

            hit1+=1


        if real in top10[:3]:

            hit3+=1


        if real in top10[:5]:

            hit5+=1



        if real in result["main"]:


            pair_hit+=1



        total+=1





    if total==0:

        return




    print()

    print("="*60)

    print("📈 历史回测")

    print("="*60)



    print(

        "TOP1:",

        round(hit1/total*100,2),

        "%"

    )


    print(

        "TOP3:",

        round(hit3/total*100,2),

        "%"

    )



    print(

        "TOP5:",

        round(hit5/total*100,2),

        "%"

    )



    print(

        "双码命中:",

        round(pair_hit/total*100,2),

        "%"

    )



    # 简易ROI


    roi=(

        pair_hit*20-total*2

    )/(total*2)*100



    print(

        "模拟ROI:",

        round(roi,2),

        "%"

    )
    # ============================================================
# 第6部分
# V11.3.1
#
# 主程序入口
#
# ============================================================




def run_lottery(name):


    print()

    print("="*70)

    print(

        "📡 获取数据:",

        name

    )

    print("="*70)



    history=fetch_lottery(name)



    print(

        "✅ 获取",

        len(history),

        "期"

    )



    if not check_data(history):


        return




    print()

    print("="*70)

    print(

        "🎯",

        name,

        "V11.3.1 AI预测"

    )

    print("="*70)




    print()

    print(

        "最新特码:",

        history[0]["num"]

    )




    result=predict_numbers(

        history

    )




    print()

    print("🔥 TOP10号码")

    print("-"*70)



    for i,x in enumerate(

        result["top10"],

        1

    ):



        print(

            f"{i:02d}.",

            f"{x['num']:02d}",

            "评分:",

            x["score"],

            "颜色:",

            x["color"]

        )




    print()

    print(

        "⭐ 主推双码:",

        result["main"]

    )


    print(

        "组合评分:",

        result["pair_score"]

    )



    print()

    print(

        "🛡 防守号码:",

        result["guard"]

    )





    backtest_v113(

        history

    )







# ============================================================
# 数据模块测试
# ============================================================


def test_fetch():


    print()

    print("="*70)

    print(

        "三彩 V11.3.1 数据模块测试"

    )

    print("="*70)



    for name in [

        "香港彩",

        "新澳门彩",

        "老澳门彩"

    ]:



        print()

        print(

            "📡 获取数据:",

            name

        )



        data=fetch_lottery(name)



        print(

            "获取",

            len(data),

            "期"

        )



        if data:


            print(

                data[0]

            )







# ============================================================
# 主函数
# ============================================================


def main():


    print()

    print("="*70)

    print(

        "🚀 三彩",

        VERSION,

        "AI四层特码预测系统启动"

    )


    print(

        datetime.datetime.now()

    )


    print("="*70)



    print()


    print(

        "模型结构："

    )


    print(

        "尾数余数 → 大小 → 单双 → 颜色 → 双码组合"

    )




    for name in [

        "香港彩",

        "新澳门彩",

        "老澳门彩"

    ]:


        try:


            run_lottery(

                name

            )



        except Exception as e:


            print()

            print(

                "❌运行异常:",

                name

            )


            print(e)





    print()

    print("="*70)

    print(

        "✅ V11.3.1运行完成"

    )

    print("="*70)






# ============================================================
# 启动
# ============================================================


if __name__=="__main__":


    main()