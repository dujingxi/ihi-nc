#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Filename: nc.py
# Description: The optimal target LR is calculated according to various attributes and network conditions.

# Copyright (C) 2018 dujingxi

# Author: dujingxi <dujingxi@streamocean.com>
# License: StreamOcean
# Last-Updated: 2018/05/01

import sys
import os
import copy
import json
import time
import random
from lib.pyRedis import *
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
#  import daemon
import multiprocessing 


def updateQos(src_level, dst_level, src_lrtype, price, percent_lost, mrtt, artt):
    """ 计算path值并更新数据库 """
    if percent_lost == 0:
        qos = percent_lost*0 + mrtt*0.5 + artt*0.5
    elif 0 < percent_lost <= 10:
        qos = percent_lost*0.8 + mrtt*0.1 + artt*0.1
    elif 10 < percent_lost <= 30:
        qos = percent_lost*0.9 + mrtt*0.05 + artt*0.05
    else:
        qos = None
    #  sqls = """select `weight`, `layer_distance` from net_qos where `level_src`='%s' and `level_dst`='%s'""" % (src_level, dst_level)
    #  weight = db.execFetch(sqls)[0][0]
    #  layer_distance = db.execFetch(sqls)[0][1]
    weight, layer_distance = redis_client.hmget("qos:%s:%s"%(src_level, dst_level), "weight", "layer_distance")
    weight = float(weight); layer_distance = int(layer_distance)
    if qos:
        if weight != 0:# and layer_distance != 0:
            if layer_distance != 0:
            #  value = math.sqrt(price/100)+qos
                if price==0: path = layer_distance*qos/weight
                else: path = math.sqrt(price/100)*layer_distance*qos/weight
            else:
                if src_lrtype == "dlr":
                    if price==0: path = qos/weight
                    else: path = math.sqrt(price/100)*qos/weight
                else:
                    impassable_num = len(getAncestor(src_level)) + 1
                    print impassable_num
                    if price==0: path = impassable_num*qos/weight
                    else: path = math.sqrt(price/100)*impassable_num*qos/weight
        else: path = 0
    else:
        path = 0
    redis_client.hset("qos:%s:%s"%(src_level, dst_level), "path", path)
    return qos, path
#  print updateQos("766", "587", "lr", 0, 0, 12.09, 4.66)

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
                res = db.execFetch(sqls)
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
                res = db.execFetch(sqlss)
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
        #  reqbody = json.loads(self.request.body)
        reqbody = eval(self.request.body)
        act = reqbody["account"]
        ep = reqbody["userid"]
        ep_user = "%s_%s"%(ep, act)
        level = reqbody["node_level"]
        vsp_id = reqbody["vsp_id"]
        sqli = """insert into `adjacency` (`account`, `ep_id`, `level_id`, `vsp_id`) values ("%s", "%s", "%s", "%s")"""%(act, ep_user, level, vsp_id)
        rows = db.execOnly(sqli)
        if rows == 1: 
            redis_client.hmset("user:%s"% ep_user, {"level_id": level, "vsp_id": vsp_id})
            self.write({"code":200, "status": "success"})
        else: self.write({"code": 404, "status": "error"})

    @tornado.gen.coroutine
    def get(self, epid=''):
        if epid != '':
            sqls = """select `account`, `ep_id`,`level_id`, `vsp_id` from `adjacency` where `ep_id`='%s'"""%epid
            res = db.execFetch(sqls)
            if not res:
                self.write({"code":400, "stauts":"failed", "msg":"User not found."})
            else:
                self.write({"code":200, "stauts":"success", "data":{"account": res[0][0], "epid":res[0][1], "level_id":res[0][2], "vsp_id": res[0][3]}})
        else:
            sqls = """select `account`, `ep_id`,`level_id`, `vsp_id` from `adjacency`"""
            res = db.execFetch(sqls)
            ep_level_list = []
            for record in res:
                ep_level_list.append({"account": record[0], "epid":record[1], "level_id":record[2], "vsp_id": record[3]})
            self.write({"code": 200, "stauts": "success", "data":ep_level_list})

    def put(self, epid):
        #  reqbody = json.loads(self.request.body)
        reqbody = eval(self.request.body)
        act = reqbody["account"]
        level = reqbody['node_level']
        vsp = reqbody["vsp_id"]
        sqlu = """update `adjacency` set `account`="%s", `level_id`="%s" , `vsp_id`="%s" where `ep_id`='%s'""" % (act, level, vsp, epid )
        rows = db.execOnly(sqlu)
        if rows: 
            redis_client.hmset("user:%s"%epid, {"level_id": level, "vsp_id": vsp})
            self.write({"code": 200, "status": "success"})
        else: self.write({"code": 400, "status": "error"})

    def delete(self, epid):
        sqld = """delete from `adjacency` where `ep_id`='%s'"""%epid
        rows = db.execOnly(sqld)
        if rows == 0: self.write({"code": 400, "status":"error", "msg":"User not found."})
        else: 
            redis_client.delete("user:%s"%epid)
            self.write({"code": 200, "status":"success"})


