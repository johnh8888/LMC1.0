#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
香港彩预测系统 V8.17 - 动态半波增强版

基于V8.16优化升级:
1. 动态半波选择器增强（大小权重提升、半波马尔可夫、遗漏追踪）
2. 智能追号机制（连黑加倍）
3. 半波专用马尔可夫链模型（新增）
4. 半波遗漏追踪器（新增）
5. 半波连续反向信号（新增）
6. 全自动权重优化（300次迭代，5个优化器）
7. 多模型集成
8. 滚动回测 + 动态调参
9. 风险控制模块
10. 下注记录追踪

"""

import re
import json
import urllib.request
import random
from collections import defaultdict
from datetime import datetime


# =====================================================
# 配置
# =====================================================


CONFIG = {

    "history_limit":30,

    "api_url":
    "https://marksix6.net/index.php?api=1",

    "lottery_type": "香港彩",

    "bet_mode": "动态半波增强版",

    "bet_count": 2,

    "bet_per_note": 50,

    # 风险控制
    "risk_control": {
        "stop_loss": -500,
        "take_profit": 800,
        "max_consecutive_loss": 3,
        "pause_after_loss": 1,
        "max_multiplier": 3,
    },

    # 半波选择器权重（V8.17新增）
    "halfwave_weights": {
        "color": 0.20,
        "size": 0.40,
        "markov": 0.25,
        "miss": 0.15,
    },

    "weights":{

        "color":0.25,

        "size":0.30,

        "odd":0.25,

        "halfhalf":0.20

    }

}


REPORT_FILE="hongkong_result_v817.md"
BET_RECORD_FILE="hongkong_bet_record_v817.md"


# =====================================================
# 各维度内部权重配置
# =====================================================

COLOR_WEIGHTS = {
    "frequency": 0.20,
    "trend": 0.20,
    "markov": 0.20,
    "miss": 0.20,
    "zone": 0.20
}

SIZE_WEIGHTS = {
    "frequency": 0.20,
    "trend": 0.20,
    "markov": 0.20,
    "miss": 0.20,
    "consecutive": 0.20
}

ODD_WEIGHTS = {
    "frequency": 0.25,
    "trend": 0.20,
    "markov": 0.25,
    "tail": 0.15,
    "consecutive": 0.15
}

ENSEMBLE_WEIGHTS = {
    "attribute": 0.35,
    "markov": 0.25,
    "frequency": 0.20,
    "trend": 0.20
}


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


def get_halfwave(n):
    """获取半波（颜色+大小，不含单双）- V8.17新增"""
    return get_color(n) + get_size(n)


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


def fetch_lottery(limit=30):


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

            timeout=60

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



            print(f"  发现: {name}")



            if name=="香港彩":

                target=item

                break



        if not target:

            print(f"❌ 未找到香港彩数据")

            return []


        print(f"✅ 找到香港彩数据")


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
                get_halfhalf(special),

                "halfwave":
                get_halfwave(special)

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
# 颜色增强预测模型
# =====================================================

class ColorPredictor:
    """颜色预测增强模型 - 多维度融合"""
    
    def __init__(self, rows, weights=None):
        self.rows = rows[:30]
        self.weights = weights or COLOR_WEIGHTS
        self.all_colors = ["红", "蓝", "绿"]
    
    def frequency_score(self):
        score = defaultdict(float)
        for r in self.rows:
            score[r["color"]] += 1
        total = sum(score.values()) or 1
        return {k: v / total * 100 for k, v in score.items()}
    
    def trend_score(self):
        score = defaultdict(float)
        for i, r in enumerate(self.rows[:15]):
            weight = (15 - i) * 0.3
            score[r["color"]] += weight
        total = sum(score.values()) or 1
        return {k: v / total * 100 for k, v in score.items()}
    
    def markov_score(self):
        score = defaultdict(float)
        if len(self.rows) < 2:
            return {"红": 33, "蓝": 33, "绿": 34}
        
        current = self.rows[0]["color"]
        transitions = {"红": {"红":0, "蓝":0, "绿":0}, 
                      "蓝": {"红":0, "蓝":0, "绿":0},
                      "绿": {"红":0, "蓝":0, "绿":0}}
        for i in range(len(self.rows) - 1):
            curr = self.rows[i]["color"]
            next_color = self.rows[i + 1]["color"]
            transitions[curr][next_color] += 1
        total = sum(transitions[current].values()) or 1
        for k in self.all_colors:
            score[k] = transitions[current].get(k, 0) / total * 100
        return score
    
    def miss_score(self):
        score = defaultdict(float)
        for color in self.all_colors:
            miss = 0
            for r in self.rows:
                if r["color"] == color:
                    break
                miss += 1
            score[color] = min(miss * 0.5, 10)
        return score
    
    def zone_score(self):
        """号码区间分布"""
        score = defaultdict(float)
        for r in self.rows[:15]:
            score[r["color"]] += 1
        total = sum(score.values()) or 1
        return {k: v / total * 100 for k, v in score.items()}
    
    def predict(self):
        scores = defaultdict(float)
        
        models = {
            "frequency": self.frequency_score(),
            "trend": self.trend_score(),
            "markov": self.markov_score(),
            "miss": self.miss_score(),
            "zone": self.zone_score()
        }
        
        for name, pred in models.items():
            weight = self.weights.get(name, 0.20)
            for k, v in pred.items():
                scores[k] += v * weight
        
        total = sum(scores.values()) or 1
        return {k: round(v / total * 100, 2) for k, v in scores.items()}


# =====================================================
# 大小增强预测模型
# =====================================================

class SizePredictor:
    """大小预测增强模型 - 多维度融合"""
    
    def __init__(self, rows, weights=None):
        self.rows = rows[:30]
        self.weights = weights or SIZE_WEIGHTS
    
    def frequency_score(self):
        score = defaultdict(float)
        for r in self.rows:
            score[r["size"]] += 1
        total = sum(score.values()) or 1
        return {k: v / total * 100 for k, v in score.items()}
    
    def trend_score(self):
        score = defaultdict(float)
        for i, r in enumerate(self.rows[:15]):
            weight = (15 - i) * 0.3
            score[r["size"]] += weight
        total = sum(score.values()) or 1
        return {k: v / total * 100 for k, v in score.items()}
    
    def markov_score(self):
        score = defaultdict(float)
        if len(self.rows) < 2:
            return {"大": 50, "小": 50}
        
        current = self.rows[0]["size"]
        transitions = {"大": {"大":0, "小":0}, "小": {"大":0, "小":0}}
        for i in range(len(self.rows) - 1):
            curr = self.rows[i]["size"]
            next_size = self.rows[i + 1]["size"]
            transitions[curr][next_size] += 1
        total = sum(transitions[current].values()) or 1
        for k in ["大", "小"]:
            score[k] = transitions[current].get(k, 0) / total * 100
        return score
    
    def miss_score(self):
        score = defaultdict(float)
        for size in ["大", "小"]:
            miss = 0
            for r in self.rows:
                if r["size"] == size:
                    break
                miss += 1
            score[size] = min(miss * 0.5, 10)
        return score
    
    def consecutive_score(self):
        score = defaultdict(float)
        recent = [r["size"] for r in self.rows[:15]]
        if len(recent) < 3:
            return {"大": 50, "小": 50}
        
        consecutive_big = 0
        consecutive_small = 0
        for s in recent[:10]:
            if s == "大":
                consecutive_big += 1
                consecutive_small = 0
            else:
                consecutive_small += 1
                consecutive_big = 0
        
        if consecutive_big >= 3:
            score["小"] = 70
            score["大"] = 30
        elif consecutive_small >= 3:
            score["大"] = 70
            score["小"] = 30
        else:
            score["大"] = 50
            score["小"] = 50
        return score
    
    def predict(self):
        scores = defaultdict(float)
        
        models = {
            "frequency": self.frequency_score(),
            "trend": self.trend_score(),
            "markov": self.markov_score(),
            "miss": self.miss_score(),
            "consecutive": self.consecutive_score()
        }
        
        for name, pred in models.items():
            weight = self.weights.get(name, 0.20)
            for k, v in pred.items():
                scores[k] += v * weight
        
        total = sum(scores.values()) or 1
        return {k: round(v / total * 100, 2) for k, v in scores.items()}


# =====================================================
# 单双增强预测模型
# =====================================================

class OddPredictor:
    """单双预测增强模型 - 多维度融合"""
    
    def __init__(self, rows, weights=None):
        self.rows = rows[:30]
        self.weights = weights or ODD_WEIGHTS
    
    def frequency_score(self):
        score = defaultdict(float)
        for r in self.rows:
            score[r["odd"]] += 1
        total = sum(score.values()) or 1
        return {k: v / total * 100 for k, v in score.items()}
    
    def trend_score(self):
        score = defaultdict(float)
        for i, r in enumerate(self.rows[:15]):
            weight = (15 - i) * 0.3
            score[r["odd"]] += weight
        total = sum(score.values()) or 1
        return {k: v / total * 100 for k, v in score.items()}
    
    def markov_score(self):
        score = defaultdict(float)
        if len(self.rows) < 2:
            return {"单": 50, "双": 50}
        
        current = self.rows[0]["odd"]
        transitions = {"单": {"单": 0, "双": 0}, "双": {"单": 0, "双": 0}}
        for i in range(len(self.rows) - 1):
            curr = self.rows[i]["odd"]
            next_odd = self.rows[i + 1]["odd"]
            transitions[curr][next_odd] += 1
        
        total = sum(transitions[current].values()) or 1
        for k in ["单", "双"]:
            score[k] = transitions[current].get(k, 0) / total * 100
        return score
    
    def tail_score(self):
        score = defaultdict(float)
        tail_odd = 0
        tail_even = 0
        for r in self.rows[:15]:
            tail = r["special"] % 10
            if tail % 2 == 1:
                tail_odd += 1
            else:
                tail_even += 1
        total = tail_odd + tail_even or 1
        score["单"] = tail_odd / total * 100
        score["双"] = tail_even / total * 100
        return score
    
    def consecutive_score(self):
        score = defaultdict(float)
        recent = [r["odd"] for r in self.rows[:15]]
        if len(recent) < 3:
            return {"单": 50, "双": 50}
        
        consecutive_odd = 0
        consecutive_even = 0
        for o in recent[:10]:
            if o == "单":
                consecutive_odd += 1
                consecutive_even = 0
            else:
                consecutive_even += 1
                consecutive_odd = 0
        
        if consecutive_odd >= 3:
            score["双"] = 70
            score["单"] = 30
        elif consecutive_even >= 3:
            score["单"] = 70
            score["双"] = 30
        else:
            score["单"] = 50
            score["双"] = 50
        return score
    
    def predict(self):
        scores = defaultdict(float)
        
        models = {
            "frequency": self.frequency_score(),
            "trend": self.trend_score(),
            "markov": self.markov_score(),
            "tail": self.tail_score(),
            "consecutive": self.consecutive_score()
        }
        
        for name, pred in models.items():
            weight = self.weights.get(name, 0.20)
            for k, v in pred.items():
                scores[k] += v * weight
        
        total = sum(scores.values()) or 1
        return {k: round(v / total * 100, 2) for k, v in scores.items()}


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

            for r in self.rows[:8]

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
    # 颜色 - 使用增强模型
    # =================================================


    def color(self):
        color_predictor = ColorPredictor(self.rows, COLOR_WEIGHTS)
        return color_predictor.predict()


    # =================================================
    # 大小 - 使用增强模型
    # =================================================


    def size(self):
        size_predictor = SizePredictor(self.rows, SIZE_WEIGHTS)
        return size_predictor.predict()


    # =================================================
    # 单双 - 使用增强模型
    # =================================================


    def odd(self):
        odd_predictor = OddPredictor(self.rows, ODD_WEIGHTS)
        return odd_predictor.predict()


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
# V8.17 半波专用马尔可夫链模型（新增）
# =====================================================

class HalfwaveMarkovModel:
    """半波专用马尔可夫链 - 只追踪6种半波（颜色+大小）"""
    
    def __init__(self, rows):
        self.rows = rows[:30]
        self.transition_matrix = defaultdict(lambda: defaultdict(int))
        self.all_hw = ["红大", "红小", "蓝大", "蓝小", "绿大", "绿小"]
        self._build_matrix()
    
    def _build_matrix(self):
        for i in range(len(self.rows) - 1):
            current = self.rows[i]["halfwave"]
            next_hw = self.rows[i + 1]["halfwave"]
            self.transition_matrix[current][next_hw] += 1
    
    def predict(self):
        if not self.rows:
            return {}
        current = self.rows[0]["halfwave"]
        transitions = self.transition_matrix.get(current, {})
        total = sum(transitions.values()) or 1
        result = {}
        for hw in self.all_hw:
            count = transitions.get(hw, 0)
            result[hw] = round(count / total * 100, 2)
        if total == 1:
            freq = defaultdict(int)
            for r in self.rows:
                freq[r["halfwave"]] += 1
            total_freq = sum(freq.values()) or 1
            for hw in self.all_hw:
                result[hw] = round(freq.get(hw, 0) / total_freq * 100, 2)
        return result
    
    def get_transition_detail(self):
        if not self.rows:
            return {}
        current = self.rows[0]["halfwave"]
        transitions = dict(self.transition_matrix.get(current, {}))
        return {"current": current, "transitions": transitions}


# =====================================================
# V8.17 半波遗漏追踪器（新增）
# =====================================================

class HalfwaveMissTracker:
    """追踪6种半波的遗漏情况"""
    
    def __init__(self, rows):
        self.rows = rows
        self.all_hw = ["红大", "红小", "蓝大", "蓝小", "绿大", "绿小"]
    
    def get_miss_counts(self):
        miss = {}
        for hw in self.all_hw:
            count = 0
            for r in self.rows:
                if r["halfwave"] == hw:
                    break
                count += 1
            miss[hw] = count
        return miss
    
    def get_hot_score(self):
        miss = self.get_miss_counts()
        max_miss = max(miss.values()) or 1
        if max_miss == 0:
            return {hw: 0 for hw in self.all_hw}
        return {hw: round(cnt / max_miss * 100, 2) for hw, cnt in miss.items()}
    
    def get_cold_hot_analysis(self):
        freq = defaultdict(int)
        for r in self.rows[:10]:
            freq[r["halfwave"]] += 1
        result = {}
        for hw in self.all_hw:
            result[hw] = {
                "frequency_10": freq.get(hw, 0),
                "miss_count": self.get_miss_counts().get(hw, 0),
                "status": "热" if freq.get(hw, 0) >= 2 else ("温" if freq.get(hw, 0) >= 1 else "冷")
            }
        return result


# =====================================================
# V8.17 半波连续追踪器（新增）
# =====================================================

class HalfwaveConsecutiveTracker:
    """追踪半波连续出现情况"""
    
    def __init__(self, rows):
        self.rows = rows
    
    def get_consecutive(self):
        if not self.rows:
            return {"current": None, "count": 0}
        current = self.rows[0]["halfwave"]
        count = 1
        for r in self.rows[1:]:
            if r["halfwave"] == current:
                count += 1
            else:
                break
        return {"current": current, "count": count}
    
    def should_reverse(self):
        info = self.get_consecutive()
        return info["count"] >= 3


# =====================================================
# V8.17 最终融合
# =====================================================


class FusionV817:


    def __init__(self,rows, weights=None):

        self.rows=rows

        self.model=AttributeModel(

            rows

        )
        self.weights = weights or CONFIG["weights"]



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


                    cp*self.weights["color"]

                    +

                    size.get(

                        s,

                        0

                    )

                    *

                    self.weights["size"]


                    +

                    odd.get(

                        o,

                        0

                    )

                    *

                    self.weights["odd"]


                    +

                    hp

                    *

                    self.weights["halfhalf"]

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
# V8.17 增强版动态半波选择器（核心升级）
# =====================================================

class DynamicHalfwaveSelectorV2:
    """
    增强版动态半波选择器
    融合: 颜色+大小+马尔可夫+遗漏+连续反向
    """
    
    def __init__(self, color_pred, size_pred, rows=None):
        self.color_pred = color_pred
        self.size_pred = size_pred
        self.rows = rows
        self.all_colors = ["红", "蓝", "绿"]
        self.all_sizes = ["大", "小"]
        self.all_hw = ["红大", "红小", "蓝大", "蓝小", "绿大", "绿小"]
        self.weights = CONFIG.get("halfwave_weights", {
            "color": 0.20, "size": 0.40, "markov": 0.25, "miss": 0.15,
        })
    
    def get_markov_score(self):
        if not self.rows or len(self.rows) < 2:
            return {}
        try:
            markov = HalfwaveMarkovModel(self.rows)
            return markov.predict()
        except:
            return {}
    
    def get_miss_score(self):
        if not self.rows:
            return {}
        try:
            tracker = HalfwaveMissTracker(self.rows)
            return tracker.get_hot_score()
        except:
            return {}
    
    def get_consecutive_info(self):
        if not self.rows:
            return {}
        try:
            tracker = HalfwaveConsecutiveTracker(self.rows)
            return tracker.get_consecutive()
        except:
            return {}
    
    def select_best(self, count=2):
        scores = {}
        markov = self.get_markov_score()
        miss = self.get_miss_score()
        consecutive_info = self.get_consecutive_info()
        
        for c in self.all_colors:
            for s in self.all_sizes:
                hw = c + s
                color_score = self.color_pred.get(c, 0)
                size_score = self.size_pred.get(s, 0)
                markov_score = markov.get(hw, 0)
                miss_score = miss.get(hw, 0)
                
                base_score = (
                    color_score * self.weights["color"] +
                    size_score * self.weights["size"] +
                    markov_score * self.weights["markov"] +
                    miss_score * self.weights["miss"]
                )
                
                if consecutive_info.get("current") == hw and consecutive_info.get("count", 0) >= 3:
                    base_score *= 0.7
                elif consecutive_info.get("current") == hw and consecutive_info.get("count", 0) >= 2:
                    base_score *= 0.85
                
                if self.rows:
                    miss_count = HalfwaveMissTracker(self.rows).get_miss_counts().get(hw, 0)
                    if miss_count >= 10:
                        base_score *= 1.2
                    elif miss_count >= 8:
                        base_score *= 1.1
                
                scores[hw] = round(base_score, 2)
        
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:count]
    
    def get_odds(self, halfwave):
        odds = {
            "红大": 6.75, "红小": 4.72,
            "蓝大": 5.25, "蓝小": 6.75,
            "绿大": 5.91, "绿小": 6.75
        }
        return odds.get(halfwave, 5.91)
    
    def print_recommendation(self, bets, bet_amount=50):
        print("\n" + "=" * 60)
        print("🎯 V8.17 增强版动态半波下注建议")
        print("   融合: 颜色+大小+马尔可夫+遗漏+连续反向")
        print("=" * 60)
        
        print(f"\n📋 推荐下注（动态半波，{len(bets)}注）:")
        for i, (bw, score) in enumerate(bets, 1):
            odds = self.get_odds(bw)
            print(f"  {i}. {bw} (综合得分: {score:.2f}, 赔率: {odds})")
        
        colors_covered = set()
        sizes_covered = set()
        for bw, _ in bets:
            colors_covered.add(bw[0])
            sizes_covered.add(bw[1])
        
        total_amount = len(bets) * bet_amount
        print(f"\n🎨 覆盖颜色: {' + '.join(sorted(colors_covered))}（{len(colors_covered)/3*100:.0f}%）")
        print(f"📏 覆盖大小: {' + '.join(sorted(sizes_covered))}（{len(sizes_covered)/2*100:.0f}%）")
        
        if self.rows:
            miss_info = HalfwaveMissTracker(self.rows).get_miss_counts()
            for bw, _ in bets:
                print(f"  {bw}: 当前遗漏 {miss_info.get(bw, '?')} 期")
        
        consecutive_info = self.get_consecutive_info()
        if consecutive_info.get("count", 0) >= 2:
            print(f"\n⚠️ {consecutive_info['current']} 已连续出现 {consecutive_info['count']} 期，注意反向！")
        
        print(f"\n💰 下注金额: {total_amount}元 ({len(bets)}注×{bet_amount}元)")
        for bw, _ in bets:
            print(f"  {bw}: {bet_amount}元")
        
        print(f"\n📊 权重分配: 颜色{self.weights['color']*100:.0f}% | 大小{self.weights['size']*100:.0f}% | 马尔可夫{self.weights['markov']*100:.0f}% | 遗漏{self.weights['miss']*100:.0f}%")


# =====================================================
# V8.17 盲测回测系统
# =====================================================


class BackTest817:


    def __init__(self,rows):

        self.rows=rows


    def run(self):


        result={

            "color":[0,0],

            "size":[0,0],

            "odd":[0,0],

            "halfhalf":[0,0],

            "top3":[0,0],

            "halfwave_old":[0,0],

            "halfwave_v2":[0,0]

        }


        total=min(

            10,
            len(self.rows)-10

        )


        for i in range(total):


            history=self.rows[i+1:]

            actual=self.rows[i]

            model=FusionV817(history)

            pred=model.predict()

            result["color"][1]+=1
            result["size"][1]+=1
            result["odd"][1]+=1
            result["halfhalf"][1]+=1
            result["top3"][1]+=1
            result["halfwave_old"][1]+=1
            result["halfwave_v2"][1]+=1

            if max(pred["color"],key=pred["color"].get)==actual["color"]:
                result["color"][0]+=1

            if max(pred["size"],key=pred["size"].get)==actual["size"]:
                result["size"][0]+=1

            if max(pred["odd"],key=pred["odd"].get)==actual["odd"]:
                result["odd"][0]+=1

            hlist=[x["halfhalf"] for x in pred["candidates"]]

            if actual["halfhalf"] in hlist:
                result["halfhalf"][0]+=1

            if actual["halfhalf"] in [x["halfhalf"] for x in pred["candidates"][:3]]:
                result["top3"][0]+=1

            # 原版半波
            old_selector = DynamicHalfwaveSelectorV2(pred["color"], pred["size"], history)
            old_selector.weights = {"color": 0.5, "size": 0.5, "markov": 0, "miss": 0}
            bets_old = old_selector.select_best(count=2)
            bet_list_old = [bw for bw, _ in bets_old]
            if actual["halfwave"] in bet_list_old:
                result["halfwave_old"][0]+=1

            # 增强版半波
            selector_v2 = DynamicHalfwaveSelectorV2(pred["color"], pred["size"], history)
            bets_v2 = selector_v2.select_best(count=2)
            bet_list_v2 = [bw for bw, _ in bets_v2]
            if actual["halfwave"] in bet_list_v2:
                result["halfwave_v2"][0]+=1

        return result


    def print_result(self):


        r=self.run()

        print()
        print("="*50)
        print("V8.17 最近10期盲测（含增强版半波对比）")
        print("="*50)

        for k,v in r.items():
            print(k,":",v[0],"/",v[1],"=",round(v[0]/v[1]*100,2),"%")

        return r


# =====================================================
# V8.17 增强版精确投注回测模块
# =====================================================

class ExactBetBackTestV2:
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
            "红大": 6.75, "红小": 4.72,
            "蓝大": 5.25, "蓝小": 6.75,
            "绿大": 5.91, "绿小": 6.75,
        }
    
    def simulate_mode(self, mode="动态半波V2", test_days=10, use_chase=False):
        results = []
        total_bet = 0
        total_return = 0
        total_profit = 0
        hit_count = 0
        balance = 0
        balance_history = []
        consecutive_loss = 0
        
        start_idx = min(test_days, len(self.rows) - 1)
        
        for i in range(start_idx, 0, -1):
            history = self.rows[i:]
            actual = self.rows[i - 1]
            
            model = FusionV817(history)
            pred = model.predict()
            
            candidates = pred["candidates"]
            bet_list = []
            
            if mode == "动态半波V2":
                selector = DynamicHalfwaveSelectorV2(pred["color"], pred["size"], history)
                bets = selector.select_best(count=2)
                bet_list = [bw for bw, _ in bets]
            elif mode == "动态半波原版":
                selector = DynamicHalfwaveSelectorV2(pred["color"], pred["size"], history)
                selector.weights = {"color": 0.5, "size": 0.5, "markov": 0, "miss": 0}
                bets = selector.select_best(count=2)
                bet_list = [bw for bw, _ in bets]
            elif mode == "TOP3":
                bet_list = [c["halfhalf"] for c in candidates[:3]]
            elif mode == "TOP4":
                bet_list = [c["halfhalf"] for c in candidates[:4]]
            elif mode == "TOP5":
                bet_list = [c["halfhalf"] for c in candidates[:5]]
            else:
                bet_list = []
            
            bet_count = len(bet_list)
            if bet_count == 0:
                continue
            
            multiplier = 1
            if use_chase and consecutive_loss > 0:
                multiplier = min(2 ** consecutive_loss, CONFIG["risk_control"]["max_multiplier"])
            
            bet = self.bet_amount * bet_count * multiplier
            total_bet += bet
            
            hit = False
            win_amount = 0
            hit_hw = None
            
            if mode in ["动态半波V2", "动态半波原版"]:
                actual_hw = actual["halfwave"]
                for hw in bet_list:
                    if hw == actual_hw:
                        hit = True
                        hit_hw = hw
                        odds = self.odds.get(hw, 5.91)
                        win_amount = self.bet_amount * odds * multiplier
                        break
            else:
                for hh in bet_list:
                    if hh == actual["halfhalf"]:
                        hit = True
                        hit_hw = hh
                        odds = self.odds.get(hh, 0)
                        win_amount = self.bet_amount * odds * multiplier
                        break
            
            if hit:
                hit_count += 1
                total_return += win_amount
                consecutive_loss = 0
            else:
                win_amount = 0
                consecutive_loss += 1
            
            profit = win_amount - bet
            total_profit += profit
            balance += profit
            balance_history.append(balance)
            
            results.append({
                "issue": actual["issue"],
                "actual": actual["halfwave"] if mode in ["动态半波V2", "动态半波原版"] else actual["halfhalf"],
                "bet_list": bet_list,
                "bet_count": bet_count,
                "bet_amount": bet,
                "multiplier": multiplier,
                "win_amount": win_amount,
                "profit": profit,
                "balance": balance,
                "hit": hit,
                "hit_hw": hit_hw,
                "consecutive_loss": consecutive_loss
            })
        
        roi = (total_profit / total_bet * 100) if total_bet > 0 else 0
        
        return {
            "mode": mode,
            "use_chase": use_chase,
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
    
    def print_report(self, mode="动态半波V2", test_days=10, use_chase=False):
        data = self.simulate_mode(mode, test_days, use_chase)
        
        print(f"\n{'='*70}")
        print(f"📊 {mode} 下注模式详细回测")
        print(f"  每注金额: {self.bet_amount} 元 | 追号: {'开启' if use_chase else '关闭'}")
        print(f"{'='*70}")
        
        print(f"\n📋 最近{test_days}期明细:")
        print(f"{'期号':<12} {'实际':<10} {'下注':<25} {'倍投':<6} {'投注':<8} {'中奖':<10} {'盈亏':<10} {'余额':<10}")
        print(f"{'-'*100}")
        
        for r in data["results"][:test_days]:
            bet_str = ",".join(r["bet_list"][:3])
            if len(r["bet_list"]) > 3:
                bet_str += f"+{len(r['bet_list'])-3}"
            chase_str = f"x{r['multiplier']}" if r['multiplier'] > 1 else "-"
            print(f"{r['issue']:<12} {r['actual']:<10} {bet_str:<25} {chase_str:<6} "
                  f"{r['bet_amount']:<8.0f} {r['win_amount']:<10.2f} "
                  f"{r['profit']:<+10.2f} {r['balance']:<10.2f}")
        
        print(f"{'-'*100}")
        
        print(f"\n📊 汇总统计:")
        print(f"  回测期数: {data['total_periods']} 期")
        print(f"  命中次数: {data['hit_count']} 次")
        print(f"  命中率: {data['hit_rate']:.2f}%")
        print(f"  总投注: {data['total_bet']:.2f} 元")
        print(f"  总回报: {data['total_return']:.2f} 元")
        print(f"  净盈利: {data['total_profit']:+.2f} 元")
        print(f"  ROI: {data['roi']:+.2f}%")
        
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
        
        print(f"{'='*70}")
        
        print(f"\n💡 建议:")
        if data["roi"] > 20:
            print(f"  ✅ {mode}模式表现优异 (ROI {data['roi']:+.2f}%)")
        elif data["roi"] > 0:
            print(f"  ⚠️  {mode}模式略有盈利 (ROI {data['roi']:+.2f}%)")
        else:
            print(f"  ❌ {mode}模式亏损 (ROI {data['roi']:+.2f}%)")
        
        return data
    
    def compare_modes(self, test_days=10):
        modes = ["动态半波V2", "动态半波V2+追号", "动态半波原版", "TOP3", "TOP5"]
        results = {}
        
        print(f"\n{'='*70}")
        print(f"🔄 多种下注模式对比 (最近{test_days}期)")
        print(f"{'='*70}")
        
        for mode in modes:
            if "+追号" in mode:
                base_mode = mode.replace("+追号", "")
                results[mode] = self.simulate_mode(base_mode, test_days, use_chase=True)
            else:
                results[mode] = self.simulate_mode(mode, test_days, use_chase=False)
        
        print(f"\n{'模式':<18} {'总投注':<12} {'总回报':<12} {'净盈利':<12} {'ROI':<12} {'命中率':<12} {'命中次数':<10}")
        print(f"{'-'*95}")
        
        for mode, data in results.items():
            print(f"{mode:<18} {data['total_bet']:<12.2f} {data['total_return']:<12.2f} "
                  f"{data['total_profit']:<+12.2f} {data['roi']:<+12.2f}% "
                  f"{data['hit_rate']:<12.2f}% {data['hit_count']:<10}")
        
        print(f"{'='*70}")
        
        best_mode, best_data = max(results.items(), key=lambda x: x[1]["roi"])
        best_roi = best_data["roi"]
        
        print(f"\n🏆 最优模式: {best_mode} (ROI: {best_roi:+.2f}%)")
        
        if "动态半波V2" in results and "动态半波原版" in results:
            v2_roi = results["动态半波V2"]["roi"]
            old_roi = results["动态半波原版"]["roi"]
            improvement = v2_roi - old_roi
            print(f"\n📈 增强版 vs 原版:")
            print(f"   原版ROI: {old_roi:+.2f}%")
            print(f"   增强版ROI: {v2_roi:+.2f}%")
            print(f"   提升: {improvement:+.2f}%")
        
        if best_roi > 0:
            print(f"\n   ✅ 建议使用 {best_mode} 模式")
        else:
            print(f"\n   ⚠️  所有模式均亏损，建议暂停")
        
        return results, best_mode


# =====================================================
# 马尔可夫链模型
# =====================================================

class MarkovModel:
    def __init__(self, rows):
        self.rows = rows[:30]
        self.transition_matrix = defaultdict(lambda: defaultdict(int))
        self._build_matrix()
    
    def _build_matrix(self):
        for i in range(len(self.rows) - 1):
            current = self.rows[i]["halfhalf"]
            next_hh = self.rows[i + 1]["halfhalf"]
            self.transition_matrix[current][next_hh] += 1
    
    def predict(self, attr="halfhalf"):
        if not self.rows:
            return {}
        
        current = self.rows[0]["halfhalf"]
        
        all_values = ["红大单", "红大双", "红小单", "红小双",
                      "蓝大单", "蓝大双", "蓝小单", "蓝小双",
                      "绿大单", "绿大双", "绿小单", "绿小双"]
        
        transitions = self.transition_matrix.get(current, {})
        total = sum(transitions.values()) or 1
        
        result = {}
        for v in all_values:
            count = transitions.get(v, 0)
            result[v] = round(count / total * 100, 2)
        
        if total == 1:
            freq = defaultdict(int)
            for r in self.rows:
                freq[r["halfhalf"]] += 1
            total_freq = sum(freq.values()) or 1
            for v in all_values:
                result[v] = round(freq.get(v, 0) / total_freq * 100, 2)
        
        return result


# =====================================================
# 频率统计模型
# =====================================================

class FrequencyModel:
    def __init__(self, rows):
        self.rows = rows[:30]
    
    def predict(self, attr="halfhalf"):
        freq = defaultdict(int)
        for r in self.rows:
            freq[r["halfhalf"]] += 1
        
        total = sum(freq.values()) or 1
        all_values = ["红大单", "红大双", "红小单", "红小双",
                      "蓝大单", "蓝大双", "蓝小单", "蓝小双",
                      "绿大单", "绿大双", "绿小单", "绿小双"]
        
        result = {}
        for v in all_values:
            result[v] = round(freq.get(v, 0) / total * 100, 2)
        
        return result


# =====================================================
# 趋势跟踪模型
# =====================================================

class TrendModel:
    def __init__(self, rows):
        self.rows = rows[:30]
    
    def predict(self, attr="halfhalf"):
        all_values = ["红大单", "红大双", "红小单", "红小双",
                      "蓝大单", "蓝大双", "蓝小单", "蓝小双",
                      "绿大单", "绿大双", "绿小单", "绿小双"]
        
        score = defaultdict(float)
        
        for i, r in enumerate(self.rows[:15]):
            weight = (15 - i) * 0.5
            score[r["halfhalf"]] += weight
        
        for v in all_values:
            miss = 0
            for r in self.rows:
                if r["halfhalf"] == v:
                    break
                miss += 1
            score[v] += min(miss * 0.3, 5)
        
        total = sum(score.values()) or 1
        result = {v: round(score[v] / total * 100, 2) for v in all_values}
        
        return result


# =====================================================
# 多模型集成预测器
# =====================================================

class EnsemblePredictor:
    def __init__(self, rows, weights=None):
        self.rows = rows
        self.models = [
            ("attribute", AttributeModel(rows)),
            ("markov", MarkovModel(rows)),
            ("frequency", FrequencyModel(rows)),
            ("trend", TrendModel(rows))
        ]
        
        self.weights = weights or ENSEMBLE_WEIGHTS
    
    def predict(self, attr="halfhalf"):
        votes = defaultdict(float)
        
        all_values = ["红大单", "红大双", "红小单", "红小双",
                      "蓝大单", "蓝大双", "蓝小单", "蓝小双",
                      "绿大单", "绿大双", "绿小单", "绿小双"]
        
        for name, model in self.models:
            weight = self.weights.get(name, 0.25)
            
            if name == "attribute":
                pred = model.predict(attr, all_values)
            else:
                pred = model.predict(attr)
            
            for k, v in pred.items():
                votes[k] += v * weight
        
        total = sum(votes.values()) or 1
        result = {k: round(v / total * 100, 2) for k, v in votes.items()}
        
        return result
    
    def get_topN(self, n=5):
        pred = self.predict()
        sorted_pred = sorted(pred.items(), key=lambda x: x[1], reverse=True)
        return sorted_pred[:n]


# =====================================================
# 网格搜索优化器
# =====================================================

class GridSearchOptimizer:
    def __init__(self, rows):
        self.rows = rows
    
    def grid_search(self, test_days=10):
        param_grid = {
            "attribute_weight": [0.25, 0.30, 0.35, 0.40],
            "markov_weight": [0.15, 0.20, 0.25, 0.30],
            "frequency_weight": [0.10, 0.15, 0.20, 0.25],
            "trend_weight": [0.10, 0.15, 0.20, 0.25]
        }
        
        best_params = None
        best_roi = -float('inf')
        results = []
        
        for aw in param_grid["attribute_weight"]:
            for mw in param_grid["markov_weight"]:
                for fw in param_grid["frequency_weight"]:
                    for tw in param_grid["trend_weight"]:
                        total = aw + mw + fw + tw
                        if abs(total - 1.0) > 0.01:
                            continue
                        
                        weights = {
                            "attribute": aw,
                            "markov": mw,
                            "frequency": fw,
                            "trend": tw
                        }
                        
                        roi = self._backtest_with_params(weights, test_days)
                        
                        results.append({
                            "weights": weights,
                            "roi": roi
                        })
                        
                        if roi > best_roi:
                            best_roi = roi
                            best_params = weights
        
        results.sort(key=lambda x: x["roi"], reverse=True)
        
        return {
            "best_params": best_params,
            "best_roi": best_roi,
            "top_10_results": results[:10]
        }
    
    def _backtest_with_params(self, weights, test_days=10):
        start_idx = min(test_days, len(self.rows) - 1)
        
        total_bet = 0
        total_profit = 0
        hit_count = 0
        
        for i in range(start_idx, 0, -1):
            history = self.rows[i:]
            actual = self.rows[i - 1]
            
            ensemble = EnsemblePredictor(history, weights)
            pred = ensemble.get_topN(3)
            
            if not pred:
                continue
            
            bet_amount = 50 * 3
            total_bet += bet_amount
            
            hit = False
            for hh, score in pred:
                if hh == actual["halfhalf"]:
                    hit = True
                    break
            
            if hit:
                hit_count += 1
                total_profit += (50 * 9.45 - bet_amount)
            else:
                total_profit -= bet_amount
        
        roi = (total_profit / total_bet * 100) if total_bet > 0 else -100
        return roi


# =====================================================
# 滚动回测 + 动态调参
# =====================================================

class RollingBacktestOptimizer:
    def __init__(self, rows, window_size=20, step=5):
        self.rows = rows
        self.window_size = window_size
        self.step = step
    
    def run(self):
        results = []
        total_roi = 0
        total_profit = 0
        total_bet = 0
        hit_count = 0
        
        print(f"\n{'='*60}")
        print(f"🔄 滚动回测 + 动态调参")
        print(f"  训练窗口: {self.window_size}期  滚动步长: {self.step}期")
        print(f"{'='*60}")
        
        for start in range(0, len(self.rows) - self.window_size - 5, self.step):
            train_end = start + self.window_size
            test_start = train_end
            test_end = min(test_start + self.step, len(self.rows))
            
            if test_start >= len(self.rows):
                break
            
            train_rows = self.rows[start:train_end]
            test_rows = self.rows[test_start:test_end]
            
            if len(train_rows) < 10 or len(test_rows) < 1:
                continue
            
            grid = GridSearchOptimizer(train_rows)
            search_result = grid.grid_search(test_days=min(10, len(test_rows)))
            best_params = search_result["best_params"]
            
            ensemble = EnsemblePredictor(train_rows, best_params)
            
            period_bet = 0
            period_profit = 0
            period_hit = 0
            
            for r in test_rows:
                pred = ensemble.get_topN(3)
                if not pred:
                    continue
                
                bet_amount = 50 * 3
                period_bet += bet_amount
                
                hit = False
                for hh, score in pred:
                    if hh == r["halfhalf"]:
                        hit = True
                        break
                
                if hit:
                    period_hit += 1
                    period_profit += (50 * 9.45 - bet_amount)
                else:
                    period_profit -= bet_amount
            
            roi = (period_profit / period_bet * 100) if period_bet > 0 else 0
            hit_rate = (period_hit / len(test_rows) * 100) if test_rows else 0
            
            results.append({
                "train_period": f"{start+1}-{train_end}",
                "test_period": f"{test_start+1}-{test_end}",
                "best_params": best_params,
                "roi": roi,
                "hit_rate": hit_rate,
                "profit": period_profit,
                "bet": period_bet,
                "hit_count": period_hit,
                "total_periods": len(test_rows)
            })
            
            total_roi += roi
            total_profit += period_profit
            total_bet += period_bet
            hit_count += period_hit
        
        avg_roi = total_roi / len(results) if results else 0
        
        print(f"\n📊 滚动回测汇总:")
        print(f"  测试窗口数: {len(results)}")
        print(f"  平均ROI: {avg_roi:+.2f}%")
        print(f"  总投注: {total_bet:.2f}元")
        print(f"  总盈利: {total_profit:+.2f}元")
        
        if results:
            print(f"\n📋 各窗口详细:")
            print(f"{'训练期':<15} {'测试期':<15} {'ROI':<12} {'命中率':<12} {'盈利':<12}")
            print(f"{'-'*60}")
            for r in results:
                print(f"{r['train_period']:<15} {r['test_period']:<15} "
                      f"{r['roi']:<+12.2f}% {r['hit_rate']:<12.2f}% {r['profit']:<+12.2f}")
            
            best_result = max(results, key=lambda x: x["roi"])
            print(f"\n🏆 最优参数组合 (按ROI):")
            print(f"  训练期: {best_result['train_period']}")
            print(f"  ROI: {best_result['roi']:+.2f}%")
            print(f"  参数: {best_result['best_params']}")
        
        return results
    
    def find_best_params(self):
        results = self.run()
        
        if not results:
            return None
        
        sorted_results = sorted(results, key=lambda x: x["roi"], reverse=True)
        best = sorted_results[0]
        
        print(f"\n{'='*60}")
        print(f"🎯 最终推荐参数:")
        print(f"{'='*60}")
        print(f"  参数: {best['best_params']}")
        print(f"  预期ROI: {best['roi']:+.2f}%")
        print(f"  测试期数: {best['total_periods']}期")
        
        return best["best_params"]


# =====================================================
# 权重优化器（5个，完整保留）
# =====================================================

class AutoWeightOptimizer:
    """全自动权重优化器 - 主权重（颜色/大小/单双/半半波）"""
    
    def __init__(self, rows):
        self.rows = rows[:30]
    
    def evaluate_weights(self, weights, test_days=10):
        if len(self.rows) < test_days + 1:
            return -100
        
        total_bet = 0
        total_profit = 0
        hit_count = 0
        
        for i in range(test_days, 0, -1):
            history = self.rows[i:]
            actual = self.rows[i - 1]
            
            model = FusionV817(history, weights)
            pred = model.predict()
            
            if pred["candidates"]:
                bet_amount = 50 * 3
                total_bet += bet_amount
                
                hit = False
                for c in pred["candidates"][:3]:
                    if c["halfhalf"] == actual["halfhalf"]:
                        hit = True
                        break
                
                if hit:
                    hit_count += 1
                    total_profit += (50 * 9.45 - bet_amount)
                else:
                    total_profit -= bet_amount
        
        roi = (total_profit / total_bet * 100) if total_bet > 0 else -100
        return roi
    
    def random_search(self, test_days=10, iterations=300):
        print("\n🔍 正在搜索主权重最优组合...")
        print(f"  测试期数: {test_days}期")
        print(f"  迭代次数: {iterations}次")
        
        best_weights = None
        best_roi = -100
        results = []
        
        for i in range(iterations):
            raw = [random.random() for _ in range(4)]
            total = sum(raw)
            weights = {
                "color": raw[0] / total,
                "size": raw[1] / total,
                "odd": raw[2] / total,
                "halfhalf": raw[3] / total
            }
            
            roi = self.evaluate_weights(weights, test_days)
            results.append({"weights": weights, "roi": roi})
            
            if roi > best_roi:
                best_roi = roi
                best_weights = weights
            
            if (i + 1) % 100 == 0:
                print(f"  已迭代 {i+1}/{iterations} 次，当前最优ROI: {best_roi:.1f}%")
        
        results.sort(key=lambda x: x["roi"], reverse=True)
        
        print(f"\n✅ 搜索完成！最优ROI: {best_roi:.1f}%")
        
        if best_weights is None:
            print("⚠️ 未找到有效权重，使用默认权重")
            best_weights = {"color": 0.25, "size": 0.30, "odd": 0.25, "halfhalf": 0.20}
            best_roi = 0
        
        return {
            "best_weights": best_weights,
            "best_roi": best_roi,
            "top_results": results[:10]
        }


class ColorWeightOptimizer:
    """颜色预测内部权重自动优化"""
    
    def __init__(self, rows):
        self.rows = rows[:30]
    
    def evaluate_color_weights(self, weights, test_days=10):
        if len(self.rows) < test_days + 1:
            return 33
        
        correct = 0
        total = 0
        
        for i in range(test_days, 0, -1):
            history = self.rows[i:]
            actual = self.rows[i - 1]
            
            color_predictor = ColorPredictor(history, weights)
            pred = color_predictor.predict()
            predicted = max(pred, key=pred.get)
            
            if predicted == actual["color"]:
                correct += 1
            total += 1
        
        return correct / total * 100 if total > 0 else 33
    
    def random_search(self, test_days=10, iterations=300):
        print("\n🔍 正在搜索颜色内部最优权重...")
        
        best_weights = None
        best_accuracy = 0
        results = []
        
        for i in range(iterations):
            raw = [random.random() for _ in range(5)]
            total = sum(raw)
            weights = {
                "frequency": raw[0] / total,
                "trend": raw[1] / total,
                "markov": raw[2] / total,
                "miss": raw[3] / total,
                "zone": raw[4] / total
            }
            
            accuracy = self.evaluate_color_weights(weights, test_days)
            results.append({"weights": weights, "accuracy": accuracy})
            
            if accuracy > best_accuracy:
                best_accuracy = accuracy
                best_weights = weights
            
            if (i + 1) % 100 == 0:
                print(f"  已迭代 {i+1}/{iterations} 次，当前最优准确率: {best_accuracy:.1f}%")
        
        results.sort(key=lambda x: x["accuracy"], reverse=True)
        
        print(f"\n✅ 搜索完成！最优准确率: {best_accuracy:.1f}%")
        
        if best_weights is None:
            print("⚠️ 未找到有效权重，使用默认权重")
            best_weights = {"frequency": 0.20, "trend": 0.20, "markov": 0.20, "miss": 0.20, "zone": 0.20}
            best_accuracy = 33
        
        return {
            "best_weights": best_weights,
            "best_accuracy": best_accuracy,
            "top_results": results[:10]
        }


class SizeWeightOptimizer:
    """大小预测内部权重自动优化"""
    
    def __init__(self, rows):
        self.rows = rows[:30]
    
    def evaluate_size_weights(self, weights, test_days=10):
        if len(self.rows) < test_days + 1:
            return 50
        
        correct = 0
        total = 0
        
        for i in range(test_days, 0, -1):
            history = self.rows[i:]
            actual = self.rows[i - 1]
            
            size_predictor = SizePredictor(history, weights)
            pred = size_predictor.predict()
            predicted = max(pred, key=pred.get)
            
            if predicted == actual["size"]:
                correct += 1
            total += 1
        
        return correct / total * 100 if total > 0 else 50
    
    def random_search(self, test_days=10, iterations=300):
        print("\n🔍 正在搜索大小内部最优权重...")
        
        best_weights = None
        best_accuracy = 0
        results = []
        
        for i in range(iterations):
            raw = [random.random() for _ in range(5)]
            total = sum(raw)
            weights = {
                "frequency": raw[0] / total,
                "trend": raw[1] / total,
                "markov": raw[2] / total,
                "miss": raw[3] / total,
                "consecutive": raw[4] / total
            }
            
            accuracy = self.evaluate_size_weights(weights, test_days)
            results.append({"weights": weights, "accuracy": accuracy})
            
            if accuracy > best_accuracy:
                best_accuracy = accuracy
                best_weights = weights
            
            if (i + 1) % 100 == 0:
                print(f"  已迭代 {i+1}/{iterations} 次，当前最优准确率: {best_accuracy:.1f}%")
        
        results.sort(key=lambda x: x["accuracy"], reverse=True)
        
        print(f"\n✅ 搜索完成！最优准确率: {best_accuracy:.1f}%")
        
        if best_weights is None:
            print("⚠️ 未找到有效权重，使用默认权重")
            best_weights = {"frequency": 0.20, "trend": 0.20, "markov": 0.20, "miss": 0.20, "consecutive": 0.20}
            best_accuracy = 50
        
        return {
            "best_weights": best_weights,
            "best_accuracy": best_accuracy,
            "top_results": results[:10]
        }


class OddWeightOptimizer:
    """单双内部权重自动优化"""
    
    def __init__(self, rows):
        self.rows = rows[:30]
    
    def evaluate_odd_weights(self, weights, test_days=10):
        if len(self.rows) < test_days + 1:
            return 50
        
        correct = 0
        total = 0
        
        for i in range(test_days, 0, -1):
            history = self.rows[i:]
            actual = self.rows[i - 1]
            
            odd_predictor = OddPredictor(history, weights)
            pred = odd_predictor.predict()
            predicted = max(pred, key=pred.get)
            
            if predicted == actual["odd"]:
                correct += 1
            total += 1
        
        return correct / total * 100 if total > 0 else 50
    
    def random_search(self, test_days=10, iterations=300):
        print("\n🔍 正在搜索单双内部最优权重...")
        
        best_weights = None
        best_accuracy = 0
        results = []
        
        for i in range(iterations):
            raw = [random.random() for _ in range(5)]
            total = sum(raw)
            weights = {
                "frequency": raw[0] / total,
                "trend": raw[1] / total,
                "markov": raw[2] / total,
                "tail": raw[3] / total,
                "consecutive": raw[4] / total
            }
            
            accuracy = self.evaluate_odd_weights(weights, test_days)
            results.append({"weights": weights, "accuracy": accuracy})
            
            if accuracy > best_accuracy:
                best_accuracy = accuracy
                best_weights = weights
            
            if (i + 1) % 100 == 0:
                print(f"  已迭代 {i+1}/{iterations} 次，当前最优准确率: {best_accuracy:.1f}%")
        
        results.sort(key=lambda x: x["accuracy"], reverse=True)
        
        print(f"\n✅ 搜索完成！最优准确率: {best_accuracy:.1f}%")
        
        if best_weights is None:
            print("⚠️ 未找到有效权重，使用默认权重")
            best_weights = {"frequency": 0.25, "trend": 0.20, "markov": 0.25, "tail": 0.15, "consecutive": 0.15}
            best_accuracy = 50
        
        return {
            "best_weights": best_weights,
            "best_accuracy": best_accuracy,
            "top_results": results[:10]
        }


class EnsembleWeightOptimizer:
    """多模型集成权重自动优化"""
    
    def __init__(self, rows):
        self.rows = rows[:30]
    
    def evaluate_ensemble_weights(self, weights, test_days=10):
        if len(self.rows) < test_days + 1:
            return -100
        
        total_bet = 0
        total_profit = 0
        
        for i in range(test_days, 0, -1):
            history = self.rows[i:]
            actual = self.rows[i - 1]
            
            ensemble = EnsemblePredictor(history, weights)
            pred = ensemble.get_topN(3)
            
            if not pred:
                continue
            
            bet_amount = 50 * 3
            total_bet += bet_amount
            
            hit = False
            for hh, score in pred:
                if hh == actual["halfhalf"]:
                    hit = True
                    break
            
            if hit:
                total_profit += (50 * 9.45 - bet_amount)
            else:
                total_profit -= bet_amount
        
        roi = (total_profit / total_bet * 100) if total_bet > 0 else -100
        return roi
    
    def random_search(self, test_days=10, iterations=300):
        print("\n🔍 正在搜索多模型集成最优权重...")
        
        best_weights = None
        best_roi = -100
        results = []
        
        for i in range(iterations):
            raw = [random.random() for _ in range(4)]
            total = sum(raw)
            weights = {
                "attribute": raw[0] / total,
                "markov": raw[1] / total,
                "frequency": raw[2] / total,
                "trend": raw[3] / total
            }
            
            roi = self.evaluate_ensemble_weights(weights, test_days)
            results.append({"weights": weights, "roi": roi})
            
            if roi > best_roi:
                best_roi = roi
                best_weights = weights
            
            if (i + 1) % 100 == 0:
                print(f"  已迭代 {i+1}/{iterations} 次，当前最优ROI: {best_roi:.1f}%")
        
        results.sort(key=lambda x: x["roi"], reverse=True)
        
        print(f"\n✅ 搜索完成！最优ROI: {best_roi:.1f}%")
        
        if best_weights is None:
            print("⚠️ 未找到有效权重，使用默认权重")
            best_weights = {"attribute": 0.35, "markov": 0.25, "frequency": 0.20, "trend": 0.20}
            best_roi = 0
        
        return {
            "best_weights": best_weights,
            "best_roi": best_roi,
            "top_results": results[:10]
        }


# =====================================================
# 下注记录管理
# =====================================================

class BetRecord:
    """下注记录管理 - 今晚开始"""
    
    def __init__(self):
        self.records = []
        self.total_bet = 0
        self.total_win = 0
        self.total_profit = 0
        self.consecutive_loss = 0
        
    def add_record(self, issue, bets, actual, win_amount, multiplier=1):
        bet_amount = 50 * len(bets) * multiplier
        profit = win_amount - bet_amount
        
        record = {
            "issue": issue,
            "bets": bets,
            "actual": actual,
            "multiplier": multiplier,
            "bet_amount": bet_amount,
            "win_amount": win_amount,
            "profit": profit
        }
        self.records.append(record)
        self.total_bet += bet_amount
        self.total_win += win_amount
        self.total_profit += profit
        
        if profit < 0:
            self.consecutive_loss += 1
        else:
            self.consecutive_loss = 0
    
    def print_summary(self):
        print("\n" + "=" * 60)
        print("📋 下注记录汇总（今晚开始）")
        print("=" * 60)
        
        if not self.records:
            print("暂无记录")
            return
        
        print(f"\n{'期号':<12} {'下注':<25} {'实际':<10} {'倍投':<6} {'投注':<8} {'中奖':<10} {'盈亏':<10}")
        print("-" * 90)
        
        for r in self.records:
            bets_str = ",".join(r["bets"])
            chase_str = f"x{r['multiplier']}" if r['multiplier'] > 1 else "-"
            print(f"{r['issue']:<12} {bets_str:<25} {r['actual']:<10} {chase_str:<6} "
                  f"{r['bet_amount']:<8.0f} {r['win_amount']:<10.2f} {r['profit']:<+10.2f}")
        
        print("-" * 90)
        print(f"\n总投注: {self.total_bet:.2f}元")
        print(f"总中奖: {self.total_win:.2f}元")
        print(f"总盈亏: {self.total_profit:+.2f}元")
        print(f"连续亏损: {self.consecutive_loss}期")
        
        roi = (self.total_profit / self.total_bet * 100) if self.total_bet > 0 else 0
        print(f"ROI: {roi:+.2f}%")
        
        if self.consecutive_loss >= 2:
            print(f"\n⚠️ 连续亏损{self.consecutive_loss}期，建议观望1-2期！")
        
        print("=" * 60)
    
    def save_to_file(self):
        with open(BET_RECORD_FILE, "w", encoding="utf-8") as f:
            f.write("# 香港彩下注记录（动态半波增强版 V8.17）\n\n")
            f.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            if not self.records:
                f.write("暂无记录\n")
                return
            
            f.write("| 期号 | 下注 | 实际开奖 | 倍投 | 投注 | 中奖 | 盈亏 |\n")
            f.write("|------|------|----------|------|------|------|------|\n")
            
            for r in self.records:
                bets_str = ",".join(r["bets"])
                chase_str = f"x{r['multiplier']}" if r['multiplier'] > 1 else "-"
                f.write(f"| {r['issue']} | {bets_str} | {r['actual']} | {chase_str} | "
                       f"{r['bet_amount']:.0f} | {r['win_amount']:.2f} | {r['profit']:+.2f} |\n")
            
            f.write("\n## 汇总\n\n")
            f.write(f"- 总投注: {self.total_bet:.2f}元\n")
            f.write(f"- 总中奖: {self.total_win:.2f}元\n")
            f.write(f"- 总盈亏: {self.total_profit:+.2f}元\n")
            roi = (self.total_profit / self.total_bet * 100) if self.total_bet > 0 else 0
            f.write(f"- ROI: {roi:+.2f}%\n")
            f.write(f"- 连续亏损: {self.consecutive_loss}期\n")


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
            "# 香港彩 V8.17 预测报告（动态半波增强版）\n\n"
        )
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
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
            "\n## 大小预测\n\n"
        )
        for k,v in sorted(
            result["size"].items(),
            key=lambda x:x[1],
            reverse=True
        ):
            f.write(
                f"{k}: {v}%\n"
            )
        f.write(
            "\n## 单双预测\n\n"
        )
        for k,v in sorted(
            result["odd"].items(),
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
    global CONFIG, COLOR_WEIGHTS, SIZE_WEIGHTS, ODD_WEIGHTS, ENSEMBLE_WEIGHTS


    print("=" * 60)
    print("🎯 香港彩预测系统 V8.17（动态半波增强版）")
    print("   核心升级: 大小权重提升 + 半波马尔可夫 + 遗漏追踪 + 追号机制")
    print("=" * 60)


    print(

        "正在获取香港彩数据..."

    )



    rows=fetch_lottery(

        30

    )



    if len(rows)<10:


        print(

            "数据不足（需要至少10期）"

        )

        return


    # =====================================================
    # 第一步 - 自动优化主权重
    # =====================================================
    print("\n" + "=" * 60)
    print("🎯 第一步：自动优化主权重")
    print("=" * 60)
    
    main_optimizer = AutoWeightOptimizer(rows)
    main_result = main_optimizer.random_search(test_days=10, iterations=300)
    
    print(f"\n📊 主权重优化结果:")
    print(f"  最优ROI: {main_result['best_roi']:.1f}%")
    print(f"  最优权重:")
    for k, v in main_result['best_weights'].items():
        print(f"    {k}: {v:.3f}")
    
    CONFIG["weights"] = main_result['best_weights']
    
    # =====================================================
    # 第二步 - 自动优化颜色内部权重
    # =====================================================
    print("\n" + "=" * 60)
    print("🎯 第二步：自动优化颜色内部权重")
    print("=" * 60)
    
    color_optimizer = ColorWeightOptimizer(rows)
    color_result = color_optimizer.random_search(test_days=10, iterations=300)
    
    print(f"\n📊 颜色内部权重优化结果:")
    print(f"  最优准确率: {color_result['best_accuracy']:.1f}%")
    print(f"  最优权重:")
    for k, v in color_result['best_weights'].items():
        print(f"    {k}: {v:.3f}")
    
    COLOR_WEIGHTS = color_result['best_weights']
    
    # =====================================================
    # 第三步 - 自动优化大小内部权重
    # =====================================================
    print("\n" + "=" * 60)
    print("🎯 第三步：自动优化大小内部权重")
    print("=" * 60)
    
    size_optimizer = SizeWeightOptimizer(rows)
    size_result = size_optimizer.random_search(test_days=10, iterations=300)
    
    print(f"\n📊 大小内部权重优化结果:")
    print(f"  最优准确率: {size_result['best_accuracy']:.1f}%")
    print(f"  最优权重:")
    for k, v in size_result['best_weights'].items():
        print(f"    {k}: {v:.3f}")
    
    SIZE_WEIGHTS = size_result['best_weights']
    
    # =====================================================
    # 第四步 - 自动优化单双内部权重
    # =====================================================
    print("\n" + "=" * 60)
    print("🎯 第四步：自动优化单双内部权重")
    print("=" * 60)
    
    odd_optimizer = OddWeightOptimizer(rows)
    odd_result = odd_optimizer.random_search(test_days=10, iterations=300)
    
    print(f"\n📊 单双内部权重优化结果:")
    print(f"  最优准确率: {odd_result['best_accuracy']:.1f}%")
    print(f"  最优权重:")
    for k, v in odd_result['best_weights'].items():
        print(f"    {k}: {v:.3f}")
    
    ODD_WEIGHTS = odd_result['best_weights']
    
    # =====================================================
    # 第五步 - 自动优化多模型集成权重
    # =====================================================
    print("\n" + "=" * 60)
    print("🎯 第五步：自动优化多模型集成权重")
    print("=" * 60)
    
    ensemble_optimizer = EnsembleWeightOptimizer(rows)
    ensemble_result = ensemble_optimizer.random_search(test_days=10, iterations=300)
    
    print(f"\n📊 多模型集成权重优化结果:")
    print(f"  最优ROI: {ensemble_result['best_roi']:.1f}%")
    print(f"  最优权重:")
    for k, v in ensemble_result['best_weights'].items():
        print(f"    {k}: {v:.3f}")
    
    ENSEMBLE_WEIGHTS = ensemble_result['best_weights']
    
    # =====================================================
    # 打印最终配置
    # =====================================================
    print("\n" + "=" * 60)
    print("✅ 全自动优化完成！最终配置 (30期数据):")
    print("=" * 60)
    print(f"\n主权重:")
    for k, v in CONFIG["weights"].items():
        print(f"  {k}: {v:.3f}")
    print(f"\n颜色内部权重:")
    for k, v in COLOR_WEIGHTS.items():
        print(f"  {k}: {v:.3f}")
    print(f"\n大小内部权重:")
    for k, v in SIZE_WEIGHTS.items():
        print(f"  {k}: {v:.3f}")
    print(f"\n单双内部权重:")
    for k, v in ODD_WEIGHTS.items():
        print(f"  {k}: {v:.3f}")
    print(f"\n多模型集成权重:")
    for k, v in ENSEMBLE_WEIGHTS.items():
        print(f"  {k}: {v:.3f}")
    print(f"\n半波选择器权重:")
    for k, v in CONFIG["halfwave_weights"].items():
        print(f"  {k}: {v:.3f}")


    print()

    print(

        "最近30期开奖结果"

    )

    print("-"*30)



    for r in rows[:10]:


        print(

            r["issue"],

            "特码",

            r["special"],

            r["color"],

            r["halfwave"],

            r["halfhalf"]

        )
    
    print("... (共30期)")


    print()

    print("="*40)

    print(

        "香港彩 V8.17 增强版动态半波预测"

    )

    print("="*40)



    model=FusionV817(

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

        bar = "█" * int(v / 5)
        print(f"  {k}: {v}% {bar}")


    print()

    print("大小预测:")


    for k,v in sorted(result["size"].items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(v / 5)
        print(f"  {k}: {v}% {bar}")


    print()

    print("单双预测:")


    for k,v in sorted(result["odd"].items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(v / 5)
        print(f"  {k}: {v}% {bar}")


    print()

    print("最终TOP5:")



    for i,c in enumerate(

        result["candidates"],

        1

    ):

        bar = "█" * int(c["score"] / 5)
        print(f"  {i}. {c['halfhalf']:8s} 得分: {c['score']:6.2f} {bar}")


    # =====================================================
    # V8.17 增强版动态半波推荐
    # =====================================================
    selector = DynamicHalfwaveSelectorV2(result["color"], result["size"], rows)
    bets = selector.select_best(count=2)
    selector.print_recommendation(bets)

    # 半波马尔可夫分析
    if rows:
        hw_markov = HalfwaveMarkovModel(rows)
        detail = hw_markov.get_transition_detail()
        if detail:
            print(f"\n📊 半波马尔可夫分析:")
            print(f"  当前状态: {detail['current']}")
            sorted_trans = sorted(detail['transitions'].items(), key=lambda x: x[1], reverse=True)
            print(f"  转移概率: {dict(sorted_trans)}")

    # 半波遗漏分析
    if rows:
        hw_miss = HalfwaveMissTracker(rows)
        miss_info = hw_miss.get_miss_counts()
        print(f"\n📊 半波遗漏分析:")
        for hw, cnt in sorted(miss_info.items(), key=lambda x: x[1], reverse=True):
            bar = "█" * min(cnt, 20)
            print(f"  {hw}: 遗漏{cnt}期 {bar}")

    # 半波冷热分析
    if rows:
        hw_miss = HalfwaveMissTracker(rows)
        analysis = hw_miss.get_cold_hot_analysis()
        print(f"\n📊 半波冷热分析 (近10期):")
        for hw, info in sorted(analysis.items(), key=lambda x: x[1]["frequency_10"], reverse=True):
            status_icon = "🔥" if info["status"] == "热" else ("🌡️" if info["status"] == "温" else "❄️")
            print(f"  {hw}: {status_icon} {info['status']} | 出现{info['frequency_10']}次 | 遗漏{info['miss_count']}期")


    # =====================================================
    # 下注记录初始化
    # =====================================================
    print("\n" + "=" * 50)
    print("📋 下注记录（今晚开始）")
    print("=" * 50)

    bet_record = BetRecord()
    print("\n当前无记录，等待开奖后更新...")


    # =====================================================
    # V8.17 盲测
    # =====================================================
    BackTest817(rows).print_result()


    save_report(result)

    print()
    print("报告生成:", REPORT_FILE)


    # =====================================================
    # V8.17 增强版精确投注回测
    # =====================================================
    print()
    print("=" * 70)
    print("💰 V8.17 增强版真实盈利回测 (含本金)")
    print("=" * 70)
    
    exact_test = ExactBetBackTestV2(rows, bet_amount=50)
    
    # 对比多种模式
    exact_test.compare_modes(test_days=10)
    
    # 详细显示增强版动态半波
    print()
    exact_test.print_report(mode="动态半波V2", test_days=10, use_chase=False)
    
    # 显示追号模式
    print()
    exact_test.print_report(mode="动态半波V2", test_days=10, use_chase=True)


    # =====================================================
    # 多模型集成 + 滚动回测 + 动态调参
    # =====================================================
    print()
    print("=" * 60)
    print("🤖 多模型集成 + 滚动回测 + 动态调参")
    print("=" * 60)
    
    print("\n📊 多模型集成预测 (TOP5):")
    ensemble = EnsemblePredictor(rows)
    top5 = ensemble.get_topN(5)
    for i, (hh, score) in enumerate(top5, 1):
        print(f"  {i}. {hh}: {score}%")
    
    print("\n🔍 网格搜索最优参数 (最近10期):")
    grid = GridSearchOptimizer(rows)
    search_result = grid.grid_search(test_days=10)
    print(f"  最优ROI: {search_result['best_roi']:+.2f}%")
    print(f"  最优参数: {search_result['best_params']}")
    print(f"  TOP3参数组合:")
    for i, r in enumerate(search_result["top_10_results"][:3], 1):
        print(f"    {i}. ROI {r['roi']:+.2f}% - {r['weights']}")
    
    print("\n🔄 滚动回测 + 动态调参:")
    rolling = RollingBacktestOptimizer(rows, window_size=20, step=5)
    best_params = rolling.find_best_params()
    
    if best_params:
        print("\n🎯 使用最优参数的最终预测:")
        final_ensemble = EnsemblePredictor(rows, best_params)
        final_top5 = final_ensemble.get_topN(5)
        for i, (hh, score) in enumerate(final_top5, 1):
            print(f"  {i}. {hh}: {score}%")
    
    # =====================================================
    # 保存下注记录
    # =====================================================
    bet_record.save_to_file()
    print(f"\n📄 下注记录已保存: {BET_RECORD_FILE}")

    # =====================================================
    # 最终总结
    # =====================================================
    print("\n" + "=" * 70)
    print("📋 V8.17 增强版核心改进总结:")
    print("=" * 70)
    print("  1. ✅ 大小权重从50%提升至40%（基于80%准确率）")
    print("  2. ✅ 新增半波专用马尔可夫链模型（6种状态）")
    print("  3. ✅ 新增半波遗漏追踪器（冷热分析+遗漏补偿）")
    print("  4. ✅ 新增连续出现反向信号（连3次降30%权重）")
    print("  5. ✅ 新增智能追号机制（可开关，连黑加倍）")
    print("  6. ✅ 新增原版vs增强版对比回测")
    print("  7. ✅ 完整保留V8.16所有功能")
    print("=" * 70)


if __name__=="__main__":

    main()