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
7. 真实盈利回测（含本金）

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
# V8.16 精确投注回测模块（含本金）
# =====================================================

class ExactBetBackTest:
    def __init__(self, rows, odds_config=None, bet_amount=50):
        self.rows = rows
        self.bet_amount = bet_amount
        self.odds = odds_config or {
            "红": 5.82, "蓝": 5.82, "绿": 5.82,
            "大": 6.6, "小": 4.7,
            "单": 5.82, "双": 5.16,
            "红大单": 9.45, "红大双": 11.82,
            "红小单": 9.45, "红小双": 9.45,
            "蓝大单": 9.45, "蓝大双": 11.82,
            "蓝小单": 15.76, "蓝小双": 11.82,
            "绿大单": 11.82, "绿大双": 11.82,
            "绿小单": 11.82, "绿小双": 15.76,
        }
    
    def simulate_mode(self, mode="TOP1", test_days=10):
        """
        模拟下注模式
        mode: 'TOP1', 'TOP2', 'TOP3'
        """
        results = []
        total_bet = 0
        total_return = 0
        total_profit = 0
        hit_count = 0
        balance = 0
        balance_history = []
        
        start_idx = min(test_days, len(self.rows) - 1)
        
        for i in range(start_idx, 0, -1):
            history = self.rows[i:]
            actual = self.rows[i - 1]
            
            model = FusionV816(history)
            pred = model.predict()
            
            # 根据模式选择下注
            candidates = pred["candidates"]
            bet_list = []
            
            if mode == "TOP1" and candidates:
                bet_list = [candidates[0]["halfhalf"]]
            elif mode == "TOP2":
                bet_list = [c["halfhalf"] for c in candidates[:2]]
            elif mode == "TOP3":
                bet_list = [c["halfhalf"] for c in candidates[:3]]
            else:
                bet_list = []
            
            # 计算投注
            bet_count = len(bet_list)
            if bet_count == 0:
                continue
            
            bet = self.bet_amount * bet_count
            total_bet += bet
            
            # 判断中奖
            hit = False
            win_amount = 0
            hit_hh = None
            
            for hh in bet_list:
                if hh == actual["halfhalf"]:
                    hit = True
                    hit_hh = hh
                    odds = self.odds.get(hh, 0)
                    win_amount = self.bet_amount * odds  # 含本金
                    break
            
            if hit:
                hit_count += 1
                total_return += win_amount
            else:
                win_amount = 0
            
            profit = win_amount - bet
            total_profit += profit
            balance += profit
            balance_history.append(balance)
            
            results.append({
                "issue": actual["issue"],
                "actual": actual["halfhalf"],
                "bet_list": bet_list,
                "bet_count": bet_count,
                "bet_amount": bet,
                "win_amount": win_amount,
                "profit": profit,
                "balance": balance,
                "hit": hit,
                "hit_hh": hit_hh
            })
        
        roi = (total_profit / total_bet * 100) if total_bet > 0 else 0
        
        return {
            "mode": mode,
            "results": results,
            "total_bet": total_bet,
            "total_return": total_return,
            "total_profit": total_profit,
            "hit_count": hit_count,
            "total_periods": len(results),
            "hit_rate": hit_count / len(results) * 100 if results else 0,
            "roi": roi,
            "balance_history": balance_history
        }
    
    def print_report(self, mode="TOP1", test_days=10):
        """打印详细报告"""
        data = self.simulate_mode(mode, test_days)
        
        print(f"\n{'='*60}")
        print(f"📊 {mode} 下注模式详细回测 (含本金)")
        print(f"  每注金额: {self.bet_amount} 元")
        print(f"  赔率计算: 中奖金额 = 投注 × 赔率")
        print(f"{'='*60}")
        
        # 每期明细
        print(f"\n📋 最近{test_days}期明细:")
        print(f"{'期号':<12} {'实际开奖':<12} {'下注':<25} {'投注':<8} {'中奖':<10} {'盈亏':<10} {'余额':<10}")
        print(f"{'-'*85}")
        
        for r in data["results"][:test_days]:
            bet_str = ",".join(r["bet_list"][:3])
            if len(r["bet_list"]) > 3:
                bet_str += f"+{len(r['bet_list'])-3}"
            print(f"{r['issue']:<12} {r['actual']:<12} {bet_str:<25} "
                  f"{r['bet_amount']:<8.0f} {r['win_amount']:<10.2f} "
                  f"{r['profit']:<+10.2f} {r['balance']:<10.2f}")
        
        print(f"{'-'*85}")
        
        # 汇总统计
        print(f"\n📊 汇总统计:")
        print(f"  回测期数: {data['total_periods']} 期")
        print(f"  命中次数: {data['hit_count']} 次")
        print(f"  命中率: {data['hit_rate']:.2f}%")
        print(f"  总投注: {data['total_bet']:.2f} 元")
        print(f"  总回报: {data['total_return']:.2f} 元")
        print(f"  净盈利: {data['total_profit']:+.2f} 元")
        print(f"  ROI: {data['roi']:+.2f}%")
        
        # 盈亏柱状图
        if data["results"]:
            print(f"\n📈 最近{min(test_days, len(data['results']))}期盈亏走势:")
            max_profit = max([abs(r["profit"]) for r in data["results"][:test_days]]) or 1
            for i, r in enumerate(data["results"][:test_days]):
                bar_len = int((r["profit"] / max_profit) * 20)
                if r["profit"] > 0:
                    bar = "█" * min(bar_len, 20) + "░" * (20 - min(bar_len, 20))
                    print(f"  第{i+1:2d}期: {bar} +{r['profit']:6.2f}元")
                elif r["profit"] < 0:
                    bar = "█" * min(abs(bar_len), 20) + "░" * (20 - min(abs(bar_len), 20))
                    print(f"  第{i+1:2d}期: {bar} {r['profit']:6.2f}元")
                else:
                    print(f"  第{i+1:2d}期: {'░░░░░░░░░░░░░░░░░░░░'} {r['profit']:6.2f}元")
        
        print(f"{'='*60}")
        
        # 建议
        print(f"\n💡 建议:")
        if data["roi"] > 20:
            print(f"  ✅ {mode}模式表现优异 (ROI {data['roi']:+.2f}%)")
            print(f"     最近{data['total_periods']}期盈利 {data['total_profit']:+.2f} 元")
        elif data["roi"] > 0:
            print(f"  ⚠️  {mode}模式略有盈利 (ROI {data['roi']:+.2f}%)")
            print(f"     建议继续观察或调整策略")
        else:
            print(f"  ❌ {mode}模式亏损 (ROI {data['roi']:+.2f}%)")
            print(f"     最近{data['total_periods']}期亏损 {data['total_profit']:+.2f} 元")
            print(f"     建议考虑其他模式或停止下注")
        
        return data
    
    def compare_modes(self, test_days=10):
        """对比TOP1、TOP2、TOP3三种模式"""
        modes = ["TOP1", "TOP2", "TOP3"]
        results = {}
        
        print(f"\n{'='*60}")
        print(f"🔄 三种下注模式对比 (最近{test_days}期)")
        print(f"{'='*60}")
        
        for mode in modes:
            results[mode] = self.simulate_mode(mode, test_days)
        
        print(f"\n{'模式':<10} {'总投注':<12} {'总回报':<12} {'净盈利':<12} {'ROI':<12} {'命中率':<12} {'命中次数':<10}")
        print(f"{'-'*80}")
        
        for mode, data in results.items():
            print(f"{mode:<10} {data['total_bet']:<12.2f} {data['total_return']:<12.2f} "
                  f"{data['total_profit']:<+12.2f} {data['roi']:<+12.2f}% "
                  f"{data['hit_rate']:<12.2f}% {data['hit_count']:<10}")
        
        print(f"{'='*60}")
        
        # 找出最优
        best_mode = max(results, key=lambda x: results[x]["roi"])
        best_roi = results[best_mode]["roi"]
        
        print(f"\n🏆 最优模式: {best_mode} (ROI: {best_roi:+.2f}%)")
        
        if results[best_mode]["roi"] > 0:
            print(f"   ✅ 建议使用 {best_mode} 模式")
        else:
            print(f"   ⚠️  所有模式均亏损，建议暂停")
        
        return results, best_mode


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


    # ===== 新增：精确投注回测 =====
    print()
    print("=" * 60)
    print("💰 真实盈利回测 (含本金)")
    print("=" * 60)
    
    exact_test = ExactBetBackTest(rows, bet_amount=50)
    
    # 对比三种模式
    exact_test.compare_modes(test_days=10)
    
    # 详细显示TOP1模式
    print()
    exact_test.print_report(mode="TOP1", test_days=10)


if __name__=="__main__":

    main()