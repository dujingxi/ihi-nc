#!/usr/bin/env python
#-*- coding: utf-8 -*-

import logging
import sys
import json
import urllib2
from MysqlDB import db
import nc_config
from ncDef import getAlllevel
from netQos import netQos


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

def check_lrg(lrgid, lrgname, vspid):
    sqls = """select * from `lr_grid` where `lrg_id`='%s'""" % lrgid
    res = db.execFatch(sqls)
    if len(res) == 0:
        sqli = """insert into `lr_grid` (`lrg_id`, `lrg_name`, `vsp_id`) values ('%s', '%s', '%s')""" % (lrgid, lrgname, vspid)
        db.execOnly(sqli)
        return True
    return False

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
        logger.info("Truncate tables end...")
    # 重新获取adjacency、lr_node 两个表的数据并填充数据库
    for db_table in ("adjacency", "lr_node", "lr_grid", "lr_cluster"):
        if db_table == "adjacency": url = nc_config.SOTP_USR_LR_URL
        elif db_table == "lr_node": url = nc_config.SOTP_LR_INFO_URL
        elif db_table == "lr_grid": url = nc_config.SOTP_LR_GRID_URL
        else: url = nc_config.SOTP_LR_CLUSTER_URL
        res = getMsg(url)
        if not res["data"]:
            logger.error("Init failed, msg: %s"%res["msg"])
            sys.exit(0)
        if res["data"]["code"] != 200:
            print "ERROR: API for %s failure" % db_table
            logger.error("API for %s failure"%db_table)
        api_data = res["data"]["data"]
        query_data = []
        if db_table == "adjacency":
            for user_lr in api_data:
                if user_lr["user_id"] == '' or user_lr["node_level"] == '' or user_lr["vsp_id"] == '': continue
                ep_user = "%s_%s"%(user_lr["user_id"], user_lr["account"])
                query_data.append((user_lr["account"], ep_user, str(user_lr["node_level"]), user_lr["vsp_id"]))
            sqli = """insert into `adjacency` (`account`, `ep_id`, `level_id`, `vsp_id`) values (%s, %s, %s, %s)"""
        elif db_table == "lr_node":
            lr_all_list = []
            for lr_info in api_data:
                lr_all_list.append(lr_info["id"])
                query_data.append((lr_info["id"], lr_info["name"], lr_info["p_node_level"], lr_info["ip"], lr_info["port"], lr_info["op_name"], lr_info["net_type"], lr_info["price"], lr_info["lr_type"], str(lr_info["lrc_ids"]), lr_info["level_id"]))#  -------------------
            sqli = """insert into `lr_node` (`lr_id`, `name`, `plevel_id`, `ip`, `port`, `operator`, `cloud`, `price`, `lr_type`, `lrc_ids`, `level_id`, `sysload`) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)"""
        elif db_table == "lr_grid":
            for lrg in api_data:
                lrg_id = lrg["id"]
                lrg_name = lrg["name"]
                vsp_id = lrg["owner"]
                query_data.append((lrg_id, lrg_name, vsp_id))
            sqli = """insert into `lr_grid` (`lrg_id`,`lrg_name`,`vsp_id`) values (%s, %s, %s)"""
        else:
            for lrc in api_data:
                lrcname = lrc["name"]
                lrcid = lrc["id"]
                lrcregion = lrc["region"]
                lrgids = lrc["lrg_ids"]
                query_data.append((lrcid, lrcname, lrcregion, str(lrgids)))
                sqli = """insert into `lr_cluster` (`lrc_id`, `lrc_name`, `region`, `lrg_ids`) values (%s, %s, %s, %s)"""
        logger.info("%s query_data: %s"%(db_table, query_data))
        db.execOnly(sqli, query_data)
        logger.info("Fill table %s success."%db_table)
    # 初始化生成 net_qos 表数据
    #  sqltest = """select `lr_id` from `lr_node`"""
    #  res = db.execFatch(sqltest)
    #  lr_all_list = []
    #  for i in res:
        #  lr_all_list.append(i[0])
    sql_cmd = """INSERT INTO `level_node` (`level_id`) select distinct `level_id` from `lr_node`"""
    db.execOnly(sql_cmd)
    level_list = getAlllevel()
    for level in level_list:
        netqos = netQos(level)
        netqos.lrAddself()


