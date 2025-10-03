#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分類器狀態診斷腳本
檢查系統目前是使用 RF 模型還是隨機分類
"""

import sys
import os
from pathlib import Path
from pymongo import MongoClient
import json


# 顏色輸出
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def print_header(text):
    print(f"\n{Colors.BLUE}{'=' * 70}{Colors.END}")
    print(f"{Colors.BLUE}{text.center(70)}{Colors.END}")
    print(f"{Colors.BLUE}{'=' * 70}{Colors.END}\n")


def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_warning(text):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def check_config_file():
    """檢查配置檔案"""
    print_header("步驟 1: 檢查配置檔案")

    config_path = Path('a_sub_system/analysis_service/config.py')

    if not config_path.exists():
        print_error(f"配置檔案不存在: {config_path}")
        return None

    print_success(f"配置檔案存在: {config_path}")

    # 讀取配置內容
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 檢查 method
    if "'method': 'rf_model'" in content or '"method": "rf_model"' in content:
        print_success("配置中 method = 'rf_model'")
        method = 'rf_model'
    elif "'method': 'random'" in content or '"method": "random"' in content:
        print_warning("配置中 method = 'random' (仍在使用隨機分類!)")
        method = 'random'
    else:
        print_warning("無法確定 method 設定")
        method = 'unknown'

    # 檢查 model_path
    import re
    model_path_match = re.search(r"'model_path':\s*'([^']*)'", content)
    if model_path_match:
        model_path = model_path_match.group(1)
        print_success(f"model_path = '{model_path}'")

        # 檢查路徑是否存在
        if model_path and model_path != 'None':
            if Path(model_path).exists():
                print_success(f"模型目錄存在")

                # 檢查模型檔案
                model_file = Path(model_path) / 'rf_classifier.pkl'
                if model_file.exists():
                    print_success(f"模型檔案存在: rf_classifier.pkl")
                else:
                    print_error(f"模型檔案不存在: rf_classifier.pkl")
            else:
                print_error(f"模型目錄不存在: {model_path}")
        else:
            print_warning("model_path 未設定或為 None")
    else:
        print_warning("配置中找不到 model_path 設定")

    return {
        'method': method,
        'config_path': str(config_path)
    }


def check_classifier_file():
    """檢查分類器檔案"""
    print_header("步驟 2: 檢查分類器檔案")

    classifier_path = Path('a_sub_system/analysis_service/processors/step3_classifier.py')

    if not classifier_path.exists():
        print_error(f"分類器檔案不存在: {classifier_path}")
        return None

    print_success(f"分類器檔案存在: {classifier_path}")

    # 讀取內容並檢查是否為更新版
    with open(classifier_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if '_load_model' in content and 'rf_classifier.pkl' in content:
        print_success("使用更新版分類器 (支援 RF 模型)")
        classifier_type = 'updated'
    else:
        print_warning("使用舊版分類器 (僅支援隨機分類)")
        classifier_type = 'old'

    return {
        'classifier_type': classifier_type,
        'classifier_path': str(classifier_path)
    }


def check_recent_predictions():
    """檢查最近的預測結果"""
    print_header("步驟 3: 檢查最近的預測結果")

    try:
        # 連接 MongoDB
        client = MongoClient("mongodb://web_ui:hod2iddfsgsrl@localhost:27020/admin")
        db = client['web_db']
        collection = db['recordings']

        print_success("MongoDB 連接成功")

        # 查詢最近 5 筆已完成的記錄
        records = list(collection.find(
            {'current_step': 4, 'analysis_status': 'completed'},
            sort=[('updated_at', -1)]
        ).limit(5))

        if not records:
            print_warning("沒有找到已完成的記錄")
            return None

        print_success(f"找到 {len(records)} 筆最近的記錄\n")

        results = []
        for i, record in enumerate(records, 1):
            analyze_uuid = record.get('AnalyzeUUID', 'UNKNOWN')
            updated_at = record.get('updated_at', 'UNKNOWN')

            print(f"記錄 {i}: {analyze_uuid}")
            print(f"  更新時間: {updated_at}")

            # 檢查分類結果
            analyze_features = record.get('analyze_features', [])
            if len(analyze_features) >= 3:
                classification = analyze_features[2]
                classification_results = classification.get('classification_results', {})
                method = classification_results.get('method', 'unknown')
                summary = classification_results.get('summary', {})
                final_prediction = summary.get('final_prediction', 'unknown')

                print(f"  分類方法: {method}")
                print(f"  預測結果: {final_prediction}")

                if method == 'rf_model':
                    print_success("  → 使用 RF 模型 ✓")

                    # 檢查是否有機率資訊
                    predictions = classification_results.get('predictions', [])
                    if predictions and len(predictions) > 0:
                        first_pred = predictions[0]
                        if 'proba_normal' in first_pred:
                            print(f"  信心度資訊: Normal={first_pred.get('proba_normal', 0):.3f}, "
                                  f"Abnormal={first_pred.get('proba_abnormal', 0):.3f}")
                elif method == 'random':
                    print_warning("  → 使用隨機分類 ⚠")
                else:
                    print_warning(f"  → 未知方法: {method}")

                results.append({
                    'uuid': analyze_uuid,
                    'method': method,
                    'prediction': final_prediction,
                    'updated_at': str(updated_at)
                })
            else:
                print_error("  記錄缺少分類結果")

            print()

        client.close()
        return results

    except Exception as e:
        print_error(f"檢查預測結果失敗: {e}")
        return None


def check_model_files():
    """檢查模型檔案"""
    print_header("步驟 4: 檢查模型檔案")

    model_dirs = [
        'models',
        './models',
        '../models',
        'a_sub_system/train/RF/models'
    ]

    found = False
    for model_dir in model_dirs:
        model_path = Path(model_dir)
        if model_path.exists():
            print_success(f"找到模型目錄: {model_path.absolute()}")

            # 檢查必要檔案
            required_files = [
                'rf_classifier.pkl',
                'feature_scaler.pkl',
                'model_metadata.json'
            ]

            for file in required_files:
                file_path = model_path / file
                if file_path.exists():
                    size = file_path.stat().st_size / 1024  # KB
                    print_success(f"  {file} ({size:.2f} KB)")
                else:
                    print_error(f"  {file} 不存在")

            # 讀取元資料
            metadata_path = model_path / 'model_metadata.json'
            if metadata_path.exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)

                print(f"\n模型資訊:")
                print(f"  訓練日期: {metadata.get('training_date', 'Unknown')}")
                print(f"  聚合方式: {metadata.get('aggregation', 'Unknown')}")
                print(f"  特徵標準化: {metadata.get('normalize', 'Unknown')}")

            found = True
            break

    if not found:
        print_error("找不到模型檔案!")
        print_warning("請確認是否已執行 train_rf_model.py")


def generate_fix_commands(config_info, classifier_info, predictions):
    """生成修復命令"""
    print_header("診斷結果與修復建議")

    issues = []

    # 檢查配置
    if config_info and config_info['method'] == 'random':
        issues.append({
            'issue': '配置檔案中 method 仍為 random',
            'fix': f"""
