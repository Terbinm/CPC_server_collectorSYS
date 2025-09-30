# processors/step3_classifier.py - 分類器（目前使用隨機分類）

import numpy as np
from typing import List, Dict, Any
from config import CLASSIFICATION_CONFIG
from utils.logger import logger


class AudioClassifier:
    """音訊分類器"""
    
    def __init__(self):
        """初始化分類器"""
        self.config = CLASSIFICATION_CONFIG
        self.method = self.config['method']
        
        logger.info(f"分類器初始化: method={self.method}")
        
        # 未來可在此載入真實模型
        if self.config['model_path']:
            self._load_model(self.config['model_path'])
    
    def _load_model(self, model_path: str):
        """
        載入分類模型（預留介面）
        
        Args:
            model_path: 模型檔案路徑
        """
        # TODO: 實作真實模型載入
        logger.warning(f"模型載入功能尚未實作: {model_path}")
    
    def classify(self, features_data: List[Dict]) -> Dict[str, Any]:
        """
        對所有切片進行分類
        
        Args:
            features_data: LEAF 特徵資料列表
            
        Returns:
            分類結果字典，包含：
            {
                'predictions': [每個切片的預測結果],
                'summary': {
                    'total_segments': 總切片數,
                    'normal_count': 正常切片數,
                    'abnormal_count': 異常切片數,
                    'normal_percentage': 正常比例,
                    'abnormal_percentage': 異常比例,
                    'final_prediction': 最終判斷結果
                },
                'method': 使用的分類方法
            }
        """
        try:
            logger.info(f"開始分類: {len(features_data)} 個切片")
            
            predictions = []
            
            for feature_data in features_data:
                # 檢查特徵是否有效
                if feature_data.get('feature_vector') is None:
                    prediction = {
                        'segment_id': feature_data.get('segment_id', -1),
                        'prediction': 'unknown',
                        'confidence': 0.0,
                        'error': '特徵無效'
                    }
                else:
                    # 執行分類
                    if self.method == 'random':
                        prediction = self._random_classify(feature_data)
                    else:
                        # 未來可添加其他分類方法
                        prediction = self._random_classify(feature_data)
                
                predictions.append(prediction)
            
            # 統計結果
            summary = self._calculate_summary(predictions)
            
            result = {
                'predictions': predictions,
                'summary': summary,
                'method': self.method
            }
            
            logger.info(f"分類完成: {summary['final_prediction']} "
                       f"(正常: {summary['normal_count']}, 異常: {summary['abnormal_count']})")
            
            return result
            
        except Exception as e:
            logger.error(f"分類失敗: {e}")
            return {
                'predictions': [],
                'summary': {
                    'error': str(e)
                },
                'method': self.method
            }
    
    def _random_classify(self, feature_data: Dict) -> Dict[str, Any]:
        """
        隨機分類（用於測試）
        
        Args:
            feature_data: 特徵資料
            
        Returns:
            預測結果
        """
        # 根據設定的機率隨機分類
        is_normal = np.random.random() < self.config['normal_probability']
        
        prediction = {
            'segment_id': feature_data.get('segment_id', -1),
            'prediction': 'normal' if is_normal else 'abnormal',
            'confidence': np.random.uniform(0.6, 0.95),  # 隨機信心分數
            'method': 'random'
        }
        
        return prediction
    
    def _model_classify(self, feature_data: Dict) -> Dict[str, Any]:
        """
        使用模型進行分類（預留介面）
        
        Args:
            feature_data: 特徵資料
            
        Returns:
            預測結果
        """
        # TODO: 實作真實模型預測
        logger.warning("模型分類功能尚未實作，使用隨機分類")
        return self._random_classify(feature_data)
    
    def _calculate_summary(self, predictions: List[Dict]) -> Dict[str, Any]:
        """
        計算分類結果摘要
        
        Args:
            predictions: 預測結果列表
            
        Returns:
            摘要統計
        """
        total = len(predictions)
        
        if total == 0:
            return {
                'total_segments': 0,
                'normal_count': 0,
                'abnormal_count': 0,
                'unknown_count': 0,
                'normal_percentage': 0.0,
                'abnormal_percentage': 0.0,
                'final_prediction': 'unknown'
            }
        
        # 統計各類別數量
        normal_count = sum(1 for p in predictions if p['prediction'] == 'normal')
        abnormal_count = sum(1 for p in predictions if p['prediction'] == 'abnormal')
        unknown_count = sum(1 for p in predictions if p['prediction'] == 'unknown')
        
        # 計算百分比
        normal_percentage = (normal_count / total) * 100
        abnormal_percentage = (abnormal_count / total) * 100
        
        # 決定最終判斷（以多數為準）
        if abnormal_count > normal_count:
            final_prediction = 'abnormal'
        elif normal_count > abnormal_count:
            final_prediction = 'normal'
        else:
            final_prediction = 'uncertain'
        
        # 計算平均信心度
        avg_confidence = np.mean([p['confidence'] for p in predictions 
                                 if 'confidence' in p])
        
        summary = {
            'total_segments': total,
            'normal_count': normal_count,
            'abnormal_count': abnormal_count,
            'unknown_count': unknown_count,
            'normal_percentage': round(normal_percentage, 2),
            'abnormal_percentage': round(abnormal_percentage, 2),
            'final_prediction': final_prediction,
            'average_confidence': round(float(avg_confidence), 3)
        }
        
        return summary
    
    def set_model(self, model_path: str):
        """
        設定模型路徑（預留介面）
        
        Args:
            model_path: 模型檔案路徑
        """
        self.config['model_path'] = model_path
        self._load_model(model_path)
        logger.info(f"已設定模型: {model_path}")