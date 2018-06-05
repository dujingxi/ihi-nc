#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import logging
from MysqlDB import db
from netQos import netQos
from pyRedis import redis_client
import nc_config


class lrNode(object):
    """ lrnode 类，提供 lr 实例记录的属性获取、记录获取、除去自身的所有lr列表获取、以及Lr记录的添加，删除，修改等的API """
    def __init__(self, id):
        self.logger = logging.getLogger("nc")
        self.lr_id = id

    def getProperty(self, attr):
        sqls = """select %s from lr_node where lr_id='%s'""" % (attr, self.lr_id)
        res = db.execFetch(sqls)
        return res[0][0]

    def getLrnode(self, all=False):
        if all:
            sqls = """select `lr_id`,`name`,`ip`,`port`,`plevel_id`,`operator`,`cloud`,`price`, `lr_type`,`sysload`, `level_id`, `lrc_ids` from `lr_node`"""
            res = db.execFetch(sqls)
            all_lr_list = []
            for record in res:
                all_lr_list.append({"lrid": record[0], "name": record[1], "ip": record[2], "port": record[3], "plevel_id": record[4], "operator": record[5], "cloud": record[6], "price": record[7], "lr_type": record[8], "sysload": record[9], "level_id": record[10], "lrc_id": record[11]})
            data = all_lr_list
        else:
            lr_list = redis_client.keys("lrid:*:%s"%self.lr_id)
            if not lr_list: return None
            lr = lr_list.pop()
            lr_ip, lr_port, lr_type = redis_client.hmget(lr, "ip", "port", "lr_type")
            data = {"lrid": self.lr_id, "ip": lr_ip, "port": lr_port, "lr_type": lr_type, "level_id": lr.split(":")[1]}

            #  sqls = """select `lr_id`,`name`,`ip`,`port`,`operator`,`cloud`,`price`,`lr_type`, `plevel_id`, `sysload`, `level_id`, `lrc_ids`  from lr_node where lr_id='%s'""" % self.lr_id
            #  res = db.execFetch(sqls)
            #  if len(res) != 0: data = {"lrid": res[0][0], "name": res[0][1], "ip": res[0][2], "port": res[0][3], "operator": res[0][4], "cloud": res[0][5], "price": res[0][6], "lr_type": res[0][7],  "plevel_id": res[0][8], "sysload": res[0][9], "level_id": res[0][10], "lrc_id": res[0][11]}
            #  else: data = nc_config.DEFAULT_LR
        return data

    def getDstlist(self):
        sqls = """select lr_id from lr_node"""
        lr_dst_list = []
        res = db.execFetch(sqls)
        if len(res) == 0:
            self.logger.error("lr_node table empty.")
            sys.exit(0)
        for record in res:
            lr_dst_list.append(record[0])
        lr_dst_list.remove(self.lr_id)
        return lr_dst_list


    def addLrnode(self, sql_data):
        sqli = """insert into lr_node (`lr_id`, `name`, `plevel_id`, `ip`, `port`, `operator`, `cloud`, `price`, `lr_type`, `sysload`, `lrc_ids`, `level_id`, `last_subtime`) values ( "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", %s, "%s", "%s", %s)""" % sql_data
        try:
            res = db.execOnly(sqli)
        except:
            res = 0
        plevel_id = sql_data[2]
        level_id = sql_data[-2]
        if res > 0:
            sql_select = """select `level_id` from `level_node`"""
            level_list = [x[0] for x in db.execFetch(sql_select)]
            if level_id not in level_list:
                sql_1 = """insert into level_node (`level_id`, `plevel_id`) values ('%s', '%s')"""%(level_id,plevel_id)
                db.execOnly(sql_1)
                netqos = netQos(level_id)
                ret = netqos.lrAddall()
                if ret > 0:
                    self.logger.info("Add lr_node with lrid=%s done."%self.lr_id)
                    return {"code": 200, "status": "success", "msg": "Add lr_node with lrid=%s done."%self.lr_id}
                else:
                    self.logger.error("Add lr_node with lrid=%s fail, on update table netqos."%self.lr_id)
                    return {"code": 400, "status": "failed", "msg": "Add lr_node with lrid=%s fail, on update table netqos."%self.lr_id}
            else:
                self.logger.info("Add lr_node success, level_id exists.")
                return {"code": 200, "status": "success", "msg": "Add lr_node success, level_id exists."}
        else:
            self.logger.error("Add lr_node with lrid=%s failed."%self.lr_id)
            return {"code": 400, "status": "exist", "msg": "Add lr_node with lrid=%s failed."%self.lr_id}

    def modLrnode(self, sql_data, level_id, plevel_id, old_level, lrid):
        sqlu = """update lr_node set `name`="%s", `plevel_id`="%s", `ip`="%s", `port`="%s", `operator`="%s", `cloud`="%s", `price`="%s", `lr_type`="%s", `sysload`=%s, `lrc_ids`="%s", `level_id`='%s', `last_subtime`=%s  where `lr_id`='%s' """ % sql_data
        sqlu_1 = """update level_node set `plevel_id`='%s' where `level_id`='%s'""" % (plevel_id, level_id)
        sql_select = """select `level_id` from `level_node`"""
        level_list = [x[0] for x in db.execFetch(sql_select)]
        #  sql_parent = """select `plevel_id` from level_node where `level_id`='%s'"""%old_level
        #  old_parent_level = db.execFetch(sql_parent)[0][0]

        if level_id not in level_list:
            sql_1 = """insert into level_node (`level_id`, `plevel_id`) values ('%s', '%s')"""%(level_id,plevel_id)
            if old_level:
                sql_check = """select lr_id from lr_node where level_id='%s'""" % old_level
                result = db.execFetch(sql_check)
                if len(result) <= 1:
                    sql_s_old = """select `plevel_id` from level_node where `level_id`='%s'"""% old_level
                    sql_u_old = """update level_node set `plevel_id`='%s' where `plevel_id`='%s'""" 
                    need_r = db.execFetch(sql_s_old)
                    if need_r:
                        db.execFetch(sql_u_old % (need_r[0][0], old_level))
                    sql_delete = """delete from `level_node` where `level_id`='%s'""" % old_level
                    db.execOnly(sql_delete)
                    netqos = netQos(old_level)
                    netqos.lrDel()
            db.execOnly(sql_1)
            netqos = netQos(level_id)
            ret = netqos.lrAddall()
            if ret > 0:
                self.logger.info("Add new level and qos for  lrid=%s done."%self.lr_id)
                #  return {"code": 200, "status": "success", "msg": "Add new level and qos for  lrid=%s done."%self.lr_id}
            else:
                self.logger.error("Add new level for lrid=%s fail, on update table netqos."%self.lr_id)
                #  return {"code": 400, "status": "failed", "msg": "Add new level for lrid=%s fail, on update table netqos."%self.lr_id}
        else:
            if level_id != old_level:
                sql_check = """select lr_id from lr_node where level_id='%s'""" % old_level
                result = db.execFetch(sql_check)
                if len(result) <= 1:
                    sql_delete = """delete from `level_node` where `level_id`='%s'""" % old_level
                    db.execOnly(sql_delete)
                    netqos = netQos(old_level)
                    netqos.lrDel()
        #  print sqlu
        try:
            db.execOnly(sqlu_1)
            res = db.execOnly(sqlu)
        except Exception, e:
            #  print "**************",e
            res = 0
        if res: 
            self.logger.info("Modify lr_node [%s] success."%self.lr_id)
            ret = {"code": 200, "status": "success"}
        else:
            self.logger.info("Modify lr_node [%s] failed."%self.lr_id)
            ret = {"code": 400, "status": "failed"}
        return ret

    def delLrnode(self):
        #  sql_1 = """select `lr_id`,`plr_id` from `lr_node` where `plr_id` REGEXP '%s'"""%self.lr_id
        #  sql_3 = """select `plr_id` from `lr_node` where `lr_id`='%s'"""%self.lr_id
        #  # 更新以本身为父层的LR记录
        #  res = db.execFetch(sql_1)
        #  if len(res) > 0:
            #  for node in res:
                #  lrid = node[0]
                #  plrid = eval(node[1])
                #  plrid.remove(self.lr_id)
                #  if len(plrid) == 0:
                    #  ret = db.execFetch(sql_3)[0][0]
                    #  new_plr = ret
                #  else: new_plr = str(plrid)
                #  self.logger.info("update lr_node -> lrid : %s, parent_lr: %s"%(lrid, new_plr))
                #  sql_2 = """update `lr_node` set `plr_id`="%s" where `lr_id`='%s'"""%(new_plr, lrid)
                #  db.execOnly(sql_2)
        #  # 更新以本身为LR的用户记录
        #  sql_4 = """select `ep_id`,`lr_id` from `adjacency` where lr_id REGEXP '%s'"""%self.lr_id
        #  res = db.execFetch(sql_4)
        #  if len(res) > 0:
            #  for user in res:
                #  userid = user[0]
                #  userlr = eval(user[1])
                #  userlr.remove(self.lr_id)
                #  if len(userlr) == 0:
                    #  new_userlr = db.execFetch(sql_3)[0][0]
                #  else: new_userlr = str(userlr)
                #  self.logger.info("update user table -> ep_id: %s, lr_id: %s"%(userid, new_userlr))
                #  sql_5 = """update `adjacency` set `lr_id`="%s" where `ep_id`='%s'"""%(new_userlr, userid)
                #  db.execOnly(sql_5)
        # 删除LR记录
        sql_6 = """delete from lr_node where lr_id='%s'"""%self.lr_id
        sql_s = """select `level_id` from lr_node where `lr_id`='%s'""" % self.lr_id
        level_id_res = db.execFetch(sql_s)
        if len(level_id_res) == 0:
            level_id = None
            self.logger.warn("Not found level_id by lr_id [%s]"%self.lr_id)
        else: level_id = level_id_res[0][0]
        #  res = db.execFetch(sql_6)
        #  if res > 0:
        if level_id:
            sql_check = """select lr_id from lr_node where level_id='%s'""" % level_id
            result = db.execFetch(sql_check)
            if len(result) <= 1:
                sql_delete = """delete from `level_node` where `level_id`='%s'""" % level_id
                db.execOnly(sql_delete)
                netqos = netQos(level_id)
                netqos.lrDel()
        db.execFetch(sql_6)
        self.logger.info("Del lr_node with lrid=%s success."%level_id)
        return {"code": 200, "status": "success"}
        #  else:
            #  self.logger.warning("Del lr_node with lrid=%s failed, nod found."%self.lr_id)
            #  return {"code": 400, "status": "failed", "msg": "Not found record."}

    def setProperty(self, attr, value):
        sqlu = """update lr_node set %s=%s where lr_id='%s'""" % (attr, value, self.lr_id)
        res = db.execOnly(sqlu)
        if res == 1:
            self.logger.info("Update %s to [%s] where lrid is %s" % (attr, value, self.lr_id))
        else:
            self.logger.warning("Update %s to [%s] where lrid is %s failed" % (attr, value, self.lr_id))
        return res


