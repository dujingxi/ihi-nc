#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import copy
import logging
import tornado.web
from pyRedis import redis_client
from ncDef import detectForce
import nc_config


# 将指定level_id的上层层级关系按照lr_type分成两个列表
def split_level(level_id):
    ancestors_list = redis_client.lrange("ancestors:%s"%level_id, 0, -1)
    dlr_ancestors_list = []
    lr_ancestors_list = []
    for level in ancestors_list:
        level_type = redis_client.hget("level:%s"%level, "level_type")
        if level_type == "dlr": 
            dlr_ancestors_list.append(level)
    dlr_len = len(dlr_ancestors_list)
    lr_ancestors_list = ancestors_list[dlr_len:]
    return [dlr_ancestors_list, lr_ancestors_list]
#  print split_level("40")


# 从lrc中竞选出一个状态最好的lr服务器，若当前cluster中所有lr的服务都不可用，则返回空
def best_lr(level_id, redis_lrc_list):
    lr = ''; sysload = 10000  # uncertain
    for lr_obj in redis_lrc_list:
        lr_active, lr_sysload = redis_client.hmget(lr_obj, "active", "sysload")
        if lr_active == '1':
            if int(lr_sysload) <= sysload: 
                lr = lr_obj
                sysload = int(lr_sysload)
        else: continue
    if lr:
        return lr   # lr => lr92385aebbf2d97cf320180504100221
    else:
        return None
#  print best_lr("492", ["lr:492:1c2d179d6ea676892f4e05d04dced9d9", "lr:492:ca55fea7bf556d8f7d4d1e021cb78ace", "lr:492:da2b89a94efd468cad5db5f771ed2595", "lr:492:e1f304cf13f99636091ff8c78d0dacc7"])


# 从指定level_id中选择最优的LR返回
def choose_result(level_id):
    level_cluster = redis_client.hget("level:%s"%level_id, "level_cluster")
    level_cluster_list = level_cluster.split(":")
    lr_list = redis_client.keys("lr:%s:*"%level_id)
    if len(level_cluster_list) == 1:
        lr = best_lr(level_id, lr_list)
        if lr: res = {"status": True, "type": "lrc", "data": lr}
        else: res = {"status": False, "type": "lrc", "data": None}
        return res
    else:
        lrc_dict = {}; lr_res = []
        for cluster_type in level_cluster_list:
            lrc_dict[cluster_type] = []
        for lr in lr_list:
            lr_cluster = redis_client.hget(lr, "cluster")
            lrc_dict[lr_cluster].append(lr)
        for k in lrc_dict.keys():
            lr = best_lr(level_id, lrc_dict[k])
            if not lr:
                res = {"status": False, "type": "lrg", "data": None}
                return res
            lr_res.append(lr)
        res = {"status": True, "type": "lrg", "data": lr_res}
        return res
#  print choose_result("492")


# 传入层级关系列表，根据LRG/LRC选出代表LR，若当前层无有效lr，往上层找，一直到最顶层
def loop_choose(parents_list, logger):
    result = ""
    while True:
        res = choose_result(parents_list[0])
        if res["status"]: 
            result = res; break
        else: 
            logger.warning("Level [%s] has no LR available."%parents_list[0])
            #  print "Level [%s] has no LR available."%parents_list[0]
        parents_list = parents_list[1:]
        if len(parents_list) == 0: break
    return result
#  print loop_choose(['517', '516', '321', '1'])


def set_data(caller, result):
    data = []
    if result["type"] == "lrg":
        for lr_obj in result["data"]:
            lrid = lr_obj.split(":")[2]; lrip, lrport, lrtype = redis_client.hmget(lr_obj, "ip", "port", "lr_type")
            data.append({"lrid": lrid, "ip":lrip, "port":lrport, "lr_type":lrtype, "epids": [], "star": False})
        #  response = {"code":200, "mark":"undecided", "data": data}  ##########
    else: 
        lrid = result["data"].split(":")[2]; lrip, lrport, lrtype = redis_client.hmget(result["data"], "ip", "port", "lr_type")
        data.append({"lrid": lrid, "ip":lrip, "port":lrport, "lr_type":lrtype, "epids": [], "star": False})
        #  response = {"code": 200, "mark": "fixed", "data": data}
    return data


def set_star(caller, logger):
    caller_level = redis_client.get("user:%s"%caller)
    _, lr_parents = split_level(caller_level)
    star_res = loop_choose(lr_parents, logger)
    if star_res and star_res["type"] == "lrc":
        star_id = star_res["data"].split(":")[2]; starip, starport, startype = redis_client.hmget(star_res["data"], "ip", "port", "lr_type")
        res = {"lrid": star_id, "ip": starip, "port":starport, "lr_type":startype, "epids":[], "star": True}
    else:
        star = nc_config.DEFAULT_LR
        star["star"] = True
        res = star
    return res



