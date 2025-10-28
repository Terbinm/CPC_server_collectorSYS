# test_scan.py - 测试文件扫描功能

import sys
from pathlib import Path
from mimii_batch_upload import BatchUploader

def test_scan():
    """测试文件扫描功能"""
    print("=" * 80)
    print("MIMII 文件扫描测试")
    print("=" * 80)

    try:
        uploader = BatchUploader()
        print(f"\n上传目录: {uploader.uploader.config['database']}")

        # 扫描文件
        dataset_files = uploader.scan_directory()

        if not dataset_files:
            print("\n未找到任何文件")
            return

        print(f"\n找到 {len(dataset_files)} 个文件")

        # 统计信息
        label_counts = {}
        snr_counts = {}
        machine_counts = {}
        obj_id_counts = {}

        for entry in dataset_files:
            label = entry['label']
            metadata = entry['path_metadata']

            label_counts[label] = label_counts.get(label, 0) + 1

            snr = metadata.get('snr')
            if snr:
                snr_counts[snr] = snr_counts.get(snr, 0) + 1

            machine = metadata.get('machine_type')
            if machine:
                machine_counts[machine] = machine_counts.get(machine, 0) + 1

            obj_id = metadata.get('obj_ID')
            if obj_id:
                obj_id_counts[obj_id] = obj_id_counts.get(obj_id, 0) + 1

        print("\n标签统计:")
        for label, count in sorted(label_counts.items()):
            print(f"  {label}: {count} 个")

        print("\nSNR 统计:")
        for snr, count in sorted(snr_counts.items()):
            print(f"  {snr}: {count} 个")

        print("\n机器类型统计:")
        for machine, count in sorted(machine_counts.items()):
            print(f"  {machine}: {count} 个")

        print("\nobj_ID 统计:")
        for obj_id, count in sorted(obj_id_counts.items()):
            print(f"  {obj_id}: {count} 个")

        # 显示几个样本
        print("\n样本数据 (前 3 个):")
        for i, entry in enumerate(dataset_files[:3]):
            file_path = entry['path']
            label = entry['label']
            metadata = entry['path_metadata']

            print(f"\n[{i+1}] {file_path.name}")
            print(f"    完整路径: {metadata.get('relative_path')}")
            print(f"    标签: {label}")
            print(f"    SNR: {metadata.get('snr')}")
            print(f"    机器类型: {metadata.get('machine_type')}")
            print(f"    obj_ID: {metadata.get('obj_ID')}")
            print(f"    文件序号: {metadata.get('file_id_number')}")

        uploader.cleanup()

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)

if __name__ == '__main__':
    test_scan()
