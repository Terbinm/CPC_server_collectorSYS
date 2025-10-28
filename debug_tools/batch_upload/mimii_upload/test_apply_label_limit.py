import sys
import unittest
from collections import Counter
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from config import UploadConfig
from mimii_batch_upload import BatchUploader


def _build_entry(base: Path, parts: str, label: str, file_index: int):
    file_path = base / parts / f"{file_index:08d}.wav"
    return {
        'path': file_path,
        'label': label,
        'path_metadata': {
            'relative_path': str(file_path)
        }
    }


class ApplyLabelLimitTests(unittest.TestCase):
    def setUp(self):
        self.original_limit = UploadConfig.UPLOAD_BEHAVIOR['per_label_limit']

    def tearDown(self):
        UploadConfig.UPLOAD_BEHAVIOR['per_label_limit'] = self.original_limit

    def test_balances_across_folders(self):
        uploader = BatchUploader.__new__(BatchUploader)

        base = Path("mimii_data")
        folder_parts = [
            Path("6_dB_pump/pump/id_00/normal"),
            Path("6_dB_pump/pump/id_02/normal"),
            Path("6_dB_pump/pump/id_04/normal"),
        ]

        dataset_files = []
        for folder_idx, folder in enumerate(folder_parts):
            for file_idx in range(4):
                dataset_files.append(
                    _build_entry(base, str(folder), 'normal', folder_idx * 10 + file_idx)
                )

        UploadConfig.UPLOAD_BEHAVIOR['per_label_limit'] = 6

        limited = uploader._apply_label_limit(dataset_files)

        self.assertEqual(len(limited), 6)

        counts = Counter(str(entry['path'].parent) for entry in limited)
        self.assertTrue(all(count == 2 for count in counts.values()))
        self.assertEqual(
            set(counts.keys()),
            {str(base / folder) for folder in folder_parts}
        )

    def test_warns_when_average_below_one(self):
        uploader = BatchUploader.__new__(BatchUploader)

        base = Path("mimii_data")
        dataset_files = []
        for folder_idx in range(5):
            folder = Path(f"0_dB_fan/fan/id_{folder_idx:02d}/normal")
            dataset_files.append(
                _build_entry(base, str(folder), 'normal', folder_idx)
            )

        UploadConfig.UPLOAD_BEHAVIOR['per_label_limit'] = 3

        with self.assertLogs('batch_upload', level='WARNING') as captured:
            limited = uploader._apply_label_limit(dataset_files)

        self.assertEqual(len(limited), 3)
        self.assertTrue(
            any("平均每個資料夾僅" in message for message in captured.output),
            msg="Expected warning about low average uploads per folder."
        )


if __name__ == '__main__':
    unittest.main()
