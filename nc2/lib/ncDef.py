#!/usr/bin/env python
# -*- coding: utf-8 -*-

import copy
import math
import logging
from MysqlDB import db
from pyRedis import redis_client
from lrCluster import lrCluster
from logging.handlers import TimedRotatingFileHandler
import sys
import nc_config
sys.setrecursionlimit(100000)

def initLog(name):
    ''' 初始化日志功能模块 '''
    log_path = nc_config.LOG_PATH
    log_keep = nc_config.LOG_KEEP
    log_level = nc_config.LOG_LEVEL
    logger = logging.getLogger(name)
    formatter = logging.Formatter("%(asctime)s - line:%(lineno)d - %(levelname)s: %(message)s")
    fileHandler = TimedRotatingFileHandler(log_path, when='d', interval=1, backupCount=log_keep)
    fileHandler.setFormatter(formatter)
    #  streamhandler = logging.StreamHandler()
    #  streamhandler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.setLevel(log_level)
    logger.addHandler(fileHandler)
    #  logger.addHandler(streamhandler)
    return logger

def getAlllevel():
    sqls = """select `level_id` from `level_node`"""
    level_list = []
    res = db.execFetch(sqls)
    for level in res:
        level_list.append(level[0])
    return level_list

def getLrProperty(lrid, attr):
    sqls = """select %s from `lr_node` where `lr_id`='%s'""" % (attr, lrid)
    res = db.execFetch(sqls)
    return res[0][0]

def getPlevel(level):
    sql = """select plevel_id from level_node where level_id='%s'""" % level
    res = db.execFetch(sql)
    if res:
        return res[0][0]
    else: 
        return None


def getAncestor(level_id, reslist=[]):
    ''' 递归获取指定LR的父层LR '''
    sqls = """select `plevel_id`,`lr_type` from lr_node where `level_id`='%s' """ % level_id
    while True:
        sql_result = db.execFetch(sqls)
        #  print sql_result
        if len(sql_result) == 0:# or sql_result[0][1] == 'lr': # or sql_result[0][0] == '0':
            if reslist: return reslist[:-1]
            else: return reslist
        else:
            reslist.append(sql_result[0][0])
            return getAncestor(sql_result[0][0], reslist)
#  print getAncestor("517")

# when (scope == inner, lr_type == dlr), find the parent of top dlr level, return a LR level.
def getDlrRoot(level_id):
    p_level_list = getAncestor(level_id, [])
    p_level_list.insert(0, level_id)
    p_level_list.reverse()
    print p_level_list
    while True:
        now_level = p_level_list[-1]
        lr_level = redis_client.keys("lrid:%s:*"%now_level)[0]
        lr_type = redis_client.hget(lr_level, "lr_type")
        if lr_type == "lr":
            return lr_level.split(":")[1]
        else:
            plevel = getPlevel(lr_level.split(":")[1])
            p_level_lr = redis_client.keys("lrid:%s:*"%plevel)[0]
            p_lr_type = redis_client.hget(p_level_lr, "lr_type")
            if p_lr_type == "lr": return lr_level.split(":")[1]
        p_level_list.pop()
#  print getDlrRoot("463")

def getAdjacency(epid, item="level_id"):
    """ 获取指定userid距离最近的层级LR集群 """
    ## for redis
    if item == "level_id":
        ret_id = redis_client.hget("user:%s"%epid, "level_id")
    else:
        ret_id = redis_client.hget("user:%s"%epid, "vsp_id")
    return ret_id
    #  if item == "level_id":
        #  sqls = """select `level_id` from `adjacency` where `ep_id`='%s'"""%epid
    #  else:
        #  sqls = """select `vsp_id` from `adjacency` where `ep_id`='%s'""" % epid
    #  try:
        #  ret_id = db.execFetch(sqls)[0][0]
        #  return ret_id
    #  except Exception, e:
        #  return None


def getDescendant(level_id, reslist=[]):
    ''' 递归获取指定LR的子层LR '''
    sqls = """select distinct level_id from lr_node where plevel_id='%s'"""%level_id
    res = db.execFetch(sqls)
    if len(res) == 0: return reslist
    for i in range(len(res)):
        lr = res[i][0]
        if lr not in reslist: reslist.append(lr)
        if i == len(res)-1: return getDescendant(lr, reslist)
        else: reslist = getDescendant(lr, reslist)
#  print getDescendant("16", [])

def getRootlevel():
    ''' 获取根LR列表 '''
    sqls = """select distinct level_id from level_node where plevel_id='0'"""
    res = db.execFetch(sqls)
    reslist = []
    for level in res:
        reslist.append(level[0])
    return reslist
