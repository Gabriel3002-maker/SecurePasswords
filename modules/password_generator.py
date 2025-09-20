import random
import string
import secrets

class PasswordGenerator:
    def __init__(self):
        self.lowercase = string.ascii_lowercase
        self.uppercase = string.ascii_uppercase
        self.digits = string.digits
        self.symbols = "!@#$%^&*()_+-=[]{}|;:,.<>?"

    def generate_password(self, length: int = 16, use_lowercase: bool = True,
                         use_uppercase: bool = True, use_digits: bool = True,
                         use_symbols: bool = True) -> str:
        """
        Generate a secure random password

        Args:
            length: Length of the password (minimum 4)
            use_lowercase: Include lowercase letters
            use_uppercase: Include uppercase letters
            use_digits: Include digits
            use_symbols: Include special characters

        Returns:
            Generated password string
        """
        if length < 4:
            length = 4

        # Ensure at least one character type is selected
        if not any([use_lowercase, use_uppercase, use_digits, use_symbols]):
            use_lowercase = True

        # Build character set based on options
        char_set = ""
        if use_lowercase:
            char_set += self.lowercase
        if use_uppercase:
            char_set += self.uppercase
        if use_digits:
            char_set += self.digits
        if use_symbols:
            char_set += self.symbols

        # Ensure minimum requirements are met
        password = []
        if use_lowercase:
            password.append(secrets.choice(self.lowercase))
        if use_uppercase:
            password.append(secrets.choice(self.uppercase))
        if use_digits:
            password.append(secrets.choice(self.digits))
        if use_symbols:
            password.append(secrets.choice(self.symbols))

        # Fill remaining length with random characters
        remaining_length = length - len(password)
        if remaining_length > 0:
            password.extend(secrets.choice(char_set) for _ in range(remaining_length))

        # Shuffle the password
        random.shuffle(password)

        return ''.join(password)

    def generate_pin(self, length: int = 4) -> str:
        """Generate a numeric PIN"""
        return ''.join(secrets.choice(self.digits) for _ in range(length))

    def generate_passphrase(self, num_words: int = 4, separator: str = "-") -> str:
        """Generate a passphrase using common words"""
        # Common words for passphrases
        word_list = [
            "apple", "banana", "cherry", "date", "elder", "fig", "grape", "honey",
            "kiwi", "lemon", "mango", "nectar", "orange", "peach", "quince", "rose",
            "sun", "tree", "unity", "violet", "water", "xray", "yellow", "zebra",
            "bridge", "castle", "diamond", "eagle", "forest", "garden", "hammer",
            "island", "jungle", "knight", "ladder", "mountain", "needle", "ocean",
            "palace", "queen", "river", "sword", "tiger", "umbrella", "valley",
            "whale", "xylophone", "yacht", "zeppelin"
        ]

        words = [secrets.choice(word_list).capitalize() for _ in range(num_words)]
        return separator.join(words)

    def check_password_strength(self, password: str) -> dict:
        """
        Check the strength of a password

        Returns:
            Dictionary with strength score and feedback
        """
        score = 0
        feedback = []

        # Length check
        if len(password) >= 8:
            score += 1
        else:
            feedback.append("Password should be at least 8 characters long")

        if len(password) >= 12:
            score += 1

        # Character variety checks
        has_lower = any(c.islower() for c in password)
        has_upper = any(c.isupper() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_symbol = any(c in self.symbols for c in password)

        if has_lower:
            score += 1
        else:
            feedback.append("Add lowercase letters")

        if has_upper:
            score += 1
        else:
            feedback.append("Add uppercase letters")

        if has_digit:
            score += 1
        else:
            feedback.append("Add numbers")

        if has_symbol:
            score += 1
        else:
            feedback.append("Add special characters")

        # Common patterns check
        if password.lower() in ["password", "123456", "qwerty", "admin", "letmein"]:
            score = 0
            feedback.append("Avoid common passwords")

        # Determine strength level
        if score <= 2:
            strength = "Weak"
        elif score <= 4:
            strength = "Medium"
        elif score <= 6:
            strength = "Strong"
        else:
            strength = "Very Strong"

        return {
            "score": score,
            "strength": strength,
            "feedback": feedback
        }

    def get_password_entropy(self, password: str) -> float:
        """
        Calculate password entropy (bits of security)

        Args:
            password: The password to analyze

        Returns:
            Entropy in bits
        """
        char_set_size = 0

        if any(c.islower() for c in password):
            char_set_size += 26
        if any(c.isupper() for c in password):
            char_set_size += 26
        if any(c.isdigit() for c in password):
            char_set_size += 10
        if any(c in self.symbols for c in password):
            char_set_size += len(self.symbols)

        if char_set_size == 0:
            return 0

        import math
        return len(password) * math.log2(char_set_size)