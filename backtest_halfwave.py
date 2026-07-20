# ============================================================
# 三彩 V11.4 稳定完整版
#
# AI四层特码分析系统
#
# 模块:
# 1. 稳定数据获取
# 2. 数据校验
# 3. 尾数余数分析
# 4. 大小分析
# 5. 单双分析
# 6. 颜色分析
# 7. 动态权重
# 8. 双码组合
# 9. 历史回测
#
# ============================================================


import requests
import re
import json
import time
import math
import datetime
import random
import os
from collections import Counter,defaultdict




# ============================================================
# 版本
# ============================================================


VERSION = "V11.4"




# =========================================================
# V11.5 数据获取模块
# =========================================================

import requests
import time


# ===============================
# API配置
# ===============================

API_URL = "https://marksix6.net/index.php?api=1"


LOTTERY_CONFIG = {

    "香港彩":{
        "type":"hk"
    },

    "新澳门彩":{
        "type":"new"
    },

    "老澳门彩":{
        "type":"old"
    }

}



# ===============================
# 数据获取
# ===============================


def fetch_lottery(name):

    print()
    print("="*70)
    print(f"📡 获取数据: {name}")
    print("="*70)


    if name not in LOTTERY_CONFIG:

        print(
            f"❌ 未知彩种:{name}"
        )

        return []



    try:


        params={

            "type":
            LOTTERY_CONFIG[name]["type"]

        }


        r=requests.get(

            API_URL,

            params=params,

            timeout=15

        )


        r.encoding="utf-8"



        if r.status_code !=200:


            print(
                "❌ API连接失败",
                r.status_code
            )

            return []



        data=r.json()



        # ===========================
        # 兼容不同接口结构
        # ===========================


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


            print(
                "❌ 数据格式错误"
            )

            return []




        records=[]



        for item in data:


            if not isinstance(item,dict):

                continue



            # -----------------------
            # 期号
            # -----------------------

            issue=(

                item.get("qishu")

                or

                item.get("issue")

                or

                item.get("period")

                or

                item.get("expect")

            )



            # -----------------------
            # 特码
            # -----------------------

            number=(

                item.get("tm")

                or

                item.get("special")

                or

                item.get("number")

                or

                item.get("te")

            )



            try:

                number=int(number)

            except:

                continue



            if number<1 or number>49:

                continue



            records.append({

                "issue":str(issue),

                "number":number

            })





        # ===========================
        # 去重
        # ===========================


        new=[]

        seen=set()


        for x in records:


            key=(

                x["issue"],

                x["number"]

            )


            if key not in seen:

                seen.add(key)

                new.append(x)



        records=new



        print(

            f"✅ 获取 {len(records)} 期"

        )



        return records





    except Exception as e:


        print(

            "❌ fetch_lottery错误:",

            e

        )


        return []





# ===============================
# 数据校验
# ===============================


def check_data(data,name):


    print()

    print("🔍 数据校验")


    if not data:


        print(
            "❌ 无数据"
        )

        return False



    print(

        f"数据数量:{len(data)}"

    )



    latest=data[0]


    print(

        "最新期:",

        latest["issue"]

    )


    print(

        "最新特码:",

        latest["number"]

    )



    if 1<=latest["number"]<=49:


        print(
            "✅ 数据正常"
        )

        return True


    else:

        print(
            "❌ 号码异常"
        )

        return False




# ============================================================
# 数据缓存
# ============================================================


CACHE_DIR="cache"



if not os.path.exists(CACHE_DIR):

    os.makedirs(CACHE_DIR)





# ============================================================
# 参数
# ============================================================


MAX_HISTORY = 500



TOP_COUNT = 10



PAIR_COUNT = 2





# ============================================================
# 颜色定义
# ============================================================


RED = {

    1,2,7,8,12,13,18,19,
    23,24,29,30,34,35,
    40,45,46

}


BLUE = {

    3,4,9,10,14,15,20,
    25,26,31,36,37,41,
    42,47,48

}