# 传入所有内网的adjacency_level，以及其对应的dlr_parents，根据dlr最高层找到相同局域网中的对象
def group_uniq(all_dlr_level_parents):
    temp_dict = {}; result_dict = {}; all_dlr_level_parents_copy = copy.copy(all_dlr_level_parents)
    while len(all_dlr_level_parents) > 0:
        adjacency_parents = all_dlr_level_parents.popitem()
        dlr_root = adjacency_parents[1][-1]
        if dlr_root not in temp_dict:
            temp_dict[dlr_root] = [adjacency_parents[0]]
        else:
            temp_dict[dlr_root].append(adjacency_parents[0])
    for same_net in temp_dict.values():
        count = len(same_net)
        for level in all_dlr_level_parents_copy[same_net[0]]:
            n = 0
            for i in range(count):
                if level in all_dlr_level_parents_copy[same_net[i]]: n += 1
            if n == count:
                result_dict[level] = same_net
                break
    return result_dict
#  dd = {"421": ["421", "321", "516", "229"], "517":["517", "516", "229"], "33": ["33", "516", "229"], "324": ["324", "774", "771"], "772": ["772", "771"], "99":["99", "87", "220"]}
#  print group_uniq(dd)            # {'99': ['99'], '771': ['772', '324'], '516': ['33', '421', '517']}


# 选择指定level列表最终的会议level
def elect_func(callerid, adjacency_list, all_person_level, logger):
    all_dlr_level_parents = {}
    dlr_root_level = None
    for level_id in adjacency_list:
        level_type = redis_client.hget("level:%s"%level_id, "level_type")
        #  parents_list = redis_client.lrange("ancestors:%s"%level_id, 0, -1)
        if level_type == "dlr":
            dlr_parents_list, _ = split_level(level_id)
            dlr_root_level = dlr_parents_list[-1]
            all_dlr_level_parents[level_id] = dlr_parents_list
    if not dlr_root_level:
        caller_level = redis_client.get("user:%s"%callerid)
        caller_lr_parents_list = redis_client.lrange("ancestors:%s"%caller_level)
        result = loop_choose(caller_lr_parents_list, logger)
        logger.warning("Personlist does not have dlr type, returning the caller's adjacency [%s/%s]"%(callerid, caller_level))

    group_dict = group_uniq(all_dlr_level_parents)
    group_dict_copy = copy.copy(group_dict)
    response_data = []
    for target,adjacency_list_x in group_dict.items():
        dlr_parents_list, _ = split_level(target)
        res = loop_choose(dlr_parents_list, logger)
        if not res: 
            logger.warning("LANs where level %s don't find a valid DLR, will use caller's LR."%target)
            group_dict_copy.pop(target)
        else:
            data = set_data(callerid, res)      # {"lrid": lrid, "ip":lrip, "port":lrport, "lr_type":lrtype, "epids": [], "star": False}
            epids = []
            for adjacency in adjacency_list_x:
                epids += all_person_level[adjacency]
            for x in data:
                x["epids"] = epids
            response_data += data
    diff_target = set(group_dict) - set(group_dict_copy)
    if len(response_data) == 1 and len(diff_target) == 0:
        return response_data
    star = set_star(callerid, logger)
    use_caller_lr_list = []; epids = []
    for target in diff_target:
        use_caller_lr_list += group_dict[target]
    for adjacency in use_caller_lr_list:
        epids += all_person_level[adjacency]
    star["epids"] = epids
    response_data.append(star)
    return response_data


