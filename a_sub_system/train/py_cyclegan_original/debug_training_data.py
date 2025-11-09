"""
Debug 訓練資料 - 檢查正規化和資料分布
"""

import sys
from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import CONFIG
from data import MongoDBLEAFLoader, LEAFDomainDataset

def main():
    print("=" * 80)
    print("CycleGAN 訓練資料診斷")
    print("=" * 80)

    # 載入配置
    data_config = CONFIG['data']
    mongodb_config = CONFIG['mongodb']

    try:
        # 載入資料
        print("\n1. 載入資料...")
        loader = MongoDBLEAFLoader(
            mongo_uri=mongodb_config['uri'],
            db_name=mongodb_config['database'],
            collection_name=mongodb_config['collection']
        )

        # 載入少量資料測試（限制為 100 筆）
        data = loader.load_dual_domain(
            domain_a_query=data_config['domain_a']['mongo_query'],
            domain_b_query=data_config['domain_b']['mongo_query'],
            max_samples_per_domain=100
        )

        domain_a_features = data['domain_a']
        domain_b_features = data['domain_b']
        loader.close()

        print(f"✓ Domain A: {len(domain_a_features)} 樣本")
        print(f"✓ Domain B: {len(domain_b_features)} 樣本")

        # 2. 分析原始資料統計
        print("\n2. 原始資料統計...")

        # 合併所有樣本
        all_a = np.vstack([f for f in domain_a_features if len(f) > 0])
        all_b = np.vstack([f for f in domain_b_features if len(f) > 0])

        print(f"\nDomain A (原始):")
        print(f"  - Shape: {all_a.shape}")
        print(f"  - Mean: {all_a.mean():.4f}")
        print(f"  - Std: {all_a.std():.4f}")
        print(f"  - Min: {all_a.min():.4f}")
        print(f"  - Max: {all_a.max():.4f}")
        print(f"  - 各維度 Mean 範圍: [{all_a.mean(axis=0).min():.4f}, {all_a.mean(axis=0).max():.4f}]")
        print(f"  - 各維度 Std 範圍: [{all_a.std(axis=0).min():.4f}, {all_a.std(axis=0).max():.4f}]")

        print(f"\nDomain B (原始):")
        print(f"  - Shape: {all_b.shape}")
        print(f"  - Mean: {all_b.mean():.4f}")
        print(f"  - Std: {all_b.std():.4f}")
        print(f"  - Min: {all_b.min():.4f}")
        print(f"  - Max: {all_b.max():.4f}")
        print(f"  - 各維度 Mean 範圍: [{all_b.mean(axis=0).min():.4f}, {all_b.mean(axis=0).max():.4f}]")
        print(f"  - 各維度 Std 範圍: [{all_b.std(axis=0).min():.4f}, {all_b.std(axis=0).max():.4f}]")

        # 3. 測試正規化
        print("\n3. 測試正規化...")

        dataset = LEAFDomainDataset(
            domain_a_features=domain_a_features,
            domain_b_features=domain_b_features,
            normalize=True,
            augment=False,
            max_sequence_length=None
        )

        # 取得正規化參數
        norm_params = dataset.get_normalization_params()

        print(f"\n正規化參數:")
        print(f"  Domain A:")
        print(f"    - Mean: {norm_params['mean_a'].mean():.4f}")
        print(f"    - Std: {norm_params['std_a'].mean():.4f}")
        print(f"  Domain B:")
        print(f"    - Mean: {norm_params['mean_b'].mean():.4f}")
        print(f"    - Std: {norm_params['std_b'].mean():.4f}")

        # 4. 檢查正規化後的資料
        print("\n4. 檢查正規化後的資料...")

        # 取幾個樣本
        samples_to_check = min(10, len(dataset))
        normalized_a_list = []
        normalized_b_list = []

        for i in range(samples_to_check):
            feat_a, feat_b = dataset[i]
            normalized_a_list.append(feat_a.numpy())
            normalized_b_list.append(feat_b.numpy())

        normalized_a = np.vstack(normalized_a_list)
        normalized_b = np.vstack(normalized_b_list)

        print(f"\nDomain A (正規化後):")
        print(f"  - Mean: {normalized_a.mean():.4f}")
        print(f"  - Std: {normalized_a.std():.4f}")
        print(f"  - Min: {normalized_a.min():.4f}")
        print(f"  - Max: {normalized_a.max():.4f}")

        print(f"\nDomain B (正規化後):")
        print(f"  - Mean: {normalized_b.mean():.4f}")
        print(f"  - Std: {normalized_b.std():.4f}")
        print(f"  - Min: {normalized_b.min():.4f}")
        print(f"  - Max: {normalized_b.max():.4f}")

        # 5. 計算 L1 距離
        print("\n5. 計算兩個域之間的距離...")

        # 正規化後的距離
        l1_distance = np.abs(normalized_a - normalized_b).mean()
        l2_distance = np.sqrt(((normalized_a - normalized_b) ** 2).mean())

        print(f"  - L1 距離 (正規化後): {l1_distance:.4f}")
        print(f"  - L2 距離 (正規化後): {l2_distance:.4f}")

        # 原始資料的距離（對齊樣本數）
        min_samples = min(all_a.shape[0], all_b.shape[0])
        l1_distance_raw = np.abs(all_a[:min_samples] - all_b[:min_samples]).mean()
        l2_distance_raw = np.sqrt(((all_a[:min_samples] - all_b[:min_samples]) ** 2).mean())

        print(f"  - L1 距離 (原始): {l1_distance_raw:.4f}")
        print(f"  - L2 距離 (原始): {l2_distance_raw:.4f}")

        # 6. 檢查是否有異常值
        print("\n6. 檢查異常值...")

        # 檢查是否有 NaN 或 Inf
        has_nan_a = np.isnan(all_a).any()
        has_nan_b = np.isnan(all_b).any()
        has_inf_a = np.isinf(all_a).any()
        has_inf_b = np.isinf(all_b).any()

        print(f"  Domain A: NaN={has_nan_a}, Inf={has_inf_a}")
        print(f"  Domain B: NaN={has_nan_b}, Inf={has_inf_b}")

        # 檢查極端值
        threshold = 100
        extreme_a = (np.abs(all_a) > threshold).sum()
        extreme_b = (np.abs(all_b) > threshold).sum()

        print(f"  Domain A: {extreme_a} 個值 > {threshold}")
        print(f"  Domain B: {extreme_b} 個值 > {threshold}")

        # 7. 建議
        print("\n" + "=" * 80)
        print("診斷結果與建議")
        print("=" * 80)

        if l1_distance_raw > 100:
            print("⚠️ 警告: 兩個域的原始資料差異非常大 (L1 > 100)")
            print("   建議: 檢查資料來源是否正確")

        if normalized_a.std() < 0.5 or normalized_a.std() > 2.0:
            print("⚠️ 警告: Domain A 正規化後標準差異常")
            print(f"   當前: {normalized_a.std():.4f}, 預期接近 1.0")

        if normalized_b.std() < 0.5 or normalized_b.std() > 2.0:
            print("⚠️ 警告: Domain B 正規化後標準差異常")
            print(f"   當前: {normalized_b.std():.4f}, 預期接近 1.0")

        if l1_distance > 10:
            print("⚠️ 警告: 正規化後兩個域距離仍然很大 (L1 > 10)")
            print("   建議: 考慮調整 lambda_cycle 權重或使用其他正規化方法")

        if extreme_a > 0 or extreme_b > 0:
            print(f"⚠️ 警告: 發現極端值")
            print(f"   建議: 考慮使用 robust scaler 或 clipping")

        print("\n✓ 診斷完成")

    except Exception as e:
        print(f"\n✗ 錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
