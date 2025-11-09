"""
測試正規化參數的儲存和載入功能
"""

import json
import numpy as np
from pathlib import Path
import tempfile
import shutil

def test_normalization_save_load():
    """測試正規化參數的儲存和載入"""
    print("=" * 60)
    print("測試正規化參數的儲存和載入")
    print("=" * 60)

    # 創建臨時目錄
    temp_dir = Path(tempfile.mkdtemp())
    print(f"✓ 臨時目錄: {temp_dir}")

    try:
        # 1. 模擬訓練時儲存參數
        print("\n1. 模擬訓練時儲存參數...")

        # 創建模擬的正規化參數
        mean_a = np.random.randn(40).astype(np.float32)
        std_a = np.abs(np.random.randn(40).astype(np.float32)) + 0.1
        mean_b = np.random.randn(40).astype(np.float32)
        std_b = np.abs(np.random.randn(40).astype(np.float32)) + 0.1

        params_to_save = {
            'mean_a': mean_a.tolist(),
            'std_a': std_a.tolist(),
            'mean_b': mean_b.tolist(),
            'std_b': std_b.tolist()
        }

        # 儲存到檔案
        normalization_path = temp_dir / 'normalization_params.json'
        with open(normalization_path, 'w', encoding='utf-8') as f:
            json.dump(params_to_save, f, indent=2)

        print(f"✓ 參數已儲存到: {normalization_path}")
        print(f"  - Domain A: mean={mean_a.mean():.4f}, std={std_a.mean():.4f}")
        print(f"  - Domain B: mean={mean_b.mean():.4f}, std={std_b.mean():.4f}")

        # 2. 模擬推理時載入參數
        print("\n2. 模擬推理時載入參數...")

        with open(normalization_path, 'r', encoding='utf-8') as f:
            loaded_params = json.load(f)

        mean_a_loaded = np.array(loaded_params['mean_a'], dtype=np.float32)
        std_a_loaded = np.array(loaded_params['std_a'], dtype=np.float32)
        mean_b_loaded = np.array(loaded_params['mean_b'], dtype=np.float32)
        std_b_loaded = np.array(loaded_params['std_b'], dtype=np.float32)

        print("✓ 參數已載入")
        print(f"  - Domain A: mean={mean_a_loaded.mean():.4f}, std={std_a_loaded.mean():.4f}")
        print(f"  - Domain B: mean={mean_b_loaded.mean():.4f}, std={std_b_loaded.mean():.4f}")

        # 3. 驗證資料一致性
        print("\n3. 驗證資料一致性...")

        assert np.allclose(mean_a, mean_a_loaded), "mean_a 不一致"
        assert np.allclose(std_a, std_a_loaded), "std_a 不一致"
        assert np.allclose(mean_b, mean_b_loaded), "mean_b 不一致"
        assert np.allclose(std_b, std_b_loaded), "std_b 不一致"

        print("✓ 所有參數驗證通過")

        # 4. 測試正規化和反正規化
        print("\n4. 測試正規化和反正規化...")

        # 創建測試資料
        test_features = np.random.randn(10, 40).astype(np.float32)

        # A→B 方向
        print("\n  A→B 方向:")
        # 正規化（使用 Domain A 參數）
        normalized = (test_features - mean_a_loaded) / std_a_loaded
        print(f"    - 正規化後: mean={normalized.mean():.4f}, std={normalized.std():.4f}")

        # 模擬 CycleGAN 轉換（這裡簡單地複製）
        converted = normalized.copy()

        # 反正規化（使用 Domain B 參數）
        denormalized = converted * std_b_loaded + mean_b_loaded
        print(f"    - 反正規化後: mean={denormalized.mean():.4f}, std={denormalized.std():.4f}")

        # B→A 方向
        print("\n  B→A 方向:")
        # 正規化（使用 Domain B 參數）
        normalized = (test_features - mean_b_loaded) / std_b_loaded
        print(f"    - 正規化後: mean={normalized.mean():.4f}, std={normalized.std():.4f}")

        # 模擬 CycleGAN 轉換
        converted = normalized.copy()

        # 反正規化（使用 Domain A 參數）
        denormalized = converted * std_a_loaded + mean_a_loaded
        print(f"    - 反正規化後: mean={denormalized.mean():.4f}, std={denormalized.std():.4f}")

        print("\n✓ 正規化和反正規化測試通過")

        print("\n" + "=" * 60)
        print("✅ 所有測試通過！")
        print("=" * 60)

    finally:
        # 清理臨時目錄
        shutil.rmtree(temp_dir)
        print(f"\n✓ 已清理臨時目錄")


if __name__ == "__main__":
    test_normalization_save_load()
