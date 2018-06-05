#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import math
from lrCluster import lrCluster
from ncDef import *
from MysqlDB import db
from pyRedis import redis_client


#  def getLrProperty(lrid, attr):
    #  sqls = """select %s from `lr_node` where `lr_id`='%s'""" % (attr, lrid)
    #  res = db.execFetch(sqls)
    #  return res[0][0]
#
#
class netQos(object):
    """
    添加一条lr记录时，生成 net qos 的计算结果记录，插入net_qos表。
    lraddself 插入源为lrid，到其他lr的所有联通性计算记录，初始化时调用
    lraddall 插入源为lrid，到其他lr，以及其他lr到lrid的所有计算记录，使用中添加lrnode时调用
    lrdel 删除net_qos中lrid有关的记录，删除lrnode时调用
    getvalidlr 获取源为lrid，并且与其联通性不为0（即可以联通）的 lr 列表，API 供LR客户端调用
    """
    def __init__(self, level_id):
        self.src_level = level_id
        self.logger = logging.getLogger("nc")

    def lrAddself(self):

        dst_level_list = getAlllevel()
        #  dst_level_list.remove(self.src_level)
        level_conn_list, relationship_list = checkCloud(self.src_level, dst_level_list)
        operator_res = checkOperator(self.src_level, dst_level_list)
        operator_half_conn_list = set(operator_res["half_conn"])
        operator_not_conn_list = set(operator_res["not_conn"])
        res_half_list = list(set(level_conn_list) & operator_half_conn_list)
        res_conn_list = list(set(level_conn_list) - set(res_half_list) - operator_not_conn_list)
        self.logger.info("level_id: %s - connlist: %s - halflist: %s "%(self.src_level, res_conn_list, res_half_list ))
        dlr_level_list = {}
        for k,v in enumerate(relationship_list):
            dlr_level_list[v] = k

        sql_data_1 = []
        for dst_level in dst_level_list:
            if dst_level == self.src_level:
                weight = 1; layer_distance = 0; path = weight
                sql_data_1.append((self.src_level, dst_level, weight, layer_distance, path))
                redis_client.hmset("qos:%s:%s"%(self.src_level, dst_level), {"weight": weight, "layer_distance": layer_distance, "path": path})
                continue
            dst_lrc = lrCluster(dst_level)
            dst_lr_id = dst_lrc.randomLr()
            dst_price = getLrProperty(dst_lr_id, "price")
            if dlr_level_list.has_key(dst_level): layer_distance = dlr_level_list[dst_level] 
            else: layer_distance = 0

            if (dst_level not in res_conn_list) and (dst_level not in res_half_list):
                weight = 0; path = 0
            else:
                if dst_level in res_conn_list: weight = 1
                elif dst_level in res_half_list: weight = 0.5
                if dst_price == 0: 
                    if layer_distance: 
                        path = layer_distance/weight
                    else:
                        impassable_num = len(dlr_level_list)
                        path = impassable_num/weight
                else: 
                    if layer_distance: 
                        path = math.sqrt(dst_price/100)*layer_distance/weight
                    else:
                        impassable_num = len(dlr_level_list)
                        path = math.sqrt(dst_price/100)*impassable_num/weight
            sql_data_1.append((self.src_level, dst_level, weight, layer_distance, path))
            redis_client.hmset("qos:%s:%s"%(self.src_level, dst_level), {"weight": weight, "layer_distance": layer_distance, "path": path})

        if not sql_data_1: return 0
        else:
            sqli = """insert into net_qos (`level_src`, `level_dst`, `weight`, `layer_distance`, `path`) values (%s, %s, %s, %s, %s)"""
            return db.execOnly(sqli, sql_data_1)

    def lrAddall(self):
        self.lrAddself()
        src_lrc = lrCluster(self.src_level)
        src_lr_id = src_lrc.randomLr()
        src_price = getLrProperty(src_lr_id, "price")
        dst_level_list = getAlllevel()
        sql_data = []
        for dst_level in dst_level_list:
            if dst_level == self.src_level: continue
            check_cloud_res, relationship_list = checkCloud(dst_level, [self.src_level])
            dlr_level_list = {}
            for k,v in enumerate(relationship_list):
                dlr_level_list[v] = k
            if dlr_level_list.has_key(self.src_level): layer_distance = dlr_level_list[self.src_level] 
            else: layer_distance = 0

            if len(check_cloud_res) <= 1:
                weight = path = 0
            else:
                check_operator_res = checkOperator(dst_level, [self.src_level])
                if len(check_operator_res["conn_list"]) != 0: weight = 1
                elif len(check_operator_res["half_conn"]) != 0: weight = 0.5
                if src_price == 0: 
                    if layer_distance: 
                        path = layer_distance/weight
                    else:
                        impassable_num = len(dlr_level_list)
                        path = impassable_num/weight
                else: 
                    if layer_distance: 
                        path = math.sqrt(src_price/100)*layer_distance/weight
                    else:
                        impassable_num = len(dlr_level_list)
                        path = math.sqrt(src_price/100)*impassable_num/weight

            sql_data.append((dst_level, self.src_level, weight, layer_distance, path))
            #  print "*"*40, dst_level, self.src_level, weight, layer_distance, path
            redis_client.hmset("qos:%s:%s"%(dst_level,self.src_level), {"weight": weight, "layer_distance": layer_distance, "path": path})

        if not sql_data: return 0
        else:
            sqli = """insert into net_qos (`level_src`, `level_dst`, `weight`, `layer_distance`, `path`) values (%s, %s, %s, %s, %s)"""

            return db.execOnly(sqli, sql_data)

    def lrDel(self):
        del_list = redis_client.keys("qos:*:%s"%self.src_level)
        del_list += redis_client.keys("qos:%s:*"%self.src_level)
        for k in del_list: redis_client.delete(k)
        sqld = """delete from net_qos where `level_src`='%s' or `level_dst`='%s'""" % (self.src_level, self.src_level)
        self.logger.info("delete record with level_id -> %s"%self.src_level)
        return db.execOnly(sqld)

    '''
    def lrMod(self):
        self.lrDel()
        self.lrAddall()
        self.logger.info("mod record with lrid -> %s"%self.lr_src)
    '''

    def setProperty(self, dst, attr, value):
        sqlu = """update `net_qos` set %s='%s' where `level_src`='%s' and `level_dst`='%s'""" % (attr, value, self.lr_src, dst)
        res = db.execOnly(sqlu)
        return res

    def getValidlevel(self):
        qos_list = redis_client.keys("qos:%s:*"%self.src_level)
        level_list = []
        for qos in qos_list:
            weight = redis_client.hget(qos, "weight")
            if float(weight) != 0.0: level_list.append(qos.split(":")[2])
        #  sqls = """select `level_dst` from `net_qos` where `level_src`='%s' and weight!=0"""%self.src_level
        #  res = db.execFetch(sqls)
        #  level_list = []
        #  for level in res:
            #  level_list.append(level[0])
        return level_list

    def getValidlr(self):
        level_list = self.getValidlevel()
        lr_valid_list = []
        for level in level_list:
            dst_lrc = lrCluster(level)
            dst_lr_id = dst_lrc.randomLr()
            #  ip = getLrProperty(dst_lr_id, "ip")
            #  port = getLrProperty(dst_lr_id, "port")
            #  lr_valid_list.append({"id": lr[0], "ip": ip, "port":port})
            lr_valid_list.append(dst_lr_id)
        return lr_valid_list


