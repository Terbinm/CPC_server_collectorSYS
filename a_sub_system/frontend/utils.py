import hashlib
import logging

logger = logging.getLogger(__name__)


def calculate_file_hash(file_path):
    """
    計算給定文件的 SHA-256 哈希值

    :param file_path: 文件路徑
    :return: 哈希值的十六進制字符串
    """
    try:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        logger.error(f"計算文件哈希值時出錯: {str(e)}")
        return None