編輯檔案: {config_info['config_path']}
修改: 'method': 'random' → 'method': 'rf_model'
            """
        })

    # 檢查分類器
    if classifier_info and classifier_info['classifier_type'] == 'old':
        issues.append({
            'issue': '使用舊版分類器',
            'fix': f"""
備份舊分類器:
cp {classifier_info['classifier_path']} {classifier_info['classifier_path']}.backup

替換為新分類器:
cp step3_classifier_updated.py {classifier_info['classifier_path']}
            """
        })

    # 檢查預測結果
    if predictions:
        using_random = any(p['method'] == 'random' for p in predictions)
        if using_random:
            issues.append({
                'issue': '最近的預測仍在使用隨機分類',
                'fix': """
請確認:
1. 配置已更新 (method='rf_model')
2. 分類器已替換為新版本
3. model_path 指向正確的模型目錄
4. 已重啟 analysis_service
            """
            })

    if issues:
        print_error(f"發現 {len(issues)} 個問題:\n")
        for i, issue in enumerate(issues, 1):
            print(f"{i}. {issue['issue']}")
            print(f"{Colors.YELLOW}{issue['fix']}{Colors.END}")
    else:
        print_success("系統配置正確，正在使用 RF 模型!")
        print("\n如果仍有疑問，請:")
        print("1. 重啟 analysis_service")
        print("2. 上傳新的測試音頻")
        print("3. 檢查新預測結果")


def main():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║            分類器狀態診斷工具 v1.0                                  ║
║                                                                  ║
║  本工具將檢查系統是否正確使用 RF 模型                               ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    # 執行各項檢查
    config_info = check_config_file()
    classifier_info = check_classifier_file()
    predictions = check_recent_predictions()
    check_model_files()

    # 生成修復建議
    generate_fix_commands(config_info, classifier_info, predictions)

    print(f"\n{Colors.BLUE}{'=' * 70}{Colors.END}")
    print(f"{Colors.BLUE}{'診斷完成'.center(70)}{Colors.END}")
    print(f"{Colors.BLUE}{'=' * 70}{Colors.END}\n")


if __name__ == '__main__':
    main()