class changeLrHandler(tornado.web.RequestHandler):
    """ LR-NODE 表API接口 """
    def post(self, lrid=None):
        reqbody = eval(self.request.body)
        lr_id = reqbody.get("id")
        lr_name = reqbody.get("name")
        plevel_id = reqbody.get("p_node_level", '0')
        ip = reqbody.get("ip")
        port = reqbody.get("port")
        operator = reqbody.get("op_name", "aliyun")
        cloud = reqbody.get("net_type")
        price = reqbody.get("price", 0)
        lr_type = reqbody.get("lr_type")
        level_id = reqbody.get("level_id")
        lrc_id = reqbody.get("lrc_ids", '[]')
        sysload = reqbody.get("sysload", 0)
        last_subtime = int(time.time())
        redis_client.hmset("lrid:%s:%s"%(level_id, lr_id), {"sysload": sysload, "ip": ip, "port": port, "lr_type": lr_type, "last_subtime": last_subtime, "active": '1' })
        sql_data = (lr_id, lr_name, plevel_id, ip, port, operator, cloud, price, lr_type, sysload, str(lrc_id), level_id, last_subtime)
        lr_node = lrNode(lr_id)
        res = lr_node.addLrnode(sql_data)
        self.write(res)

    @tornado.gen.coroutine
    def get(self, lrid=''):
        lr_node = lrNode(lrid)
        if lrid != '': 
            ret = lr_node.getLrnode()
            if not ret: 
                self.write({"code": 400, "msg": "Lr not found."}); return
        else: ret = lr_node.getLrnode(True)
        self.write({"data":ret})

    def put(self, lrid):
        #  reqbody = json.loads(self.request.body)
        reqbody = eval(self.request.body)
        lr_name = reqbody.get("name")
        plevel_id = str(reqbody.get("p_node_level"))
        ip = reqbody.get("ip")
        port = reqbody.get("port")
        operator = reqbody.get("op_name")
        cloud = reqbody.get("net_type")
        price = reqbody.get("price")
        lr_type = reqbody.get("lr_type")
        level_id = reqbody.get("level_id")
        lrc_id = reqbody.get("lrc_ids", '[]')
        sysload = reqbody.get("sysload", 0)
        last_subtime = int(time.time())
        sql_data = (lr_name, plevel_id, ip, port, operator, cloud, price, lr_type, sysload, str(lrc_id), level_id, last_subtime, lrid)
        r_res = redis_client.keys("lrid:*:%s"%lrid)
        if r_res: 
            old_level = r_res[0].split(":")[1]
            redis_client.delete(r_res.pop())
        else:
            old_level = None
        redis_client.hmset("lrid:%s:%s"%(level_id, lrid), {"sysload": sysload, "ip": ip, "port": port, "lr_type": lr_type, "last_subtime": last_subtime, "active": '1'})
        lr_node = lrNode(lrid)
        res = lr_node.modLrnode(sql_data, level_id, plevel_id, old_level, lrid)
        self.write(res)

    def delete(self, lrid):
        lr_node = lrNode(lrid)
        res = lr_node.delLrnode()
        lr = redis_client.keys("lrid:*:%s"%lrid)
        if lr: redis_client.delete(lr[0])
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
    def post(self):
        reqbody = json.loads(self.request.body)
        lr_id = reqbody.get("id")
        lr_sysload = reqbody.get("sysload", 0)
        lr_active = reqbody.get("active", '1')
        cur_time = int(time.time())
        #  print lr_id,lr_sysload,lr_active,cur_time
        lr = redis_client.keys("lrid:*:%s"%lr_id)
        if not lr:
            self.write({"code": 400, "msg": "Lr not found"})
            return
        redis_client.hmset(lr[0], {"sysload": lr_sysload, "last_subtime": cur_time, "active": lr_active} )
        lr_port = redis_client.hget(lr[0], "port")
        #  lr_node = lrNode(lr_id)
        #  lr_node.setProperty("sysload", lr_sysload)
        self.write({"code": 200, "status": "success", "port": lr_port})
    
    def get(self):
        try:
            lr_id = self.get_argument("lrid")
        except Exception,e :
            self.write({"code": 400, "msg": e.log_message})
            return
        lr = redis_client.keys("lrid:*:%s"%lr_id)
        if lr:
            lr_port = redis_client.hget(lr[0], "port")
            self.write({"code": 200, "port": lr_port})
        else:
            self.write({"code": 404, "msg": "Lr not found"})

