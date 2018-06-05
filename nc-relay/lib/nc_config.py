# -*- coding: utf-8 -*-

# basic config
tables = ["adjacency", "lr_node",  "force_route", "level_node"]
#  operators = {
    #  'outer': ["aliyun", "aws"],
    #  'inner': ["ct", "cu", "cernet"]
#  }
#  area_net = "local_network"
#  private_net = "private_cloud"

# REDIS 中 LR （sysload/last_subtime/active）等数据写入MYSQL的间隔时间
REDIS_SAVEIN_MYSQL_INTERVAL = 3600

# 检查　last_subtime 的间隔时间
LAST_SUBTIME_INTERVAL = 3600

#　last_subtime 相差多少时间以上，视为 LR 无效
LAST_SUBTIME_VALID_TIME = 7200 

# 多进程监听的web服务端口，用于nginx反向代理
PORT_LIST = [10000, 10001, 10002, 10003]

# SOTP API URL
SOTP_USR_LR_URL = "http://172.16.1.200:808/SOTP_nc/index.php/interface/user/users_and_node/node_type/lr"
SOTP_LR_INFO_URL = "http://172.16.1.200:808/SOTP_nc/index.php/interface/lr/get_all"
#  SOTP_LR_GRID_URL = "http://172.16.1.200:808/SOTP/index.php/interface/lr/getAllClusterGrid"
#  SOTP_LR_CLUSTER_URL = "http://172.16.1.200:808/SOTP/index.php/interface/lr/getAllCluster"

# configuration for log
LOG_PATH = "log/nc.log"
LOG_LEVEL = 20  # { 'DEBUG':10, 'INFO':20, 'WARNING':30, 'ERROR':40, 'CRITICAL':50 }
LOG_KEEP = 20

# default lr
DEFAULT_LR = {
    "lrid": "lr_default_lr",
    "ip": "172.16.1.1",
    "port":9200,
    "lr_type": "lr",
    "epids": [],
    "star": False
}

#  default star lr for lr_type==lr and lr_cluster==lrg 国际台中继转发服务器
DEFAULT_STAR_LR = {
    "lrid": "lr_default_star_lr_ooooooooooooooooo",
    "ip": "172.16.1.99",
    "port":9000,
    "lr_type": "lr",
    "epids": [],
    "star": True
}

# configuration for mysql DB
MYSQL_ARGUMENTS = {
    "host": "172.16.1.215",
    "port": 3306,
    "db": "ncrelay",
    "user": "root",
    "passwd": "db"
}

# configuration for redis
REDIS_ARGUMENTS = {
    "host": "127.0.0.1",
    "port": 6380,
    "db": 0,
    "password": None
}

'''
type: (dlr, std)
operator: (cernet, aliyun, ct)
cloud: (public, private, campus)
'''