GREEN = {

    5,6,11,16,17,21,22,
    27,28,32,33,38,39,
    43,44,49

}





# ============================================================
# 获取颜色
# ============================================================


def get_color(num):


    if num in RED:

        return "红"


    elif num in BLUE:

        return "蓝"


    elif num in GREEN:

        return "绿"


    return "未知"





# ============================================================
# 大小
#
# 1-24 小
# 25-49 大
# ============================================================


def get_size(num):


    if num <=24:

        return "小"


    return "大"





# ============================================================
# 单双
# ============================================================


def get_odd_even(num):


    if num % 2:

        return "单"


    return "双"





# ============================================================
# 尾数
# ============================================================


def get_tail(num):


    return num % 10





# ============================================================
# 余数
# ============================================================


def get_mod(num):


    return num % 7





# ============================================================
# 数据标准格式
#
# {
#   issue:"",
#   num:27,
#   color:"绿"
# }
#
# ============================================================


def format_item(issue,num):


    return {


        "issue":str(issue),


        "num":int(num),


        "color":get_color(int(num)),


        "size":get_size(int(num)),


        "odd":get_odd_even(int(num)),


        "tail":get_tail(int(num)),


        "mod":get_mod(int(num))


    }





# ============================================================
# 请求头
# ============================================================


HEADERS={


    "User-Agent":

    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"



}




# ============================================================
# 网络请求
# ============================================================


def http_get(url):


    try:


        r=requests.get(

            url,

            headers=HEADERS,

            timeout=15

        )


        r.encoding="utf-8"


        return r.text



    except Exception as e:


        print(

            "接口请求失败:",

            e

        )


        return ""





# ============================================================
# 缓存保存
# ============================================================


def save_cache(name,data):


    try:


        path=os.path.join(

            CACHE_DIR,

            name+".json"

        )


        with open(

            path,

            "w",

            encoding="utf-8"

        ) as f:


            json.dump(

                data,

                f,

                ensure_ascii=False

            )



    except:


        pass





# ============================================================
# 缓存读取
# ============================================================


def load_cache(name):


    try:


        path=os.path.join(

            CACHE_DIR,

            name+".json"

        )


        if os.path.exists(path):


            with open(

                path,

                encoding="utf-8"

            ) as f:


                return json.load(f)



    except:


        pass



    return []
    # ============================================================
# 第2部分
# V11.4 稳定数据模块
#
# fetch_lottery()
#
# ============================================================




def extract_rows(obj):

    """
    从不同JSON结构提取数据列表
    """



    if isinstance(obj,list):

        return obj



    if isinstance(obj,dict):


        keys=[

            "data",

            "result",

            "list",

            "rows",

            "history",

            "items",

            "records"

        ]



        for k in keys:


            value=obj.get(k)



            if isinstance(value,list):


                return value




            if isinstance(value,dict):


                r=extract_rows(value)


                if r:


                    return r



    return []







def extract_number(item):


    """
    自动提取特码
    """



    if not isinstance(item,dict):


        return None




    keys=[


        "tm",

        "tema",

        "teMa",

        "special",

        "specialNum",

        "special_number",

        "code",

        "num",

        "number",

        "hao",

        "haoma",

        "特码"

    ]




    for k in keys:


        if k in item:


            try:


                value=str(item[k])



                nums=re.findall(

                    r"\d+",

                    value

                )



                if nums:


                    n=int(nums[-1])



                    if 1<=n<=49:


                        return n



            except:


                continue




    return None







def extract_issue(item):


    if not isinstance(item,dict):

        return ""



    keys=[


        "issue",

        "qihao",

        "period",

        "expect",

        "no",

        "qishu",

        "期号"

    ]



    for k in keys:


        if k in item:


            return str(item[k])



    return ""








def parse_lottery_text(text):


    """
    非JSON备用解析
    """



    result=[]




    # 尝试寻找 期号+特码


    pattern=re.findall(

        r'(\d{3,8}).{0,20}?(\d{1,2})',

        text

    )




    for issue,num in pattern:


        n=int(num)



        if 1<=n<=49:


            result.append(

                format_item(

                    issue,

                    n

                )

            )



    return result







