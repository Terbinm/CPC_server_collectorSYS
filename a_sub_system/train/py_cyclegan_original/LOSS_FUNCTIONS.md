# CycleGAN 損失函數公式（py_cyclegan_original）

來源程式：`a_sub_system/train/py_cyclegan_original/training/losses.py`

---

## 1. Cycle Consistency Loss

對應類別：`CycleLoss`

程式行為：`nn.L1Loss()`（Mean reduction）後再乘上超參數 `lambda_cycle`。

公式：

```math
\mathcal{L}_{\text{cycle}}(x, \hat{x}) = \lambda_{\text{cycle}} \cdot \frac{1}{N} \sum_{i=1}^{N} \left| \hat{x}_i - x_i \right|
```

其中：

- \( x \) 為真實樣本（`real`）
- \( \hat{x} \) 為經過兩次映射後的重建樣本（`reconstructed`）
- \( \lambda_{\text{cycle}} = 10.0 \) 為預設權重

---

## 2. Adversarial Loss（LSGAN）

對應類別：`AdversarialLoss`

程式行為：`nn.MSELoss()` 比對預測結果與「真／假」標籤（`is_real` 影響目標值）。

公式：

```math
\mathcal{L}_{\text{LSGAN}}(p, y) = \frac{1}{N} \sum_{i=1}^{N} \left( p_i - y_i \right)^2,
\quad y_i =
\begin{cases}
1, & \text{若樣本視為真實（is\_real = True）} \\
0, & \text{若樣本視為生成（is\_real = False）}
\end{cases}
```

其中 \( p \) 為鑑別器對輸入樣本的預測。此損失可同時用於優化鑑別器與生成器（生成器期望 `y=1` 以欺騙鑑別器）。

---

## 3. Identity Loss

對應類別：`IdentityLoss`

程式行為：`nn.L1Loss()`（Mean reduction）後再乘上超參數 `lambda_identity`。

公式：

```math
\mathcal{L}_{\text{id}}(x, G(x)) = \lambda_{\text{id}} \cdot \frac{1}{N} \sum_{i=1}^{N} \left| G(x)_i - x_i \right|
```

其中：

- \( x \) 為來源域樣本（`real`）
- \( G(x) \) 為相同生成器在同域上的輸出（`identity`），例如 \( G_{XY}(y) \approx y \)
- \( \lambda_{\text{id}} = 5.0 \) 為預設權重

---

## 4. 總結

- 兩個 L1 類損失（Cycle、Identity）透過不同權重平衡結構與色彩保留。
- LSGAN 以均方誤差穩定對抗訓練，避免傳統 GAN 的梯度消失問題。
- 權重可在 `config.py` 或模型設定中視需求調整，以控制風格轉換與內容保真之取捨。
