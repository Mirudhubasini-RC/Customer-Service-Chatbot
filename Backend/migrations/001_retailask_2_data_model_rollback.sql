-- RetailAsk 2.0 Step 1 — ROLLBACK for migration 001_retailask_2_data_model.sql
-- Removes only the additive 2.0 objects. Does NOT delete products/sales/customer_queries rows.
-- After rollback, products.brand_id / products.category_id are dropped if present.

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=0;

DROP TABLE IF EXISTS `customer_feedback`;
DROP TABLE IF EXISTS `issues`;

-- Drop product FK constraints / columns added in Step 1 (ignore errors if already gone)
SET @db := DATABASE();

SET @sql := (
  SELECT IF(
    COUNT(*) > 0,
    'ALTER TABLE `products` DROP FOREIGN KEY `products_ibfk_brand`',
    'SELECT ''products_ibfk_brand not present'''
  )
  FROM information_schema.TABLE_CONSTRAINTS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'products' AND CONSTRAINT_NAME = 'products_ibfk_brand'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    COUNT(*) > 0,
    'ALTER TABLE `products` DROP FOREIGN KEY `products_ibfk_category`',
    'SELECT ''products_ibfk_category not present'''
  )
  FROM information_schema.TABLE_CONSTRAINTS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'products' AND CONSTRAINT_NAME = 'products_ibfk_category'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    COUNT(*) > 0,
    'ALTER TABLE `products` DROP COLUMN `brand_id`',
    'SELECT ''products.brand_id not present'''
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'products' AND COLUMN_NAME = 'brand_id'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    COUNT(*) > 0,
    'ALTER TABLE `products` DROP COLUMN `category_id`',
    'SELECT ''products.category_id not present'''
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'products' AND COLUMN_NAME = 'category_id'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

DROP TABLE IF EXISTS `brands`;
DROP TABLE IF EXISTS `categories`;

SET FOREIGN_KEY_CHECKS=1;
