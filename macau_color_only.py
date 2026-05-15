from pathlib import Path

script = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===========================================================
HMM + XGBoost Research Framework V6
Author: OpenAI ChatGPT
===========================================================

科研级高噪声离散序列研究框架：

Features
--------
- Walk-forward validation
- Hidden Markov Model (HMM)
- XGBoost classifier
- Bayesian-style probability output
- Risk metrics
- Monte Carlo bankroll simulation
- Statistical significance test
- LogLoss evaluation
- Feature engineering

Install
-------
pip install numpy pandas xgboost hmmlearn scikit-learn matplotlib

Run
---
python research_v6.py
"""

import math
import random
from collections import Counter

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from hmmlearn import hmm
from sklearn.metrics import accuracy_score, log_loss
from xgboost import XGBClassifier

# =========================================================
# CONFIG
# =========================================================

COLORS = ["红", "蓝", "绿"]

COLOR_TO_INT = {
    "红": 0,
    "蓝": 1,
    "绿": 2
}

INT_TO_COLOR = {
    0: "红",
    1: "蓝",
    2: "绿"
}

N_HIDDEN = 3
WINDOW = 200
TEST_SIZE = 200
BANKROLL_INIT = 10000
BET_SIZE = 100

RANDOM_SEED = 42

random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# =========================================================
# ENCODE
# =========================================================

def encode(seq):
    return np.array([
        COLOR_TO_INT[x]
        for x in seq
    ])

# =========================================================
# HMM FEATURES
# =========================================================

def hmm_features(train):

    X = encode(train).reshape(-1, 1)

    model = hmm.CategoricalHMM(
        n_components=N_HIDDEN,
        n_iter=100,
        random_state=RANDOM_SEED
    )

    model.fit(X)

    hidden_states = model.predict(X)

    last_state = hidden_states[-1]

    trans_prob = model.transmat_[last_state]

    return {
        "hidden_state": int(last_state),
        "trans_prob": trans_prob
    }

# =========================================================
# FEATURE ENGINEERING
# =========================================================

def make_features(train):

    feat = {}

    recent = train[-5:]

    for i, c in enumerate(recent):
        feat[f"recent_{i}"] = COLOR_TO_INT[c]

    for window in [10, 30]:

        sub = train[-window:]

        cnt = Counter(sub)

        for c in COLORS:
            feat[f"freq_{window}_{c}"] = (
                cnt[c] / max(len(sub), 1)
            )

    for c in COLORS:

        omission = len(train)

        for i, x in enumerate(reversed(train)):
            if x == c:
                omission = i
                break

        feat[f"omission_{c}"] = omission

    hmm_feat = hmm_features(train)

    feat["hidden_state"] = hmm_feat["hidden_state"]

    for i, p in enumerate(hmm_feat["trans_prob"]):
        feat[f"hmm_trans_{i}"] = float(p)

    return feat

# =========================================================
# DATASET
# =========================================================

def build_dataset(series):

    X = []
    y = []

    for i in range(50, len(series) - 1):

        train = series[:i]

        feat = make_features(train)

        X.append(list(feat.values()))

        y.append(
            COLOR_TO_INT[series[i]]
        )

    return np.array(X), np.array(y)

# =========================================================
# WALK FORWARD
# =========================================================

def walk_forward_split(X, y):

    split = int(len(X) * 0.8)

    return (
        X[:split],
        X[split:],
        y[:split],
        y[split:]
    )

# =========================================================
# MODEL
# =========================================================

def train_model(X_train, y_train):

    model = XGBClassifier(
        n_estimators=120,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="mlogloss",
        random_state=RANDOM_SEED
    )

    model.fit(X_train, y_train)

    return model

# =========================================================
# METRICS
# =========================================================

def multiclass_log_loss(prob, actual):

    eps = 1e-15

    p = max(prob[actual], eps)

    return -math.log(p)

def significance_test(p_model, p_random, n):

    se = math.sqrt(
        p_random * (1 - p_random) / n
    )

    if se == 0:
        return "无法计算"

    z = (p_model - p_random) / se

    if abs(z) > 1.96:
        return f"显著 (z={z:.2f})"

    return f"不显著 (z={z:.2f})"

def risk_metrics(curve):

    arr = np.array(curve)

    peak = np.maximum.accumulate(arr)

    drawdown = (arr - peak) / peak

    returns = np.diff(arr) / arr[:-1]

    sharpe = (
        np.mean(returns)
        /
        (np.std(returns) + 1e-9)
    )

    return {
        "final_return":
            (arr[-1] / arr[0]) - 1,

        "max_drawdown":
            float(drawdown.min()),

        "volatility":
            float(np.std(arr)),

        "sharpe":
            float(sharpe)
    }

# =========================================================
# MONTE CARLO
# =========================================================

def monte_carlo_bankroll(
    hit_rate,
    runs=500,
    trades=200
):

    final_values = []

    for _ in range(runs):

        bankroll = BANKROLL_INIT

        for _ in range(trades):

            if random.random() < hit_rate:
                bankroll += BET_SIZE
            else:
                bankroll -= BET_SIZE

        final_values.append(bankroll)

    return {
        "mean_final":
            np.mean(final_values),

        "std_final":
            np.std(final_values),

        "worst":
            np.min(final_values),

        "best":
            np.max(final_values)
    }

# =========================================================
# PLOT
# =========================================================

def plot_curve(curve):

    plt.figure(figsize=(10, 5))

    plt.plot(curve)

    plt.title("Bankroll Curve")

    plt.xlabel("Trade")

    plt.ylabel("Capital")

    plt.grid(True)

    plt.tight_layout()

    plt.savefig("bankroll_curve.png")

# =========================================================
# RANDOM BASELINE
# =========================================================

def random_baseline(y_test):

    pred = np.random.randint(0, 3, size=len(y_test))

    return accuracy_score(y_test, pred)

# =========================================================
# EXPERIMENT
# =========================================================

def run_experiment(series):

    print("\n================================================")
    print("🧪 HMM + XGBoost Research Framework V6")
    print("================================================\n")

    X, y = build_dataset(series)

    X_train, X_test, y_train, y_test = walk_forward_split(X, y)

    model = train_model(X_train, y_train)

    pred = model.predict(X_test)

    prob = model.predict_proba(X_test)

    acc = accuracy_score(y_test, pred)

    ll = log_loss(y_test, prob)

    random_acc = random_baseline(y_test)

    print(f"Samples           : {len(series)}")
    print(f"Train Size        : {len(X_train)}")
    print(f"Test Size         : {len(X_test)}")

    print("\n================ Metrics ================\n")

    print(f"Model Accuracy    : {acc:.4f}")
    print(f"Random Accuracy   : {random_acc:.4f}")
    print(f"Average LogLoss   : {ll:.4f}")

    print("\n============= Significance =============\n")

    print(
        significance_test(
            acc,
            random_acc,
            len(y_test)
        )
    )

    bankroll = BANKROLL_INIT

    curve = []

    for p, actual in zip(pred, y_test):

        if p == actual:
            bankroll += BET_SIZE
        else:
            bankroll -= BET_SIZE

        curve.append(bankroll)

    metrics = risk_metrics(curve)

    print("\n=============== Risk ===================\n")

    print(
        f"Final Return      : "
        f"{metrics['final_return']:.2%}"
    )

    print(
        f"Max Drawdown      : "
        f"{metrics['max_drawdown']:.2%}"
    )

    print(
        f"Volatility        : "
        f"{metrics['volatility']:.4f}"
    )

    print(
        f"Sharpe Ratio      : "
        f"{metrics['sharpe']:.4f}"
    )

    mc = monte_carlo_bankroll(acc)

    print("\n=========== Monte Carlo ================\n")

    print(
        f"Mean Final Capital: "
        f"{mc['mean_final']:.2f}"
    )

    print(
        f"Std Final Capital : "
        f"{mc['std_final']:.2f}"
    )

    print(
        f"Worst Case        : "
        f"{mc['worst']:.2f}"
    )

    print(
        f"Best Case         : "
        f"{mc['best']:.2f}"
    )

    plot_curve(curve)

    print("\n📉 bankroll_curve.png 已生成")

    feature_importance = pd.DataFrame({
        "feature": [f"f{i}" for i in range(X.shape[1])],
        "importance": model.feature_importances_
    })

    feature_importance = feature_importance.sort_values(
        by="importance",
        ascending=False
    )

    feature_importance.to_csv(
        "feature_importance.csv",
        index=False
    )

    print("📊 feature_importance.csv 已生成")

    print("\n================ Conclusion ============\n")

    if acc > random_acc * 1.05:
        print("⚠ 检测到弱非线性结构")
    else:
        print("❌ 更接近随机过程")

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    # 示例数据
    # 实际使用时替换为你的真实颜色序列

    sample = [
        random.choice(COLORS)
        for _ in range(1200)
    ]

    run_experiment(sample)
'''

readme = r'''# HMM + XGBoost Research Framework V6

科研级高噪声离散序列研究框架。

## 功能

- Hidden Markov Model (HMM)
- XGBoost 分类器
- Walk-forward validation
- LogLoss
- Monte Carlo Simulation
- 风险指标
- 显著性检验
- 资金曲线

---

## 安装依赖

```bash
pip install numpy pandas xgboost hmmlearn scikit-learn matplotlib
```

---

## 运行

```bash
python research_v6.py
```

---

## 输出文件

- bankroll_curve.png
- feature_importance.csv

---

## 注意

这是一个统计研究框架，不代表真实存在稳定预测优势。
'''

requirements = """numpy
pandas
matplotlib
scikit-learn
xgboost
hmmlearn
"""

base = Path("/mnt/data")
(base / "research_v6.py").write_text(script, encoding="utf-8")
(base / "README.md").write_text(readme, encoding="utf-8")
(base / "requirements.txt").write_text(requirements, encoding="utf-8")

print("Files generated:")
print("- research_v6.py")
print("- README.md")
print("- requirements.txt")
