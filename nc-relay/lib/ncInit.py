#!/usr/bin/env python
#-*- coding: utf-8 -*-

import logging
import sys
import time
import json
import urllib2
from MysqlDB import db
import nc_config
from ncDef import write_level
from pyRedis import redis_client


def getMsg(url):
    try:
        req = urllib2.Request(url)
        response = urllib2.urlopen(req, timeout=5).read()
        res = json.loads(response)
        msg = ""
    except Exception, e:
        msg = e
        res = None
    return {"data": res, "msg": msg}

#  def check_lrg(lrgid, lrgname, vspid):
    #  sqls = """select * from `lr_grid` where `lrg_id`='%s'""" % lrgid
    #  res = db.execFetch(sqls)
    #  if len(res) == 0:
        #  sqli = """insert into `lr_grid` (`lrg_id`, `lrg_name`, `vsp_id`) values ('%s', '%s', '%s')""" % (lrgid, lrgname, vspid)
        #  db.execOnly(sqli)
        #  return True
    #  return False

def initDb():
    ''' 初始化数据库，在程序运行之初执行一次。或是在数据库数据与SOTP中数据有了差距时重新初始化。 '''
    logger = logging.getLogger("nc")
    tables = nc_config.tables
    # 清除三个表所有数据
    logger.info("Truncate tables start...")
    for t in tables:
        try:
            sqld = """truncate table `%s`""" % t
            db.execOnly(sqld) #               -------------------
            logger.info("Truncate table [%s] done."%t)
        except Exception,e:
            logger.error(e)
            sys.exit(0)
    else:
        redis_client.flushdb()
        logger.info("Truncate tables end...")
    # 重新获取adjacency、lr_node 两个表的数据并填充数据库
    cur_time = int(time.time())
    for db_table in ("adjacency", "lr_node"):
        if db_table == "adjacency": url = nc_config.SOTP_USR_LR_URL
        else: url = nc_config.SOTP_LR_INFO_URL
        res = getMsg(url)
        if not res["data"]:
            logger.error("Init: failed to get data from url/%s, msg: %s"% (url, res["msg"]))
            sys.exit(0)
        if res["data"]["code"] != 200:
            print "ERROR: API for %s failure" % db_table
            logger.error("API for %s failure"%db_table)
        api_data = res["data"]["data"]
        if not api_data:
            print "Data from url/%s was empty." % url
            continue
        query_data = []
        if db_table == "adjacency":
            for user_lr in api_data:
                if user_lr["user_id"] == '' or user_lr["node_level"] == '' or user_lr["vsp_id"] == '': continue
                ep_user = "%s_%s"%(user_lr["user_id"], user_lr["account"])
                query_data.append((user_lr["account"], ep_user, str(user_lr["node_level"]), user_lr["vsp_id"]))
                #  redis_client.hmset("user:%s"%ep_user, {"level_id": str(user_lr["node_level"]), "vsp_id": user_lr["vsp_id"]})
            sqli = """insert into `adjacency` (`account`, `ep_id`, `level_id`, `vsp_id`) values (%s, %s, %s, %s)"""
        else:
            lr_all_list = []
            for lr_info in api_data:
                lr_all_list.append(lr_info["id"])
                query_data.append((lr_info["id"], lr_info["name"], lr_info["p_node_level"], lr_info["ip"], lr_info["port"], lr_info["op_name"], lr_info["net_type"], lr_info["price"], lr_info["lr_type"], lr_info["level_id"], cur_time))#  -------------------
            sqli = """insert into `lr_node` (`lr_id`, `name`, `plevel_id`, `ip`, `port`, `cluster`, `cloud`, `price`, `lr_type`, `level_id`, `last_subtime`, `sysload`, `active`) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, '1')"""
        logger.info("%s query_data: %s"%(db_table, query_data))
        db.execOnly(sqli, query_data)
        logger.info("Fill table %s success."%db_table)
    # 自lr_node表中提取所有的level（去重），并初始化生成level_node表
    sqls_level = """select distinct `level_id` from lr_node"""
    level_res = db.execFetch(sqls_level)
    for level_temp in level_res:
        level = level_temp[0]
        result = write_level(level)
        if not result: logger.error("Error inserting level/%s"%level)
       

