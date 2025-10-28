"""
Data Loaders for LEAF Features

从不同来源加载 LEAF 特征：
- MongoDB (analysis_service 的 Step 2 输出)
- JSON 文件
- NPY 文件
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

try:
    from pymongo import MongoClient
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    logging.warning("pymongo not installed, MongoDB功能不可用")

logger = logging.getLogger(__name__)


class MongoDBLEAFLoader:
    """
    从 MongoDB 加载 LEAF 特征

    连接 analysis_service 的 MongoDB，读取 analyze_features[1] 中的 LEAF 特征
    """

    def __init__(
        self,
        mongo_uri: str,
        db_name: str = "sound_analysis",
        collection_name: str = "analyses",
    ):
        """
        初始化 MongoDB 连接

        Args:
            mongo_uri: MongoDB 连接字符串
            db_name: 数据库名称
            collection_name: 集合名称
        """
        if not PYMONGO_AVAILABLE:
            raise ImportError("pymongo is required for MongoDB功能")

        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

        logger.info(f"Connected to MongoDB: {db_name}.{collection_name}")

    def load_domain_features(
        self,
        query: Dict[str, Any],
        max_samples: Optional[int] = None,
    ) -> List[np.ndarray]:
        """
        加载单个域的 LEAF 特征

        Args:
            query: MongoDB 查询条件
            max_samples: 最大样本数

        Returns:
            LEAF 特征列表，每个元素是 (seq_len, 40) 的数组

        Example query:
            {
                "info_features.device_id": "device_001",
                "analysis_status": "completed",
                "analyze_features.1.features_state": "completed"
            }
        """
        # 查询条件：确保有 LEAF 特征
        query.update({
            "analyze_features.1.features_state": "completed"
        })

        # 查询文档
        cursor = self.collection.find(query)

        if max_samples:
            cursor = cursor.limit(max_samples)

        features_list = []

        for doc in cursor:
            try:
                # 获取 Step 2 的 LEAF 特征
                analyze_features = doc.get("analyze_features", [])

                # 找到 Step 2
                step_2 = next(
                    (
                        step
                        for step in analyze_features
                        if step.get("features_step") == 2
                    ),
                    None,
                )

                if not step_2:
                    logger.warning(f"No Step 2 found in doc {doc.get('_id')}")
                    continue

                # 提取 features_data（二维数组）
                features_data = step_2.get("features_data", [])

                if not features_data:
                    logger.warning(
                        f"Empty features_data in doc {doc.get('_id')}"
                    )
                    continue

                # 转换为 numpy 数组
                features = np.array(features_data, dtype=np.float32)

                # 验证形状
                if features.ndim != 2 or features.shape[1] != 40:
                    logger.warning(
                        f"Invalid feature shape {features.shape} "
                        f"in doc {doc.get('_id')}"
                    )
                    continue

                features_list.append(features)

            except Exception as e:
                logger.error(f"Error processing doc {doc.get('_id')}: {e}")
                continue

        logger.info(f"Loaded {len(features_list)} samples from MongoDB")
        return features_list

    def load_dual_domain(
        self,
        domain_a_query: Dict[str, Any],
        domain_b_query: Dict[str, Any],
        max_samples_per_domain: Optional[int] = None,
    ) -> Dict[str, List[np.ndarray]]:
        """
        加载两个域的 LEAF 特征

        Args:
            domain_a_query: Domain A 的查询条件
            domain_b_query: Domain B 的查询条件
            max_samples_per_domain: 每个域的最大样本数

        Returns:
            包含两个域特征的字典
        """
        logger.info("Loading Domain A features...")
        domain_a_features = self.load_domain_features(
            domain_a_query, max_samples_per_domain
        )

        logger.info("Loading Domain B features...")
        domain_b_features = self.load_domain_features(
            domain_b_query, max_samples_per_domain
        )

        return {
            "domain_a": domain_a_features,
            "domain_b": domain_b_features,
        }

    def close(self):
        """关闭 MongoDB 连接"""
        self.client.close()
        logger.info("MongoDB connection closed")


class FileLEAFLoader:
    """
    从文件加载 LEAF 特征

    支持的格式：
    - JSON: 包含 LEAF 特征的 JSON 文件
    - NPY: NumPy 数组文件
    """

    @staticmethod
    def load_from_json(file_path: str) -> List[np.ndarray]:
        """
        从 JSON 文件加载 LEAF 特征

        JSON 格式应该是：
        [
            [[feat1_dim1, feat1_dim2, ...], [feat2_dim1, ...], ...],  # 样本1
            [[feat1_dim1, feat1_dim2, ...], [feat2_dim1, ...], ...],  # 样本2
            ...
        ]

        Args:
            file_path: JSON 文件路径

        Returns:
            LEAF 特征列表
        """
        logger.info(f"Loading features from JSON: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        features_list = []

        for item in data:
            features = np.array(item, dtype=np.float32)

            # 验证形状
            if features.ndim != 2 or features.shape[1] != 40:
                logger.warning(f"Skipping invalid feature shape: {features.shape}")
                continue

            features_list.append(features)

        logger.info(f"Loaded {len(features_list)} samples from JSON")
        return features_list

    @staticmethod
    def load_from_npy(file_path: str) -> List[np.ndarray]:
        """
        从 NPY 文件加载 LEAF 特征

        NPY 文件应该包含一个形状为 (n_samples, seq_len, 40) 的数组

        Args:
            file_path: NPY 文件路径

        Returns:
            LEAF 特征列表
        """
        logger.info(f"Loading features from NPY: {file_path}")

        data = np.load(file_path)

        if data.ndim == 3:
            # (n_samples, seq_len, 40)
            features_list = [data[i] for i in range(len(data))]
        elif data.ndim == 2:
            # (seq_len, 40) - 单个样本
            features_list = [data]
        else:
            raise ValueError(f"Invalid NPY shape: {data.shape}")

        logger.info(f"Loaded {len(features_list)} samples from NPY")
        return features_list

    @staticmethod
    def save_to_npy(features_list: List[np.ndarray], file_path: str):
        """
        保存 LEAF 特征到 NPY 文件

        Args:
            features_list: LEAF 特征列表
            file_path: 输出文件路径
        """
        # 找到最大序列长度
        max_len = max(len(f) for f in features_list)

        # 填充到相同长度
        padded_features = []
        for features in features_list:
            if len(features) < max_len:
                pad_len = max_len - len(features)
                pad = np.zeros((pad_len, 40), dtype=np.float32)
                features = np.vstack([features, pad])
            padded_features.append(features)

        # 堆叠为 3D 数组
        data = np.stack(padded_features, axis=0)

        # 保存
        np.save(file_path, data)
        logger.info(f"Saved {len(features_list)} samples to {file_path}")


if __name__ == "__main__":
    # 测试文件加载器
    print("=== Testing FileLEAFLoader ===")

    # 创建测试数据
    test_features = [np.random.randn(50, 40) for _ in range(10)]

    # 保存到 NPY
    FileLEAFLoader.save_to_npy(test_features, "test_features.npy")

    # 加载 NPY
    loaded_features = FileLEAFLoader.load_from_npy("test_features.npy")
    print(f"Loaded {len(loaded_features)} samples")
    print(f"First sample shape: {loaded_features[0].shape}")

    # 测试 JSON
    print("\n=== Testing JSON Format ===")
    test_data = [feat.tolist() for feat in test_features]

    with open("test_features.json", "w") as f:
        json.dump(test_data, f)

    loaded_json = FileLEAFLoader.load_from_json("test_features.json")
    print(f"Loaded {len(loaded_json)} samples from JSON")

    # 清理测试文件
    import os

    os.remove("test_features.npy")
    os.remove("test_features.json")
    print("\nTest files cleaned up")
