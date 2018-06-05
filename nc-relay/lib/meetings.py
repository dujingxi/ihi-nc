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
        star = nc_config.DEFAULT_STAR_LR
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
    dlr_root_level = None; lr_type_users = []
    for level_id in adjacency_list:
        level_type = redis_client.hget("level:%s"%level_id, "level_type")
        #  parents_list = redis_client.lrange("ancestors:%s"%level_id, 0, -1)
        if level_type == "dlr":
            dlr_parents_list, _ = split_level(level_id)
            dlr_root_level = dlr_parents_list[-1]
            all_dlr_level_parents[level_id] = dlr_parents_list
        else:
            lr_type_users += all_person_level[level_id]
    if not dlr_root_level:
        caller_level = redis_client.get("user:%s"%callerid)
        caller_lr_parents_list = redis_client.lrange("ancestors:%s"%caller_level, 0, -1)
        result = loop_choose(caller_lr_parents_list, logger)
        # 国际会议允许不在同一层下的用户开会，主叫必须是国际台所在层
        if result:
            epids = []
            for epid in all_person_level.values():
                epids += epid
            data = set_data(callerid, result)
            for x in data:
                x["epids"] = epids
            if len(data) > 1:
                #  star = nc_config.DEFAULT_STAR_LR
                star = nc_config.DEFAULT_LR
                star["star"] = True
                data.append(star)
            logger.warning("Personlist does not have dlr type, returning the caller's adjacency [%s/%s]"%(callerid, caller_level))
            return data
        else:
            return nc_config.DEFAULT_LR

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
        if lr_type_users:
            star = set_star(callerid, logger)
            star["epids"] = lr_type_users
            response_data.append(star)
        return response_data
    star = set_star(callerid, logger)
    use_caller_lr_list = []; epids = []
    for target in diff_target:
        use_caller_lr_list += group_dict[target]
    for adjacency in use_caller_lr_list:
        epids += all_person_level[adjacency]
    epids += lr_type_users
    star["epids"] = epids
    response_data.append(star)
    return response_data


# 获取指定用户所在层的类型（lr/dlr）
def get_user_info(user):
    user_level = redis_client.get("user:%s"%user)
    if user_level:
        user_level_cluster_value = redis_client.hget("level:%s"%user_level, "level_cluster")
        if len(user_level_cluster_value) == 1: user_level_cluster = "lrc"
        else: user_level_cluster = "lrg"
        dlr_parents, lr_parents = split_level(user_level)
        if dlr_parents: dlr_root = dlr_parents[-1]
        else: dlr_root = ""
        res = {"status": True, "user_level": user_level, "user_level_cluster": user_level_cluster, "dlr_root": dlr_root, "dlr_parents": dlr_parents}
    else:
        res = {"status": False}
    return res

# 根据属于grid属性的层ＩＤ和cluster属性，挑选出一个可用lr
def level_cluster_lr(level_id, cluster):
    lr_list = redis_client.keys("lr:%s:*"%level_id)
    lr = ''; sysload = 10000  # uncertain
    for lr_obj in lr_list:
        lr_cluster, lr_active, lr_sysload = redis_client.hmget(lr_obj, "cluster", "active", "sysload")
        if lr_cluster == cluster:
            if lr_active == '1':
                if int(lr_sysload) <= sysload: 
                    lr = lr_obj.split(":")[2]
                    sysload = int(lr_sysload)
            else: continue
    if lr:
        return lr   # lr => lr92385aebbf2d97cf320180504100221
    else:
        return None

