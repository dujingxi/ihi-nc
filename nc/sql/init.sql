CREATE DATABASE IF NOT EXISTS `nc`;
USE `nc`;

CREATE TABLE IF NOT EXISTS `adjacency` (
    `account` VARCHAR(100) NOT NULL DEFAULT '',
    `ep_id` varchar(100) NOT NULL DEFAULT '',
    `lr_id` varchar(255) NOT NULL DEFAULT '',
    PRIMARY KEY (`ep_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `lr_node` (
    `lr_id` varchar(255) NOT NULL DEFAULT '',
    `name` VARCHAR(255) DEFAULT '',
    `plr_id` varchar(255) NOT NULL DEFAULT '',
    `ip` VARCHAR(30) NOT NULL DEFAULT '',
    `port` VARCHAR(20) NOT NULL DEFAULT '',
--     `type` varchar(20) NOT NULL DEFAULT '',
    `operator` varchar(20) NOT NULL DEFAULT '',
    `cloud` VARCHAR(20) NOT NULL DEFAULT '',
    `price` int NOT NULL DEFAULT 0,
    `lr_type` varchar(10) NOT NULL DEFAULT '',
    PRIMARY KEY (`lr_id`),
    KEY `address` (`ip`, `port`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `net_qos` (
    `id` int NOT NULL AUTO_INCREMENT,
    `lr_src` VARCHAR(255) NOT NULL DEFAULT '',
    `lr_dst` VARCHAR(255) NOT NULL DEFAULT '',
    `weight` FLOAT(5,2) NOT NULL DEFAULT 0.00,
    `path` FLOAT(5,2) NOT NULL DEFAULT 0.00,
    PRIMARY KEY (`id`),
    INDEX(`lr_src`, `lr_dst`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `force_route` (
    `id` int NOT NULL AUTO_INCREMENT,
    `account` VARCHAR(255) NOT NULL DEFAULT '',
    `lr` VARCHAR(255) NOT NULL DEFAULT '',
    `lr_id` VARCHAR(255) NOT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY (`account`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8

/* CREATE INDEX lr_index on `net_qos` (`lr_src`, `lr_dst`);
