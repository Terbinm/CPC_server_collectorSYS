# train_rf_model.py - 訓練隨機森林分類模型

import os
import sys
import numpy as np
import pickle
import json
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from pathlib import Path

# 機器學習相關
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.metrics import (
    classification_report, 
    confusion_matrix, 
    accuracy_score,
    precision_recall_fscore_support,
    roc_auc_score,
    roc_curve
)
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt
import seaborn as sns

# MongoDB
from pymongo import MongoClient

# 日誌
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelConfig:
    """模型訓練配置"""
    
    # MongoDB 配置
    MONGODB_CONFIG = {
        'host': 'localhost',
        'port': 27020,
        'username': 'web_ui',
        'password': 'hod2iddfsgsrl',
        'database': 'web_db',
        'collection': 'recordings'
    }
    
    # 特徵配置
    FEATURE_CONFIG = {
        'feature_dim': 40,  # LEAF 特徵維度
        'normalize': True,  # 是否標準化特徵
        'aggregation': 'mean'  # 特徵聚合方式：mean, max, median, all
    }
    
    # 模型配置
    MODEL_CONFIG = {
        'model_type': 'random_forest',
        'random_state': 42,
        
        # 隨機森林參數
        'rf_params': {
            'n_estimators': 100,
            'max_depth': None,
            'min_samples_split': 2,
            'min_samples_leaf': 1,
            'max_features': 'sqrt',
            'n_jobs': -1,
            'random_state': 42,
            'class_weight': 'balanced'  # 處理類別不平衡
        },
        
        # 網格搜尋參數（可選）
        'grid_search': False,
        'grid_params': {
            'n_estimators': [50, 100, 200],
            'max_depth': [None, 10, 20, 30],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4]
        }
    }
    
    # 訓練配置
    TRAINING_CONFIG = {
        'test_size': 0.2,
        'val_size': 0.1,  # 從訓練集中分出驗證集
        'cross_validation': True,
        'cv_folds': 5,
        'random_state': 42
    }
    
    # 輸出配置
    OUTPUT_CONFIG = {
        'model_dir': 'models',
        'model_filename': 'rf_classifier.pkl',
        'scaler_filename': 'feature_scaler.pkl',
        'metadata_filename': 'model_metadata.json',
        'report_dir': 'training_reports',
        'plot_confusion_matrix': True,
        'plot_feature_importance': True,
        'plot_roc_curve': True
    }


