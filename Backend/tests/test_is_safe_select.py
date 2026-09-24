"""Unit tests for is_safe_select — read-only SELECT / CTE validation."""

from __future__ import annotations

import unittest

from app import is_safe_select


class IsSafeSelectTests(unittest.TestCase):
    def test_normal_select_allowed(self):
        self.assertTrue(is_safe_select('SELECT SUM(total_price) AS revenue FROM sales'))

    def test_select_with_leading_whitespace_allowed(self):
        self.assertTrue(is_safe_select('  \n  SELECT product_name FROM products'))

    def test_select_with_leading_comment_allowed(self):
        sql = '-- analytics\nSELECT product_id FROM sales'
        self.assertTrue(is_safe_select(sql))

    def test_with_select_allowed(self):
        sql = """
        WITH product_sales AS (
            SELECT product_id, SUM(quantity) AS total_quantity_sold
            FROM sales
            GROUP BY product_id
        )
        SELECT p.product_name, ps.total_quantity_sold
        FROM product_sales ps
        JOIN products p ON ps.product_id = p.product_id
        """
        self.assertTrue(is_safe_select(sql))

    def test_with_select_leading_comment_allowed(self):
        sql = """
        /* median CTE */
        WITH product_sales AS (
            SELECT product_id, SUM(quantity) AS qty FROM sales GROUP BY product_id
        )
        SELECT * FROM product_sales
        """
        self.assertTrue(is_safe_select(sql))

    def test_with_insert_rejected(self):
        sql = """
        WITH new_rows AS (SELECT 1 AS id)
        INSERT INTO products (product_id) SELECT id FROM new_rows
        """
        self.assertFalse(is_safe_select(sql))

    def test_with_update_rejected(self):
        sql = """
        WITH targets AS (SELECT product_id FROM products WHERE product_id = 1)
        UPDATE products SET price = 0 WHERE product_id IN (SELECT product_id FROM targets)
        """
        self.assertFalse(is_safe_select(sql))

    def test_with_delete_rejected(self):
        sql = """
        WITH targets AS (SELECT product_id FROM products WHERE product_id = 1)
        DELETE FROM products WHERE product_id IN (SELECT product_id FROM targets)
        """
        self.assertFalse(is_safe_select(sql))

    def test_insert_rejected(self):
        self.assertFalse(is_safe_select('INSERT INTO sales (product_id) VALUES (1)'))

    def test_update_rejected(self):
        self.assertFalse(is_safe_select('UPDATE products SET price = 1'))

    def test_delete_rejected(self):
        self.assertFalse(is_safe_select('DELETE FROM sales'))

    def test_drop_rejected(self):
        self.assertFalse(is_safe_select('DROP TABLE sales'))

    def test_alter_rejected(self):
        self.assertFalse(is_safe_select('ALTER TABLE sales ADD COLUMN x INT'))

    def test_truncate_rejected(self):
        self.assertFalse(is_safe_select('TRUNCATE TABLE sales'))

    def test_create_rejected(self):
        self.assertFalse(is_safe_select('CREATE TABLE foo (id INT)'))

    def test_empty_rejected(self):
        self.assertFalse(is_safe_select(''))
        self.assertFalse(is_safe_select(None))

    def test_with_only_no_outer_select_rejected(self):
        # Unparseable / incomplete WITH without an outer SELECT
        self.assertFalse(is_safe_select('WITH x AS (SELECT 1)'))


if __name__ == '__main__':
    unittest.main()
