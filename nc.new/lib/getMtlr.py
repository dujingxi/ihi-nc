#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import copy
import random
import logging
import tornado.web
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
        reqbody = json.loads(self.request.body)
        caller = reqbody["callerId"]
        logger.info("%s %s %s %s -MSM request data: %s-"%(req.remote_ip, req.method, req.uri, req.headers["User-Agent"], reqbody))
        caller_account = caller.split("_")[2]
        force_res = detectForce(caller_account)
        if force_res["statu"]:
            lr_node = lrNode(force_res["lrid"])
            lr_res = lr_node.getLrnode(plr=False)
            logger.info("The account [%s] has a specified LR [%s]"%(caller_account, force_res["lrid"]))
            self.write({"code": 200, "status": "success", "data": [lr_res]})
            return
        ''' 判断多点会议 '''
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
                    res = {"code": 200, "status": "success", "data":nc_config.DEFAULT_LR}
                    logger.info("Public meetting. Not found caller's adjacency LR, return default lr")
                    self.write(res); return
                else:
                    lr_cluster = lrCluster(level_id)
                    lr_id = lr_cluster.randomLr()
                    lr_node = lrNode(lr_id)
                    lr_res = lr_node.getLrnode(plr=False)
                    logger.info("Public meetting, type [%s], caller [%s], lr [%s]"%(public_mt_type, caller, lr_res))
                    self.write({"code": 200, "status": "success", "data": [lr_res]})
                    return
            else:
                level_list = getRootlevel()
                if not level_list:
                    res = {"code": 200, "status": "success", "data":nc_config.DEFAULT_LR}
                    logger.info("Public meetting. Not found root level, return default lr")
                    self.write(res); return
                lr_cluster = lrCluster(level_list[0])
                lr_id = lr_cluster.randomLr()
                lr_node = lrNode(lr_id)
                lr_res = lr_node.getLrnode(plr=False)
                logger.info("Public meetting, type [%s], caller [%s], SO lr [%s]"%(public_mt_type, caller, lr_res))
                self.write({"code": 200, "status": "success", "data": [lr_res]})
                return
        # 非公开会议
        personlist = reqbody["calleeList"]
        personlist.append(caller)
        logger.info("Standard meeting starting, members -> [%s]"%personlist)
        near_level_list = []
        for user in personlist:
            res_level = getAdjacency(user)
            if not res_level:
                logger.info("No matching LR target found, please check if the user_id [%s] exists."%user)
                break
            if res_level not in near_level_list:
                near_level_list.append(res_level)
        if len(near_level_list) < 1:
            res = {"code": 404, "msg": "User [%s] not found, use default."%user, "data": nc_config.DEFAULT_LR}
            self.write(res)
        elif len(near_level_list) == 1:
            res_lrc = lrCluster(near_level_list[0])
            meeting_lr = res_lrc.randomLr()
            lr_node = lrNode(meeting_lr)
            lr_res = lr_node.getLrnode(plr=False)
            logger.info("The meeting has the same LR=>[%s]"%lr_res)
            self.write({"code": 200, "status": "success", "data": [lr_res]})
        else:
            #  参会方的LR列表中是否有某个LR是共有的，实际中这种情况不存在
            #  compare_res = iterCompare(near_lr_list)
            #  if len(compare_res) >= 1:
                #  lr_node = lrNode(compare_res[0])
                #  res = lr_node.getLrnode(plr=False)
                #  logger.info("Take a OBJ that everyone shares.")
                #  self.write(res)
                #  return
            all_valid_level = []
            for level_id in near_level_list:
                netqos = netQos(level_id)
                valid_level_list = netqos.getValidlevel()
                valid_level_list.append(level_id)
                all_valid_level.append(valid_level_list)
                logger.info("near_lr: %s, find the level_list: %s"%(level_id, valid_level_list))
            result = set(all_valid_level)
            for i in range(len(all_valid_level)):
                result = result & set(all_valid_level[1])
            level_list = list(result)

            if len(level_list) == 0:
                data = nc_config.DEFAULT_LR
                logger.warning("Failure to calculate the result, return default lr")
                res = {"code": 404, "status": "Find the level_list error, use default lr", "data":data}
                self.write(res)

            sqls_2 = """select `path` from `net_qos` where `level_src`='%s' and `level_dst`='%s'"""
            result_list = []
            for x in level_list:
                flag = False
                sum = 0
                for y in near_level_list:
                    if y != x: 
                        value = db.execFatch(sqls_2%(y, x))[0][0]
                        if value == 0: flag = True
                    else: value = 0
                    sum = sum + value
                if flag: continue
                result_list.append({"level": x, "path": sum})
            result_list.sort(key=lambda x:(x["path"]))
            lr_cluster = lrCluster(result_list[0])
            lr_id = lr_cluster.randomLr()
            lr_node = lrNode(lr_id)
            res = lr_node.getLrnode(plr=False)
            logger.info("Selected list %s, final choice %s"%(result_list, res))
            self.write({"code": 200, "status": "success", "data": [res]})