class DataLoader:
    """資料載入器"""
    
    def __init__(self, mongodb_config: Dict):
        """初始化 MongoDB 連接"""
        self.config = mongodb_config
        self.mongo_client = None
        self.collection = None
        self._connect()
    
    def _connect(self):
        """建立 MongoDB 連接"""
        try:
            connection_string = (
                f"mongodb://{self.config['username']}:{self.config['password']}"
                f"@{self.config['host']}:{self.config['port']}/admin"
            )
            self.mongo_client = MongoClient(connection_string)
            db = self.mongo_client[self.config['database']]
            self.collection = db[self.config['collection']]
            
            # 測試連接
            self.mongo_client.admin.command('ping')
            logger.info("✓ MongoDB 連接成功")
            
        except Exception as e:
            logger.error(f"✗ MongoDB 連接失敗: {e}")
            raise
    
    def load_data(self, aggregation: str = 'mean') -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        從 MongoDB 載入訓練資料
        
        Args:
            aggregation: 特徵聚合方式 (mean, max, median, all)
        
        Returns:
            (features, labels, analyze_uuids)
        """
        logger.info("開始載入訓練資料...")
        
        # 查詢已完成分析的記錄
        query = {
            'current_step': 4,  # 已完成所有步驟
            'analysis_status': 'completed',
            'info_features.label': {'$exists': True, '$ne': 'unknown'}
        }
        
        records = list(self.collection.find(query))
        logger.info(f"找到 {len(records)} 筆完整記錄")
        
        if not records:
            raise ValueError("沒有找到可用的訓練資料")
        
        features_list = []
        labels_list = []
        uuid_list = []
        
        for record in records:
            try:
                # 提取標籤
                label = record['info_features']['label']
                
                # 提取 LEAF 特徵
                analyze_features = record.get('analyze_features', [])
                leaf_features = None
                
                # 找到 LEAF 特徵步驟
                for step in analyze_features:
                    if step.get('features_step') == 2 and step.get('features_name') == 'LEAF Features':
                        leaf_features = step.get('features_data', [])
                        break
                
                if not leaf_features:
                    logger.warning(f"記錄 {record['AnalyzeUUID']} 缺少 LEAF 特徵")
                    continue
                
                # 提取特徵向量
                segment_features = []
                for segment in leaf_features:
                    feature_vector = segment
                    if feature_vector is not None and len(feature_vector) > 0:
                        segment_features.append(feature_vector)
                
                if not segment_features:
                    logger.warning(f"記錄 {record['AnalyzeUUID']} 特徵向量為空")
                    continue
                
                # 聚合特徵
                segment_features = np.array(segment_features)
                aggregated_feature = self._aggregate_features(segment_features, aggregation)
                
                features_list.append(aggregated_feature)
                labels_list.append(label)
                uuid_list.append(record['AnalyzeUUID'])
                
            except Exception as e:
                logger.error(f"處理記錄失敗 {record.get('AnalyzeUUID', 'UNKNOWN')}: {e}")
                continue
        
        logger.info(f"成功載入 {len(features_list)} 筆訓練資料")
        
        # 轉換為 numpy 陣列
        features = np.array(features_list)
        labels = np.array(labels_list)
        
        # 統計標籤分布
        unique, counts = np.unique(labels, return_counts=True)
        logger.info(f"\n標籤分布:")
        for label, count in zip(unique, counts):
            logger.info(f"  {label}: {count} ({count/len(labels)*100:.2f}%)")
        
        return features, labels, uuid_list
    
    def _aggregate_features(self, features: np.ndarray, method: str) -> np.ndarray:
        """
        聚合多個切片的特徵
        
        Args:
            features: (n_segments, feature_dim)
            method: 聚合方式
        
        Returns:
            聚合後的特徵向量
        """
        if method == 'mean':
            return np.mean(features, axis=0)
        elif method == 'max':
            return np.max(features, axis=0)
        elif method == 'median':
            return np.median(features, axis=0)
        elif method == 'all':
            # 使用多種統計量
            mean_feat = np.mean(features, axis=0)
            std_feat = np.std(features, axis=0)
            max_feat = np.max(features, axis=0)
            min_feat = np.min(features, axis=0)
            return np.concatenate([mean_feat, std_feat, max_feat, min_feat])
        else:
            raise ValueError(f"不支援的聚合方式: {method}")
    
    def close(self):
        """關閉連接"""
        if self.mongo_client:
            self.mongo_client.close()
            logger.info("MongoDB 連接已關閉")


class ModelTrainer:
    """模型訓練器"""
    
    def __init__(self):
        """初始化訓練器"""
        self.model = None
        self.scaler = None
        self.label_encoder = {'normal': 0, 'abnormal': 1}
        self.label_decoder = {0: 'normal', 1: 'abnormal'}
        
        # 訓練歷史
        self.training_history = {
            'train_scores': [],
            'val_scores': [],
            'cv_scores': []
        }
    
    def prepare_data(self, features: np.ndarray, labels: np.ndarray, 
                     normalize: bool = True) -> Tuple:
        """
        準備訓練資料
        
        Args:
            features: 特徵矩陣
            labels: 標籤陣列
            normalize: 是否標準化
        
        Returns:
            (X_train, X_val, X_test, y_train, y_val, y_test)
        """
        logger.info("準備訓練資料...")
        
        # 編碼標籤
        y_encoded = np.array([self.label_encoder[label] for label in labels])
        
        # 分割資料集：先分出測試集
        X_temp, X_test, y_temp, y_test = train_test_split(
            features, y_encoded,
            test_size=ModelConfig.TRAINING_CONFIG['test_size'],
            random_state=ModelConfig.TRAINING_CONFIG['random_state'],
            stratify=y_encoded
        )
        
        # 再從剩餘資料中分出驗證集
        val_size = ModelConfig.TRAINING_CONFIG['val_size']
        if val_size > 0:
            X_train, X_val, y_train, y_val = train_test_split(
                X_temp, y_temp,
                test_size=val_size / (1 - ModelConfig.TRAINING_CONFIG['test_size']),
                random_state=ModelConfig.TRAINING_CONFIG['random_state'],
                stratify=y_temp
            )
        else:
            X_train, X_val, y_train, y_val = X_temp, None, y_temp, None
        
        # 標準化特徵
        if normalize:
            logger.info("標準化特徵...")
            self.scaler = StandardScaler()
            X_train = self.scaler.fit_transform(X_train)
            X_test = self.scaler.transform(X_test)
            if X_val is not None:
                X_val = self.scaler.transform(X_val)
        
        logger.info(f"訓練集: {X_train.shape}")
        logger.info(f"驗證集: {X_val.shape if X_val is not None else 'None'}")
        logger.info(f"測試集: {X_test.shape}")
        
        return X_train, X_val, X_test, y_train, y_val, y_test
    
    def train_model(self, X_train: np.ndarray, y_train: np.ndarray,
                   X_val: Optional[np.ndarray] = None,
                   y_val: Optional[np.ndarray] = None) -> RandomForestClassifier:
        """
        訓練隨機森林模型
        
        Args:
            X_train: 訓練特徵
            y_train: 訓練標籤
            X_val: 驗證特徵（可選）
            y_val: 驗證標籤（可選）
        
        Returns:
            訓練好的模型
        """
        logger.info("=" * 60)
        logger.info("開始訓練隨機森林模型")
        logger.info("=" * 60)
        
        model_config = ModelConfig.MODEL_CONFIG
        
        if model_config['grid_search']:
            # 使用網格搜尋
            logger.info("使用網格搜尋尋找最佳參數...")
            self.model = self._grid_search(X_train, y_train)
        else:
            # 使用預設參數
            logger.info("使用預設參數訓練模型...")
            self.model = RandomForestClassifier(**model_config['rf_params'])
            self.model.fit(X_train, y_train)
        
        # 訓練集評估
        train_score = self.model.score(X_train, y_train)
        self.training_history['train_scores'].append(train_score)
        logger.info(f"訓練集準確率: {train_score:.4f}")
        
        # 驗證集評估
        if X_val is not None:
            val_score = self.model.score(X_val, y_val)
            self.training_history['val_scores'].append(val_score)
            logger.info(f"驗證集準確率: {val_score:.4f}")
        
        # 交叉驗證
        if ModelConfig.TRAINING_CONFIG['cross_validation']:
            logger.info("\n執行交叉驗證...")
            cv_scores = cross_val_score(
                self.model, X_train, y_train,
                cv=ModelConfig.TRAINING_CONFIG['cv_folds'],
                n_jobs=-1
            )
            self.training_history['cv_scores'] = cv_scores.tolist()
            logger.info(f"交叉驗證分數: {cv_scores}")
            logger.info(f"平均分數: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
        
        logger.info("\n✓ 模型訓練完成")
        return self.model
    
    def _grid_search(self, X_train: np.ndarray, y_train: np.ndarray) -> RandomForestClassifier:
        """
        網格搜尋最佳參數
        
        Args:
            X_train: 訓練特徵
            y_train: 訓練標籤
        
        Returns:
            最佳模型
        """
        base_params = ModelConfig.MODEL_CONFIG['rf_params'].copy()
        grid_params = ModelConfig.MODEL_CONFIG['grid_params']
        
        # 移除 grid_params 中的參數以避免重複
        for key in grid_params.keys():
            base_params.pop(key, None)
        
        rf = RandomForestClassifier(**base_params)
        
        grid_search = GridSearchCV(
            rf, grid_params,
            cv=ModelConfig.TRAINING_CONFIG['cv_folds'],
            n_jobs=-1,
            verbose=2,
            scoring='accuracy'
        )
        
        grid_search.fit(X_train, y_train)
        
        logger.info(f"\n最佳參數: {grid_search.best_params_}")
        logger.info(f"最佳分數: {grid_search.best_score_:.4f}")
        
        return grid_search.best_estimator_
    
    def evaluate_model(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict:
        """
        評估模型效能
        
        Args:
            X_test: 測試特徵
            y_test: 測試標籤
        
        Returns:
            評估結果字典
        """
        logger.info("\n" + "=" * 60)
        logger.info("模型評估")
        logger.info("=" * 60)
        
        # 預測
        y_pred = self.model.predict(X_test)
        y_pred_proba = self.model.predict_proba(X_test)
        
        # 計算各項指標
        accuracy = accuracy_score(y_test, y_pred)
        precision_per_class, recall_per_class, f1_per_class, support_per_class = precision_recall_fscore_support(
            y_test, y_pred, average=None
        )
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_test, y_pred, average='binary'
        )

        # 混淆矩陣
        cm = confusion_matrix(y_test, y_pred)
        
        # ROC-AUC
        try:
            auc = roc_auc_score(y_test, y_pred_proba[:, 1])
        except:
            auc = None
        
        # 顯示結果
        logger.info(f"\n測試集準確率: {accuracy:.4f}")
        logger.info(f"精確率 (Precision): {precision:.4f}")
        logger.info(f"召回率 (Recall): {recall:.4f}")
        logger.info(f"F1 分數: {f1:.4f}")
        if auc is not None:
            logger.info(f"ROC-AUC: {auc:.4f}")
        
        logger.info(f"\n混淆矩陣:")
        logger.info(f"              預測 Normal  預測 Abnormal")
        logger.info(f"實際 Normal      {cm[0][0]:6d}      {cm[0][1]:6d}")
        logger.info(f"實際 Abnormal    {cm[1][0]:6d}      {cm[1][1]:6d}")
        
        # 分類報告
        logger.info(f"\n詳細分類報告:")
        target_names = ['normal', 'abnormal']
        logger.info("\n" + classification_report(y_test, y_pred, target_names=target_names))
        
        # 組織評估結果
        evaluation = {
            'accuracy': float(accuracy),
            'precision': float(precision),
            'recall': float(recall),
            'f1_score': float(f1),
            'auc': float(auc) if auc is not None else None,
            'confusion_matrix': cm.tolist(),
            'support': support_per_class.tolist(),  # ✓ 使用 support_per_class
            'precision_per_class': precision_per_class.tolist(),  # 新增：每個類別的詳細資訊
            'recall_per_class': recall_per_class.tolist(),
            'f1_per_class': f1_per_class.tolist(),
            'classification_report': classification_report(
                y_test, y_pred, target_names=target_names, output_dict=True
            )
        }

        return evaluation
    
    def get_feature_importance(self) -> np.ndarray:
        """取得特徵重要性"""
        if self.model is None:
            raise ValueError("模型尚未訓練")
        return self.model.feature_importances_
    
    def save_model(self, output_dir: str):
        """
        儲存模型
        
        Args:
            output_dir: 輸出目錄
        """
        os.makedirs(output_dir, exist_ok=True)
        
        config = ModelConfig.OUTPUT_CONFIG
        
        # 儲存模型
        model_path = os.path.join(output_dir, config['model_filename'])
        with open(model_path, 'wb') as f:
            pickle.dump(self.model, f)
        logger.info(f"✓ 模型已儲存: {model_path}")
        
        # 儲存 Scaler
        if self.scaler is not None:
            scaler_path = os.path.join(output_dir, config['scaler_filename'])
            with open(scaler_path, 'wb') as f:
                pickle.dump(self.scaler, f)
            logger.info(f"✓ Scaler 已儲存: {scaler_path}")
        
        # 儲存元資料
        metadata = {
            'model_type': 'RandomForestClassifier',
            'feature_dim': ModelConfig.FEATURE_CONFIG['feature_dim'],
            'aggregation': ModelConfig.FEATURE_CONFIG['aggregation'],
            'normalize': ModelConfig.FEATURE_CONFIG['normalize'],
            'label_encoder': self.label_encoder,
            'label_decoder': self.label_decoder,
            'training_date': datetime.now().isoformat(),
            'model_params': ModelConfig.MODEL_CONFIG['rf_params'],
            'training_history': self.training_history
        }
        
        metadata_path = os.path.join(output_dir, config['metadata_filename'])
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ 元資料已儲存: {metadata_path}")


class ResultVisualizer:
    """結果視覺化"""
    
    @staticmethod
    def plot_confusion_matrix(cm: np.ndarray, output_path: str):
        """繪製混淆矩陣"""
        plt.figure(figsize=(8, 6))
        sns.heatmap(
            cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=['Normal', 'Abnormal'],
            yticklabels=['Normal', 'Abnormal']
        )
        plt.title('Confusion Matrix')
        plt.ylabel('True Label')
        plt.xlabel('Predicted Label')
        plt.tight_layout()
        plt.savefig(output_path, dpi=300)
        plt.close()
        logger.info(f"✓ 混淆矩陣已儲存: {output_path}")
    
    @staticmethod
    def plot_feature_importance(importance: np.ndarray, output_path: str, top_n: int = 20):
        """繪製特徵重要性"""
        indices = np.argsort(importance)[::-1][:top_n]
        
        plt.figure(figsize=(10, 6))
        plt.title(f'Top {top_n} Feature Importance')
        plt.bar(range(top_n), importance[indices])
        plt.xlabel('Feature Index')
        plt.ylabel('Importance')
        plt.xticks(range(top_n), indices)
        plt.tight_layout()
        plt.savefig(output_path, dpi=300)
        plt.close()
        logger.info(f"✓ 特徵重要性圖已儲存: {output_path}")
    
    @staticmethod
    def plot_roc_curve(y_test: np.ndarray, y_pred_proba: np.ndarray, output_path: str):
        """繪製 ROC 曲線"""
        fpr, tpr, _ = roc_curve(y_test, y_pred_proba[:, 1])
        auc = roc_auc_score(y_test, y_pred_proba[:, 1])
        
        plt.figure(figsize=(8, 6))
        plt.plot(fpr, tpr, label=f'ROC Curve (AUC = {auc:.3f})')
        plt.plot([0, 1], [0, 1], 'k--', label='Random Classifier')
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('ROC Curve')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_path, dpi=300)
        plt.close()
        logger.info(f"✓ ROC 曲線已儲存: {output_path}")


def main():
    """主程式"""
    print("""
