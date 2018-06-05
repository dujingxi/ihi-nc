#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from MysqlDB import db
from logging.handlers import TimedRotatingFileHandler
import nc_config

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

# 传入层ID，判断是否已存在于level表中，若不存在，提取出层、父层、层的lrc信息、层的type 插入进去；若已存在，检测该层的LRC信息/层type 是否有变化，若有则更新level表
def write_level(level_id):
    sqls = """select * from level_node where `level_id`='%s'"""%level_id
    res = db.execFetch(sqls)
    sqls_c = """select distinct `cluster` from lr_node  where `level_id`='%s'"""%level_id
    level_c_list = db.execFetch(sqls_c)
    level_c_by_lr = ''
    for c in level_c_list:
        level_c_by_lr += c[0]
        level_c_by_lr += ":"
    level_c_by_lr = level_c_by_lr.strip(":")
    sqls_t = """select distinct `lr_type` from lr_node where `level_id`='%s'"""%level_id
    level_type_by_lr = db.execFetch(sqls_t)[0][0]
    if len(res) == 0:
        sqls_p = """select distinct `plevel_id` from lr_node where `level_id`='%s'"""%level_id
        plevel_id = db.execFetch(sqls_p)[0][0]
        sqli = """insert into level_node (`level_id`, `level_cluster`, `level_type`, `plevel_id`) values ('%s', '%s', '%s', '%s')""" % (level_id, level_c_by_lr, level_type_by_lr, plevel_id)
        db.execFetch(sqli)
        return (level_c_by_lr, level_type_by_lr)
    else:
        sqls_c_f_level = """select `level_cluster` from level_node where `level_id`='%s'"""%level_id
        level_c_by_levelnode = db.execFetch(sqls_c_f_level)[0][0]
        if level_c_by_lr != level_c_by_levelnode:
            sqlu = """update level_node set `level_cluster`='%s' where `level_id`='%s'"""%(level_c_by_lr, level_id)
            db.execFetch(sqlu)
        sqls_t_f_level = """select `level_type` from level_node where `level_id`='%s'"""%level_id
        level_t_by_levelnode = db.execFetch(sqls_t_f_level)[0][0]
        if level_type_by_lr != level_t_by_levelnode:
            sqlu = """update level_node set `level_type`='%s' where `level_id`='%s'"""%(level_type_by_lr, level_id)
            db.execFetch(sqlu)
        return (level_c_by_lr, level_type_by_lr)


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
