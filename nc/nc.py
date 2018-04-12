#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Filename: nc.py
# Description: The optimal target LR is calculated according to various attributes and network conditions.

# Copyright (C) 2018 dujingxi

# Author: dujingxi <dujingxi@streamocean.com>
# License: StreamOcean
# Last-Updated: 2018/01/11

import sys
import pdb
import os
import json
import time
import copy
import math
import random
import urllib2
import MySQLdb as mysql
import tornado.web
import tornado.escape
import tornado.ioloop
import tornado.gen
import nc_config
import logging
from logging.handlers import TimedRotatingFileHandler
reload(sys)
sys.setdefaultencoding("utf-8")

class DB(object):
    ''' 数据库连接类，包括连接、执行sql语句、批量执行等函数块 '''
    TIMEOUT = 5

    def __init__(self, dbargs):
        # self.logger = logging.getLogger("nc")
        if not set(("host", "user", "db", "passwd")) <= set(dbargs):
            raise TypeError("Required arguments miss.")
        self.host = dbargs['host']
        if dbargs.has_key("port"):
            self.port = dbargs['port']
        else: self.port = 3306
        self.user = dbargs['user']
        self.db = dbargs['db']
        self.passwd = dbargs['passwd']
        self.conn = None
        self.connect()

    def connect(self):
        try:
            self.conn = mysql.connect(host=self.host, port=self.port, user=self.user, passwd=self.passwd, db=self.db, \
                                      connect_timeout=self.TIMEOUT, charset='utf8')
        except Exception, e:
            print e
            raise
        # else:
        #     self.logger.info("Connect to %s successed."%self.host)

    def isMany(self, data):
        if data and isinstance(data, list):
            return True
        else: return False

    def __exec(self, cur, sqli, data=None):
        if self.isMany(data):
            return cur, cur.executemany(sqli, data)
        else:
            return cur, cur.execute(sqli, data)

    def execOnly(self, sqli, data=None):
        try:
            self.conn.ping()
        except:     # MySQLdb.OperationalError
            self.connect()
        cur = self.conn.cursor()
        rows = None
        try:
            cursor, rows = self.__exec(cur, sqli, data)
            self.conn.commit()
        finally:
            cur.close()
        return rows

    def execFatch(self, sqli, data=None):
        try:
            self.conn.ping()
        except:     # MySQLdb.OperationalError
            self.connect()
        cur = self.conn.cursor()
        try:
            cursor, _ = self.__exec(cur, sqli, data)
            res = cursor.fetchall()
            self.conn.commit()
            return res
        finally:
            cur.close()

    def __del__(self):
        if self.conn:
            self.conn.close()

# 创建数据库连接实例，以下代码全都会使用此对象
db = DB(nc_config.MYSQL_ARGUMENTS)