class meeting():
    def __init__(self, caller, curmeeting, logger):
        self.caller = caller
        self.curmeeting = curmeeting
        self.logger = logger
        self.star = False
        self.is_lrg = False
        self.existing_lr = list()
        self.existing_level = dict()
        self.added_level = dict()
        self.added_data = list()
        self._set_attr()

    def _set_attr(self):
        for lr in self.curmeeting:
            lrid = lr["lrid"]
            lr_level_list = redis_client.keys("lr:*:%s"%lrid)
            if lr_level_list:
                lr_level = lr_level_list[0].split(":")[1]
                if lr["star"]:
                    self.star = lr
                else:
                    if lr_level not in self.existing_level: self.existing_level[lr_level] = [lrid]
                    else: self.existing_level[lr_level].append(lrid)
                    self.existing_lr.append({lrid: lr})
        caller_level = redis_client.get("user:%s"%self.caller)
        caller_level_type, caller_level_cluster = redis_client.hmget("level:%s"%caller_level, {"level_type", "level_cluster"})
        if caller_level_type == "lr" and (len(caller_level_cluster.split(":")) > 1):
            if caller_level in self.existing_level:
                self.is_lrg = True
                self.logger.info("Meeting type: LRG.")

    # 查看新加的用户所在层是否已存在
    def _fill_added(self, level, user, lrid=""):
        if level in self.added_level:
            added_level_lr = self.added_level[level]
            for lr in self.added_data:
                if lr["lrid"] in added_level_lr:
                    lr["epids"].append(user)
            return True
        elif lrid:
            self.added_level[level] = [lrid]
            lrip, lrport, lrtype = redis_client.hmget("lr:%s:%s"%(level, lrid), "ip", "port", "lr_type")
            self.added_data.append({"lrid": lrid, "ip":lrip, "port":lrport, "lr_type":lrtype, "epids": [user], "star": False})
            return False

    # 当为grid时，返回让ep自测的lr集合，同一个cluster属性使用会议中已存在的lr
    def _elect_need_cluster(self, level_clusters_list, user_level, user):
        level_clusters = set(level_clusters_list)
        exist_clusters = set()
        if self.existing_level.has_key(user_level):
            for lr in self.existing_level[user_level]:
                lr_cluster = redis_client.hget("lr:%s:%s"%(user_level, lr), "cluster")
                exist_clusters.add(lr_cluster)
            need_clusters = list(level_clusters - exist_clusters)
            self.added_level[user_level] = self.existing_level[user_level]
            for need_cluster in need_clusters:
                lr = level_cluster_lr(user_level, need_cluster)
                self.added_level[user_level].append(lr)
            for lr_obj in self.added_level[user_level]:
                lrip, lrport, lrtype = redis_client.hmget("lr:%s:%s"%(user_level,lr_obj), "ip", "port", "lr_type")
                self.added_data.append({"lrid": lr_obj, "ip":lrip, "port":lrport, "lr_type":lrtype, "epids": [user], "star": False})
            return 1
        else:
            res = loop_choose([user_level], self.logger)
            if res:
                data = set_data(self.caller, res)
                for i in data:
                    i["epids"] = [user]
                    self.added_data.append(i)
                return 2
            else:
                return 0

    # 当会议没有star时，添加
    def _add_star(self, epid=''):
        f = 0
        for lr in self.added_data:
            if lr["star"] == True:
                if epid != '': lr["epids"].append(epid)
                f = 1
        if f == 0:
            res = set_star(self.caller, self.logger)
            if epid != '': res["epids"].append(epid)
            star_level = redis_client.hget("lr:*:%s"%res["lrid"], "level_id")
            self.added_level[star_level] = [res["lrid"]]
            self.added_data.append(res)
            
    # 加人时执行的方法
    def addcallee(self, user):
        user_level = redis_client.get("user:%s"%user)
        if user_level:
            user_level_cluster_value = redis_client.hget("level:%s"%user_level, "level_cluster")
            user_level_cluster_value = user_level_cluster_value.split(":")
            if len(user_level_cluster_value) == 1: user_level_cluster = "lrc"
            else: user_level_cluster = "lrg"
            dlr_parents, lr_parents = split_level(user_level)
            if dlr_parents: dlr_root = dlr_parents[-1]
            else: dlr_root = ""
        else:
            self.logger.warning("Not found the level for EP user [%s]"%user)
            return False
        # 要添加的用户所在层是否已经存在，若存在，只将用户id加到epids键中
        res = self._fill_added(user_level, user)
        if res: return self.added_data
        # ＬＲＧ会议，国际台
        if self.is_lrg:
            if not dlr_root and user_level_cluster == "lrg":
                self._elect_need_cluster(user_level_cluster_value, user_level, user)
                self.logger.info("LRG meeting, return to normal.")
                return self.added_data
            else:
                star_level = redis_client.hget("lr:*:%s"%self.star["lrid"], "level_id")
                star_lrid = self.star["lrid"]
                self._fill_added(star_level, user, star_lrid)
                #  res = self._fill_added(star_level, user, star_lrid)
                #  if not res:
                    #  self.added_level[star_level] = [self.star["lrid"]]
                    #  self.star["epids"] = [user]
                    #  self.added_data.append(self.star)
                self.logger.info("LRG meeting, added user[%s] exception, use star LR."%user)
                return self.added_data

        if not dlr_root:
            if self.star:
                star_level = redis_client.hget("lr:*:%s"%self.star["lrid"], "level_id")
                star_lrid = self.star["lrid"]
                self._add_star(user)
                #  self._fill_added(star_level, user, star_lrid)
            else:
                self._add_star(user)
            self.logger.info("Normal lr user[%s], use star LR."%user)
        else:
            if user_level_cluster == "lrg":
                if self.star:
                    num = self._elect_need_cluster(user_level_cluster_value, user_level, user)
                    if num == 0:
                        self._add_star(user)
                else:
                    num = self._elect_need_cluster(user_level_cluster_value, user_level, user)
                    if num == 0: self._add_star(user)
                    else: self._add_star()
                self.logger.info("Normal dlrg user[%s]."%user)
            else:
                n = None
                for dlr_level in  dlr_parents:
                    if dlr_level in self.existing_level:
                        n = dlr_level; break
                if n:
                    lrid = self.existing_level[n][0]
                    lr = self.existing_lr[lrid]
                    lr["epids"] = [user]
                    self.added_data.append(lr)
                else:
                    res = loop_choose([dlr_root], self.logger)
                    if not res:
                        self.logger.error("User %s on level %s has not valid dlr.")
                        if self.star:
                            star_level = redis_client.hget("lr:*:%s"%self.star["lrid"], "level_id")
                            self.added_level[star_level] = [self.star["lrid"]]
                            self.star["epids"] = [user]
                            self.added_data.append(self.star)
                        else:
                            self._add_star(user)
                    else:
                        lr_id = res["data"].split(":")[2]
                        self._fill_added(dlr_root, user, lr_id)
                        if not self.star:
                            self._add_star()
                self.logger.info("Normal dlrc user[%s]."%user)

    # 返回添加时生成的数据
    def get_data(self):
        return self.added_data


