#!/usr/bin/env python
# -*- coding: utf-8 -*-

import redis
import nc_config
import logging
from  MysqlDB import db

redis_client = redis.Redis(host=nc_config.REDIS_ARGUMENTS["host"] , port=nc_config.REDIS_ARGUMENTS["port"], db=nc_config.REDIS_ARGUMENTS["db"] )

def redis_init(client):
    sqls_user = """select `ep_id`, `level_id`, `vsp_id` from adjacency"""
    res_user = db.execFetch(sqls_user)
    for ep, ep_level, ep_vsp in res_user:
        client.hmset("user:%s"%ep, {"level_id": ep_level, "vsp_id": ep_vsp})

    sqls_sys = """select `lr_id`, `level_id`, `sysload`, `ip`, `port`, `lr_type` from lr_node"""
    res_sys = db.execFetch(sqls_sys)
    for lr, level, sysload, ip, port, lr_type in res_sys:
        #  client.set("lrid:%s:%s"%(level,lr), sysload)
        client.hmset("lrid:%s:%s"%(level,lr), {"sysload": sysload, "ip": ip, "port": port, "lr_type": lr_type})

    sqls_qos = """select `level_src`,`level_dst`,`weight`,`layer_distance`,`path` from net_qos"""
    res_qos = db.execFetch(sqls_qos)
    for src,dst,weight,layer_distance,path in res_qos:
        client.hmset("qos:%s:%s"%(src,dst), {"weight": weight, "layer_distance": layer_distance, "path": path})
#  redis_init(client)

def redis_save(client):
    logger = logging.getLogger("nc")
    lr_sysload_list = client.keys("lrid:*")
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

    qos_list = client.keys("qos:*")
    sqlu_qos = """update net_qos set `path` = CASE """
    for qos in qos_list:
        qos_src = qos.split(":")[1]
        qos_dst = qos.split(":")[2]
        path = float(client.hget(qos, "path"))
        sqlu_qos += """WHEN `level_src`='%s' AND `level_dst`='%s' THEN %f """ % (qos_src, qos_dst, path)
    sqlu_qos += "END"
    db.execFetch(sqlu_qos)
    #  print sqlu_qos
    logger.info("Successfully save the redis data to mysql.")
#  redis_save(client)

