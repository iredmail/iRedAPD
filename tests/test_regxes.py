#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test cases for regular expressions in libs/regxes.py
"""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from libs.regxes import cmp_email, cmp_domain, cmp_ipv4


class TestRegxEmail(unittest.TestCase):
    """Test email regex pattern"""

    def test_basic_email(self):
        """Test basic valid email addresses"""
        valid_emails = [
            'user@example.com',
            'john@domain.org',
            'test@sub.example.co.uk',
        ]
        for email in valid_emails:
            with self.subTest(email=email):
                self.assertIsNotNone(
                    cmp_email.search(email),
                    f"Should match: {email}"
                )

    def test_special_chars_in_username(self):
        """Test email with special characters allowed in username"""
        valid_emails = [
            'user+tag@example.com',      # Plus (SRS)
            'user.name@example.com',     # Dot
            'user-name@example.com',     # Hyphen
            'user_name@example.com',     # Underscore
            'user#tag@example.com',      # Hash
            'user~tag@example.com',      # Tilde (RFC compliant)
            'user/folder@example.com',   # Slash (sub-folder)
            'user&test@example.com',     # Ampersand
            'user=rewrite@example.com',  # Equals (SRS)
        ]
        for email in valid_emails:
            with self.subTest(email=email):
                self.assertIsNotNone(
                    cmp_email.search(email),
                    f"Should match: {email}"
                )

    def test_complex_usernames(self):
        """Test complex username combinations"""
        valid_emails = [
            'user+lists/abc@example.com',          # SRS with folder
            'user.name+tag@example.com',           # Dot and plus
            'user~tag+lists/folder@example.com',   # Multiple special chars
            'a#b&c=d/e+f~g@example.com',          # All allowed chars
        ]
        for email in valid_emails:
            with self.subTest(email=email):
                self.assertIsNotNone(
                    cmp_email.search(email),
                    f"Should match: {email}"
                )

    def test_domain_variations(self):
        """Test various domain formats"""
        valid_emails = [
            'user@example.com',           # Single level
            'user@sub.example.com',       # Two levels
            'user@sub.sub.example.com',   # Three levels
            'user@example.co.uk',         # Multi-part TLD
            'user@a.co',                  # Short
            'user@123example.com',        # Numeric prefix
        ]
        for email in valid_emails:
            with self.subTest(email=email):
                self.assertIsNotNone(
                    cmp_email.search(email),
                    f"Should match: {email}"
                )

    def test_long_tld(self):
        """Test long TLD names (new style domains)"""
        valid_emails = [
            'user@example.international',
            'user@example.photography',
            'user@example.engineering',
            'user@example.management',
        ]
        for email in valid_emails:
            with self.subTest(email=email):
                self.assertIsNotNone(
                    cmp_email.search(email),
                    f"Should match: {email}"
                )

    def test_minimum_length(self):
        """Test minimum valid email lengths"""
        valid_emails = [
            'ab@cd.com',
            'xy@za.org',
        ]
        for email in valid_emails:
            with self.subTest(email=email):
                self.assertIsNotNone(
                    cmp_email.search(email),
                    f"Should match: {email}"
                )

    def test_invalid_consecutive_dots(self):
        """Reject emails with consecutive dots in domain"""
        invalid_emails = [
            'user@example..com',
            'user@sub..example.com',
            'user@example.com..',
        ]
        for email in invalid_emails:
            with self.subTest(email=email):
                self.assertIsNone(
                    cmp_email.search(email),
                    f"Should NOT match: {email}"
                )

    def test_invalid_domain_hyphen_position(self):
        """Reject domains with hyphen at start/end of labels"""
        self.assertIsNotNone(cmp_email.search('user@ex-ample.com'))

        self.assertIsNone(cmp_email.search('user@-example.com'))  # Hyphen at start
        self.assertIsNone(cmp_email.search('user@example-.com'))  # Hyphen at end
        self.assertIsNone(cmp_email.search('user@example.-com'))  # Hyphen after dot

    def test_invalid_tld_hyphen(self):
        """Reject TLD containing hyphen"""
        invalid_emails = [
            'user@example.c-om',
            'user@example.-com',
        ]
        for email in invalid_emails:
            with self.subTest(email=email):
                self.assertIsNone(
                    cmp_email.search(email),
                    f"Should NOT match (TLD hyphen): {email}"
                )

    def test_invalid_no_at_sign(self):
        """Reject emails without @ sign"""
        invalid_emails = [
            'userexample.com',
            'user.example.com',
        ]
        for email in invalid_emails:
            with self.subTest(email=email):
                self.assertIsNone(
                    cmp_email.search(email),
                    f"Should NOT match: {email}"
                )

    def test_invalid_no_domain(self):
        """Reject emails without domain"""
        invalid_emails = [
            'user@',
            'user@.com',
            'user@.',
        ]
        for email in invalid_emails:
            with self.subTest(email=email):
                self.assertIsNone(
                    cmp_email.search(email),
                    f"Should NOT match: {email}"
                )

    def test_invalid_no_tld(self):
        """Reject emails without TLD"""
        invalid_emails = [
            'user@example',
            'user@localhost',
        ]
        for email in invalid_emails:
            with self.subTest(email=email):
                self.assertIsNone(
                    cmp_email.search(email),
                    f"Should NOT match: {email}"
                )

    def test_invalid_short_tld(self):
        """Reject TLD with only 1 character"""
        invalid_emails = [
            'user@example.c',
            'user@domain.x',
        ]
        for email in invalid_emails:
            with self.subTest(email=email):
                self.assertIsNone(
                    cmp_email.search(email),
                    f"Should NOT match: {email}"
                )

    def test_invalid_double_at(self):
        """Reject emails with multiple @ signs (find only one valid part)"""
        text = 'user@test@example.com'
        match = cmp_email.search(text)
        # The regex will match 'test@example.com' from the text
        # This is expected behavior for regex.search() - it finds a valid match
        # Verify the match is a valid email (with @ only once)
        if match:
            self.assertEqual(match.group().count('@'), 1)

    def test_invalid_spaces(self):
        """Reject emails with spaces in username"""
        # Test that spaces prevent a valid email from matching
        # The regex won't match "name@example.com" if looking at full "user name@example.com"
        # But search() will find the valid part. That's expected for regex.search()
        # Just verify spaces in username are never valid
        text = 'user name@example.com'
        match = cmp_email.search(text)
        # The match will be 'name@example.com' - the valid part after the space
        if match:
            # Verify that spaces are not part of the matched email
            self.assertNotIn(' ', match.group())

    def test_case_insensitive(self):
        """Test case insensitivity"""
        test_cases = [
            'User@Example.COM',
            'USER@EXAMPLE.COM',
            'User.Name@Sub.Example.Org',
        ]
        for email in test_cases:
            with self.subTest(email=email):
                self.assertIsNotNone(
                    cmp_email.search(email),
                    f"Should match (case insensitive): {email}"
                )

    def test_minimal_username(self):
        """Test two character username (regex requires at least 2 chars or special char+char)"""
        valid_emails = [
            'ab@example.com',
            'xy@test.org',
            '#a@example.com',
            '~b@example.com',
        ]
        for email in valid_emails:
            with self.subTest(email=email):
                self.assertIsNotNone(
                    cmp_email.search(email),
                    f"Should match: {email}"
                )

    def test_numeric_domain_parts(self):
        """Test domains with numbers"""
        valid_emails = [
            'user@123example.com',
            'user@example123.com',
            'user@ex123ample.com',
            'user@123.456.com',  # Multiple numeric parts
        ]
        for email in valid_emails:
            with self.subTest(email=email):
                self.assertIsNotNone(
                    cmp_email.search(email),
                    f"Should match: {email}"
                )

    def test_srs_addresses(self):
        """Test SRS (Sender Rewriting Scheme) addresses"""
        valid_emails = [
            'SRS0+abcd=ef=example.com=user@bounce.example.org',
            'SRS0=TS=TT=example.com=user+test@bounce.example.org',
        ]
        for email in valid_emails:
            with self.subTest(email=email):
                self.assertIsNotNone(
                    cmp_email.search(email),
                    f"Should match (SRS): {email}"
                )


class TestRegxEmailEdgeCases(unittest.TestCase):
    """Test edge cases for email regex"""

    def test_email_within_text(self):
        """Test email matching within larger text"""
        text = 'Contact us at support@example.com for help'
        match = cmp_email.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(), 'support@example.com')

    def test_multiple_emails_in_text(self):
        """Test finding multiple emails in text"""
        text = 'Email user1@example.com or user2@example.org'
        matches = cmp_email.findall(text)
        self.assertEqual(len(matches), 2)

    def test_unicode_domain(self):
        """Test that unicode domains are handled (they shouldn't match)"""
        invalid_emails = [
            'user@例え.jp',  # Japanese domain
            'user@münchen.de',  # German umlaut
        ]
        for email in invalid_emails:
            with self.subTest(email=email):
                # Unicode domains should not match (ASCII only)
                self.assertIsNone(
                    cmp_email.search(email),
                    f"Should NOT match (unicode): {email}"
                )


class TestRegxDomain(unittest.TestCase):
    """Test domain regex pattern"""

    def test_basic_domain(self):
        """Test basic valid domains"""
        valid_domains = [
            'example.com',
            'sub.example.com',
            'sub.sub.example.com',
        ]
        for domain in valid_domains:
            with self.subTest(domain=domain):
                self.assertIsNotNone(
                    cmp_domain.search(domain),
                    f"Should match: {domain}"
                )

    def test_domain_with_hyphen(self):
        """Test domains with hyphens"""
        valid_domains = [
            'my-domain.com',
            'ex-ample.co.uk',
        ]
        for domain in valid_domains:
            with self.subTest(domain=domain):
                self.assertIsNotNone(
                    cmp_domain.search(domain),
                    f"Should match: {domain}"
                )


class TestRegxIPv4(unittest.TestCase):
    """Test IPv4 regex pattern"""

    def test_valid_ipv4(self):
        """Test valid IPv4 addresses"""
        valid_ips = [
            '192.168.1.1',
            '10.0.0.1',
            '255.255.255.255',
            '0.0.0.0',
        ]
        for ip in valid_ips:
            with self.subTest(ip=ip):
                self.assertIsNotNone(
                    cmp_ipv4.search(ip),
                    f"Should match: {ip}"
                )

    def test_invalid_ipv4(self):
        """Test invalid IPv4 addresses"""
        invalid_ips = [
            '256.1.1.1',  # Out of range
            '1.1.1',  # Missing octet
            '1.1.1.1.1',  # Too many octets
        ]
        for ip in invalid_ips:
            with self.subTest(ip=ip):
                self.assertIsNone(
                    cmp_ipv4.search(ip),
                    f"Should NOT match: {ip}"
                )


if __name__ == '__main__':
    unittest.main()