def detect_lr_list(lr_id):
    level_id = redis_client.keys("lrid:*:%s"%lr_id)[0].split(":")[1]
    level_list = getAlllevel()
    all_lr_list = []
    target_lr_list = []
    for level in level_list:
        lrc = redis_client.keys("lrid:%s:*"%level)
        qosc = redis_client.keys("qos:%s:%s"%(level_id, level))
        weight = redis_client.hget(qosc[0], "weight")
        lr_list = []
        for lr in lrc:
            active = redis_client.hget(lr, "active")
            if active == '1': lr_list.append(lr.split(":")[2])
        if not lr_list: 
            all_lr_list.append({level:"death"})
            continue
        lr_list.sort()
        if weight != "0":
            ip, port = redis_client.hmget("lrid:%s:%s"%(level, lr_list[0]), "ip", "port")
            target_lr_list.append({"lrid": lr_list[0], "ip": ip, "port": port})
        all_lr_list.append({level: lr_list[0]})
    return all_lr_list, target_lr_list


class getLrlist(tornado.web.RequestHandler):
    """ 获取需与自身（lr）测试联通性的LR列表的API """
    def get(self, lrid):
        #  lr_node = lrNode(lrid)
        #  lr_level_id = lr_node.getProperty("level_id")
        #  netqos = netQos(lr_level_id)
        #  target_lr_list = netqos.getValidlr()
        #  lrc_lr_list = detect_lr_list(1)
        lrc_lr_list, target_lr_list = detect_lr_list(lrid)
        self.write({"code": 200, "target_lr_list": target_lr_list, "lrc_lr_list": lrc_lr_list})


class upQosdata(tornado.web.RequestHandler):
    def post(self):
        reqbody = json.loads(self.request.body)
        lr_src = reqbody["id"]
        src_lr_node = lrNode(lr_src)
        src_lrc = src_lr_node.getProperty("level_id")
        src_lrtype = src_lr_node.getProperty("lr_type")
        data = reqbody["data"]
        logger = logging.getLogger("nc")
        for lr in data:
            lr_dst = lr["dst_id"]
            dst_lr_node = lrNode(lr_dst)
            dst_lrc = dst_lr_node.getProperty("level_id")
            percent_lost = lr["percent_lost"]
            mrtt = lr["mrtt"]
            artt = lr["artt"]
            price = dst_lr_node.getProperty("price")
            res = updateQos(src_lrc, dst_lrc, src_lrtype, price, percent_lost, mrtt, artt)
            qos, path = res
            logger.info("Update: level_id[%s] -> level_id[%s], qos->%s, path->%s"%(lr_src, lr_dst, qos, path))
        self.write({"code": 200, "status":"success"})


class getForceTable(tornado.web.RequestHandler):
    def get(self, account=''):
        sqls = """select `id`, `account`, `lr` from `force_route`"""
        res = db.execFetch(sqls)
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
            res_id = db.execFetch(sqls_id)
            if len(res_id) == 0:
                self.write({"code": 404})
            else:
                lr_id = res_id[0][0]
                sqli = """insert into `force_route` (`account`, `lr`, `lr_id`) values ('%s', '%s', '%s')"""%(account, lr, lr_id)
                db.execOnly(sqli)
                self.write({"code":200})


def runWeb(port=8000):
    settings = { 
            #  'debug': True,
            'debug': False,
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


def redis_cron_save(interval=7200):
    while True:
        time.sleep(interval)
        redis_save(redis_client)

def check_lr_active(interval, fail_time):
    while True:
        time.sleep(interval)
        lr_list = redis_client.keys("lrid:*")
        cur_time = int(time.time())
        for lr in lr_list:
            last_subtime = redis_client.hget(lr, "last_subtime")
            if not last_subtime: last_subtime = time.time()
            if cur_time - int(last_subtime) > fail_time:
                #  redis_client.hset(lr, "active", "0")
                redis_client.hset(lr, "active", "1")

if __name__ == '__main__':
    """ redis check """
    try:
        redis_client.ping()
    except Exception,e:
        print "Redis server connectionError: ",e
        sys.exit(-2)
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
        initLog("nc")
        p1 = multiprocessing.Process(name="redis_cron_save", target=redis_cron_save, args=(7200,))
        p2 = multiprocessing.Process(name="check_lr_active", target=check_lr_active, args=(3600,7200))
        p3 = multiprocessing.Process(name="runweb", target=runWeb, args=(sys.argv[1],))
        print "runWeb on port %s"%sys.argv[1]
        #  p1.start()
        for p in (p1,p2,p3):
            p.start()