def fetch_lottery(name):


    print()


    print(

        "📡 获取数据:",

        name

    )



    url=API_CONFIG.get(name)



    if not url or "你的" in url:


        print(

            "❌ API地址未配置:",

            name

        )


        return load_cache(name)




    data=[]




    try:



        text=http_get(url)



        if not text:


            raise Exception(

                "接口无返回"

            )





        # =========================
        # JSON解析
        # =========================


        try:


            obj=json.loads(text)



            rows=extract_rows(obj)



        except:


            rows=[]





        # =========================
        # 字典解析
        # =========================


        for item in rows:



            num=extract_number(item)



            if num:


                issue=extract_issue(item)



                data.append(

                    format_item(

                        issue,

                        num

                    )

                )





        # =========================
        # 文本备用
        # =========================


        if len(data)==0:


            data=parse_lottery_text(text)





        # =========================
        # 去重
        # =========================


        clean=[]


        seen=set()



        for x in data:



            key=(

                x["issue"],

                x["num"]

            )



            if key not in seen:


                clean.append(x)


                seen.add(key)





        data=clean[:MAX_HISTORY]





        # =========================
        # 成功保存缓存
        # =========================


        if len(data)>0:


            save_cache(

                name,

                data

            )



        else:


            print(

                "⚠ 当前接口解析0条"

            )


            cache=load_cache(name)



            if cache:


                print(

                    "🔄 使用缓存数据",

                    len(cache),

                    "期"

                )


                data=cache





    except Exception as e:



        print(

            "❌ 数据获取异常:",

            e

        )


        data=load_cache(name)





    print(

        "✅ 获取",

        len(data),

        "期"

    )



    return data
    # ============================================================
# 第3部分
# V11.4 数据校验 + 基础统计模块
#
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





    count=len(history)



    print(

        "数据数量:",

        count

    )



    if count < 20:


        print(

            "⚠ 数据不足20期"

        )



    # 检查号码范围


    error=[]



    for x in history:



        n=x.get(

            "num",

            0

        )



        if n<1 or n>49:


            error.append(x)





    if error:


        print(

            "❌ 存在错误号码",

            error

        )


        return False





    print(

        "最新期:",

        history[0].get(

            "issue",

            ""

        )

    )



    print(

        "最新特码:",

        history[0]["num"]

    )



    print(

        "颜色:",

        history[0]["color"]

    )



    print(

        "✅ 数据正常"

    )



    return True








# ============================================================
# 通用统计
# ============================================================



def count_feature(history,key):


    counter=Counter()



    for x in history:


        counter[

            x[key]

        ]+=1




    return counter






# ============================================================
# 尾数统计
# ============================================================



def tail_statistics(history):


    result=Counter()



    for x in history:



        result[

            x["tail"]

        ]+=1



    return result







# ============================================================
# 余数统计
# ============================================================



def mod_statistics(history):


    result=Counter()



    for x in history:



        result[

            x["mod"]

        ]+=1



    return result








# ============================================================
# 大小统计
# ============================================================



def size_statistics(history):


    return count_feature(

        history,

        "size"

    )








# ============================================================
# 单双统计
# ============================================================



def odd_statistics(history):


    return count_feature(

        history,

        "odd"

    )









# ============================================================
# 颜色统计
# ============================================================



def color_statistics(history):


    return count_feature(

        history,

        "color"

    )









# ============================================================
# 最近N期数据
# ============================================================



def recent(history,n=30):


    return history[:n]








# ============================================================
# 遗漏计算
# ============================================================



def calculate_missing(history):


    missing={

        i:0

        for i in range(1,50)

    }



    appeared=set()



    for x in history:


        appeared.add(

            x["num"]

        )



    for n in range(1,50):


        count=0



        for x in history:


            if x["num"]==n:


                break



            count+=1



        missing[n]=count




    return missing








# ============================================================
# 热冷分析
# ============================================================



