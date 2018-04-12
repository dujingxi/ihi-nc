#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Filename: nc.py
# Description: The optimal target LR is calculated according to various attributes and network conditions.

# Copyright (C) 2018 dujingxi

# Author: dujingxi <dujingxi@streamocean.com>
# License: StreamOcean
# Last-Updated: 2018/01/11

import sys
import os
import copy
import json
import random
from lib.MysqlDB import db
from lib.lrNode import lrNode
from lib.netQos import netQos
from lib.ncDef import *
from lib.ncInit import initDb
from lib.getMtlr import getMeetinglr
from lib.lrCluster import *
import tornado.web
import tornado.ioloop
import tornado.escape
import tornado.gen


def updateQos(src_level, dst_level, weight, price, percent_lost, mrtt, artt):
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
    netqos = netQos(src_level)
    netqos.setProperty(dst_level, "path", res)
    return qos, res
# initLog("nc")
# updateQos("lr11785a32104e7ac8620171214134654", "lr13315a3368261393420171215141358", 0.5, 50, 1.22, 12.09, 4.66)

# ll = [[0, 16.19, 6.33], [0, 20.22,15.51], [6, 12.10, 4.22], [18, 20.99, 19.09], [30, 66.03, 40.11], [58, 18.01, 0.36], [70, 33.23, 32.12], [88, 161.31, 103.28], [95, 10.88, 9.09]]
# for i in ll:
#     updateQos(1, 20, i)


'''
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
'''


class changeEpHandler(tornado.web.RequestHandler):
    """ 用户-LR 表 API 接口 """
    def post(self, epid=None):
        reqbody = json.loads(self.request.body)
        act = reqbody["account"]
        ep = reqbody["userid"]
        ep_user = "%s_%s"%(ep, act)
        level = reqbody["level_id"]
        vsp_id = reqbody["vsp_id"]
        sqli = """insert into `adjacency` (`account`, `ep_id`, `level_id`, `vsp_id`) values ("%s", "%s", "%s", "%s")"""%(act, ep_user, level, vsp_id)
        rows = db.execOnly(sqli)
        if rows == 1: self.write({"code":200, "status": "success"})
        else: self.write({"code": 404, "status": "error"})

    def get(self, epid=''):
        if epid != '':
            sqls = """select `account`, `ep_id`,`level_id`, `vsp_id` from `adjacency` where `ep_id`='%s'"""%epid
            res = db.execFatch(sqls)
            self.write({"code":200, "stauts":"success", "result":{"account": res[0][0], "epid":res[0][1], "level_id":res[0][2], "vsp_id": res[0][3]}})
        else:
            sqls = """select `account`, `ep_id`,`level_id`, `vsp_id` from `adjacency`"""
            res = db.execFatch(sqls)
            ep_level_list = []
            for record in res:
                ep_level_list.append({"code":200, "stauts":"success", "result":{"account": record[0][0], "epid":record[0][1], "level_id":record[0][2], "vsp_id": record[0][3]}})
            self.write({"code": 200, "stauts": "success", "result":ep_level_list})

    def put(self, epid):
        reqbody = json.loads(self.request.body)
        act = reqbody["account"]
        level = reqbody['level_id']
        vsp = reqbody["vsp_id"]
        sqlu = """update `adjacency` set `account`="%s", `level_id`="%s" , `vsp_id`="%s" where `ep_id`='%s'""" % (act, level, vsp, epid )
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
        lr_id = reqbody.get("id")
        lr_name = reqbody.get("name")
        plevel_id = reqbody.get("parents")
        ip = reqbody.get("ip")
        port = reqbody.get("port")
        operator = reqbody.get("op_name")
        cloud = reqbody.get("net_type")
        price = reqbody.get("price")
        lr_type = reqbody.get("lr_type")
        level_id = reqbody.get("level_id")
        lrc_id = reqbody.get("lrc_ids", '[]')
        sysload = reqbody.get("sysload", 0)
        sql_data = (lr_id, lr_name, plevel_id, ip, port, operator, cloud, price, lr_type, sysload, str(lrc_id), level_id)
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
        lr_name = reqbody.get("name")
        plevel_id = str(reqbody.get("parents"))
        ip = reqbody.get("ip")
        port = reqbody.get("port")
        operator = reqbody.get("op_name")
        cloud = reqbody.get("net_type")
        price = reqbody.get("price")
        lr_type = reqbody.get("lr_type")
        level_id = reqbody.get("level_id")
        lrc_id = reqbody.get("lrc_ids", '[]')
        sysload = reqbody.get("sysload", 0)
        sql_data = (lr_name, plevel_id, ip, port, operator, cloud, price, lr_type, sysload, str(lrc_id), level_id, lrid)
        lr_node = lrNode(lrid)
        res = lr_node.modLrnode(sql_data)
        self.write(res)

    def delete(self, lrid):
        lr_node = lrNode(lrid)
        res = lr_node.delLrnode()
        self.write(res)


