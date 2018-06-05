#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import copy
import random
import logging
import tornado.web
from pyRedis import redis_client
from lib.lrNode import lrNode
from lib.ncDef import *
from lib.netQos import netQos
from lib.lrCluster import lrGrid, vspObj
import nc_config


class getMeetinglr(tornado.web.RequestHandler):
    """ 获取会议LR """
    def post(self):
        logger = logging.getLogger("nc")
        req = self.request
        reqbody = eval(self.request.body)
        caller = reqbody["callerId"]
        logger.info("%s %s %s %s -MSM request data: %s-"%(req.remote_ip, req.method, req.uri, req.headers["User-Agent"], reqbody))
        caller_account = caller.split("_")[2]
        force_res = detectForce(caller_account)
        if force_res["statu"]:
            lr_node = lrNode(force_res["lrid"])
            lr_res = lr_node.getLrnode()
            logger.info("The account [%s] has a specified LR [%s]"%(caller_account, force_res["lrid"]))
            self.write({"code": 200, "status": "success", "data": [lr_res]})
            return
        ''' 判断多点会议 '''
        if reqbody.has_key("mt_type"):
            if reqbody["mt_type"] == "multi":
                logger.info("Multipoint meeting start..")
                caller_vsp = getAdjacency(caller, item="vsp_id")
                caller_vsp_obj = vspObj(caller_vsp)
                caller_lrg = caller_vsp_obj.getGrid()
                logger.info("Found user vsp id: %s, lr grid id: %s"%(caller_vsp, caller_lrg))
                if not caller_lrg:
                    res = {"code": 200, "status": "success", "data":nc_config.DEFAULT_LR}
                    logger.warn("Multipoint meeting. Not found caller's adjacency LR, or this VSP has no LRG, return default lr")
                    self.write(res)
                    return 
                else:
                    lr_list = []
                    caller_lrg_obj = lrGrid(caller_lrg)
                    caller_lrc_list = caller_lrg_obj.getCluster()
                    logger.info("Found lr cluster ids: %s:"%caller_lrc_list)
                    for member in caller_lrc_list:
                        lr_cluster = lrCluster(member)
                        lr_list.append(lr_cluster.randomLr(name="cluster"))
                response_list = []
                for lr_id in lr_list:
                    lr_node = lrNode(lr_id)
                    response_list.append(lr_node.getLrnode())
                logger.info("Found lr_list in lrc_list: %s"%response_list)
                self.write({"code": 200, "status": "success", "data": response_list})
                return 
        ''' 判断公开课 '''
        if reqbody.has_key("scope"):
            public_mt_type = reqbody["scope"]
            if public_mt_type == "inner":
                level_id =  getAdjacency(caller)
                if not level_id:
                    res = {"code": 404, "status": "warning", "data":nc_config.DEFAULT_LR}
                    logger.info("Stranger meeting. Not found caller's adjacency LR, return default lr")
                    self.write(res); return
                lr_level = redis_client.keys("lrid:%s:*"%level_id)[0]
                lr_type = redis_client.hget(lr_level, "lr_type")
                if lr_type == "lr":
                    level_res = lr_level.split(":")[1]
                else:
                    level_res = getDlrRoot(lr_level.split(":")[1])
                lr_cluster = lrCluster(level_res)
                lr_id = lr_cluster.randomLr()
                lr_node = lrNode(lr_id)
                lr_res = lr_node.getLrnode()
                logger.info("Stranger meeting, type [%s], caller [%s], dlr [%s]"%(public_mt_type, caller, lr_res))
                self.write({"code": 200, "status": "success", "data": [lr_res]})
                return
            else:
                level_list = getRootlevel()
                if not level_list:
                    res = {"code": 404, "status": "warning", "data":nc_config.DEFAULT_LR}
                    logger.info("Stranger meeting. Not found root level, return default lr")
                    self.write(res); return
                lr_cluster = lrCluster(level_list[0])
                lr_id = lr_cluster.randomLr()
                lr_node = lrNode(lr_id)
                lr_res = lr_node.getLrnode()
                logger.info("Stranger meeting, type [%s], caller [%s], SO lr [%s]"%(public_mt_type, caller, lr_res))
                self.write({"code": 200, "status": "success", "data": [lr_res]})
                return
            #  else:
                #  level_id =  getAdjacency(caller)
                #  level_list = redis_client.keys("qos:%s:*"%level_id)
                #  best_level = level_list[0]
                #  for level in level_list:
                    #  layer_count = redis_client.hget(level, "layer_distance")
                    #  if layer_count > redis_client.hget(best_level, "layer_distance"): best_level = level
                #  lr_cluster = lrCluster(best_level.split(":")[2])
                #  lr_id = lr_cluster.randomLr()
                #  lr_node = lrNode(lr_id)
                #  lr_res = lr_node.getLrnode()
                #  logger.info("Stranger meeting, type [%s], caller [%s], lr [%s]"%(public_mt_type, caller, lr_res))
                #  self.write({"code": 200, "status": "success", "data": [lr_res]})
                #  return

        # 非公开会议
        personlist = reqbody["calleeList"]
        personlist.append(caller)
        logger.info("Standard meeting starting, members -> [%s]"%personlist)
        near_level_set = set()
        for user in personlist:
            res_level = getAdjacency(user)
            if not res_level:
                logger.info("No matching level target found, please check if the user_id [%s] exists."%user)
                break
            if res_level not in near_level_set:
                near_level_set.add(res_level)
        if len(near_level_set) < 1:
            res = {"code": 404, "msg": "Find the near_level_set failure for the personlist [%s], use default LR." % personlist, "data": nc_config.DEFAULT_LR}
            self.write(res)
        elif len(near_level_set) == 1:
            res_lrc = lrCluster(near_level_set.pop())
            meeting_lr = res_lrc.randomLr()
            if meeting_lr:
                lr_node = lrNode(meeting_lr)
                lr_res = lr_node.getLrnode()
                logger.info("The meeting has the same LR=>[%s]"%lr_res)
                self.write({"code": 200, "status": "success", "data": [lr_res]})
            else:
                logger.info("The members of the meeting are at the same level, but the LR fails at this level.")
                self.write({"code": 404, "status": "success", "data": nc_config.DEFAULT_LR})
        else:
            #  for level_id in near_level_set:
                #  netqos = netQos(level_id)
                #  valid_level_list = netqos.getValidlevel()
                #  valid_level_list.append(level_id)
                #  all_valid_level.append(valid_level_list)
                #  logger.info("near_lr: %s, find the level_list: %s"%(level_id, valid_level_list))
            #  result = set(all_valid_level[0])
            #  for i in range(len(all_valid_level)):
                #  result = result & set(all_valid_level[i])
            #  level_list = list(result)

            all_valid_level = []
            near_level_list = list(near_level_set)
            for i in range(len(near_level_list)):
                netqos = netQos(near_level_list[i])
                valid_level_list = netqos.getValidlevel()
                #  valid_level_list.append(near_level_set[i])
                if i == 0: all_valid_level = valid_level_list
                all_valid_level = [ val for val in all_valid_level if val in valid_level_list ]

            if len(all_valid_level) == 0:
                data = nc_config.DEFAULT_LR
                logger.warning("Failure to calculate the result, return default lr")
                res = {"code": 404, "status": "Find the level_list error, use default lr", "data":data}
                self.write(res)
                return

            #  sqls_2 = """select `path` from `net_qos` where `level_src`='%s' and `level_dst`='%s'"""
            result_list = []
            for x in all_valid_level:
                flag = False
                sum = 0
                for y in near_level_list:
                    if y != x: 
                        #  value = db.execFetch(sqls_2%(y, x))[0][0]
                        value = float(redis_client.hget("qos:%s:%s" % (y,x), "path"))
                        if value == 0: flag = True
                    else: value = 0
                    sum = sum + value
                if flag: continue
                result_list.append({"level": x, "path": sum})
            if not result_list:
                res = {"code": 404, "msg": "Check the result_list failure for the personlist [%s], use default LR." % personlist, "data": nc_config.DEFAULT_LR}
                self.write(res)
                return
            result_list.sort(key=lambda x:(x["path"]))
            lr_cluster = lrCluster(result_list[0]["level"])
            lr_id = lr_cluster.randomLr()
            lr_node = lrNode(lr_id)
            res = lr_node.getLrnode()
            logger.info("Selected list %s, final choice %s"%(result_list, res))
            self.write({"code": 200, "status": "success", "data": [res]})