def hot_cold(history):


    counter=Counter()



    for x in history:


        counter[

            x["num"]

        ]+=1




    hot=[

        x[0]

        for x in counter.most_common(10)

    ]



    cold=sorted(

        counter,

        key=lambda x:counter[x]

    )[:10]



    return {


        "hot":hot,


        "cold":cold


    }





# ============================================================
# 特征生成
# ============================================================



def build_features(history):


    return {


        "tail":

        tail_statistics(history),



        "mod":

        mod_statistics(history),



        "size":

        size_statistics(history),



        "odd":

        odd_statistics(history),



        "color":

        color_statistics(history),



        "missing":

        calculate_missing(history),



        "hotcold":

        hot_cold(history)


    }
    # ============================================================
# 第4部分
# V11.4 四层AI评分模型
#
# 尾数 + 余数
# 大小
# 单双
# 颜色
#
# ============================================================




# ============================================================
# 模型权重
# ============================================================


WEIGHTS={


    "tail":0.25,


    "mod":0.15,


    "size":0.15,


    "odd":0.15,


    "color":0.15,


    "trend":0.10,


    "missing":0.05



}







# ============================================================
# 归一化
# ============================================================


def normalize(value,max_value):


    if max_value==0:


        return 0



    return round(

        value/max_value*100,

        2

    )







# ============================================================
# 尾数评分
# ============================================================



def tail_score(num,history):


    stat=tail_statistics(

        history

    )


    tail=num%10



    value=stat[tail]



    return normalize(

        value,

        max(stat.values()) if stat else 1

    )








# ============================================================
# 余数评分
# ============================================================



def mod_score(num,history):


    stat=mod_statistics(

        history

    )


    mod=num%7



    value=stat[mod]



    return normalize(

        value,

        max(stat.values()) if stat else 1

    )








# ============================================================
# 大小评分
# ============================================================



def size_score(num,history):


    stat=size_statistics(

        history

    )



    size=get_size(num)



    return normalize(

        stat[size],

        max(stat.values())

        if stat else 1

    )








# ============================================================
# 单双评分
# ============================================================



def odd_score(num,history):


    stat=odd_statistics(

        history

    )



    odd=get_odd_even(num)



    return normalize(

        stat[odd],

        max(stat.values())

        if stat else 1

    )








# ============================================================
# 颜色评分
# ============================================================



def color_score(num,history):


    stat=color_statistics(

        history

    )


    color=get_color(num)



    return normalize(

        stat[color],

        max(stat.values())

        if stat else 1

    )








# ============================================================
# 遗漏评分
# ============================================================



def missing_score(num,history):


    missing=calculate_missing(

        history

    )


    m=missing[num]



    # 避免极端遗漏


    if m>=20:


        return 100



    if m>=10:


        return 80



    if m>=5:


        return 60



    return 40







# ============================================================
# 趋势评分
# ============================================================



def trend_score(num,history):


    recent_data=history[:30]



    count=0



    for x in recent_data:


        if x["num"]==num:


            count+=1



    return normalize(

        count,

        max(1,len(recent_data))

    )








# ============================================================
# 单号码综合评分
# ============================================================



def number_score(num,history):


    scores={


        "tail":

        tail_score(

            num,

            history

        ),



        "mod":

        mod_score(

            num,

            history

        ),



        "size":

        size_score(

            num,

            history

        ),



        "odd":

        odd_score(

            num,

            history

        ),



        "color":

        color_score(

            num,

            history

        ),



        "trend":

        trend_score(

            num,

            history

        ),



        "missing":

        missing_score(

            num,

            history

        )


    }




    total=0



    for k,v in scores.items():


        total += (

            v*

            WEIGHTS[k]

        )



    return {


        "num":

        num,


        "score":

        round(total,2),



        "detail":

        scores,



        "color":

        get_color(num),



        "size":

        get_size(num),



        "odd":

        get_odd_even(num)



    }








# ============================================================
# 全号码评分
# ============================================================



