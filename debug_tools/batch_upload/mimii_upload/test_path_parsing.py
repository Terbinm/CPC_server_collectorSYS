# test_path_parsing.py - 测试 MIMII 路径解析功能

from pathlib import Path
from config import UploadConfig

# 模拟 BatchUploader 的路径解析方法
def analyze_file_path(file_path: Path):
    """
    从路径解析 MIMII 资料的参数

    路径范例: mimii_data/6_dB_pump/pump/id_02/normal/00000001.wav
    提取: SNR(6_dB), machine_type(pump), obj_ID(id_02), label(normal), file_id(00000001)
    """
    base_path = Path(UploadConfig.UPLOAD_DIRECTORY)
    try:
        relative = file_path.relative_to(base_path)
    except ValueError:
        relative = file_path

    parts = relative.parts

    # 初始化元数据
    metadata = {
        'relative_path': str(relative).replace("\\", "/"),
    }

    label = 'unknown'

    # MIMII 路径结构：{snr}_{machine_type}/{machine_type}/{obj_ID}/{label}/{filename}
    if len(parts) >= 4:
        # 第一层：提取 SNR 和机器类型
        first_level = parts[0]  # e.g., "6_dB_pump"

        # 解析 SNR 和机器类型
        for machine_type in UploadConfig.MACHINE_TYPES:
            if machine_type in first_level.lower():
                metadata['machine_type'] = machine_type
                # 提取 SNR (移除机器类型部分)
                snr_part = first_level.replace(f"_{machine_type}", "").replace(f"{machine_type}", "")
                if snr_part:
                    metadata['snr'] = snr_part.strip('_')
                break

        # 第三层：obj_ID
        if len(parts) >= 3 and parts[2].startswith('id_'):
            metadata['obj_ID'] = parts[2]

        # 第四层：标签
        if len(parts) >= 4:
            label_folder = parts[3].lower()
            for label_key, folder_name in UploadConfig.LABEL_FOLDERS.items():
                if folder_name.lower() == label_folder:
                    label = label_key
                    break

    # 从文件名称提取序号
    filename = file_path.stem
    try:
        file_id_number = int(filename)
        metadata['file_id_number'] = file_id_number
    except ValueError:
        # 文件名不是纯数字，忽略
        pass

    return label, metadata

# 测试样例
test_cases = [
    "6_dB_pump/pump/id_02/normal/00000001.wav",
    "-6_dB_pump/pump/id_00/abnormal/00000005.wav",
    "0_dB_fan/fan/id_04/normal/00000010.wav",
    "6_dB_slider/slider/id_02/abnormal/00000020.wav",
]

print("=" * 80)
print("MIMII 路径解析测试")
print("=" * 80)

for test_path in test_cases:
    full_path = Path(UploadConfig.UPLOAD_DIRECTORY) / test_path
    label, metadata = analyze_file_path(full_path)

    print(f"\n路径: {test_path}")
    print(f"标签: {label}")
    print(f"元数据:")
    for key, value in metadata.items():
        print(f"  {key}: {value}")

print("\n" + "=" * 80)
print("测试完成")
print("=" * 80)