#  print getRootlevel()


def checkOperator(src_level, dst_level_list):
    """ 根据网络运营商类型，计算出一个LR 到其他所有LR的联通性 """
    src_lrc = lrCluster(src_level)
    src_lr_id = src_lrc.randomLr()
    src_operator = getLrProperty(src_lr_id, "operator").lower()
    operators_outer = nc_config.operators["outer"]
    conn_list = []
    not_conn_list = []
    half_conn_list = []
    for dst_level in dst_level_list:
        dst_lrc = lrCluster(dst_level)
        dst_lr_id = dst_lrc.randomLr()
        dst_operator = getLrProperty(dst_lr_id, "operator").lower()
        if src_operator == dst_operator: conn_list.append(dst_level)
        else:
            comp_res = set(operators_outer) & set([src_operator, dst_operator])
            if len(comp_res) > 0: half_conn_list.append(dst_level)
            else: not_conn_list.append(dst_level)
    return {"conn_list": conn_list, "half_conn": half_conn_list, "not_conn": not_conn_list}
#  print checkOperator("527", ["694"])

#  def getSameLevel(lr):
    #  """ 查找与提供的LR处于同一层级的LR集合 """
    #  sqls = """select `plr_id` from `lr_node` where `plr_id` != 'root'"""
    #  all_plr = db.execFetch(sqls)
    #  for plr in all_plr:
        #  print plr
        #  if lr in eval(plr[0]): return eval(plr[0])
        #  else: continue
    #  return []

def checkCloud(src_level, dst_level_list):
    """ 根据LR的互联网云类型，计算到其他所有LR的联通性 """
    dst_level_list_copy = copy.deepcopy(dst_level_list)
    relationship_list = getAncestor(src_level, [])
    relationship_list.insert(0, src_level)
    src_lrc = lrCluster(src_level)
    src_lr_id = src_lrc.randomLr()
    src_lrtype = getLrProperty(src_lr_id, "lr_type")
    # 修改dlr可以联通的是父层所有，包括lr类型
    #  element_1 = src_lrtype == "dlr"
    #  element_2 = True
    #  p_level = getPlevel(src_level)
    #  p_src_lrc = lrCluster(p_level)
    #  p_src_lrid = p_src_lrc.randomLr()
    #  if p_src_lrid:
        #  p_src_lrtype = getLrProperty(p_src_lrid, "lr_type")
        #  element_2 = p_src_lrtype == "dlr"
#
    #  if element_1 and element_2:
    if src_lrtype == "dlr":
        lr_conn_list = relationship_list 
        #  lrtype = "dlr"
    else:
        for dst_level in dst_level_list:
            dst_lrc = lrCluster(dst_level)
            dst_lr_id = dst_lrc.randomLr()
            dst_lr_type = getLrProperty(dst_lr_id, "lr_type")
            if dst_lr_type == "dlr": dst_level_list_copy.remove(dst_level)
        lr_conn_list = dst_level_list_copy
        if src_level not in lr_conn_list: lr_conn_list.insert(0, src_level)
        #  lrtype = "lr"
    return (lr_conn_list, relationship_list)

#  ll = getAlllevel()
#  print checkCloud("492", ["694"])

#  def iterCompare(self_list):
    #  """ 传如一个二维列表，对比表内每个元素，最终计算出所有元素列表公有的值，以列表返回 """
    #  set_list = [set(x) for x in self_list]
    #  num = len(set_list)
    #  n = 0; res = set()
    #  for i in range(num):
        #  res = res & set_list[n]
        #  n += 1
        #  if n >= num: break
    #  return list(res)

def detectForce(account):
    """ 检测帐号是否有指定LR """
    sqls = """select `lr_id` from `force_route` where `account`='%s'"""%account
    #  sql_id = """select `lr_id` from `lr_node` where `ip`='%s' and port='%s'"""
    rows = db.execFetch(sqls)
    if len(rows) > 0:
        lrid = rows[0][0]
        return {"statu": True, "lrid": lrid}
    else:
        return {"statu": False}
#  detectForce('abc')

def setMembership(level_id, plevel_id):
    sqls = """select count(*) from `level_node` where `level_id`='%s'""" % level_id
    sqli = """insert into level_node (`level_id`, `plevel_id`) values ('%s', '%s')"""%(level_id, plevel_id)
    count = db.execFetch(sqls)[0][0]
    #  print level_id, plevel_id, type(count)
    if count == 0: 
        db.execFetch(sqli)
        return True
    else: return False

#  setMembership(492, 1)