class lrGridHandler(tornado.web.RequestHandler):
    def post(self, lrgid=None):
        reqbody = json.loads(self.request.body)
        grid_id = reqbody.get("lrg_id")
        grid_name = reqbody.get("lrg_name")
        vsp_id = reqbody.get("vsp_id")
        lr_grid = lrGrid(grid_id)
        res = lr_grid.addGrid(grid_name, vsp_id)
        if res == 0: msg = "Failed, please check if lr_grid exists."
        else: msg = "Grid add success."
        self.write({"code": 200, "msg": msg})

        
    def put(self, lrgid):
        reqbody = json.loads(self.request.body)
        grid_name = reqbody.get("lrg_name", None)
        vsp_id = reqbody.get("vsp_id", None)
        lr_grid = lrGrid(lrgid)
        lr_grid.modGrid(grid_name, vsp_id)
        self.write({"code": 200})

    def delete(self, lrgid):
        lr_grid = lrGrid(lrgid)
        res = lr_grid.delGrid()
        if res:
            self.write({"code": 200, "msg": "delete success"})
        else: self.write({"code": 400, "msg": "Unknown error."})


class  lrClusterHandler(tornado.web.RequestHandler):
    def post(self, lrcid=None):
        reqbody = json.loads(self.request.body)
        print "add lrc: %s"%reqbody
        lrc_id = reqbody.get("lrc_id")
        lrc_name = reqbody.get("lrc_name")
        lrc_region = reqbody.get("region", '')
        lrg_id = reqbody.get("lrg_ids", '[]')
        lr_cluster = lrCluster(lrc_id)
        res = lr_cluster.addLrc(lrc_name, str(lrg_id), lrc_region)
        if res == 0: msg = "Failed, please check if lrc exists."
        else: msg = "Cluster add success."
        self.write({"code": 200, "msg": msg})

    def put(self, lrcid):
        reqbody = json.loads(self.request.body)
        lrc_name = reqbody.get("lrc_name", '')
        lrc_region = reqbody.get("region", '')
        lrg_id = reqbody.get("lrg_ids", '')
        lr_cluster = lrCluster(lrcid)
        lr_cluster.modCluster(lrc_name, str(lrg_id), lrc_region)
        self.write({"code": 200})

    def delete(self, lrcid):
        lr_cluster = lrCluster(lrcid)
        res = lr_cluster.delCluster()
        if res:
            self.write({"code": 200, "msg": "delete success"})
        else: self.write({"code": 400, "msg": "Unknown error."})


class upSysload(tornado.web.RequestHandler):
    """ 获取需与自身（lr）测试联通性的LR列表的API """
    def post(self):
        reqbody = json.loads(self.request.body)
        lr_id = reqbody.get("id")
        lr_sysload = reqbody.get("sysload", 0)
        lr_node = lrNode(lr_id)
        lr_node.setProperty("sysload", lr_sysload)
        self.write({"code": 200, "status": "success"})


class getLrlist(tornado.web.RequestHandler):
    def get(self, lrid):
        lr_node = lrNode(lrid)
        lr_level_id = lr_node.getProperty("level_id")
        netqos = netQos(lr_level_id)
        target_lr_list = netqos.getValidlr()
        lrc_lr_list = detect_lr_list()
        self.write({"code": 200, "target_lr_list": target_lr_list, "lrc_lr_list": lrc_lr_list})


class upQosdata(tornado.web.RequestHandler):
    def post(self):
        reqbody = json.loads(self.request.body)
        lr_src = reqbody["id"]
        src_lr_node = lrNode(lr_src)
        src_lrc = src_lr_node.getProperty("level_id")
        data = reqbody["data"]
        logger = logging.getLogger("nc")
        for lr in data:
            lr_dst = lr["dst_id"]
            dst_lr_node = lrNode(lr_dst)
            dst_lrc = dst_lr_node.getProperty("level_id")
            percent_lost = lr["percent_lost"]
            mrtt = lr["mrtt"]
            artt = lr["artt"]
            sqls = """select `weight` from `net_qos` where `level_src`='%s' and `level_dst`='%s'"""%(src_lrc, dst_lrc)
            weight = db.execFatch(sqls)
            price = dst_lr_node.getProperty("price")
            res = updateQos(src_lrc, dst_lrc, weight[0][0], price, percent_lost, mrtt, artt)
            qos, path = res
            logger.info("Update: level_id[%s] -> level_id[%s], qos->%s, path->%s"%(lr_src, lr_dst, qos, path))
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
        (r"/api/getlist/(.*)", getLrlist),
        (r"/api/upsysload", upSysload),
        (r"/api/getmtlr", getMeetinglr),
        (r"/api/upqosdata", upQosdata),
        (r"/api/lrgid/(.*)", lrGridHandler),
        (r"/api/lrcid/(.*)", lrClusterHandler),
    ], **settings)
    applicaton.listen(port)
    tornado.ioloop.IOLoop.instance().start()


def detect_lr_list():
    level_list = getAlllevel()
    result = []
    for level in level_list:
        lrc = lrCluster(level)
        lr = lrc.randomLr()
        result.append(lr)
    return result

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
