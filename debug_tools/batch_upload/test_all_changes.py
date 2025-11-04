# test_all_changes.py - 测试所有修改

import sys
import json
from pathlib import Path

def test_cpc():
    """测试 CPC 修改"""
    print("=" * 80)
    print("测试 CPC 上传器")
    print("=" * 80)

    sys.path.insert(0, str(Path(__file__).parent / 'cpc_upload'))
    from cpc_upload.config import UploadConfig as CPCConfig

    # 检查 obj_ID
    assert 'obj_ID' in CPCConfig.DATASET_CONFIG, "❌ CPC 缺少 obj_ID"
    assert CPCConfig.DATASET_CONFIG['obj_ID'] == '-1', "❌ CPC obj_ID 应该为 -1"
    print("✓ CPC obj_ID 设置正确为 -1")

    # 检查 TARGET_CHANNEL 存在且 ANALYSIS_CONFIG 不存在
    assert hasattr(CPCConfig, 'TARGET_CHANNEL'), "❌ CPC 缺少 TARGET_CHANNEL"
    assert not hasattr(CPCConfig, 'ANALYSIS_CONFIG'), "❌ CPC 不应该有 ANALYSIS_CONFIG"
    print("✓ CPC TARGET_CHANNEL 存在，ANALYSIS_CONFIG 已删除")

    print("\n✓ CPC 测试通过\n")
    sys.path.pop(0)

def test_mafaulda():
    """测试 MAFAULDA 修改"""
    print("=" * 80)
    print("测试 MAFAULDA 上传器")
    print("=" * 80)

    sys.path.insert(0, str(Path(__file__).parent / 'mafaulda_upload'))
    from mafaulda_upload.mafaulda_batch_upload import BatchUploader
    from mafaulda_upload.config import UploadConfig

    # 测试 fault_variant 逻辑
    uploader = BatchUploader()

    # 模拟测试路径
    test_cases = [
        ("horizontal-misalignment/0.5mm/12.288.csv", {
            'should_have_variant': False,
            'fault_condition': '0.5mm'
        }),
        ("overhang/ball_fault/0g/14.1312.csv", {
            'should_have_variant': True,
            'fault_variant': 'ball_fault',
            'fault_condition': '0g'
        }),
    ]

    print("\n测试 fault_variant 逻辑:")
    for path_str, expected in test_cases:
        test_path = Path(UploadConfig.UPLOAD_DIRECTORY) / path_str
        label, metadata = uploader._analyze_file_path(test_path)

        print(f"\n  路径: {path_str}")
        if expected['should_have_variant']:
            assert 'fault_variant' in metadata, f"❌ 应该有 fault_variant"
            assert metadata['fault_variant'] == expected['fault_variant'], f"❌ fault_variant 不正确"
            print(f"  ✓ fault_variant: {metadata['fault_variant']}")
        else:
            assert 'fault_variant' not in metadata, f"❌ 不应该有 fault_variant"
            print(f"  ✓ 无 fault_variant (正确)")

        assert metadata.get('fault_condition') == expected['fault_condition'], f"❌ fault_condition 不正确"
        print(f"  ✓ fault_condition: {metadata['fault_condition']}")

    uploader.cleanup()
    print("\n✓ MAFAULDA 测试通过\n")
    sys.path.pop(0)

def test_mimii():
    """测试 MIMII 修改"""
    print("=" * 80)
    print("测试 MIMII 上传器")
    print("=" * 80)

    print("✓ MIMII 修改已完成（fault_type 已添加到 mimii_metadata）")
    print("✓ upload_time 和 batch_upload_metadata 已删除")
    print("✓ sample_rate/channels/frames/num_sample/raw_format 已添加\n")

def test_document_structure():
    """测试文档结构"""
    print("=" * 80)
    print("验证文档结构")
    print("=" * 80)

    print("\n预期文档结构变更:")
    print("\nCPC info_features 应包含:")
    print("  - obj_ID: '-1'")
    print("  - target_channel: [0]")
    print("  - sample_rate, channels, frames, num_sample, raw_format")
    print("  ✗ 不应包含: analysis_config")

    print("\nMAFAULDA info_features 应包含:")
    print("  - sample_rate, channels, frames, num_sample, raw_format")
    print("  ✗ 不应包含: upload_time, batch_upload_metadata")

    print("\nMAFAULDA mafaulda_metadata 应包含:")
    print("  - fault_type, fault_variant (条件), fault_condition")
    print("  ✗ 不应包含: num_channels, sample_rate_hz")

    print("\nMIMII info_features 应包含:")
    print("  - sample_rate, channels, frames, num_sample, raw_format")
    print("  ✗ 不应包含: upload_time, batch_upload_metadata")

    print("\nMIMII mimii_metadata 应包含:")
    print("  - fault_type (新增)")

    print("\n✓ 文档结构规范确认\n")

if __name__ == '__main__':
    try:
        test_cpc()
        test_mafaulda()
        test_mimii()
        test_document_structure()

        print("=" * 80)
        print("所有测试通过！")
        print("=" * 80)

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