def score_all(history):


    result=[]



    for num in range(1,50):


        result.append(

            number_score(

                num,

                history

            )

        )



    result.sort(

        key=lambda x:

        x["score"],

        reverse=True

    )



    return result








# ============================================================
# TOP号码
# ============================================================



def get_top_numbers(history,count=10):


    scores=score_all(

        history

    )



    return scores[:count]
    # ============================================================
# 第5部分
# V11.4 动态组合模块
#
# ============================================================



from itertools import combinations





# ============================================================
# TOP号码池
# ============================================================


def get_candidate_pool(history,limit=15):


    scores=score_all(

        history

    )


    return scores[:limit]








# ============================================================
# 属性差异评分
# ============================================================



def attribute_balance(a,b):


    score=0



    # 颜色不同加分


    if a["color"] != b["color"]:


        score += 20



    else:


        score += 5





    # 大小不同


    if a["size"] != b["size"]:


        score += 15



    else:


        score += 8






    # 单双不同


    if a["odd"] != b["odd"]:


        score += 15



    else:


        score += 8



    return score







# ============================================================
# 双码组合评分
# ============================================================



def pair_score(a,b):


    score=0



    # 基础分


    score += a["score"]


    score += b["score"]





    # 平衡奖励


    score += attribute_balance(

        a,

        b

    )




    # 号码距离


    distance=abs(

        a["num"]

        -

        b["num"]

    )



    if distance>=10:


        score += 10



    elif distance>=5:


        score += 5



    else:


        score -=5





    return round(

        score,

        2

    )








# ============================================================
# 生成所有双码
# ============================================================



def generate_pairs(history):


    pool=get_candidate_pool(

        history,

        20

    )



    pairs=[]



    for a,b in combinations(

        pool,

        2

    ):


        s=pair_score(

            a,

            b

        )



        pairs.append(

            {


                "pair":

                (

                    a["num"],

                    b["num"]

                ),



                "score":

                s,



                "a":

                a,



                "b":

                b



            }

        )



    pairs.sort(

        key=lambda x:

        x["score"],

        reverse=True

    )



    return pairs








# ============================================================
# 主推双码
# ============================================================



def get_best_pair(history):


    pairs=generate_pairs(

        history

    )



    if not pairs:


        return None



    return pairs[0]








# ============================================================
# 防守号码
# ============================================================



def get_defense_numbers(history,count=3):


    scores=score_all(

        history

    )


    result=[]



    for x in scores:


        if x["num"] not in result:


            result.append(

                x["num"]

            )



        if len(result)>=count:


            break




    return result








# ============================================================
# 颜色分布
# ============================================================



def color_distribution(nums):


    c=Counter()



    for n in nums:


        c[

            get_color(n)

        ]+=1



    return dict(c)








# ============================================================
# 输出TOP10
# ============================================================



def print_top(scores):


    print()


    print(

        "🔥 TOP10号码"

    )


    print("-"*70)



    for i,x in enumerate(

        scores[:10],

        1

    ):


        d=x["detail"]



        print(

            f"{i:02d}. "

            f"{x['num']:02d} "

            f"总分:{x['score']} "

            f"尾:{d['tail']} "

            f"余:{d['mod']} "

            f"大小:{d['size']} "

            f"单双:{d['odd']} "

            f"颜色:{d['color']}"

        )








# ============================================================
# 打印组合
# ============================================================



def print_pair(pair):


    if not pair:


        print(

            "无组合"

        )


        return




    print()


    print(

        "⭐ 主推双码:",

        pair["pair"]

    )


    print(

        "组合评分:",

        pair["score"]

    )
    # ============================================================
# 第6部分
# V11.4 历史回测模块
#
# ============================================================





# ============================================================
# 单期预测
# ============================================================


def predict_one(history):


    scores=score_all(

        history

    )



    top10=scores[:10]



    pair=get_best_pair(

        history

    )



    return {


        "top":

        [

            x["num"]

            for x in top10

        ],



        "pair":

        pair["pair"]

        if pair

        else None



    }