#  nc_config.DEFAULT_LR["epids"] = ['u1', 'u2', 'u3']
#  print nc_config.DEFAULT_LR
class getMeetinglr(tornado.web.RequestHandler):
    """ 获取会议LR """
    def post(self):
        logger = logging.getLogger("nc")
        req = self.request
        #  print "^"*20, type(self.request.body), self.request.body
        #  reqbody = json.loads(self.request.body)
        reqbody = eval(self.request.body)
        caller = reqbody["callerId"]
        logger.info("%s %s %s %s -MSM request data: %s-"%(req.remote_ip, req.method, req.uri, req.headers["User-Agent"], reqbody))
        user_list = redis_client.keys("user:%s"%caller)
        if not user_list:
            logger.error("The caller was not found, use default LR.")
            self.write({"code": 404, "mark": "fixed", "data": [nc_config.DEFAULT_LR]})
        # 判断该账号是否设置了强制使用的LR
        caller_account = caller.split("_")[2]
        force_res = detectForce(caller_account)
        if force_res["statu"]:
            lrid = force_res["lrid"]
            lr_obj = redis_client.keys("lr:*:%s"%lrid)
            ip, port, lr_type = redis_client.hmget(lr_obj[0], "ip", "port", "lr_type")
            lr_res = {"lrid": lrid, "ip":ip, "port": port, "lr_type": lr_type, "epids":[], "star": False}
            logger.info("The account [%s] has a specified LR [%s]"%(caller_account, force_res["lrid"]))
            self.write({"code": 200,  "mark": "fixed", "data": [lr_res]})  # mark: fixed/undecided
            #  return
        # 含calleeList，通讯录会议
        if reqbody.has_key("calleeList"):
            personlist = reqbody["calleeList"]
            personlist.append(caller)
            logger.info("Contacts style meeting starting, members -> [%s]"%personlist)
            near_level_list = []; all_person_level = {}
            for ep in personlist:
                adjacency_level = redis_client.get("user:%s"%ep)
                if not adjacency_level:
                    logger.warning("No matching level target found, please check the user_id [%s] exists."%ep)
                    continue
                if adjacency_level not in near_level_list: 
                    near_level_list.append(adjacency_level)
                    all_person_level[adjacency_level] = [ep]
                else:
                    all_person_level[adjacency_level].append(ep)
            if len(near_level_list) < 1:
                nc_config.DEFAULT_LR["epids"] = personlist
                logger.error("Contacts style meeting, did not find an adjacency, use default LR.")
                self.write({"code": 404, "mark": "fixed", "data": [nc_config.DEFAULT_LR]})
                #  return 404
            elif len(near_level_list) == 1:
                level_id = near_level_list[0]
                parents_list = redis_client.lrange("ancestors:%s"%level_id, 0, -1)
                result = loop_choose(parents_list, logger)
                #  result: "" || {"status": True, "type": "lrg"|"lrc", "data": lr_res|None}  lr_res: [ lr:39:lr78920180518155843, lr:39:lr78945afe87b30 ]
                if result:
                    data = set_data(caller, result)
                    if len(data) == 1:
                        response = {"code": 200, "mark": "fixed", "data": data}
                    else:
                        star = set_star(caller, logger)
                        for x in data:
                            x["epids"] = personlist
                        data.append(star)
                        response = {"code": 200, "mark": "undecided", "data": data}
                    logger.info("Contacts style meeting, personlist has the same adjacency. Response: %s"%data)
                    self.write(response)
                    #  return 200
                else:
                    nc_config.DEFAULT_LR["epids"] = personlist
                    nc_config.DEFAULT_LR["star"] = False
                    logger.error("Contacts style meeting, personlist has the same adjacency, but didn't choose a valid LR. Use default LR.")
                    self.write({"code": 404, "mark": "fixed", "data": [nc_config.DEFAULT_LR]})
                    #  return 404
            else:
                response_data = elect_func(caller, near_level_list, all_person_level, logger)
                epids_set = set()
                for i in response_data:
                    epids = frozenset(i["epids"])
                    epids_set.add(epids)
                if len(epids_set) == len(response_data):
                    response = {"code": 200, "mark": "fixed", "data": response_data}
                else:
                    response = {"code": 200, "mark": "undecided", "data": response_data}
                logger.info("Contacts style meeting, effective return: %s"%response)
                self.write(response)
                #  return 200
        else:
            caller_level = redis_client.get("user:%s"%caller)
            caller_dlr_parents_list, caller_lr_parents_list = split_level(caller_level)
            if caller_dlr_parents_list:
                caller_lr_parents_list.insert(0, caller_dlr_parents_list[-1])
            #  print "$"*10, caller_meeting_level
            res = loop_choose(caller_lr_parents_list, logger)
            if not res:
                nc_config.DEFAULT_LR["epids"] = personlist
                nc_config.DEFAULT_LR["star"] = False
                logger.error("Caller meeting, didn't choose a valid LR. Use default LR.")
                self.write({"code": 404, "mark": "fixed", "data": [nc_config.DEFAULT_LR]})
            else:
                data = set_data(caller, res)
                for d in data:
                    d["epids"] = [caller]
                if len(data) > 1: mark = "undecided"
                else: mark = "fixed"
                logger.info("Caller meeting, response: %s"%data)
                self.write({"code": 200, "mark": mark, "data": data})
 

class addCallee(tornado.web.RequestHandler):
    def post(self):
        logger = logging.getLogger("nc")






