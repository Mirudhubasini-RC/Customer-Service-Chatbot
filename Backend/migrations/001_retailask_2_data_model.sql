-- RetailAsk 2.0 Step 1 — additive data-model migration for EXISTING databases
-- Safe to run on a DB that already has products / sales / customer_queries.
-- Does NOT drop or rename existing tables/columns.
-- Does NOT modify customer_queries.
--
-- brands / categories / issues / customer_feedback rows and product brand/category
-- assignments below are DEMO / ENRICHED data for analytics demos.

SET NAMES utf8mb4;

-- ---------------------------------------------------------------------------
-- DEMO / ENRICHED: lookup tables
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `brands` (
  `brand_id` int NOT NULL AUTO_INCREMENT,
  `brand_name` varchar(100) NOT NULL,
  PRIMARY KEY (`brand_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `categories` (
  `category_id` int NOT NULL AUTO_INCREMENT,
  `category_name` varchar(100) NOT NULL,
  PRIMARY KEY (`category_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `issues` (
  `issue_id` int NOT NULL AUTO_INCREMENT,
  `issue_name` varchar(100) NOT NULL,
  PRIMARY KEY (`issue_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `brands` (`brand_id`, `brand_name`) VALUES
(1,'TechNova'),
(2,'SoundMax'),
(3,'DeskPro'),
(4,'PowerLink'),
(5,'ViewClear')
ON DUPLICATE KEY UPDATE `brand_name` = VALUES(`brand_name`);

INSERT INTO `categories` (`category_id`, `category_name`) VALUES
(1,'Computers'),
(2,'Mobile'),
(3,'Audio'),
(4,'Accessories'),
(5,'Furniture'),
(6,'Networking')
ON DUPLICATE KEY UPDATE `category_name` = VALUES(`category_name`);

INSERT INTO `issues` (`issue_id`, `issue_name`) VALUES
(1,'Defective product'),
(2,'Late delivery'),
(3,'Wrong item received'),
(4,'Pricing concern'),
(5,'Battery life'),
(6,'Durability'),
(7,'Compatibility'),
(8,'Packaging damage')
ON DUPLICATE KEY UPDATE `issue_name` = VALUES(`issue_name`);

-- ---------------------------------------------------------------------------
-- Extend products with nullable FKs (additive; preserves existing rows)
-- ---------------------------------------------------------------------------
SET @db := DATABASE();

SET @sql := (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `products` ADD COLUMN `brand_id` int DEFAULT NULL',
    'SELECT ''products.brand_id already exists'''
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'products' AND COLUMN_NAME = 'brand_id'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `products` ADD COLUMN `category_id` int DEFAULT NULL',
    'SELECT ''products.category_id already exists'''
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'products' AND COLUMN_NAME = 'category_id'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Add FK constraints if missing
SET @sql := (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `products` ADD CONSTRAINT `products_ibfk_brand` FOREIGN KEY (`brand_id`) REFERENCES `brands` (`brand_id`)',
    'SELECT ''products_ibfk_brand already exists'''
  )
  FROM information_schema.TABLE_CONSTRAINTS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'products' AND CONSTRAINT_NAME = 'products_ibfk_brand'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE `products` ADD CONSTRAINT `products_ibfk_category` FOREIGN KEY (`category_id`) REFERENCES `categories` (`category_id`)',
    'SELECT ''products_ibfk_category already exists'''
  )
  FROM information_schema.TABLE_CONSTRAINTS
  WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'products' AND CONSTRAINT_NAME = 'products_ibfk_category'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- DEMO / ENRICHED: backfill brand/category on existing product_ids (names/prices untouched)
UPDATE `products` SET `brand_id` = 1, `category_id` = 1 WHERE `product_id` = 1;
UPDATE `products` SET `brand_id` = 1, `category_id` = 2 WHERE `product_id` = 2;
UPDATE `products` SET `brand_id` = 2, `category_id` = 3 WHERE `product_id` = 3;
UPDATE `products` SET `brand_id` = 5, `category_id` = 1 WHERE `product_id` = 4;
UPDATE `products` SET `brand_id` = 4, `category_id` = 4 WHERE `product_id` = 5;
UPDATE `products` SET `brand_id` = 4, `category_id` = 4 WHERE `product_id` = 6;
UPDATE `products` SET `brand_id` = 1, `category_id` = 2 WHERE `product_id` = 7;
UPDATE `products` SET `brand_id` = 1, `category_id` = 2 WHERE `product_id` = 8;
UPDATE `products` SET `brand_id` = 4, `category_id` = 4 WHERE `product_id` = 9;
UPDATE `products` SET `brand_id` = 5, `category_id` = 4 WHERE `product_id` = 10;
UPDATE `products` SET `brand_id` = 4, `category_id` = 4 WHERE `product_id` = 11;
UPDATE `products` SET `brand_id` = 4, `category_id` = 6 WHERE `product_id` = 12;
UPDATE `products` SET `brand_id` = 2, `category_id` = 3 WHERE `product_id` = 13;
UPDATE `products` SET `brand_id` = 3, `category_id` = 5 WHERE `product_id` = 14;
UPDATE `products` SET `brand_id` = 3, `category_id` = 5 WHERE `product_id` = 15;
UPDATE `products` SET `brand_id` = 3, `category_id` = 5 WHERE `product_id` = 16;
UPDATE `products` SET `brand_id` = 4, `category_id` = 4 WHERE `product_id` = 17;
UPDATE `products` SET `brand_id` = 4, `category_id` = 4 WHERE `product_id` = 18;
UPDATE `products` SET `brand_id` = 4, `category_id` = 4 WHERE `product_id` = 19;
UPDATE `products` SET `brand_id` = 4, `category_id` = 4 WHERE `product_id` = 20;
UPDATE `products` SET `brand_id` = 3, `category_id` = 5 WHERE `product_id` = 21;
UPDATE `products` SET `brand_id` = 4, `category_id` = 4 WHERE `product_id` = 22;
UPDATE `products` SET `brand_id` = 3, `category_id` = 5 WHERE `product_id` = 23;
UPDATE `products` SET `brand_id` = 4, `category_id` = 4 WHERE `product_id` = 24;

-- ---------------------------------------------------------------------------
-- DEMO / ENRICHED: customer_feedback
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `customer_feedback` (
  `feedback_id` int NOT NULL AUTO_INCREMENT,
  `product_id` int NOT NULL,
  `issue_id` int DEFAULT NULL,
  `feedback_text` text NOT NULL,
  `sentiment` enum('positive','negative','neutral') NOT NULL,
  `is_return` tinyint(1) NOT NULL DEFAULT '0',
  `return_reason` varchar(255) DEFAULT NULL,
  `feedback_date` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`feedback_id`),
  KEY `customer_feedback_product_id` (`product_id`),
  KEY `customer_feedback_issue_id` (`issue_id`),
  CONSTRAINT `customer_feedback_ibfk_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`product_id`),
  CONSTRAINT `customer_feedback_ibfk_issue` FOREIGN KEY (`issue_id`) REFERENCES `issues` (`issue_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `customer_feedback` (
  `feedback_id`, `product_id`, `issue_id`, `feedback_text`, `sentiment`, `is_return`, `return_reason`, `feedback_date`
) VALUES
(1,1,1,'Laptop screen developed dead pixels within two weeks of purchase.','negative',1,'Defective display','2024-08-20 10:15:00'),
(2,1,5,'Battery lasts barely 3 hours under light office use.','negative',0,NULL,'2024-08-22 14:30:00'),
(3,2,NULL,'Smartphone camera quality is excellent for the price.','positive',0,NULL,'2024-08-18 09:05:00'),
(4,3,6,'Headphones ear cushions tore after one month of daily use.','negative',1,'Poor durability','2024-08-25 16:40:00'),
(5,3,NULL,'Sound clarity is great for calls and music.','positive',0,NULL,'2024-08-12 11:20:00'),
(6,6,7,'Mouse pairing drops frequently with older laptops.','negative',0,NULL,'2024-08-19 13:10:00'),
(7,7,5,'Smartwatch battery drains overnight even with low usage.','negative',1,'Battery failure','2024-08-28 08:45:00'),
(8,8,2,'Tablet arrived 8 days later than the promised delivery window.','negative',0,NULL,'2024-08-21 17:55:00'),
(9,12,NULL,'Router setup was simple and coverage is strong across rooms.','positive',0,NULL,'2024-08-15 12:00:00'),
(10,12,7,'Router firmware update broke compatibility with some IoT devices.','negative',0,NULL,'2024-09-01 19:25:00'),
(11,14,8,'Desk chair box arrived crushed; foam was compressed.','negative',1,'Packaging damage','2024-08-23 15:05:00'),
(12,15,NULL,'Standing desk is sturdy and height adjustment is smooth.','positive',0,NULL,'2024-08-27 10:50:00'),
(13,4,4,'Monitor price jumped right after my purchase; felt overcharged.','neutral',0,NULL,'2024-08-16 18:30:00'),
(14,19,3,'Ordered a power bank but received a charger instead.','negative',1,'Wrong item received','2024-08-29 09:40:00'),
(15,10,NULL,'Webcam image is clear for remote meetings.','positive',0,NULL,'2024-08-14 20:10:00')
ON DUPLICATE KEY UPDATE
  `product_id` = VALUES(`product_id`),
  `issue_id` = VALUES(`issue_id`),
  `feedback_text` = VALUES(`feedback_text`),
  `sentiment` = VALUES(`sentiment`),
  `is_return` = VALUES(`is_return`),
  `return_reason` = VALUES(`return_reason`),
  `feedback_date` = VALUES(`feedback_date`);