class lrNode(object):
    """ lrnode 类，提供 lr 实例记录的属性获取、记录获取、除去自身的所有lr列表获取、以及Lr记录的添加，删除，修改等的API """
    def __init__(self, id):
        self.logger = logging.getLogger("nc")
        self.lr_id = id

    def getProperty(self, attr):
        sqls = """select %s from lr_node where lr_id='%s'""" % (attr, self.lr_id)
        res = db.execFatch(sqls)
        return res[0][0]

    def getLrnode(self, all=False, plr=True):
        if all:
            sqls = """select `lr_id`,`name`,`ip`,`port`,`plr_id`,`operator`,`cloud`,`price`, `lr_type` from `lr_node`"""
            res = db.execFatch(sqls)
            all_lr_list = []
            for record in res:
                all_lr_list.append({"lrid": record[0], "name": record[1], "ip": record[2], "port": record[3], "plrid": record[4], "operator": record[5], "cloud": record[6], "price": record[7], "lr_type": record[8]})
            data = all_lr_list
        else:
            #  if plr:
            sqls = """select `lr_id`,`name`,`ip`,`port`,`operator`,`cloud`,`price`,`lr_type`, `plr_id` from lr_node where lr_id='%s'""" % self.lr_id
            #  else:
            #  sqls = """select `lr_id`,`name`,`ip`,`port`,`operator`,`cloud`,`lr_type`, `price` from lr_node where lr_id='%s'""" % self.lr_id
            res = db.execFatch(sqls)
            #  if len(res[0]) == 9: plrid = res[0][7]
            #  else: plrid = "ignore"
            if len(res) != 0: data = {"lrid": res[0][0], "name": res[0][1], "ip": res[0][2], "port": res[0][3], "operator": res[0][4], "cloud": res[0][5], "price": res[0][6], "lr_type": res[0][7],  "plrid": res[0][8]}
            else: data = nc_config.DEFAULT_LR
        return {"code":200, "status": "success", "data": data}

    def getDstlist(self):
        sqls = """select lr_id from lr_node"""
        lr_dst_list = []
        res = db.execFatch(sqls)
        if len(res) == 0:
            self.logger.error("lr_node table empty.")
            sys.exit(0)
        for record in res:
            lr_dst_list.append(record[0])
        lr_dst_list.remove(self.lr_id)
        return lr_dst_list

    def addLrnode(self, sql_data):
        sqli = """insert into lr_node (`lr_id`, `name`, `plr_id`, `ip`, `port`, `operator`, `cloud`, `price`, `lr_type`) values ("%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s")""" % sql_data
        print sqli
        res = db.execOnly(sqli)
        if res > 0:
            netqos = netQos(self.lr_id)
            ret = netqos.lrAddall()
            if ret > 0:
                self.logger.info("Add lr_node with lrid=%s done."%self.lr_id)
                return {"code": 200, "status": "success", "msg": "Add lr_node with lrid=%s done."%self.lr_id}
            else:
                self.logger.error("Add lr_node with lrid=%s fail, on update table netqos."%self.lr_id)
                return {"code": 400, "status": "failed", "msg": "Add lr_node with lrid=%s fail, on update table netqos."%self.lr_id}
        else:
            self.logger.error("Add lr_node with lrid=%s failed."%self.lr_id)
            return {"code": 400, "status": "failed", "msg": "Add lr_node with lrid=%s failed."%self.lr_id}

    def modLrnode(self, sql_data):
        self.delLrnode()
        self.addLrnode(sql_data)
        return {"code": 200, "status": "success"}

    def delLrnode(self):
        sql_1 = """select `lr_id`,`plr_id` from `lr_node` where `plr_id` REGEXP '%s'"""%self.lr_id
        sql_3 = """select `plr_id` from `lr_node` where `lr_id`='%s'"""%self.lr_id
        # 更新以本身为父层的LR记录
        res = db.execFatch(sql_1)
        if len(res) > 0:
            for node in res:
                lrid = node[0]
                plrid = eval(node[1])
                plrid.remove(self.lr_id)
                if len(plrid) == 0:
                    ret = db.execFatch(sql_3)[0][0]
                    new_plr = ret
                else: new_plr = str(plrid)
                self.logger.info("update lr_node -> lrid : %s, parent_lr: %s"%(lrid, new_plr))
                sql_2 = """update `lr_node` set `plr_id`="%s" where `lr_id`='%s'"""%(new_plr, lrid)
                db.execOnly(sql_2)
        # 更新以本身为LR的用户记录
        sql_4 = """select `ep_id`,`lr_id` from `adjacency` where lr_id REGEXP '%s'"""%self.lr_id
        res = db.execFatch(sql_4)
        if len(res) > 0:
            for user in res:
                userid = user[0]
                userlr = eval(user[1])
                userlr.remove(self.lr_id)
                if len(userlr) == 0:
                    new_userlr = db.execFatch(sql_3)[0][0]
                else: new_userlr = str(userlr)
                self.logger.info("update user table -> ep_id: %s, lr_id: %s"%(userid, new_userlr))
                sql_5 = """update `adjacency` set `lr_id`="%s" where `ep_id`='%s'"""%(new_userlr, userid)
                db.execOnly(sql_5)
        # 删除LR记录
        sql_6 = """delete from lr_node where lr_id='%s'"""%self.lr_id
        res = db.execFatch(sql_6)
        if res > 0:
            netqos = netQos(self.lr_id)
            netqos.lrDel()
            self.logger.info("Del lr_node with lrid=%s success."%self.lr_id)
            return {"code": 200, "status": "success"}
        else:
            self.logger.warning("Del lr_node with lrid=%s failed, nod found."%self.lr_id)
            return {"code": 400, "status": "failed", "msg": "Not found record."}
'''
    def setProperty(self, attr, value):
        sqlu = """update lr_node set %s='%s' where lr_id='%s'""" % (attr, value, self.lr_id)
        res = db.execOnly(sqlu)
        if res == 1:
            self.logger.info("Update %s to [%s] where lrid is %s" % (attr, value, self.lr_id))
        else:
            self.logger.warning("Update %s to [%s] where lrid is %s failed" % (attr, value, self.lr_id))
        return res
'''

def initLog(name):
    ''' 初始化日志功能模块 '''
    log_path = nc_config.LOG_PATH
    log_keep = nc_config.LOG_KEEP
    log_level = nc_config.LOG_LEVEL
    logger = logging.getLogger(name)
    formatter = logging.Formatter("%(asctime)s - line:%(lineno)d - %(levelname)s: %(message)s")
    fileHandler = TimedRotatingFileHandler(log_path, when='d', interval=1, backupCount=log_keep)
    fileHandler.setFormatter(formatter)
    streamhandler = logging.StreamHandler()
    streamhandler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.setLevel(log_level)
    logger.addHandler(fileHandler)
    logger.addHandler(streamhandler)
    return logger


