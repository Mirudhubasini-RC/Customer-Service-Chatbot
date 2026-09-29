-- RetailAsk — user feedback on answers (continual feedback loop).
-- Additive only. The backend also creates this table on first use
-- (feedback_store.ensure_table), so running this file is optional.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `answer_feedback` (
  `feedback_id` int NOT NULL AUTO_INCREMENT,
  `question` text NOT NULL,
  `answer` text,
  `rating` enum('up','down') NOT NULL,
  `comment` text,
  `expected_answer` text,
  `route` varchar(32) DEFAULT NULL,
  `generated_sql` text,
  `expected_route` varchar(32) DEFAULT NULL,
  `expected_keywords` varchar(500) DEFAULT NULL,
  `in_eval_set` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `reviewed_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`feedback_id`),
  KEY `answer_feedback_rating` (`rating`),
  KEY `answer_feedback_in_eval_set` (`in_eval_set`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
