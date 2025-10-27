import os
import torch
import json
import logging
from typing import Dict, List, Any, Tuple
from pathlib import Path
from pl_module import PlMotorModule


class CPCToMAConverter:
    """
    改進版 CPC 到 MA 域轉換器
    支援處理包含額外欄位的輸入資料，並保留 metadata
    """

    def __init__(self, config_path: str = None):
        """
        初始化轉換器

        Args:
            config_path: 配置檔案路徑，如果為 None 則使用預設配置
        """
        self.feature_names = ['PC1', 'PC2', 'PC3', 'PC4', 'PC5', 'PC6', 'PC7', 'PC8', 'PC9']
        self.setup_logging()

        if config_path:
            self.config = self.load_config(config_path)
        else:
            self.config = self.get_default_config()

        self.model = None
        self.device = None

    def setup_logging(self):
        """設定日誌記錄"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('logs/cpc_ma_converter.log', encoding='utf-8')
            ]
        )
        self.logger = logging.getLogger(__name__)

    def load_config(self, config_path: str) -> Dict[str, Any]:
        """
        載入配置檔案

        Args:
            config_path: 配置檔案路徑

        Returns:
            配置字典
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.logger.info(f"✅ 成功載入配置檔案: {config_path}")
            return config
        except Exception as e:
            self.logger.error(f"❌ 載入配置檔案失敗: {e}")
            raise

    def get_default_config(self) -> Dict[str, Any]:
        """
        獲取預設配置

        Returns:
            預設配置字典
        """
        return {
            "model_path": "saves/Batchnorm_version.ckpt",
            "input_file": "INPUT_FILE/dsf.json",
            "output_file": "output/output.json",
            "ma_mean": [-10.458306312561035, 0.13611924648284912, 0.5830099582672119,
                        -0.3114570379257202, 0.0929986760020256, 0.025233712047338486,
                        0.05144552141427994, 0.08644217997789383, -0.0184825100004673],
            "ma_std": [0.38871443271636963, 0.9911067485809326, 0.4081033170223236,
                       0.4781879186630249, 0.5191605091094971, 0.3806946277618408,
                       0.8335772156715393, 0.7095304131507874, 1.1242226362228394],
            "preserve_metadata": True,
            "output_format": "json"
        }

    def load_model(self) -> None:
        """載入模型"""
        try:
            self.logger.info("📥 開始載入模型...")
            model_path = self.config["model_path"]

            if not os.path.exists(model_path):
                raise FileNotFoundError(f"模型檔案不存在: {model_path}")

            self.model = PlMotorModule.load_from_checkpoint(model_path)
            self.model.eval()

            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model.to(self.device)

            self.logger.info(f"✅ 模型載入完成 (設備: {self.device})")

        except Exception as e:
            self.logger.error(f"❌ 模型載入失敗: {e}")
            raise

    def load_input_data(self) -> Tuple[List[Dict[str, Any]], torch.Tensor]:
        """
        載入輸入資料

        Returns:
            Tuple[原始資料列表, CPC特徵張量]
        """
        try:
            input_file = self.config["input_file"]
            self.logger.info(f"📁 載入輸入資料: {input_file}")

            with open(input_file, "r", encoding='utf-8') as f:
                input_data = json.load(f)

            # 提取 PC 特徵
            cpc_features = []
            valid_data = []

            for i, item in enumerate(input_data):
                try:
                    # 檢查是否包含所有必要的 PC 特徵
                    row = [float(item[feat]) for feat in self.feature_names]
                    cpc_features.append(row)
                    valid_data.append(item)
                except (KeyError, ValueError) as e:
                    self.logger.warning(f"⚠️ 跳過第 {i + 1} 筆資料，原因: {e}")
                    continue

            if not cpc_features:
                raise ValueError("未找到有效的 CPC 特徵資料")

            cpc_tensor = torch.tensor(cpc_features, dtype=torch.float32)
            self.logger.info(f"✅ 成功載入 {len(cpc_features)} 筆有效的 CPC 特徵")

            return valid_data, cpc_tensor

        except Exception as e:
            self.logger.error(f"❌ 載入輸入資料失敗: {e}")
            raise

    def normalize_cpc_features(self, cpc_tensor: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        正規化 CPC 特徵

        Args:
            cpc_tensor: CPC 特徵張量

        Returns:
            Tuple[正規化後的張量, 均值, 標準差]
        """
        self.logger.info("🔢 計算 CPC 統計並正規化...")

        cpc_mean = torch.mean(cpc_tensor, dim=0)
        cpc_std = torch.std(cpc_tensor, dim=0)
        cpc_normalized = (cpc_tensor - cpc_mean) / (cpc_std + 1e-5)

        return cpc_normalized, cpc_mean, cpc_std

    def add_position_encoding(self, cpc_normalized: torch.Tensor) -> torch.Tensor:
        """
        添加位置編碼

        Args:
            cpc_normalized: 正規化後的 CPC 特徵

        Returns:
            添加位置編碼後的張量
        """
        self.logger.info("📍 添加位置編碼...")

        position_encoding = torch.linspace(0, 1, len(cpc_normalized)).unsqueeze(1)
        cpc_with_position = torch.cat([cpc_normalized, position_encoding], dim=1).to(self.device)

        return cpc_with_position

    def perform_domain_transfer(self, cpc_with_position: torch.Tensor) -> torch.Tensor:
        """
        執行域轉換

        Args:
            cpc_with_position: 包含位置編碼的 CPC 特徵

        Returns:
            轉換後的 MA 特徵（正規化狀態）
        """
        self.logger.info("🔀 執行 CPC → MA 轉換...")

        with torch.no_grad():
            ma_normalized = self.model.generator_A_to_B(cpc_with_position)

        return ma_normalized

    def denormalize_ma_features(self, ma_normalized: torch.Tensor) -> torch.Tensor:
        """
        反正規化 MA 特徵

        Args:
            ma_normalized: 正規化的 MA 特徵

        Returns:
            反正規化後的 MA 特徵
        """
        self.logger.info("🔄 反正規化為 MA 域...")

        ma_mean = torch.tensor(self.config["ma_mean"], dtype=torch.float32).to(self.device)
        ma_std = torch.tensor(self.config["ma_std"], dtype=torch.float32).to(self.device)

        ma_features = (ma_normalized * (ma_std + 1e-5) + ma_mean).cpu()

        return ma_features

    def format_output(self, original_data: List[Dict[str, Any]], ma_features: torch.Tensor) -> List[Dict[str, Any]]:
        """
        格式化輸出資料

        Args:
            original_data: 原始輸入資料
            ma_features: 轉換後的 MA 特徵

        Returns:
            格式化後的輸出資料
        """
        self.logger.info("📝 格式化輸出...")

        output_data = []
        preserve_metadata = self.config.get("preserve_metadata", True)

        for i, (original_item, ma_feature) in enumerate(zip(original_data, ma_features)):
            # 建立輸出項目
            output_item = {}

            # 如果要保留 metadata，先複製非 PC 欄位
            if preserve_metadata:
                for key, value in original_item.items():
                    if key not in self.feature_names:
                        output_item[key] = value

            # 添加轉換後的 MA 特徵
            for name, value in zip(self.feature_names, ma_feature):
                output_item[name] = float(value.item())

            output_data.append(output_item)

        return output_data

    def save_output(self, output_data: List[Dict[str, Any]]) -> None:
        """
        保存輸出資料

        Args:
            output_data: 要保存的輸出資料
        """
        output_file = self.config["output_file"]
        self.logger.info(f"💾 保存結果到: {output_file}")

        # 確保輸出目錄存在
        output_dir = os.path.dirname(output_file)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # 保存資料
        with open(output_file, "w", encoding='utf-8') as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)

        self.logger.info(f"✅ 轉換完成！")
        self.logger.info(f"📊 成功轉換了 {len(output_data)} 筆特徵")
        self.logger.info(f"📁 輸出檔案: {output_file}")

    def convert(self) -> None:
        """
        執行完整的轉換流程
        """
        try:
            self.logger.info("🔄 開始 CPC → MA 域轉換...")

            # 1. 載入模型
            self.load_model()

            # 2. 載入輸入資料
            original_data, cpc_tensor = self.load_input_data()

            # 3. 正規化 CPC 特徵
            cpc_normalized, cpc_mean, cpc_std = self.normalize_cpc_features(cpc_tensor)

            # 4. 添加位置編碼
            cpc_with_position = self.add_position_encoding(cpc_normalized)

            # 5. 執行域轉換
            ma_normalized = self.perform_domain_transfer(cpc_with_position)

            # 6. 反正規化 MA 特徵
            ma_features = self.denormalize_ma_features(ma_normalized)

            # 7. 格式化輸出
            output_data = self.format_output(original_data, ma_features)

            # 8. 保存結果
            self.save_output(output_data)

        except Exception as e:
            self.logger.error(f"❌ 轉換失敗: {str(e)}")
            raise

    def validate_config(self) -> bool:
        """
        驗證配置檔案

        Returns:
            配置是否有效
        """
        required_keys = ["model_path", "input_file", "output_file", "ma_mean", "ma_std"]

        for key in required_keys:
            if key not in self.config:
                self.logger.error(f"❌ 配置檔案缺少必要參數: {key}")
                return False

        if len(self.config["ma_mean"]) != 9 or len(self.config["ma_std"]) != 9:
            self.logger.error("❌ MA 統計參數必須包含 9 個數值")
            return False

        return True


def main():
    """
    主執行函數
    """
    # 配置檔案路徑 (如果存在的話)
    config_file = "config.json"

    try:
        # 初始化轉換器
        if os.path.exists(config_file):
            converter = CPCToMAConverter(config_file)
        else:
            print("⚠️ 未找到配置檔案，使用預設配置")
            converter = CPCToMAConverter()

        # 驗證配置
        if not converter.validate_config():
            raise ValueError("配置檔案驗證失敗")

        # 執行轉換
        converter.convert()

    except Exception as e:
        print(f"❌ 程式執行失敗: {str(e)}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())