#  nc_config.DEFAULT_LR["epids"] = ['u1', 'u2', 'u3']
#  print nc_config.DEFAULT_LR
class getMeetinglr(tornado.web.RequestHandler):
    """ 获取会议LR """
    def post(self):
        logger = logging.getLogger("nc")
        req = self.request
        reqbody = json.loads(self.request.body)
        #  reqbody = eval(self.request.body)
        caller = reqbody["callerId"]
        logger.info(' -- %s -- "%s %s %s" - "%s" -- MSM request data: %s --'%(req.remote_ip, req.method, req.version, req.uri, req.headers["User-Agent"], reqbody))
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
                        #  level_type = redis_client.hget("level:%s"%level_id, "level_type")
                        #  if level_type == "lr":
                            #  star = nc_config.DEFAULT_STAR_LR
                        #  else:
                            #  star = set_star(caller, logger)
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
        req = self.request
        reqbody = json.loads(self.request.body)
        #  reqbody = eval(self.request.body)
        logger.info(' -- %s -- "%s %s %s" - "%s" -- MSM request data: %s --'%(req.remote_ip, req.method, req.version, req.uri, req.headers["User-Agent"], reqbody))
        caller = reqbody["callerId"]
        addcallee = reqbody["addCallee"]
        curmeeting = reqbody["curMeeting"]
        star = False; existing_lr = dict()
        for lr in curmeeting:
            if lr["star"]: star = lr
            lrid = lr["lrid"]
            lr_list = redis_client.keys("lr:*:%s"%lrid)
            if lr_list:
                lr_level = lr_list[0].split(":")[1]
                existing_lr["lr:%s:%s"%(lr_level, lrid)] = lr
        add_num = len(addcallee)
        if add_num < 1:
            logging.warning("Missing parameters, the calleeList was empty.")
            self.write({"code":400, "mark":"undecided", "data": data})
        else:
            my_meet = meeting(caller, curmeeting, logger)
            for user in addcallee:
                my_meet.addcallee(user)

            response_data = my_meet.get_data()
            epids_set = set()
            for i in response_data:
                epids = frozenset(i["epids"])
                epids_set.add(epids)
            if len(epids_set) == len(response_data):
                response = {"code": 200, "mark": "fixed", "data": response_data}
            else:
                response = {"code": 200, "mark": "undecided", "data": response_data}
            logger.info("Response: %s"%response)
            self.write(response)