#  def getAncestor(lrid, reslist=[]):
    #  ''' 递归获取指定LR的父层LR '''
    #  sqls = """select plr_id from lr_node where lr_id='%s'"""%lrid
    #  while True:
        #  plr_id = db.execFatch(sqls)[0][0]
        #  if plr_id != 'root':
            #  reslist.append(plr_id)
            #  return getAncestor(plr_id, reslist)
        #  else: return reslist
#  # print getAncestor("lr_23")
def getAncestor(lrid, reslist=[]):
    ''' 递归获取指定LR的父层LR '''
    sqls = """select `plr_id` from `lr_node` where `lr_id`='%s'"""%lrid
    while True:
        plr_id = db.execFatch(sqls)[0][0]
        if plr_id != 'root':
            plr_id = eval(plr_id)
            for plr in plr_id:
                reslist.append(plr)
            return getAncestor(plr_id[0], reslist)
        else: return reslist
#  print getAncestor("lr_9")

def getAdjacency(epid):
    """ 获取指定userid距离最近的层级LR集群 """
    sqls = """select `lr_id` from `adjacency` where `ep_id`='%s'"""%epid
    #  logger = logging.getLogger("nc")
    #  logger.info("sql: %s"%sqls)
    try:
        lr_list = db.execFatch(sqls)[0][0]
        lr_list = eval(lr_list)
        #  lrid = random.sample(lr_list, 1)
        return lr_list
    except Exception, e:
        return None


def getDescendant(lrid, reslist=[]):
    ''' 递归获取指定LR的子层LR '''
    sqls = """select lr_id from lr_node where plr_id REGEXP '%s'"""%lrid
    res = db.execFatch(sqls)
    if len(res) == 0: return reslist
    for i in range(len(res)):
        lr = res[i][0]
        if lr not in reslist: reslist.append(lr)
        if i == len(res)-1: return getDescendant(lr, reslist)
        else: reslist = getDescendant(lr, reslist)
#  print getDescendant("lr3")

def getRootlr():
    ''' 获取根LR列表 '''
    sqls = """select lr_id from lr_node where plr_id='root'"""
    res = db.execFatch(sqls)
    reslist = []
    for lr in res:
        reslist.append(lr[0])
    return reslist


def checkOperator(src_operator, lr_dst_list):
    """ 根据网络运营商类型，计算出一个LR 到其他所有LR的联通性 """
    src_operator = src_operator.lower()
    operators_outer = nc_config.operators["outer"]
    conn_list = []
    not_conn_list = []
    half_conn_list = []
    for lr_dst in lr_dst_list:
        lr_dst_node = lrNode(lr_dst)
        lr_dst_operator = lr_dst_node.getProperty("operator").lower()
        if src_operator == lr_dst_operator:
            conn_list.append(lr_dst)
        else:
            comp_res = set(operators_outer) & set([src_operator, lr_dst_operator])
            if len(comp_res) > 0: half_conn_list.append(lr_dst)
            else: not_conn_list.append(lr_dst)
    return {"conn_list": conn_list, "half_conn": half_conn_list, "not_conn": not_conn_list}

#  def getSameLevel(lr):
    #  """ 查找与提供的LR处于同一层级的LR集合 """
    #  sqls = """select `plr_id` from `lr_node` where `plr_id` != 'root'"""
    #  all_plr = db.execFatch(sqls)
    #  for plr in all_plr:
        #  print plr
        #  if lr in eval(plr[0]): return eval(plr[0])
        #  else: continue
    #  return []

def checkCloud(lr, lr_dst_list):
    """ 根据LR的互联网云类型，计算到其他所有LR的联通性 """
    my_dst_list = copy.deepcopy(lr_dst_list)
    lrnode = lrNode(lr)
    lr_cloud = lrnode.getProperty("cloud")
    if lr_cloud == nc_config.area_net:
        lr_conn_list = set(getAncestor(lr, []))
    elif lr_cloud == nc_config.private_net:
        lr_conn_list = set(getAncestor(lr, []) + getDescendant(lr, []))
    else:
        for lr_dst in my_dst_list:
            lr_dst_node = lrNode(lr_dst)
            lr_dst_cloud = lr_dst_node.getProperty("cloud")
            if lr_dst_cloud == nc_config.area_net: my_dst_list.remove(lr_dst)
        lr_conn_list = set(my_dst_list)
    lr_conn_list = lr_conn_list | set(getRootlr())
    return lr_conn_list     # return set()
# print checkCloud("lr_23", ["lr_1"])