# ============================================================
# TOP命中统计
# ============================================================



def backtest(history):


    if len(history)<50:


        return {}





    top1=0

    top3=0

    top5=0


    pair_hit=0



    total=0




    # 从旧到新滚动


    for i in range(

        len(history)-30,

        0,

        -1

    ):



        train=history[i:]



        real=history[i-1]["num"]





        pred=predict_one(

            train

        )



        nums=pred["top"]



        pair=pred["pair"]






        if len(nums)>0 and real==nums[0]:


            top1+=1



        if real in nums[:3]:


            top3+=1



        if real in nums[:5]:


            top5+=1





        if pair and real in pair:


            pair_hit+=1




        total+=1






    if total==0:


        return {}





    return {



        "TOP1":

        round(

            top1/total*100,

            2

        ),



        "TOP3":

        round(

            top3/total*100,

            2

        ),



        "TOP5":

        round(

            top5/total*100,

            2

        ),



        "PAIR":

        round(

            pair_hit/total*100,

            2

        ),



        "TOTAL":

        total



    }









# ============================================================
# 模拟资金回测
# ============================================================



def roi_test(history):


    balance=0



    bet=100



    win=0

    lose=0



    for i in range(

        len(history)-50,

        0,

        -1

    ):



        train=history[i:]



        real=history[i-1]["num"]




        pred=predict_one(

            train

        )



        pair=pred["pair"]





        balance-=bet





        if pair and real in pair:


            # 模拟赔率

            balance += bet*12


            win+=1



        else:


            lose+=1





    return {


        "profit":

        balance,


        "win":

        win,


        "lose":

        lose



    }









# ============================================================
# 输出回测
# ============================================================



def print_backtest(history):


    print()


    print(

        "📈 历史回测"

    )



    result=backtest(

        history

    )



    if not result:


        print(

            "数据不足"

        )


        return





    print(

        "TOP1:",

        result["TOP1"],

        "%"

    )



    print(

        "TOP3:",

        result["TOP3"],

        "%"

    )



    print(

        "TOP5:",

        result["TOP5"],

        "%"

    )



    print(

        "双码命中:",

        result["PAIR"],

        "%"

    )





    roi=roi_test(

        history

    )



    print(

        "模拟利润:",

        roi["profit"]

    )


    print(

        "胜:",

        roi["win"],

        "负:",

        roi["lose"]

    )
    # ============================================================
# 第7部分
# V11.4 主运行模块
#
# ============================================================





# ============================================================
# 单个彩种分析
# ============================================================



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





    if not history:


        print(

            "❌ 数据为空:",

            name

        )


        return





    if not check_data(

        history

    ):


        print(

            "❌ 数据校验失败"

        )


        return





    print()


    print("="*70)

    print(

        "🎯",

        name,

        VERSION,

        "AI预测"

    )

    print("="*70)





    print()


    print(

        "最新特码:",

        history[0]["num"]

    )





    scores=get_top_numbers(

        history,

        TOP_COUNT

    )





    print_top(

        scores

    )





    best=get_best_pair(

        history

    )



    print_pair(

        best

    )





    defense=get_defense_numbers(

        history,

        3

    )





    print()


    print(

        "🛡 防守号码:",

        defense

    )






    print_backtest(

        history

    )









# ============================================================
# 数据测试
# ============================================================



def test_fetch():


    print("="*70)

    print(

        "三彩 V11.4 数据模块测试"

    )

    print("="*70)





    for name in API_CONFIG.keys():


        data=fetch_lottery(

            name

        )


        print(

            name,

            ":",

            len(data),

            "期"

        )



        if data:


            print(

                "最新特码:",

                data[0]["num"]

            )



        else:


            print(

                "无数据"

            )







# ============================================================
# 主入口
# ============================================================



def main():


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



        analyze_lottery(

            name

        )







    print()


    print("="*70)

    print(

        "✅",

        VERSION,

        "运行完成"

    )

    print("="*70)









if __name__=="__main__":


    main()
    