#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from MysqlDB import db
from ncDef import write_level
from pyRedis import redis_client, getAncestor, reset_ancestors
import nc_config


class lrNode(object):
    """ lrnode 类，提供 lr 实例记录的属性获取、记录获取、除去自身的所有lr列表获取、以及Lr记录的添加，删除，修改等的API """
    def __init__(self, id):
        self.logger = logging.getLogger("nc")
        self.lr_id = id


    def getLrnode(self, all=False):
        if all:
            sqls = """select `lr_id`,`name`,`ip`,`port`,`plevel_id`,`cluster`,`cloud`,`price`, `lr_type`,`sysload`, `level_id`, `last_subtime`, `active` from `lr_node`"""
            res = db.execFetch(sqls)
            all_lr_list = []
            for record in res:
                all_lr_list.append({"lrid": record[0], "name": record[1], "ip": record[2], "port": record[3], "plevel_id": record[4], "cluster": record[5], "cloud": record[6], "price": record[7], "lr_type": record[8], "sysload": record[9], "level_id": record[10], "last_subtime": record[11], "active": record[12] })
            data = all_lr_list
        else:
            lr_list = redis_client.keys("lr:*:%s"%self.lr_id)
            if not lr_list: return None
            lr = lr_list.pop()
            lr_ip, lr_port, lr_type, cluster, last_subtime, active = redis_client.hmget(lr, "ip", "port", "lr_type", "cluster", "last_subtime", "active")
            data = {"lrid": self.lr_id, "ip": lr_ip, "port": lr_port, "lr_type": lr_type, "level_id": lr.split(":")[1], "cluster": cluster, "last_subtime": last_subtime, "active": active}
        return data


    def addLrnode(self, sql_data, level_id, plevel_id ):
        sqli = """insert into lr_node (`lr_id`, `name`, `plevel_id`, `ip`, `port`, `cluster`, `cloud`, `price`, `lr_type`, `sysload`, `level_id`, `last_subtime`, `active`) values ( "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", "%s", %s, "%s", %s, '1')""" % sql_data
        try:
            res = db.execOnly(sqli)
        except:
            res = 0
        if res > 0:
            level_cluster, level_type = write_level(level_id)
            redis_client.hmset("level:%s"%level_id, {"plevel_id": plevel_id, "level_cluster": level_cluster, "level_type": level_type})
            # 生成　ancestors/level 的redis记录
            l_list = redis_client.keys("level:%s"%level_id)
            if not l_list:
                redis_client.rpush("ancestors:%s"%level_id, level_id)
                for l in getAncestor(level_id, []):
                    redis_client.rpush("ancestors:%s"%level_id, l)

            self.logger.info("Add lr_node with lrid=%s done."%self.lr_id)
            return {"code": 200, "status": "success", "msg": "Add lr_node with lrid=%s done."%self.lr_id}
        else:
            self.logger.error("Add lr_node with lrid=%s failed, insert statement failed to execute."%self.lr_id)
            return {"code": 400, "status": "exist", "msg": "Add lr_node with lrid=%s failed."%self.lr_id}


    def modLrnode(self, sql_data, level_id, plevel_id, old_level, lrid):
        sqlu = """update lr_node set `name`="%s", `plevel_id`="%s", `ip`="%s", `port`="%s", `cluster`="%s", `cloud`="%s", `price`="%s", `lr_type`="%s", `sysload`=%s, `level_id`='%s', `last_subtime`=%s  where `lr_id`='%s' """ % sql_data
        sqlu_1 = """update level_node set `plevel_id`='%s' where `level_id`='%s'""" % (plevel_id, level_id)
        sql_select = """select `level_id` from `level_node`"""
        level_list = [x[0] for x in db.execFetch(sql_select)]
        #  sql_parent = """select `plevel_id` from level_node where `level_id`='%s'"""%old_level
        #  old_parent_level = db.execFetch(sql_parent)[0][0]

        if level_id not in level_list:
            if old_level:
                sql_check = """select lr_id from lr_node where level_id='%s'""" % old_level
                result = db.execFetch(sql_check)
                if len(result) <= 1:
                    sql_s_old = """select `level_id`, `plevel_id` from level_node where `level_id`='%s'"""% old_level
                    sql_u_old = """update level_node set `plevel_id`='%s' where `plevel_id`='%s'""" 
                    need_r = db.execFetch(sql_s_old)
                    if need_r:
                        db.execFetch(sql_u_old % (need_r[0][1], old_level))
                        for l in need_r:
                            redis_client.hset("level:%s"%l[0], "plevel_id", l[1])
                    sql_delete = """delete from `level_node` where `level_id`='%s'""" % old_level
                    db.execOnly(sql_delete)
                    redis_client.delete("level:%s"%old_level)
            db.execOnly(sqlu)
            res = write_level(level_id)
            redis_client.hmset("level:%s"%level_id, {"plevel_id": plevel_id, "level_cluster": res[0], "level_type": res[1]})
            reset_ancestors()
            self.logger.info("Add new level and qos for  lrid=%s done."%self.lr_id)
                #  return {"code": 200, "status": "success", "msg": "Add new level and qos for  lrid=%s done."%self.lr_id}
        else:
            if level_id != old_level:
                sql_check = """select lr_id from lr_node where level_id='%s'""" % old_level
                result = db.execFetch(sql_check)
                if len(result) <= 1:
                    sql_delete = """delete from `level_node` where `level_id`='%s'""" % old_level
                    db.execOnly(sql_delete)
                    redis_client.delete("level:%s"%old_level)
                    reset_ancestors()
        #  print sqlu
        try:
            db.execOnly(sqlu_1)
            result = db.execOnly(sqlu)
            write_level(old_level)
            res = write_level(level_id) 
            redis_client.hmset("level:%s"%level_id, {"plevel_id": plevel_id, "level_cluster": res[0], "level_type": res[1]})
            redis_client.delete("ancestors:%s"%level_id)
            redis_client.rpush("ancestors:%s"%level_id, level_id)
            for l in getAncestor(level_id, []):
                redis_client.rpush("ancestors:%s"%level_id, l)
        except Exception, e:
            #  print "**************",e
            result = 0
        if result: 
            self.logger.info("Modify lr_node [%s] success."%self.lr_id)
            ret = {"code": 200, "status": "success"}
        else:
            self.logger.info("Modify lr_node [%s] failed."%self.lr_id)
            ret = {"code": 400, "status": "failed"}
        return ret


    def delLrnode(self):
        # 删除LR记录
        sql_6 = """delete from lr_node where lr_id='%s'"""%self.lr_id
        db.execFetch(sql_6)
        level_id_res = redis_client.keys("lr:*:%s"%self.lr_id)
        if len(level_id_res) == 0:
            level_id = None
            self.logger.warn("Not found level_id by lr_id [%s]"%self.lr_id)
        else: level_id = level_id_res[0].split(":")[1]
        if level_id:
            #  sql_check = """select lr_id from lr_node where level_id='%s'""" % level_id
            #  result = db.execFetch(sql_check)
            result = redis_client.keys("lr:%s:*"%level_id)
            #  print "*"*20
            level_cluster,_ = write_level(level_id)
            redis_client.hset("level:%s"%level_id, "level_cluster", level_cluster)
            if len(result) <= 1:
                sql_delete = """delete from `level_node` where `level_id`='%s'""" % level_id
                db.execOnly(sql_delete)
                redis_client.delete("level:%s"%level_id)
                reset_ancestors()
        self.logger.info("Del lr_node with lrid=%s success."%level_id)
        return {"code": 200, "status": "success"}