class netQos(object):
    """
    添加一条lr记录时，生成 net qos 的计算结果记录，插入net_qos表。
    lraddself 插入源为lrid，到其他lr的所有联通性计算记录，初始化时调用
    lraddall 插入源为lrid，到其他lr，以及其他lr到lrid的所有计算记录，使用中添加lrnode时调用
    lrdel 删除net_qos中lrid有关的记录，删除lrnode时调用
    getvalidlr 获取源为lrid，并且与其联通性不为0（即可以联通）的 lr 列表，API 供LR客户端调用
    """
    def __init__(self, lrid):
        self.lr_src = lrid
        self.logger = logging.getLogger("nc")

    def lrAddself(self):
        lrnode = lrNode(self.lr_src)
        lr_dst_list = lrnode.getDstlist()
        lr_operator = lrnode.getProperty("operator")
        lr_price = lrnode.getProperty("price")

        lr_conn_list = checkCloud(self.lr_src, lr_dst_list)
        operator_res = checkOperator(lr_operator, lr_dst_list)
        operator_half_conn_list = set(operator_res["half_conn"])
        operator_not_conn_list = set(operator_res["not_conn"])
        res_half_list = list(lr_conn_list & operator_half_conn_list)    # 0.5 lr_dst
        res_conn_list = list(lr_conn_list - set(res_half_list) - set(operator_not_conn_list))     # 1 lr_dst
        self.logger.info("lr: %s - connlist: %s - halflist: %s "%(self.lr_src, res_conn_list,res_half_list))
        sql_data = []
        for lr_dst in lr_dst_list:
            dstnode = lrNode(lr_dst)
            dst_lr_price = dstnode.getProperty("price")
            if lr_dst in res_conn_list:
                weight = 1
                if dst_lr_price == 0: path = weight
                else: path = math.sqrt(dst_lr_price/100)/weight
            elif lr_dst in res_half_list:
                weight = 0.5
                if dst_lr_price == 0: path = weight
                else: path = math.sqrt(dst_lr_price/100)/weight
            else:
                weight = 0; path = 0
            sql_data.append((self.lr_src, lr_dst, weight, path))
        sqli = """insert into net_qos (`lr_src`, `lr_dst`, `weight`, `path`) values (%s, %s, %s, %s)"""
        return db.execOnly(sqli, sql_data)

    def lrAddall(self):
        self.lrAddself()
        lrnode = lrNode(self.lr_src)
        lr_src_price = lrnode.getProperty("price")
        lr_dst_list = lrnode.getDstlist()
        sql_data = []
        for lr_dst in lr_dst_list:
            check_cloud_res = checkCloud(lr_dst, [self.lr_src])
            if self.lr_src in list(check_cloud_res):
                lr_dst_node = lrNode(lr_dst)
                lr_dst_operator = lr_dst_node.getProperty("operator")
                #  lr_dst_price = lr_dst_node.getProperty("price")
                check_operator_res = checkOperator(lr_dst_operator, [self.lr_src])
                if len(check_operator_res["conn_list"]) != 0:
                    weight = 1; path = math.sqrt(lr_src_price/100)/weight
                elif len(check_operator_res["half_conn"]) != 0:
                    weight = 0.5; path = math.sqrt(lr_src_price/100)/weight
                else:
                    weight = 0; path = 0
            else: weight = 0; path = 0
            sql_data.append((lr_dst, self.lr_src, weight, path))
        sqli = """insert into net_qos (`lr_src`, `lr_dst`, `weight`, `path`) values (%s, %s, %s, %s)"""
        return db.execOnly(sqli, sql_data)

    def lrDel(self):
        sqld = """delete from net_qos where `lr_src`='%s' or `lr_dst`='%s'""" % (self.lr_src, self.lr_src)
        self.logger.info("delete record with lrid -> %s"%self.lr_src)
        return db.execOnly(sqld)

    '''
    def lrMod(self):
        self.lrDel()
        self.lrAddall()
        self.logger.info("mod record with lrid -> %s"%self.lr_src)
    '''

    def setProperty(self, dst, attr, value):
        sqlu = """update `net_qos` set %s='%s' where `lr_src`='%s' and `lr_dst`='%s'""" % (attr, value, self.lr_src, dst)
        res = db.execOnly(sqlu)
        return res

    def getValidlr(self):
        lr_valid_list = []
        sqls = """select lr_dst from net_qos where `lr_src`='%s' and weight != 0"""%self.lr_src
        sql_res = db.execFatch(sqls)
        if len(sql_res) == 0:
            # self.logger.warning("Found 0 record, please check your lrid.")
            status = "failed"
        else:
            # self.logger.info("Found %s record."%len(sql_res))
            status = "success"
            for lr in sql_res:
                lr_node = lrNode(lr[0])
                ip = lr_node.getProperty("ip")
                port = lr_node.getProperty("port")
                lr_valid_list.append({"id": lr[0], "ip": ip, "port":port})
        return {"code": 200, "status": status, "node_list": lr_valid_list}


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
            logger.info("Truncate [%s] done."%t)
        except Exception,e:
            logger.error(e)
            sys.exit(0)
    else:
        logger.info("Truncate tables end...")
    # 重新获取adjacency、lr_node 两个表的数据并填充数据库
    for db_table in ("adjacency", "lr_node"):
        if db_table == "adjacency": url = nc_config.SOTP_USR_LR_URL
        else: url = nc_config.SOTP_LR_INFO_URL
        try:
            req = urllib2.Request(url)
            response = urllib2.urlopen(req, timeout=5).read()
            res = json.loads(response)
        except Exception, e:
            logger.error("Open url %s failed."%url)
            sys.exit(0)
        if res["code"] != 200:
            logger.error("API for %s failure"%db_table)
        api_data = res["data"]
        query_data = []
        if db_table == "adjacency":
            for user_lr in api_data:
                if user_lr["user_id"] == '' or user_lr["nodes"] == '': continue
                ep_user = "%s_%s"%(user_lr["user_id"], user_lr["account"])
                query_data.append((user_lr["account"], ep_user, str(user_lr["nodes"])))
            logger.info("adjacency query_data: %s"%query_data)#        ---------------------
            sqli = """insert into `adjacency` (`account`, `ep_id`, `lr_id`) values (%s, %s, %s)"""
            db.execOnly(sqli, query_data)#            ----------------------
            logger.info("Fill table adjacency success.")
        else:
            lr_all_list = []
            for lr_info in api_data:
                lr_all_list.append(lr_info["id"])
                query_data.append((lr_info["id"], lr_info["name"], str(lr_info["parents"]), lr_info["ip"], lr_info["port"], lr_info["op_name"], lr_info["net_type"], lr_info["price"], lr_info["lr_type"]))#  -------------------
            logger.info("lr_node query_data: %s"%query_data)#  ----------------
            sqli = """insert into `lr_node` (`lr_id`, `name`, `plr_id`, `ip`, `port`, `operator`, `cloud`, `price`, `lr_type`) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            db.execOnly(sqli, query_data)#        -----------------------
            logger.info("Fill table lr_node success.")
    # 初始化生成 net_qos 表数据
    #  sqltest = """select `lr_id` from `lr_node`"""
    #  res = db.execFatch(sqltest)
    #  lr_all_list = []
    #  for i in res:
        #  lr_all_list.append(i[0])
    for lr in lr_all_list:
        netqos = netQos(lr)
        netqos.lrAddself()


def updateQos(lr_src, lr_dst, weight, price, percent_lost, mrtt, artt):
    """ 计算path值并更新数据库 """
    if percent_lost == 0:
        qos = percent_lost*0 + mrtt*0.5 + artt*0.5
    elif 0 < percent_lost <= 10:
        qos = percent_lost*0.8 + mrtt*0.1 + artt*0.1
    elif 10 < percent_lost <= 30:
        qos = percent_lost*0.9 + mrtt*0.05 + artt*0.05
    # elif 40 < percent_lost <= 70:
    #     qos = percent_lost*0.6 + mrtt*0.2 + artt*0.2
    # elif 70 < percent_lost <= 90:
    #     qos = percent_lost*0.8 + mrtt*0.1 + artt*0.1
    else:
        qos = None
    if qos:
        value = math.sqrt(price/100)+qos
        if weight != 0: res = value/weight
        else: res = 0
    else:
        res = 0
    netqos = netQos(lr_src)
    netqos.setProperty(lr_dst, "path", res)
    return qos, res
# initLog("nc")
# updateQos("lr11785a32104e7ac8620171214134654", "lr13315a3368261393420171215141358", 0.5, 50, 1.22, 12.09, 4.66)

# ll = [[0, 16.19, 6.33], [0, 20.22,15.51], [6, 12.10, 4.22], [18, 20.99, 19.09], [30, 66.03, 40.11], [58, 18.01, 0.36], [70, 33.23, 32.12], [88, 161.31, 103.28], [95, 10.88, 9.09]]
# for i in ll:
#     updateQos(1, 20, i)

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
    sql_id = """select `lr_id` from `lr_node` where `ip`='%s' and port='%s'"""
    rows = db.execFatch(sqls)
    if len(rows) > 0:
        lrid = rows[0][0]
        return {"statu": True, "lrid": lrid}
    else:
        return {"statu": False}
#  detectForce('abc')


class getEpHandler(tornado.web.RequestHandler):
    """获取用户-LR记录信息"""
    def get(self):
        id = self.get_argument("id", None)
        limit = self.get_argument("limit", None)
        if id is None:
            if limit is None or (limit.isdigit() and int(limit) != 0):
                if limit is None:
                    sqls = """select `account`,`ep_id`,`lr_id` from `adjacency`"""
                else:
                    sqls = """select `account`,`ep_id`,`lr_id` from `adjacency` limit %s"""%limit
                data = {"status": "success", "data": []}
                res = db.execFatch(sqls)
                for record in res:
                    account, epid, lrid = record
                    data["data"].append({"account": account, "epid": epid, "lrid": lrid})
                logging.info("Data success.")
                self.write(data)
            else:
                logging.error("Error of submission parameter(limit).")
                self.write({"status": "error", "msg": "Error of submission parameter(limit)."})

        else:
            if limit is not None:
                logging.error("Parameter `id` and parameter `limit` cannot appear at the same time")
                self.write({"status": "error", "msg": "Parameter `id` and `limit` cannot appear at the same time"})
            else:
                sqlss = """select `account`,`ep_id`,`lr_id` from `adjacency` where `ep_id`='%s'"""%id
                res = db.execFatch(sqlss)
                if len(res) != 0:
                    account, epid, lrid = res[0]
                    data = {"status": "success", "data": {"account": account, "epid": epid, "lrid": lrid}}
                else: data = {"status": "success", "data": None}
                logging.info("Data success, id -> %s"%id)
                self.write(data)


class changeEpHandler(tornado.web.RequestHandler):
    """ 用户-LR 表 API 接口 """
    def post(self, epid=None):
        reqbody = json.loads(self.request.body)
        act = reqbody["account"]
        ep = reqbody["userid"]
        ep_user = "%s_%s"%(ep, act)
        lr = reqbody["lrid"]
        sqli = """insert into `adjacency` (`account`, `ep_id`, `lr_id`) values ("%s", "%s", "%s")"""%(act, ep_user, lr)
        rows = db.execOnly(sqli)
        if rows == 1: self.write({"code":200, "status": "success"})
        else: self.write({"code": 404, "status": "error"})

    def get(self, epid=''):
        if epid != '':
            sqls = """select `ep_id`,`lr_id`, `account` from `adjacency` where `ep_id`='%s'"""%epid
            res = db.execFatch(sqls)
            self.write({"code":200, "stauts":"success", "result":{"epid":res[0][0], "lrid":res[0][1]}})
        else:
            sqls = """select `ep_id`,`lr_id`, `account` from `adjacency`"""
            res = db.execFatch(sqls)
            ep_lr_list = []
            for record in res:
                ep_lr_list.append({"epid": record[0], "lrid": record[1], "account":record[2]})
            self.write({"code": 200, "stauts": "success", "result":ep_lr_list})

    def put(self, epid):
        reqbody = json.loads(self.request.body)
        act = reqbody["account"]
        lr = reqbody['lrid']
        sqlu = """update `adjacency` set `account`="%s", `lr_id`="%s" where `ep_id`='%s'""" % (act, lr, epid)
        rows = db.execOnly(sqlu)
        if rows: self.write({"code": 200, "status": "success"})
        else: self.write({"code": 400, "status": "error"})

    def delete(self, epid):
        sqld = """delete from `adjacency` where `ep_id`='%s'"""%epid
        rows = db.execOnly(sqld)
        if rows == 0: self.write({"code": 400, "status":"error", "msg":"User not found."})
        else: self.write({"code": 200, "status":"success"})


class changeLrHandler(tornado.web.RequestHandler):
    """ LR-NODE 表API接口 """
    def post(self, lrid=None):
        reqbody = json.loads(self.request.body)
        lr_id = reqbody["id"]
        lr_name = reqbody["name"]
        plr_id = str(reqbody["parents"])
        ip = reqbody["ip"]
        port = reqbody["port"]
        operator = reqbody["op_name"]
        cloud = reqbody["net_type"]
        price = reqbody["price"]
        lr_type = reqbody["lr_type"]
        sql_data = (lr_id, lr_name, plr_id, ip, port, operator, cloud, price, lr_type)
        print sql_data
        lr_node = lrNode(lr_id)
        res = lr_node.addLrnode(sql_data)
        self.write(res)

    def get(self, lrid=''):
        lr_node = lrNode(lrid)
        if lrid != '': ret = lr_node.getLrnode()
        else: ret = lr_node.getLrnode(True)
        self.write(ret)

    def put(self, lrid):
        reqbody = json.loads(self.request.body)
        lr_name = reqbody["name"]
        plr_id = reqbody["parents"]
        ip = reqbody["ip"]
        port = reqbody["port"]
        operator = reqbody["op_name"]
        cloud = reqbody["net_type"]
        price = reqbody["price"]
        lr_type = reqbody["lr_type"]
        sql_data = (lrid, lr_name, plr_id, ip, port, operator, cloud, price, lr_type)
        lr_node = lrNode(lrid)
        res = lr_node.modLrnode(sql_data)
        self.write(res)

    def delete(self, lrid):
        lr_node = lrNode(lrid)
        res = lr_node.delLrnode()
        self.write(res)


class getNodelist(tornado.web.RequestHandler):
    """ 获取需与自身（lr）测试联通性的LR列表的API """
    def get(self, id):
        netqos = netQos(id)
        res = netqos.getValidlr()
        self.write(res)


class getMeetinglr(tornado.web.RequestHandler):
    """ 获取会议LR """
    def post(self):
        logger = logging.getLogger("nc")
        reqbody = json.loads(self.request.body)
        caller = reqbody["callerId"]
        caller_account = caller.split("_")[2]
        force_res = detectForce(caller_account)
        if force_res["statu"]:
            lr_node = lrNode(force_res["lrid"])
            lr_res = lr_node.getLrnode(plr=False)
            logger.info("The account [%s] has a specified LR [%s]"%(caller_account, force_res["lrid"]))
            self.write(lr_res)
            return
        if reqbody.has_key("scope"):
            public_mt_type = reqbody["scope"]
            if public_mt_type == "inner":
                lr_list =  getAdjacency(caller)
                if not lr_list:
                    res = {"code": 200, "status": "success", "data":nc_config.DEFAULT_LR}
                    logger.info("Public meetting. Not found caller's adjacency LR, return default lr")
                    self.write(res); return
                else:
                    lr_node = lrNode(lr_list[0])
                    lr_res = lr_node.getLrnode(plr=False)
                    logger.info("Public meetting, type [%s], caller [%s], lr [%s]"%(public_mt_type, caller, lr_res))
                    self.write(lr_res)
                    return
            else:
                lr_list = getRootlr()
                lr_node = lrNode(lr_list[0])
                lr_res = lr_node.getLrnode(plr=False)
                logger.info("Public meetting, type [%s], caller [%s], SO lr [%s]"%(public_mt_type, caller, lr_res))
                self.write(lr_res)
                return
        # 非公开会议（公开课）
        calleeList = reqbody["calleeList"]
        if len(calleeList) == 0: personlist = [caller]
        else: personlist = copy.deepcopy(calleeList)
        logger.info("Standard meeting starting, members -> [%s]"%personlist)
        #  account_list = [p.split('_')[2] for p in personlist]
        #  result = {"code": 200, "data":{"lrid":"test", "ip":"1.1.1.1", "port":9004}, "personlist": personlist}
        #  self.write(result)
        near_lr_list = []
        for user in personlist:
            res_list = getAdjacency(user)
            if not res_list:
                logger.info("No matching LR target found, please check if the user_id exists.")
                break
            if res_list not in near_lr_list:
                near_lr_list.append(res_list)
        if len(near_lr_list) < 1:
            res = {"code": 404, "msg": "User [%s] not found, use default."%user, "data": nc_config.DEFAULT_LR}
            self.write(res)
        elif len(near_lr_list) == 1:
            meeting_lr = random.sample(near_lr_list[0], 1)[0]
            lr_node = lrNode(meeting_lr)
            lr_res = lr_node.getLrnode(plr=False)
            logger.info("The meeting has the same LR=>[%s]"%lr_res)
            self.write(lr_res)
        else:
            #  参会方的LR列表中是否有某个LR是共有的，实际中这种情况不存在
            #  compare_res = iterCompare(near_lr_list)
            #  if len(compare_res) >= 1:
                #  lr_node = lrNode(compare_res[0])
                #  res = lr_node.getLrnode(plr=False)
                #  logger.info("Take a OBJ that everyone shares.")
                #  self.write(res)
                #  return
            all_valid_lr = []
            # waitting update
            near_lr_list = [random.sample(l, 1)[0] for l in near_lr_list]
            for lr_id in near_lr_list:
                netqos = netQos(lr_id)
                valid_lr = netqos.getValidlr()
                valid_lr = [item["id"] for item in valid_lr["node_list"]]
                valid_lr.append(lr_id)
                all_valid_lr.append(valid_lr)
                logger.info("near-lr %s: valid lr-list %s" % (lr_id, valid_lr))
            result = set(all_valid_lr[0])
            for i in range(len(all_valid_lr)):
                result = result & set(all_valid_lr[i])
            lr_list = list(result)

            if len(lr_list) == 0:
                data = nc_config.DEFAULT_LR
                logger.warning("Failure to calculate the result, return default lr")
                res = {"code": 200, "status": "success", "data":data}
                self.write(res)

            sqls_2 = """select `path` from `net_qos` where `lr_src`='%s' and `lr_dst`='%s'"""
            result_list = []
            for x in lr_list:
                flag = False
                sum = 0
                for y in near_lr_list:
                    if y != x: 
                        value = db.execFatch(sqls_2%(y, x))[0][0]
                        if value == 0: flag = True
                    else: value = 0
                    sum = sum + value
                if flag: continue
                result_list.append({"id": x, "path": sum})
            result_list.sort(key=lambda x:(x["path"]))
            lr_node = lrNode(result_list[0]["id"])
            res = lr_node.getLrnode(plr=False)
            logger.info("Selected list %s, final choice %s"%(result_list, res))
            self.write(res)


class upQosdata(tornado.web.RequestHandler):
    def post(self):
        reqbody = json.loads(self.request.body)
        lr_src = reqbody["id"]
        data = reqbody["data"]
        logger = logging.getLogger("nc")
        for lr in data:
            lr_dst = lr["dst_id"]
            percent_lost = lr["percent_lost"]
            mrtt = lr["mrtt"]
            artt = lr["artt"]
            lr_node = lrNode(lr_dst)
            sqls = """select `weight` from `net_qos` where `lr_src`='%s' and `lr_dst`='%s'"""%(lr_src, lr_dst)
            weight = db.execFatch(sqls)
            price = lr_node.getProperty("price")
            res = updateQos(lr_src, lr_dst, weight[0][0], price, percent_lost, mrtt, artt)
            qos, path = res
            logger.info("Update: lrid[%s] -> lrid[%s], qos->%s, path->%s"%(lr_src, lr_dst, qos, path))
        self.write({"code": 200, "status":"success"})


class getForceTable(tornado.web.RequestHandler):
    def get(self, account=''):
        sqls = """select `id`, `account`, `lr` from `force_route`"""
        res = db.execFatch(sqls)
        force_route_list = []
        if len(res) > 0:
            for record in res:
                uid = record[0]
                user = record[1]
                lr_node = record[2]
                force_route_list.append({"id": uid, "user":user, "lr":lr_node})
        self.render("index.html", force_route_list=force_route_list )

    def delete(self, account=''):
        sqld = """truncate table `force_route`"""
        db.execOnly(sqld)
        self.write("ok")

    def post(self, account):
        reqbody = json.loads(self.request.body)
        account = reqbody["account"]
        sqld = """delete from `force_route` where `account`='%s'"""%account
        db.execOnly(sqld)
        self.write("ok")


class addForce(tornado.web.RequestHandler):
    def get(self):
        self.render("add.html")

    def post(self):
        logger = logging.getLogger("nc")
        reqbody = json.loads(self.request.body)
        account = reqbody["account"]
        lr_ip = reqbody["lr_ip"]
        lr_port = reqbody["lr_port"]
        lr = "%s:%s"%(lr_ip, lr_port)
        sqls = """select * from `force_route` where `account`='%s'"""%account
        res = db.execOnly(sqls)
        if res > 0:
            self.write({"code":400})
        else:
            sqls_id = """select `lr_id` from `lr_node` where ip='%s' and port='%s'"""%(lr_ip, lr_port)
            res_id = db.execFatch(sqls_id)
            if len(res_id) == 0:
                self.write({"code": 404})
            else:
                lr_id = res_id[0][0]
                sqli = """insert into `force_route` (`account`, `lr`, `lr_id`) values ('%s', '%s', '%s')"""%(account, lr, lr_id)
                db.execOnly(sqli)
                logger.info("New record in forceroute table, account[%s] -> lr[%s]"%(account, lr))
                self.write({"code":200})


def runWeb(port=8000):
    settings = { 
            'debug': True,
            'template_path': os.path.join(os.path.dirname(__file__), 'templates'),
            'static_path': os.path.join(os.path.dirname(__file__), 'static')
            }
    applicaton = tornado.web.Application([
        # (r"/api/ep", getEpHandler),
        (r"/addforce", addForce),
        (r"/forcetable/(.*)", getForceTable),
        (r"/api/epid/(.*)", changeEpHandler),
        (r"/api/lrid/(.*)", changeLrHandler),
        (r"/api/nodelist/(.*)", getNodelist),
        (r"/api/getmtlr", getMeetinglr),
        (r"/api/upqosdata", upQosdata),
    ], **settings)
    applicaton.listen(port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == '__main__':
    if len(sys.argv) != 2 or ( sys.argv[1] != "init" and not sys.argv[1].isdigit() ):
        print """
Usage: python %s {init|80}
    - init: Initialize the table data, exits after execbution.
    - 80: Start the web service on port 80, run as a daemon.
    """%sys.argv[0]
    elif sys.argv[1] == "init":
        print "initialize..."
        initLog("nc")
        initDb()
    else:
        port = sys.argv[1]
        print "runweb on port %s"%port
        initLog("nc")
        runWeb(port)
