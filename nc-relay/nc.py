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
import time
import random
from lib.pyRedis import *
from lib.MysqlDB import db
from lib.lrNode import lrNode
from lib.ncDef import *
from lib.ncInit import initDb
from lib.meetings import getMeetinglr, addCallee
import tornado.web
import tornado.ioloop
import tornado.escape
import tornado.gen
#  import daemon
import multiprocessing 
import json


class changeEpHandler(tornado.web.RequestHandler):
    """ 用户-LR 表 API 接口 """
    def post(self, epid=None):
        reqbody = json.loads(self.request.body)
        act = reqbody["account"]
        ep = reqbody["userid"]
        ep_user = "%s_%s"%(ep, act)
        level = reqbody["node_level"]
        vsp_id = reqbody["vsp_id"]
        sqli = """insert into `adjacency` (`account`, `ep_id`, `level_id`, `vsp_id`) values ("%s", "%s", "%s", "%s")"""%(act, ep_user, level, vsp_id)
        rows = db.execOnly(sqli)
        if rows == 1: 
            redis_client.set("user:%s"% ep_user, level)
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
        reqbody = json.loads(self.request.body)
        #  reqbody = eval(self.request.body)
        act = reqbody["account"]
        level = reqbody["node_level"]
        vsp = reqbody["vsp_id"]
        sqlu = """update `adjacency` set `account`="%s", `level_id`="%s" , `vsp_id`="%s" where `ep_id`='%s'""" % (act, level, vsp, epid )
        rows = db.execOnly(sqlu)
        if rows: 
            redis_client.set("user:%s"%epid, level)
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
        #  reqbody = json.loads(self.request.body)
        reqbody = eval(self.request.body)
        lr_id = reqbody.get("id")
        lr_name = reqbody.get("name")
        plevel_id = reqbody.get("p_node_level", '0')
        ip = reqbody.get("ip")
        port = reqbody.get("port")
        cluster = reqbody.get("op_name", "aliyun")
        cloud = reqbody.get("net_type")
        price = reqbody.get("price", 0)
        lr_type = reqbody.get("lr_type")
        level_id = reqbody.get("level_id")
        #  lrc_id = reqbody.get("lrc_ids", '[]')
        sysload = reqbody.get("sysload", 0)
        last_subtime = int(time.time())
        redis_client.hmset("lr:%s:%s"%(level_id, lr_id), {"sysload": sysload, "ip": ip, "port": port, "lr_type": lr_type, "cluster": cluster, "last_subtime": last_subtime, "active": '1' })
        sql_data = (lr_id, lr_name, plevel_id, ip, port, cluster, cloud, price, lr_type, sysload, level_id, last_subtime)
        lr_node = lrNode(lr_id)
        res = lr_node.addLrnode(sql_data, level_id, plevel_id)
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
        cluster = reqbody.get("op_name")
        cloud = reqbody.get("net_type")
        price = reqbody.get("price")
        lr_type = reqbody.get("lr_type")
        level_id = reqbody.get("level_id")
        sysload = reqbody.get("sysload", 0)
        last_subtime = int(time.time())
        sql_data = (lr_name, plevel_id, ip, port, cluster, cloud, price, lr_type, sysload, level_id, last_subtime, lrid)
        r_res = redis_client.keys("lr:*:%s"%lrid)
        if r_res: 
            old_level = r_res[0].split(":")[1]
            redis_client.delete(r_res.pop())
        else:
            old_level = None
        redis_client.hmset("lr:%s:%s"%(level_id, lrid), {"sysload": sysload, "ip": ip, "port": port, "lr_type": lr_type, "cluster": cluster, "last_subtime": last_subtime, "active": '1'})
        lr_node = lrNode(lrid)
        #  print "*"*20, sql_data, level_id, plevel_id, old_level, lrid
        res = lr_node.modLrnode(sql_data, level_id, plevel_id, old_level, lrid)
        self.write(res)

    def delete(self, lrid):
        lr_node = lrNode(lrid)
        res = lr_node.delLrnode()
        lr = redis_client.keys("lr:*:%s"%lrid)
        if lr: redis_client.delete(lr[0])
        self.write(res)


class upSysload(tornado.web.RequestHandler):
    def post(self):
        reqbody = json.loads(self.request.body)
        lr_id = reqbody.get("id")
        lr_sysload = reqbody.get("sysload", 0)
        lr_active = reqbody.get("active", '1')
        cur_time = int(time.time())
        #  print lr_id,lr_sysload,lr_active,cur_time
        lr = redis_client.keys("lr:*:%s"%lr_id)
        if not lr:
            self.write({"code": 400, "msg": "Lr not found"})
            return
        redis_client.hmset(lr[0], {"sysload": lr_sysload, "last_subtime": cur_time, "active": lr_active} )
        lr_port = redis_client.hget(lr[0], "port")
        self.write({"code": 200, "status": "success", "port": lr_port})
    
    def get(self):
        try:
            lr_id = self.get_argument("lrid")
        except Exception,e :
            self.write({"code": 400, "msg": e.log_message})
            return
        lr = redis_client.keys("lr:*:%s"%lr_id)
        if lr:
            lr_port = redis_client.hget(lr[0], "port")
            self.write({"code": 200, "port": lr_port})
        else:
            self.write({"code": 404, "msg": "Lr not found"})


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
            'debug': True,
            #  'debug': False,
            'template_path': os.path.join(os.path.dirname(__file__), 'templates'),
            'static_path': os.path.join(os.path.dirname(__file__), 'static')
            }
    applicaton = tornado.web.Application([
        (r"/addforce", addForce),
        (r"/forcetable/(.*)", getForceTable),
        (r"/api/epid/(.*)", changeEpHandler),
        (r"/api/lrid/(.*)", changeLrHandler),
        (r"/api/upsysload", upSysload),
        (r"/api/getmtlr", getMeetinglr),
        (r"/api/addcallee", addCallee),
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
        lr_list = redis_client.keys("lr:*")
        cur_time = int(time.time())
        for lr in lr_list:
            last_subtime = redis_client.hget(lr, "last_subtime")
            #  if not last_subtime: last_subtime = time.time()
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
        redis_init(redis_client)
    else:
        initLog("nc")
        #  p1 = multiprocessing.Process(name="redis_cron_save", target=redis_cron_save, args=(7200,))
        #  p2 = multiprocessing.Process(name="check_lr_active", target=check_lr_active, args=(3600,7200))
        p3 = multiprocessing.Process(name="runweb", target=runWeb, args=(sys.argv[1],))
        print "runWeb on port %s"%sys.argv[1]
        p3.start()
        #  for p in (p1,p2,p3):
            #  p.start()
