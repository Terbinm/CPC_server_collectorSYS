# test_dry_run.py - 测试 Dry Run 功能

import sys
from mimii_batch_upload import BatchUploader
from config import UploadConfig

def test_dry_run():
    """测试 Dry Run 功能"""
    print("=" * 80)
    print("MIMII Dry Run 测试")
    print("=" * 80)

    # 临时限制每个标签只处理 1 个文件
    original_limit = UploadConfig.UPLOAD_BEHAVIOR['per_label_limit']
    UploadConfig.UPLOAD_BEHAVIOR['per_label_limit'] = 1

    try:
        uploader = BatchUploader()

        # 扫描文件
        dataset_files = uploader.scan_directory()

        if not dataset_files:
            print("\n未找到任何文件")
            return

        # 应用限制
        dataset_files = uploader._apply_label_limit(dataset_files)

        print(f"\n将要处理 {len(dataset_files)} 个文件 (每个标签限制 1 个)")

        # 生成预览
        print("\n生成 Dry Run 预览...")
        uploader._generate_dry_run_samples(dataset_files)

        print("\n✓ Dry Run 预览已生成")
        print(f"  请查看: reports/dry_run_previews/ 目录")

        uploader.cleanup()

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 恢复原始设置
        UploadConfig.UPLOAD_BEHAVIOR['per_label_limit'] = original_limit

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)

if __name__ == '__main__':
    test_dry_run()
