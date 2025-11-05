# CycleGAN 實作指南

## 概觀
CycleGAN 透過循環一致性（cycle-consistency）學習兩個無配對影像域之間的轉換：`G_AB` 將 A 領域影像轉成 B，`G_BA` 將 B 轉成 A，並要求影像經過兩個生成器後能重建
原圖。兩個判別器 `D_B`、`D_A` 以 70×70 PatchGAN 判斷翻譯結果的真實度。

**參考論文：** Jun-Yan Zhu, Taesung Park, Phillip Isola, Alexei A. Efros. “Unpaired Image-to-Image Translation using Cycle-Consistent Adversarial Networks.”
ICCV 2017. [arXiv:1703.10593](https://arxiv.org/abs/1703.10593)

## 建議目錄結構
- `data/`：無配對資料集（例：`horse2zebra/`、`summer2winter/`）
  - `models/`：生成器與判別器定義
  - `scripts/`：訓練與推論腳本
  - `checkpoints/`：模型權重
  - `README.md`：使用說明檔案

    ## 依賴套件
  - Python 3.8+
  - PyTorch ≥ 1.10、torchvision
  - Pillow、numpy、tqdm、tensorboard（可選）

```bash
pip install torch torchvision pillow numpy tqdm tensorboard
```
  ## 模型架構

- 生成器（G_AB, G_BA）：ResNet 風格編碼器–變換器–解碼器。
    - 編碼器：2 個 stride=2 的卷積下採樣區塊。
    - 變換器：影像 128×128 用 6 個 ResNet block；256×256 用 9 個。
    - 解碼器：2 個反卷積（或上採樣卷積）＋輸出 tanh。
- 判別器（D_A, D_B）：70×70 PatchGAN。
    - 5 層卷積，stride 交替為 2/1，除第一層外使用 InstanceNorm。
    - 輸出為每個 patch 的真偽機率矩陣。

  ## 損失函數

- 對抗損失（LSGAN）
  L_GAN(G_AB, D_B) = E_{b~p(b)}[(D_B(b)-1)^2] + E_{a~p(a)}[(D_B(G_AB(a)))^2]
  另一個域對應 G_BA, D_A。
- 循環一致損失
  L_cyc = E_a[‖G_BA(G_AB(a)) - a‖_1] + E_b[‖G_AB(G_BA(b)) - b‖_1]
- 身分損失（選用）
  L_id = E_b[‖G_AB(b) - b‖_1] + E_a[‖G_BA(a) - a‖_1]
  可維持顏色與結構。

  總損失：

  L = L_GAN(G_AB,D_B) + L_GAN(G_BA,D_A)
      + λ_cyc * L_cyc + λ_id * L_id

  常用權重：λ_cyc = 10，λ_id = 0（若需保色可設為 0.5 * λ_cyc）。

  ## 訓練流程

1. 資料載入： 將 A、B 域資料配成無對應批次，先縮放（例 256×256），再隨機裁切、水平翻轉。
2. 前向傳遞：
    - fake_B = G_AB(A_batch)，recon_A = G_BA(fake_B)
    - fake_A = G_BA(B_batch)，recon_B = G_AB(fake_A)
    - 若使用身分損失：idt_B = G_AB(B_batch)，idt_A = G_BA(A_batch)
3. 更新生成器：
    - 計算對抗、循環、一致（身分）損失。
    - 反向傳遞並更新生成器共享最佳化器（如 Adam）。
4. 更新判別器：
    - 以真實樣本對 1、生成樣本（detach）對 0。
    - 分別更新 D_A、D_B。
5. 學習率衰減：
    - 前 100 epoch 使用固定 LR（約 2e-4）。
    - 之後 100 epoch 線性遞減至 0。
6. 影像緩衝： 建議使用大小 50 的歷史影像池，更新判別器時從池中取樣以穩定訓練。
7. 紀錄： 定期輸出翻譯樣本，使用 TensorBoard 追蹤損失。

   ## 重要程式片段

   ### ResNet 生成器區塊

   class ResnetBlock(nn.Module):
       def __init__(self, dim):
           super().__init__()
           self.conv_block = nn.Sequential(
               nn.ReflectionPad2d(1),
               nn.Conv2d(dim, dim, 3),
               nn.InstanceNorm2d(dim),
               nn.ReLU(True),
               nn.ReflectionPad2d(1),
               nn.Conv2d(dim, dim, 3),
               nn.InstanceNorm2d(dim)
           )

       def forward(self, x):
           return x + self.conv_block(x)

### PatchGAN 判別器

   class NLayerDiscriminator(nn.Module):
       def __init__(self, in_channels=3, ndf=64, n_layers=3):
           super().__init__()
           kw = 4
           padw = 1
           sequence = [
               nn.Conv2d(in_channels, ndf, kw, stride=2, padding=padw),
               nn.LeakyReLU(0.2, True)
           ]
           nf_mult = nf_mult_prev = 1
           for n in range(1, n_layers):
               nf_mult_prev = nf_mult
               nf_mult = min(2 ** n, 8)
               sequence += [
                   nn.Conv2d(ndf * nf_mult_prev, ndf * nf_mult, kw,
                             stride=2, padding=padw),
                   nn.InstanceNorm2d(ndf * nf_mult),
                   nn.LeakyReLU(0.2, True),
               ]
           sequence += [
               nn.Conv2d(ndf * nf_mult, 1, kw, stride=1, padding=padw)
           ]
           self.model = nn.Sequential(*sequence)

       def forward(self, x):
           return self.model(x)

## 訓練腳本骨架

   for epoch in range(num_epochs):
       for batch in dataloader:
           real_A, real_B = batch['A'].to(device), batch['B'].to(device)
           fake_B = G_AB(real_A)
           fake_A = G_BA(real_B)
           rec_A = G_BA(fake_B)
           rec_B = G_AB(fake_A)

           loss_G = (gan_loss(D_B(fake_B), True)
                     + gan_loss(D_A(fake_A), True)
                     + lambda_cyc * (l1(rec_A, real_A) + l1(rec_B, real_B))
                     + lambda_id * (l1(G_AB(real_B), real_B) + l1(G_BA(real_A), real_A)))
           optim_G.zero_grad()
           loss_G.backward()
           optim_G.step()

           loss_D_B = (gan_loss(D_B(real_B), True)
                       + gan_loss(D_B(fake_B.detach()), False)) * 0.5
           optim_D_B.zero_grad()
           loss_D_B.backward()
           optim_D_B.step()

           loss_D_A = (gan_loss(D_A(real_A), True)
                       + gan_loss(D_A(fake_A.detach()), False)) * 0.5
           optim_D_A.zero_grad()
           loss_D_A.backward()
           optim_D_A.step()

## 資料集

- 作者提供的無配對資料：horse2zebra、apple2orange、summer2winter_yosemite 等，可透過 download_cyclegan_dataset.sh 取得。
- 先縮放至 286×286，再隨機裁成 256×256，並以 0.5 機率水平翻轉。
- 256×256 影像常用 batch size = 1 或 2。

## 超參數

- 最佳化器：Adam（β1=0.5, β2=0.999），學習率 2e-4。
- 正規化：InstanceNorm。
- 權重初始化：均值 0、標準差 0.02 的正態分佈。
- 訓練週期：200（前 100 固定 LR，後 100 線性下降）。
- 損失權重：λ_cyc=10，λ_id=0 或 5。

## 評估方式

- 質性： 儲存翻譯與循環重建圖。
- 量化： 視任務可用 FID、分類準確率或下游指標。
- 人工評估： 使用者實驗能更貼近感知品質。

## 實務技巧

- 身分損失有助於顏色保持（如照片 ↔ 畫作）。
- 影像緩衝（Image Pool）能避免判別器震盪。
- 高解析度（>512）可考慮多尺度判別器與更多 ResNet block。
- 混合精度 (AMP) 在新 GPU 上可提高吞吐量。
- 續訓時應依照進度調整學習率排程。

## Citation

  @inproceedings{zhu2017unpaired,
    title={Unpaired Image-to-Image Translation using Cycle-Consistent Adversarial Networks},
    author={Zhu, Jun-Yan and Park, Taesung and Isola, Phillip and Efros, Alexei A},
    booktitle={ICCV},
    year={2017}
  }


後續建議：
1. 選定兩個目標領域並整理無配對資料集。
2. 依上述結構實作生成器、判別器與訓練流程。
3. 先跑少量 epoch 驗證損失趨勢與輸出品質，再展開完整訓練。
