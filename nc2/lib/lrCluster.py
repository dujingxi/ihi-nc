#!/usr/bin/env python
# -*- coding:utf-8 -*-

import logging
from MysqlDB import db
from pyRedis import redis_client


class lrCluster(object):
    def __init__(self, lrcid):
        self.lrcid = lrcid
        self.logger = logging.getLogger("nc")

    def addLrc(self, lrc_name, lrg_id, region):
        sqli = """insert into lr_cluster (`lrc_id`, `lrc_name`, `lrg_ids`, `region`) values ('%s', '%s', '%s', '%s')""" % (self.lrcid, lrc_name, lrg_id, region)
        try:
            res = db.execOnly(sqli)
        except:
            res = 0
        if res: self.logger.info("Add lr_cluster [%s] success."%self.lrcid)
        else: self.logger.error("Add lr_cluster[%s] failed, please check if lr_cluster exists."% self.lrcid)
        return res

    def modCluster(self, lrc_name, lrg_id, region):
        sqlu = """update `lr_cluster` set `lrc_name`="%s", `lrg_ids`="%s", `region`="%s"  where `lrc_id`='%s'"""
        #  print sqlu % (lrc_name, lrg_id, region, self.lrcid)
        try:
            res = db.execOnly(sqlu % (lrc_name, lrg_id, region, self.lrcid))
        except Exception, e:
            #  print "#####################",e
            res = 0
        if res: self.logger.info("Modify lr_cluster [%s] success."%self.lrcid)
        else: self.logger.error("Modify lr_cluster[%s] failed."% self.lrcid)
        return res

    def delCluster(self):
        sqld = """delete from `lr_cluster` where `lrc_id`='%s'""" % self.lrcid
        ret = db.execOnly(sqld)
        if ret:
            self.logger.info("Delete lr_cluster [%s] success."%self.lrcid)
        else: 
            self.logger.error("Delete lr_cluster[%s] failed."% self.lrcid)
        sqls = """ select `lr_id`,`lrc_ids` from `lr_node` where `lrc_ids`!='[]'"""
        res = db.execFetch(sqls)
        sqlu = """update `lr_node` set `lrc_ids`="%s" where `lr_id`='%s'"""
        for lr in res:
            lrc_ids = eval(lr[1])
            if self.lrcid in lrc_ids: 
                lrc_ids.remove(self.lrcid)
                db.execOnly(sqlu % (str(lrc_ids), lr[0]))
        return True

    def randomLr(self, name="level"):
        """ 返回当前lrcluster内sysload最低的lr """
        #  if name == "level":
            #  sqls = """select `lr_id` from `lr_node` where `level_id`='%s' order by `sysload` limit 1""" % self.lrcid
            #  res = db.execFetch(sqls)
            #  if len(res) == 0: return None
            #  lrid = res[0][0]
        #  # for redis
        if name == "level":
            lr_list = redis_client.keys("lrid:%s:*"%self.lrcid)
            if not lr_list: return None
            best_lr = lr_list[0]
            for lr in lr_list:
                sysload = redis_client.hget(lr, "sysload")
                active = redis_client.hget(lr, "active")
                if sysload < redis_client.hget(best_lr, "sysload") and active == '1': best_lr = lr
            lrid = best_lr.split(":")[2]

        else:
            lr_list = []
            sqls = """ select `lr_id`,`lrc_ids`, `sysload` from `lr_node` where `lrc_id`!='[]'""" # order by `sysload` limit 1""" % self.lrcid
            res = db.execFetch(sqls)
            if len(res) == 0: return None
            for lr in res:
                lrc_ids = eval(lr[1])
                if self.lrcid in lrc_ids: lr_list.append({"lrid": lr[0], "sysload": lr[2]})
            lr_list.sort(key=lambda x:(x["sysload"]))
            lrid = lr_list[0]["lrid"]
        return lrid

    def getAlllr(self):
        sqls = """ select `lr_id` from `lr_node` where `level_id`='%s'"""%self.lrcid
        res = db.execFetch(sqls)
        if len(res) == 0:
            return None
        lr_list = []
        count = len(res)
        for lr in res:
            lr_list.append(lr[0])
        return {"count": count, "lr_list": lr_list}

    def defMember(self,lrid):
        pass


class lrGrid(object):
    def __init__(self, lrgid):
        self.lrgid = lrgid
        self.logger = logging.getLogger("nc")

    def addGrid(self, grid_name, vsp_id):
        sqli = """insert into lr_grid (`lrg_id`, `lrg_name`, `vsp_id`) values ('%s', '%s', '%s')""" % (self.lrgid, grid_name, vsp_id) 
        try:
            res = db.execOnly(sqli)
        except:
            res = 0
        if res: self.logger.info("Add lr_grid [%s] success."%self.lrgid)
        else: self.logger.error("Add lr_grid [%s] failed, please check if lr_grid exists."% self.lrgid)
        return res

    def modGrid(self, grid_name, vsp_id):
        sqlu = """update lr_grid set %s='%s' where lrg_id='%s'"""
        if grid_name: 
            res = db.execOnly(sqlu%("lrg_name", grid_name, self.lrgid))
            if res: self.logger.info("Modify lr_grid [%s] success."%self.lrgid)
            else: self.logger.error("Modify lr_grid [%s] failed, please check if lr_grid exists."% self.lrgid)
        if vsp_id: 
            res = db.execOnly(sqlu % ("vsp_id", vsp_id, self.lrgid))
            if res: self.logger.info("Modify lr_grid [%s] success."%self.lrgid)
            else: self.logger.error("Modify lr_grid [%s] failed, please check if lr_grid exists."% self.lrgid)
        return 

    def delGrid(self):
        sqld = """delete from lr_grid where `lrg_id`='%s'""" % self.lrgid
        ret = db.execOnly(sqld)
        if ret:
            self.logger.info("Delete lr_grid [%s] success."%self.lrgid)
        else: 
            self.logger.error("Delete lr_grid [%s] failed."% self.lrgid)
        sqls = """select `lrc_id`,`lrg_ids` from lr_cluster"""
        res = db.execFetch(sqls)
        sqlu = """update `lr_cluster` set `lrg_ids`='%s' where `lrg_ids`='%s'"""
        for lrc in res:
            lrgs = eval(lrc[1])
            if self.lrgid in lrgs:
                lrgs.remove(self.lrgid)
                db.execOnly(sqlu % (str(lrgs), lrc[0]))
        return True

    def getCluster(self):
        sqls = """select `lrc_id`, `lrg_ids` from lr_cluster """
        lrc_list = []
        res = db.execFetch(sqls)
        for lrc in res:
            lrg_ids = eval(lrc[1])
            if self.lrgid in lrg_ids: lrc_list.append(lrc[0])
        return lrc_list


class vspObj(object):
    def __init__(self, vspid):
        self.vspid = vspid

    def getGrid(self):
        sqls = """select `lrg_id` from `lr_grid` where `vsp_id`='%s'""" % self.vspid
        res = db.execFetch(sqls)
        if len(res) == 0: lrg = None
        else: lrg = res[0][0]
        return lrg


