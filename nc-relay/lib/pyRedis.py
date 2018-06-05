#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import redis
import nc_config
import logging
from  MysqlDB import db
sys.setrecursionlimit(100000)

redis_client = redis.Redis(host=nc_config.REDIS_ARGUMENTS["host"] , port=nc_config.REDIS_ARGUMENTS["port"], db=nc_config.REDIS_ARGUMENTS["db"] )
logger = logging.getLogger("nc")


# 获取指定level_id的上层关系
def getAncestor(level_id, reslist=[]):
    ''' 递归获取指定LR的父层LR '''
    while True:
        plevel_id = redis_client.hget("level:%s" % level_id, "plevel_id")
        if plevel_id == "0":
            return reslist
        else:
            reslist.append(plevel_id)
            return getAncestor(plevel_id, reslist)
#  print getAncestor("41")


# 自level_node表中获取所有level_id
def getAlllevel():
    level_list = []
    res = redis_client.keys("level:*")
    for level in res:
        level_list.append(level.split(":")[1])
    return level_list


# 重设redis中每层的层级关系列表
def reset_ancestors():
    level_list = getAlllevel()
    old_list = redis_client.keys("ancestors:*")
    for l in old_list:
        redis_client.delete(l)
    for level in level_list:
        redis_client.rpush("ancestors:%s"%level, level)
        for x in getAncestor(level, []):
            redis_client.rpush("ancestors:%s"%level, x)


# 初始化redis数据库
def redis_init(client):
    # 初始化用户信息，string 格式：userid:xxxxxx "level_id"
    sqls_user = """select `ep_id`, `level_id` from adjacency"""
    res_user = db.execFetch(sqls_user)
    for user in res_user:
        user_id, user_level = user
        client.set("user:%s"%user_id, user_level)

    # 初始化lr信息，hash 格式：lrid:level_id:xxxxxx {"lr_type": "dlr", "ip": "10.x.x.x", "port": "900x", "sysload": 0, "last_subtime": "1509840xxx", "active": 1}
    sqls_lr = """select `lr_id`, `level_id`, `lr_type`, `ip`, `port`, `cluster`, `sysload`, `last_subtime`, `active` from lr_node"""
    res_lr = db.execFetch(sqls_lr)
    for lr in res_lr:
        lr_id, level_id, lr_type, ip, port, cluster, sysload, last_subtime, active = lr
        client.hmset("lr:%s:%s"%(level_id, lr_id), {"sysload": sysload, "ip": ip, "port": port, "cluster": cluster, "lr_type": lr_type, "last_subtime": last_subtime, "active": active})

    # 初始化level信息，hash 格式：level:xxxxxx {"plevel_id": "xxx", "level_cluster": "xxx", "level_type": "xxx"}
    sqls_level = """select `level_id`,`level_cluster`,`plevel_id`,`level_type` from level_node"""
    res_level = db.execFetch(sqls_level)
    for level in res_level:
        level_id, level_cluster, plevel_id, level_type = level
        client.hmset("level:%s"%level_id, {"level_cluster": level_cluster, "plevel_id": plevel_id, "level_type": level_type})

    # 初始化每个level的递归父层，list 格式：ancestors:xxx ['xxx', 'xxxxx', 'xxxxx']
    reset_ancestors()
#  redis_init(redis_client)

def redis_save(client):
    #  logger = logging.getLogger("nc")
    lr_sysload_list = client.keys("lr:*")
    sqlu_sys = """update lr_node set `sysload` = CASE `lr_id` """
    sqlu_time = """update lr_node set `last_subtime` = CASE `lr_id` """
    sqlu_active = """update lr_node set `active` = CASE `lr_id` """
    for lr in lr_sysload_list:
        sysload, last_subtime, active = client.hmget(lr, "sysload", "last_subtime", "active")
        sqlu_sys += "WHEN '%s' THEN '%s' "% (lr.split(":")[2], sysload)
        sqlu_time += "WHEN '%s' THEN '%s'"%(lr.split(":")[2], last_subtime)
        sqlu_active += "WHEN '%s' THEN '%s'"%(lr.split(":")[2], active)
    sqlu_sys += "END"
    sqlu_time += "END"
    sqlu_active += "END"
    db.execFetch(sqlu_sys)
    db.execFetch(sqlu_time)
    db.execFetch(sqlu_active)

#  redis_save(client)

