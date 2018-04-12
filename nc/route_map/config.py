#!/usr/bin/env python

#######################################################
# Filename: config.py
# Description: configuration for route_map

# Author: fanyongjun <fanyongjun@streamocean.com>
# License: StreamOcean
# Last-Updated: 2018/02/02
#######################################################

# LR id file path(full path)
lr_id_dir = './.lrid'

# NC Server API
nc_get_lr_info = "http://172.16.1.172:8000/api/getlist"
nc_upload_sysload = "http://172.16.1.172:8000/api/upsysload"
nc_upload_qos = "http://172.16.1.172:8000/api/upqosdata"
# nc_server = "http://127.0.0.1:5000/test"

# ping module arguments
ping_args = {
             'timeout':2,
             'count':100,
             'psize':64,
            }
# ping check interval in second
ping_check_interval = 30

# system load check interval in second
sys_load_interval = 10

# log config
log_dir = 'logs/'
# set log level
# NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL
log_level = "INFO"
# one log file max size 100M(Byte)
log_max_size = 104857600 
# log backup num
backup_num = 5
