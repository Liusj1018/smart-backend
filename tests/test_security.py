"""app.core.security 模块的单元测试。"""

from app.core.security import BCRYPT_ROUNDS, hash_password, verify_password


class TestHashPassword:
    """hash_password 函数测试。"""

    def test_same_password_produces_different_hashes(self) -> None:
        """同一密码两次 hash 结果不同（因为随机盐）。"""
        password = "MySecurePass123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2, "同一密码两次 hash 应该产生不同结果（盐不同）"

    def test_hash_starts_with_bcrypt_identifier(self) -> None:
        """hash 应以 $2b$12$ 开头（bcrypt 标识 + cost=12）。"""
        hashed = hash_password("testpassword")

        assert hashed.startswith("$2b$12$"), f"hash 应以 $2b$12$ 开头，实际为: {hashed[:7]}"

    def test_hash_is_not_plaintext(self) -> None:
        """hash 不应包含明文密码。"""
        password = "SecretPass456!"
        hashed = hash_password(password)

        assert password not in hashed, "hash 中不应包含明文密码"

    def test_bcrypt_rounds_constant_is_12(self) -> None:
        """BCRYPT_ROUNDS 常量应为 12。"""
        assert BCRYPT_ROUNDS == 12

    def test_hash_returns_string(self) -> None:
        """hash_password 应返回字符串类型。"""
        result = hash_password("somepassword")
        assert isinstance(result, str)

    def test_hash_length_is_consistent(self) -> None:
        """bcrypt hash 长度应为 60 字符。"""
        hashed = hash_password("anypassword")
        assert len(hashed) == 60, f"bcrypt hash 长度应为 60，实际为 {len(hashed)}"


class TestVerifyPassword:
    """verify_password 函数测试。"""

    def test_correct_password_returns_true(self) -> None:
        """正确密码验证应返回 True。"""
        password = "CorrectHorseBatteryStaple"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_wrong_password_returns_false(self) -> None:
        """错误密码验证应返回 False。"""
        hashed = hash_password("RightPassword123!")

        assert verify_password("WrongPassword456!", hashed) is False

    def test_empty_password_against_real_hash_returns_false(self) -> None:
        """空密码对真实 hash 验证应返回 False。"""
        hashed = hash_password("SomePassword123!")

        assert verify_password("", hashed) is False

    def test_verify_with_different_hash_of_same_password(self) -> None:
        """用同一密码的不同 hash 验证都应通过。"""
        password = "ConsistentPassword789!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    def test_verify_returns_bool(self) -> None:
        """verify_password 应返回布尔类型。"""
        hashed = hash_password("BoolCheck123!")
        result = verify_password("BoolCheck123!", hashed)

        assert isinstance(result, bool)


class TestPasswordEdgeCases:
    """密码边界情况测试。"""

    def test_unicode_password(self) -> None:
        """支持 Unicode 密码。"""
        password = "密码测试123!@#"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True
        assert verify_password("wrongpassword", hashed) is False

    def test_seventy_two_byte_password(self) -> None:
        """支持 72 字节密码（bcrypt 上限）。"""
        password = "a" * 72
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True
        assert verify_password("a" * 71, hashed) is False

    def test_special_characters_password(self) -> None:
        """支持特殊字符密码。"""
        password = '!@#$%^&*()_+-={}[]|\\:";\'<>?,./`~'
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True
