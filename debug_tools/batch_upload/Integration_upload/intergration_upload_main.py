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
from debug_tools.batch_upload.Integration_upload.core.mongodb_handler import MongoDBUploader


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
        print("功能：多資料集選擇、中斷恢復、Dry-run 模式、資料庫備份還原")
        print("=" * 70)
        print()

    def test_database_connection(self) -> None:
        """測試資料庫連線並顯示詳細資訊"""
        print("=" * 70)
        print("資料庫連線資訊")
        print("=" * 70)

        mongodb_config = BaseUploadConfig.MONGODB_CONFIG

        # 顯示基本連線資訊
        print(f"Host: {mongodb_config['host']}")
        print(f"Port: {mongodb_config['port']}")
        print(f"Database: {mongodb_config['database']}")
        print(f"Collection: {mongodb_config['collection']}")
        print(f"Username: {mongodb_config['username']}")

        # 嘗試連線
        try:
            uploader = MongoDBUploader(
                mongodb_config=mongodb_config,
                use_gridfs=False,  # 只是測試連線，不需要 GridFS
                logger=self.logger
            )

            # 取得詳細資訊
            info = uploader.get_database_info()

            print(f"連線狀態: ✓ 成功連線")
            print(f"總記錄數: {info['record_count']:,} 筆")

            # 顯示資料庫大小
            if info['size_bytes'] > 0:
                size_mb = info['size_bytes'] / (1024 * 1024)
                print(f"資料庫大小: {size_mb:.2f} MB")

            # 顯示最後更新時間
            if info['last_updated']:
                if isinstance(info['last_updated'], str):
                    print(f"最後更新時間: {info['last_updated']}")
                else:
                    print(f"最後更新時間: {info['last_updated'].strftime('%Y-%m-%d %H:%M:%S')}")

            uploader.close()

        except Exception as e:
            print(f"連線狀態: ✗ 連線失敗")
            print(f"失敗原因: {str(e)}")
            print(f"可能原因: 資料庫未啟動 或 切換至其他資料庫實例")

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

    def select_mode(self, has_progress: bool) -> Tuple[str, bool, bool]:
        """
        讓使用者選擇上傳模式

        Args:
            has_progress: 是否有先前的進度

        Returns:
            (mode, delete_progress, delete_database) tuple
            mode: 'dry_run', 'upload', 'restore'
        """
        print("\n步驟2: 選擇上傳模式")
        print("-" * 70)

        if has_progress:
            print("\n⚠️  檢測到先前的上傳進度！")
            print("\n【Dry-run 模式】")
            print("  1. 刪除進度 + 刪除資料庫 + Dry-run")
            print("  2. 刪除進度 + 保留資料庫 + Dry-run")
            print("  3. 繼續先前進度 + Dry-run")
            print("\n【正式上傳模式】")
            print("  4. 刪除進度 + 刪除資料庫 + 正式上傳")
            print("  5. 刪除進度 + 保留資料庫 + 正式上傳")
            print("  6. 繼續先前進度 + 正式上傳")
            print("\n【還原功能】")
            print("  7. 從備份檔還原資料庫")

            while True:
                choice = input("\n請選擇 (1-7): ").strip()
                if choice == '1':
                    return 'dry_run', True, True    # Dry-run, 刪除進度, 刪除資料庫
                elif choice == '2':
                    return 'dry_run', True, False   # Dry-run, 刪除進度, 保留資料庫
                elif choice == '3':
                    return 'dry_run', False, False  # Dry-run, 保留進度, 保留資料庫
                elif choice == '4':
                    return 'upload', True, True     # 正式上傳, 刪除進度, 刪除資料庫
                elif choice == '5':
                    return 'upload', True, False    # 正式上傳, 刪除進度, 保留資料庫
                elif choice == '6':
                    return 'upload', False, False   # 正式上傳, 保留進度, 保留資料庫
                elif choice == '7':
                    return 'restore', False, False  # 還原模式
                else:
                    print("無效的選項，請重新輸入。")
        else:
            print("\n請選擇上傳模式：")
            print("  1. Dry-run 模式")
            print("  2. 正式上傳模式")
            print("  3. 從備份檔還原資料庫")

            while True:
                choice = input("\n請選擇 (1-3): ").strip()
                if choice == '1':
                    return 'dry_run', False, False  # Dry-run
                elif choice == '2':
                    return 'upload', False, False   # 正式上傳
                elif choice == '3':
                    return 'restore', False, False  # 還原模式
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

    def delete_database_with_backup(self) -> bool:
        """
        刪除資料庫並備份

        Returns:
            是否成功
        """
        print("\n" + "=" * 70)
        print("資料庫刪除與備份")
        print("=" * 70)

        mongodb_config = BaseUploadConfig.MONGODB_CONFIG

        try:
            # 建立連線
            uploader = MongoDBUploader(
                mongodb_config=mongodb_config,
                use_gridfs=False,
                logger=self.logger
            )

            # 計算記錄數
            record_count = uploader.count_records()

            if record_count == 0:
                print("\n資料庫目前沒有記錄，無需刪除。")
                uploader.close()
                return True

            # 如果筆數 > 1000，需要確認
            if record_count > 1000:
                print(f"\n⚠️  警告：即將刪除大量資料")
                print("=" * 70)
                info = uploader.get_database_info()
                print(f"資料庫: {info['database']}")
                print(f"Collection: {info['collection']}")
                print(f"目前筆數: {record_count:,} 筆")

                if info['size_bytes'] > 0:
                    size_mb = info['size_bytes'] / (1024 * 1024)
                    size_gb = size_mb / 1024
                    if size_gb >= 1:
                        print(f"估計大小: {size_gb:.2f} GB")
                    else:
                        print(f"估計大小: {size_mb:.2f} MB")

                print("\n此操作將：")
                print("1. 備份所有記錄至 reports/backups/(但是沒有備份檔案)")
                print("2. 刪除所有資料庫記錄")
                print("\n確認刪除？請輸入 'y' 確認: ", end='')

                confirmation = input().strip().lower()
                if confirmation != 'y':
                    print("\n已取消刪除操作。")
                    uploader.close()
                    sys.exit(0)

            # 建立備份
            print("\n正在備份資料庫...")
            backup_dir = Path(BaseUploadConfig.REPORT_OUTPUT['report_directory']) / 'backups'
            backup_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = backup_dir / f"backup_{timestamp}.json"

            if not uploader.backup_all_records(backup_file):
                print("\n✗ 備份失敗，取消刪除操作。")
                uploader.close()
                sys.exit(1)

            # 刪除記錄
            print("\n正在刪除資料庫記錄...")
            deleted_count = uploader.delete_all_records()

            if deleted_count > 0:
                print(f"\n✓ 已刪除 {deleted_count:,} 筆記錄")
                print(f"✓ 備份檔案：{backup_file}")
            else:
                print("\n✗ 刪除失敗")
                uploader.close()
                return False

            uploader.close()
            print("=" * 70)
            return True

        except Exception as e:
            self.logger.error(f"刪除資料庫時發生錯誤：{e}")
            print(f"\n✗ 刪除資料庫失敗：{e}")
            return False

    def list_and_select_backup(self) -> Path:
        """
        列出可用的備份檔並讓使用者選擇

        Returns:
            選擇的備份檔路徑，如果取消則返回 None
        """
        print("\n" + "=" * 70)
        print("選擇備份檔還原")
        print("=" * 70)

        backup_dir = Path(BaseUploadConfig.REPORT_OUTPUT['report_directory']) / 'backups'

        if not backup_dir.exists():
            print("\n✗ 備份目錄不存在")
            return None

        # 掃描備份檔案
        backup_files = sorted(backup_dir.glob('backup_*.json'), key=lambda p: p.stat().st_mtime, reverse=True)

        if not backup_files:
            print("\n✗ 沒有找到備份檔案")
            return None

        print("\n可用的備份檔案：")
        print("-" * 70)

        import os
        for idx, backup_file in enumerate(backup_files, 1):
            file_stat = backup_file.stat()
            file_size_mb = file_stat.st_size / (1024 * 1024)
            file_time = datetime.fromtimestamp(file_stat.st_mtime)

            print(f"\n{idx}. {backup_file.name}")
            print(f"   時間: {file_time.strftime('%Y-%m-%d %H:%M:%S')}")

            # 嘗試讀取檔案以取得記錄數
            try:
                with open(backup_file, 'r', encoding='utf-8') as f:
                    records = json.load(f)
                    print(f"   筆數: {len(records):,} 筆")
            except Exception:
                print(f"   筆數: 無法讀取")

            print(f"   大小: {file_size_mb:.2f} MB")

        print("\n" + "-" * 70)
        print("請選擇要還原的備份檔 (輸入編號) 或 q 取消: ", end='')

        while True:
            choice = input().strip().lower()
            if choice == 'q':
                print("\n已取消還原操作。")
                return None

            try:
                idx = int(choice)
                if 1 <= idx <= len(backup_files):
                    return backup_files[idx - 1]
                else:
                    print(f"無效的選項，請輸入 1-{len(backup_files)} 或 q: ", end='')
            except ValueError:
                print(f"無效的選項，請輸入 1-{len(backup_files)} 或 q: ", end='')

    def do_restore_from_backup(self) -> bool:
        """
        執行從備份檔還原

        Returns:
            是否成功
        """
        # 選擇備份檔
        backup_file = self.list_and_select_backup()
        if not backup_file:
            return False

        print("\n" + "=" * 70)
        print("資料庫還原")
        print("=" * 70)

        mongodb_config = BaseUploadConfig.MONGODB_CONFIG

        try:
            # 建立連線
            uploader = MongoDBUploader(
                mongodb_config=mongodb_config,
                use_gridfs=False,
                logger=self.logger
            )

            # 檢查目前資料庫狀態
            current_count = uploader.count_records()

            if current_count > 0:
                print(f"\n⚠️  資料庫目前有 {current_count:,} 筆記錄")
                print("還原將【附加】備份資料，不會刪除現有記錄")
                print("\n繼續還原？(y/n): ", end='')
                confirmation = input().strip().lower()
                if confirmation != 'y':
                    print("\n已取消還原操作。")
                    uploader.close()
                    return False

            # 執行還原
            print(f"\n正在從備份檔還原：{backup_file.name}")
            result = uploader.restore_from_backup(backup_file)

            print("\n" + "=" * 70)
            print("還原摘要")
            print("=" * 70)
            print(f"成功插入: {result['inserted']:,} 筆")
            print(f"跳過記錄: {result['skipped']:,} 筆")

            if result['skipped'] > 0:
                print("\n⚠️  注意：部分記錄因重複 ID 或其他錯誤而跳過")

            print("\n⚠️  注意：GridFS 檔案無法還原")
            print("本次還原僅恢復資料庫記錄（metadata）")
            print("如需完整恢復，請確保 GridFS 檔案仍存在")
            print("=" * 70)

            uploader.close()
            return True

        except Exception as e:
            self.logger.error(f"還原資料庫時發生錯誤：{e}")
            print(f"\n✗ 還原資料庫失敗：{e}")
            return False

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
        # 步驟 0：顯示橫幅
        self.print_banner()

        # 步驟 0.5：測試資料庫連線
        self.test_database_connection()

        # 步驟 1：選擇資料集
        self.select_datasets()

        # 檢查進度
        has_progress = self.check_progress()

        # 步驟 2：選擇模式
        mode, delete_progress_flag, delete_database_flag = self.select_mode(has_progress)

        # 還原模式：執行還原後直接結束
        if mode == 'restore':
            if self.do_restore_from_backup():
                print("\n✓ 資料庫還原完成。")
            else:
                print("\n✗ 資料庫還原失敗或已取消。")
            print("\n程序執行完畢。")
            return

        # 刪除進度（如果需要）
        if delete_progress_flag:
            self.delete_progress()

        # 刪除資料庫（如果需要）
        if delete_database_flag:
            if not self.delete_database_with_backup():
                print("\n❌ 資料庫刪除失敗，程序終止。")
                sys.exit(1)

        # 初始化上傳器
        if not self.initialize_uploaders():
            print("\n❌ 初始化失敗，程序終止。")
            sys.exit(1)

        # 執行上傳
        dry_run = (mode == 'dry_run')
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
