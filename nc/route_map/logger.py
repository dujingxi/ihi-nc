#!/usr/bin/env python2.7
# coding=utf-8

# Filename: logger.py
# Description: Log module

# Author: fanyongjun <fanyongjun@streamocean.com>
# License: StreamOcean
# Last-Updated: 2018/02/02

import config
import logging
import logging.handlers
import os
import os.path

logger = None
log_level = config.log_level
log_dir = config.log_dir
log_max_size = config.log_max_size
backup_num = config.backup_num

if not os.path.exists(log_dir):
    os.mkdir(log_dir)

def init_log(name):
    global logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    fh = logging.handlers.RotatingFileHandler(log_dir + name + ".log",maxBytes=log_max_size,backupCount=backup_num)
    formatter = logging.Formatter("%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s","%a, %d %b %Y %H:%M:%S")
    fh.setFormatter(formatter)
    logger.addHandler(fh)
