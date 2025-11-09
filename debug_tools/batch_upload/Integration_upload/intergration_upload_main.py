"""
整合批次上傳工具 - CLI 主程序
支援 CPC、MAFAULDA、MIMII 三種資料集的整合上傳
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure the project root (which contains the debug_tools package) is importable
_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR
for _ in range(3):
    _PROJECT_ROOT = _PROJECT_ROOT.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from debug_tools.batch_upload.Integration_upload.core.logger import BatchUploadLogger
from debug_tools.batch_upload.Integration_upload.config.base_config import BaseUploadConfig
from debug_tools.batch_upload.Integration_upload.uploaders.cpc_uploader import CPCBatchUploader
from debug_tools.batch_upload.Integration_upload.uploaders.mafaulda_uploader import MAFAULDABatchUploader
from debug_tools.batch_upload.Integration_upload.uploaders.mimii_uploader import MIMIIBatchUploader


PACKAGE_PREFIX = "debug_tools.batch_upload.Integration_upload"


class IntegrationUploadCLI:
    """整合上傳 CLI 管理器"""

    DATASET_MAP = {
        'CPC': (CPCBatchUploader, f'{PACKAGE_PREFIX}.config.cpc_config', 'CPCUploadConfig'),
        'MAFAULDA': (MAFAULDABatchUploader, f'{PACKAGE_PREFIX}.config.mafaulda_config', 'MAFAULDAUploadConfig'),
        'MIMII': (MIMIIBatchUploader, f'{PACKAGE_PREFIX}.config.mimii_config', 'MIMIIUploadConfig'),
    }

    DATASET_COMBINATIONS = {
        '1': (['CPC', 'MAFAULDA', 'MIMII'], '全部上傳'),
        '2': (['CPC'], '只上傳 CPC'),
        '3': (['MAFAULDA'], '只上傳 MAFAULDA'),
        '4': (['MIMII'], '只上傳 MIMII'),
        '5': (['CPC', 'MAFAULDA'], 'CPC + MAFAULDA'),
        '6': (['CPC', 'MIMII'], 'CPC + MIMII'),
        '7': (['MAFAULDA', 'MIMII'], 'MAFAULDA + MIMII'),
    }

    def __init__(self) -> None:
        """初始化 CLI"""
        # 設置全域日誌
        self.logger = BatchUploadLogger.setup_logger(
            name="integration_upload",
            logging_config=BaseUploadConfig.LOGGING_CONFIG
        )
        self.progress_file = Path(BaseUploadConfig.PROGRESS_FILE)
        self.selected_datasets: List[str] = []
        self.uploaders: List[Tuple[str, Any]] = []
        self.total_stats: Dict[str, Any] = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'datasets': {}
        }

    def print_banner(self) -> None:
        """顯示橫幅"""
        print("=" * 70)
        print("        批次上傳整合工具 v1.0")
        print("=" * 70)
        print("支援資料集：CPC、MAFAULDA、MIMII")
        print("功能：多資料集選擇、中斷恢復、Dry-run 模式")
        print("=" * 70)
        print()

    def check_progress(self) -> bool:
        """
        檢查是否有先前的上傳進度

        Returns:
            是否存在進度
        """
        if not self.progress_file.exists():
            return False

        try:
            with self.progress_file.open('r', encoding='utf-8') as f:
                data = json.load(f)
                # 檢查是否有任何資料集的進度
                if 'datasets' in data:
                    for dataset_name in self.selected_datasets:
                        if dataset_name in data['datasets']:
                            uploaded_files = data['datasets'][dataset_name].get('uploaded_files', [])
                            if uploaded_files:
                                return True
                return False
        except Exception:
            return False

    def select_datasets(self) -> None:
        """讓使用者選擇要上傳的資料集"""
        print("\n步驟1: 選擇要上傳的資料集")
        print("-" * 70)
        for key, (datasets, description) in self.DATASET_COMBINATIONS.items():
            print(f"  {key}. {description}")

        while True:
            choice = input("\n請選擇 (1-7): ").strip()
            if choice in self.DATASET_COMBINATIONS:
                self.selected_datasets, description = self.DATASET_COMBINATIONS[choice]
                print(f"\n已選擇：{description}")
                break
            else:
                print("無效的選項，請重新輸入。")

    def select_mode(self, has_progress: bool) -> Tuple[bool, bool]:
        """
        讓使用者選擇上傳模式

        Args:
            has_progress: 是否有先前的進度

        Returns:
            (dry_run, delete_progress) tuple
        """
        print("\n步驟2: 選擇上傳模式")
        print("-" * 70)

        if has_progress:
            print("\n⚠️  檢測到先前的上傳進度！")
            print("\n請選擇處理方式：")
            print("  1. 刪除進度並重新開始正式上傳")
            print("  2. 刪除進度並重新開始 Dry-run")
            print("  3. 繼續先前的進度並正式上傳")
            print("  4. 繼續先前的進度並 Dry-run")

            while True:
                choice = input("\n請選擇 (1-4): ").strip()
                if choice == '1':
                    return False, True  # 正式上傳，刪除進度
                elif choice == '2':
                    return True, True   # Dry-run，刪除進度
                elif choice == '3':
                    return False, False # 正式上傳，保留進度
                elif choice == '4':
                    return True, False  # Dry-run，保留進度
                else:
                    print("無效的選項，請重新輸入。")
        else:
            print("\n請選擇上傳模式：")
            print("  1. 正式上傳")
            print("  2. Dry-run（預覽模式）")

            while True:
                choice = input("\n請選擇 (1-2): ").strip()
                if choice == '1':
                    return False, False # 正式上傳
                elif choice == '2':
                    return True, False  # Dry-run
                else:
                    print("無效的選項，請重新輸入。")

    def delete_progress(self) -> None:
        """刪除進度文件"""
        if self.progress_file.exists():
            try:
                self.progress_file.unlink()
                self.logger.info("已刪除先前的進度文件。")
                print("\n✓ 已刪除先前的進度文件。")
            except Exception as e:
                self.logger.warning(f"無法刪除進度文件：{e}")

    def initialize_uploaders(self) -> bool:
        """
        初始化選定的上傳器

        Returns:
            是否成功
        """
        print("\n正在初始化上傳器...")
        self.uploaders = []

        for dataset_name in self.selected_datasets:
            try:
                uploader_class, config_module, config_class_name = self.DATASET_MAP[dataset_name]

                # 動態導入配置
                config_module_obj = __import__(config_module, fromlist=[config_class_name])
                config_class = getattr(config_module_obj, config_class_name)

                # 驗證配置
                errors = config_class.validate_base_config()
                if errors:
                    print(f"\n❌ {dataset_name} 配置錯誤：")
                    for error in errors:
                        print(f"  - {error}")
                    return False

                # 創建上傳器
                uploader = uploader_class(logger=self.logger)
                self.uploaders.append((dataset_name, uploader))
                print(f"  ✓ {dataset_name} 上傳器已初始化")

            except Exception as e:
                print(f"\n❌ 初始化 {dataset_name} 上傳器失敗：{e}")
                self.logger.error(f"初始化 {dataset_name} 上傳器失敗：{e}")
                return False

        return True

    def run_upload(self, dry_run: bool) -> None:
        """
        執行上傳

        Args:
            dry_run: 是否為 Dry-run 模式
        """
        mode_text = "Dry-run（預覽）" if dry_run else "正式上傳"
        print(f"\n{'=' * 70}")
        print(f"開始執行 {mode_text}")
        print(f"{'=' * 70}\n")

        for dataset_name, uploader in self.uploaders:
            print(f"\n>>> 處理 {dataset_name} 資料集...")
            print("-" * 70)

            try:
                uploader.batch_upload(dry_run=dry_run)

                # 收集統計
                stats = uploader.get_stats()
                self.total_stats['total'] += stats['total']
                self.total_stats['success'] += stats['success']
                self.total_stats['failed'] += stats['failed']
                self.total_stats['skipped'] += stats['skipped']
                self.total_stats['datasets'][dataset_name] = stats

            except Exception as e:
                self.logger.error(f"{dataset_name} 上傳過程中發生錯誤：{e}")
                print(f"\n❌ {dataset_name} 上傳失敗：{e}")

            finally:
                # 清理資源
                try:
                    uploader.cleanup()
                except Exception as e:
                    self.logger.warning(f"清理 {dataset_name} 上傳器時發生錯誤：{e}")

    def print_summary(self) -> None:
        """顯示總結統計"""
        print("\n" + "=" * 70)
        print("              上傳完成 - 統計匯總")
        print("=" * 70)
        print(f"\n總計：{self.total_stats['total']} 個檔案")
        print(f"成功：{self.total_stats['success']} 個檔案")
        print(f"失敗：{self.total_stats['failed']} 個檔案")
        print(f"跳過：{self.total_stats['skipped']} 個檔案")

        print("\n各資料集統計：")
        print("-" * 70)
        for dataset_name, stats in self.total_stats['datasets'].items():
            print(f"\n{dataset_name}:")
            print(f"  總計：{stats['total']}  |  成功：{stats['success']}  |  "
                  f"失敗：{stats['failed']}  |  跳過：{stats['skipped']}")

            if stats['labels']:
                print(f"  標籤分佈：")
                for label, count in sorted(stats['labels'].items()):
                    print(f"    - {label}: {count} 個檔案")

        print("\n" + "=" * 70)

    def save_combined_report(self) -> None:
        """保存合併的報告"""
        try:
            report_dir = Path(BaseUploadConfig.REPORT_OUTPUT['report_directory'])
            report_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_file = report_dir / f"combined_upload_report_{timestamp}.json"

            report_payload = {
                'timestamp': timestamp,
                'selected_datasets': self.selected_datasets,
                'total_statistics': {
                    'total': self.total_stats['total'],
                    'success': self.total_stats['success'],
                    'failed': self.total_stats['failed'],
                    'skipped': self.total_stats['skipped'],
                },
                'dataset_statistics': self.total_stats['datasets'],
            }

            with report_file.open('w', encoding='utf-8') as f:
                json.dump(report_payload, f, indent=2, ensure_ascii=False)

            self.logger.info(f"已儲存合併報告：{report_file}")
            print(f"\n報告已保存至：{report_file}")

        except Exception as e:
            self.logger.error(f"寫入合併報告失敗：{e}")

    def run(self) -> None:
        """執行 CLI 主流程"""
        self.print_banner()

        # 步驟 1：選擇資料集
        self.select_datasets()

        # 檢查進度
        has_progress = self.check_progress()

        # 步驟 2：選擇模式
        dry_run, delete_progress_flag = self.select_mode(has_progress)

        # 刪除進度（如果需要）
        if delete_progress_flag:
            self.delete_progress()

        # 初始化上傳器
        if not self.initialize_uploaders():
            print("\n❌ 初始化失敗，程序終止。")
            sys.exit(1)

        # 執行上傳
        self.run_upload(dry_run)

        # 顯示統計
        if not dry_run:
            self.print_summary()
            self.save_combined_report()

        print("\n程序執行完畢。")


def main() -> None:
    """主入口"""
    try:
        cli = IntegrationUploadCLI()
        cli.run()
    except KeyboardInterrupt:
        print("\n\n程序已被使用者中斷。")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 發生未預期的錯誤：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
