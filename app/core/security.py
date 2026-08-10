"""密码加密与验证工具。

使用 bcrypt 算法（cost=12）对密码进行哈希存储，自动加盐。
禁止使用 MD5、SHA 等快速哈希算法。
"""

import bcrypt

# bcrypt cost factor，数值越高越安全但越慢
BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希。

    每次调用自动生成随机盐，因此同一密码每次产生不同的哈希值。

    Args:
        password: 明文密码。

    Returns:
        bcrypt 哈希字符串（以 $2b$12$ 开头）。
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码是否与 bcrypt 哈希匹配。

    Args:
        plain_password: 用户输入的明文密码。
        hashed_password: 数据库中存储的 bcrypt 哈希。

    Returns:
        匹配返回 True，否则返回 False。
    """
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)
