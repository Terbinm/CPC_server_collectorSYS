"""
初始化管理员账户脚本

使用方法:
    python init_admin.py

或者使用自定义用户名和密码:
    python init_admin.py --username admin --password your_password --email admin@example.com
"""
import sys
import argparse
import getpass
from flask_bcrypt import generate_password_hash
from models.user import User
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_admin_user(username='admin', email='admin@example.com', password=None):
    """
    创建管理员用户

    Args:
        username: 用户名（默认: admin）
        email: 邮箱（默认: admin@example.com）
        password: 密码（如果为 None 则提示输入）

    Returns:
        bool: 是否创建成功
    """
    try:
        # 检查用户是否已存在
        existing_user = User.find_by_username(username)
        if existing_user:
            logger.error(f"用户 '{username}' 已存在")
            return False

        # 检查邮箱是否已被使用
        existing_email = User.find_by_email(email)
        if existing_email:
            logger.error(f"邮箱 '{email}' 已被使用")
            return False

        # 获取密码
        if password is None:
            password = getpass.getpass('请输入管理员密码: ')
            password_confirm = getpass.getpass('请确认密码: ')

            if password != password_confirm:
                logger.error("两次密码输入不一致")
                return False

        if len(password) < 6:
            logger.error("密码长度至少为 6 个字符")
            return False

        # 生成密码哈希
        password_hash = generate_password_hash(password).decode('utf-8')

        # 创建管理员用户
        user = User.create(
            username=username,
            email=email,
            password_hash=password_hash,
            role=User.ROLE_ADMIN
        )

        if user:
            logger.info(f"✓ 管理员用户创建成功")
            logger.info(f"  用户名: {username}")
            logger.info(f"  邮箱: {email}")
            logger.info(f"  角色: 管理员")
            logger.info(f"\n请使用以下信息登录:")
            logger.info(f"  URL: http://localhost:8000/auth/login")
            logger.info(f"  用户名: {username}")
            return True
        else:
            logger.error("创建管理员用户失败")
            return False

    except Exception as e:
        logger.error(f"创建管理员用户时发生错误: {str(e)}", exc_info=True)
        return False


def create_indexes():
    """创建必要的数据库索引"""
    try:
        logger.info("创建数据库索引...")
        User.create_indexes()
        logger.info("✓ 数据库索引创建成功")
        return True
    except Exception as e:
        logger.error(f"创建数据库索引失败: {str(e)}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='初始化管理员账户')
    parser.add_argument('--username', type=str, default='admin',
                      help='管理员用户名（默认: admin）')
    parser.add_argument('--email', type=str, default='admin@example.com',
                      help='管理员邮箱（默认: admin@example.com）')
    parser.add_argument('--password', type=str, default=None,
                      help='管理员密码（如果不提供则交互式输入）')
    parser.add_argument('--skip-indexes', action='store_true',
                      help='跳过创建数据库索引')

    args = parser.parse_args()

    print("=" * 60)
    print("State Management System - 初始化管理员账户")
    print("=" * 60)
    print()

    # 创建数据库索引
    if not args.skip_indexes:
        if not create_indexes():
            logger.warning("索引创建失败，但将继续创建管理员账户")
        print()

    # 创建管理员用户
    success = create_admin_user(
        username=args.username,
        email=args.email,
        password=args.password
    )

    print()
    print("=" * 60)

    if success:
        print("✓ 初始化完成！")
        return 0
    else:
        print("✗ 初始化失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