╔══════════════════════════════════════════════════════════╗
║         隨機森林分類器訓練工具 v1.0                          ║
║                                                          ║
║  功能:                                                    ║
║  1. 從 MongoDB 載入 LEAF 特徵                              ║
║  2. 訓練隨機森林分類模型                                     ║
║  3. 評估模型效能並視覺化結果                                  ║
║  4. 儲存模型供分析服務使用                                    ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    try:
        # 1. 載入資料
        logger.info("\n步驟 1: 載入訓練資料")
        logger.info("-" * 60)
        data_loader = DataLoader(ModelConfig.MONGODB_CONFIG)
        features, labels, uuids = data_loader.load_data(
            aggregation=ModelConfig.FEATURE_CONFIG['aggregation']
        )
        data_loader.close()
        
        # 2. 準備資料
        logger.info("\n步驟 2: 準備訓練資料")
        logger.info("-" * 60)
        trainer = ModelTrainer()
        X_train, X_val, X_test, y_train, y_val, y_test = trainer.prepare_data(
            features, labels,
            normalize=ModelConfig.FEATURE_CONFIG['normalize']
        )
        
        # 3. 訓練模型
        logger.info("\n步驟 3: 訓練模型")
        logger.info("-" * 60)
        model = trainer.train_model(X_train, y_train, X_val, y_val)
        
        # 4. 評估模型
        logger.info("\n步驟 4: 評估模型")
        logger.info("-" * 60)
        evaluation = trainer.evaluate_model(X_test, y_test)
        
        # 5. 儲存模型
        logger.info("\n步驟 5: 儲存模型")
        logger.info("-" * 60)
        output_dir = ModelConfig.OUTPUT_CONFIG['model_dir']
        trainer.save_model(output_dir)
        
        # 6. 生成視覺化
        if ModelConfig.OUTPUT_CONFIG['plot_confusion_matrix']:
            logger.info("\n步驟 6: 生成視覺化")
            logger.info("-" * 60)
            report_dir = ModelConfig.OUTPUT_CONFIG['report_dir']
            os.makedirs(report_dir, exist_ok=True)
            
            # 混淆矩陣
            cm_path = os.path.join(report_dir, 'confusion_matrix.png')
            ResultVisualizer.plot_confusion_matrix(
                np.array(evaluation['confusion_matrix']), cm_path
            )
            
            # 特徵重要性
            if ModelConfig.OUTPUT_CONFIG['plot_feature_importance']:
                importance = trainer.get_feature_importance()
                fi_path = os.path.join(report_dir, 'feature_importance.png')
                ResultVisualizer.plot_feature_importance(importance, fi_path)
            
            # ROC 曲線
            if ModelConfig.OUTPUT_CONFIG['plot_roc_curve'] and evaluation['auc']:
                y_pred_proba = model.predict_proba(X_test)
                roc_path = os.path.join(report_dir, 'roc_curve.png')
                ResultVisualizer.plot_roc_curve(y_test, y_pred_proba, roc_path)
        
        # 7. 儲存評估報告
        report_path = os.path.join(report_dir, 'evaluation_report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(evaluation, f, indent=2, ensure_ascii=False)
        logger.info(f"✓ 評估報告已儲存: {report_path}")
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ 訓練完成！")
        logger.info("=" * 60)
        logger.info(f"\n模型檔案位置: {output_dir}")
        logger.info(f"報告位置: {report_dir}")
        logger.info(f"\n請更新 analysis_service/config.py 中的模型路徑:")
        logger.info(f"  'model_path': '{os.path.abspath(os.path.join(output_dir, ModelConfig.OUTPUT_CONFIG['model_filename']))}'")
        
    except KeyboardInterrupt:
        logger.info("\n\n訓練被使用者中斷")
    except Exception as e:
        logger.error(f"\n訓練過程發生錯誤: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
