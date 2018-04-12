CREATE DATABASE IF NOT EXISTS `nctest`;
USE `nctest`;

CREATE TABLE IF NOT EXISTS `lr_grid` (
    `lrg_id` VARCHAR(100) NOT NULL DEFAULT '',
    `lrg_name` VARCHAR(100) DEFAULT NULL,
    `vsp_id` VARCHAR(100) NOT NULL DEFAULT '',
    PRIMARY KEY (`lrg_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `lr_cluster` (
    `lrc_id` VARCHAR(100) NOT NULL DEFAULT '',
    `lrc_name` VARCHAR(100) NOT NULL DEFAULT '',
    `region` VARCHAR(100) DEFAULT '',
    `lrg_ids` VARCHAR(500) NOT NULL DEFAULT '',
    PRIMARY KEY (`lrc_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `adjacency` (
    `account` VARCHAR(100) NOT NULL DEFAULT '',
    `ep_id` varchar(100) NOT NULL DEFAULT '',
    `level_id` varchar(100) NOT NULL DEFAULT '',
    `vsp_id` VARCHAR(100) NOT NULL DEFAULT '',
    PRIMARY KEY (`ep_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `lr_node` (
    `lr_id` varchar(255) NOT NULL DEFAULT '',
    `name` VARCHAR(255) DEFAULT '',
    `plevel_id` varchar(255) NOT NULL DEFAULT '',
    `ip` VARCHAR(30) NOT NULL DEFAULT '',
    `port` VARCHAR(20) NOT NULL DEFAULT '',
--     `type` varchar(20) NOT NULL DEFAULT '',
    `operator` varchar(20) NOT NULL DEFAULT '',
    `cloud` VARCHAR(20) NOT NULL DEFAULT '',
    `price` int NOT NULL DEFAULT 0,
    `lr_type` varchar(10) NOT NULL DEFAULT '',
    `sysload` int(100) NOT NULL DEFAULT '0',
    `level_id` varchar(100) NOT NULL DEFAULT '',
    `lrc_ids` varchar(500) DEFAULT NULL,
    PRIMARY KEY (`lr_id`),
    KEY `address` (`ip`, `port`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `net_qos` (
    `id` int NOT NULL AUTO_INCREMENT,
    `level_src` VARCHAR(255) NOT NULL DEFAULT '',
    `level_dst` VARCHAR(255) NOT NULL DEFAULT '',
    `weight` FLOAT(5,2) NOT NULL DEFAULT 0.00,
    `path` FLOAT(5,2) NOT NULL DEFAULT 0.00,
    PRIMARY KEY (`id`),
    INDEX(`level_src`, `level_dst`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `force_route` (
    `id` int NOT NULL AUTO_INCREMENT,
    `account` VARCHAR(255) NOT NULL DEFAULT '',
    `lr` VARCHAR(255) NOT NULL DEFAULT '',
    `lr_id` VARCHAR(255) NOT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY (`account`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `level_node` (
    `id` int NOT NULL AUTO_INCREMENT,
    `level_id` VARCHAR(100) NOT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY (`level_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8

/* CREATE INDEX lr_index on `net_qos` (`lr_src`, `lr_dst`);
