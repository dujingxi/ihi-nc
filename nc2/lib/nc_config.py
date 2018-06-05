
# basic config
tables = ["lr_grid", "lr_cluster", "adjacency", "lr_node", "net_qos", "force_route", "level_node"]
operators = {
    'outer': ["aliyun", "aws"],
    'inner': ["ct", "cu", "cernet"]
}
#  area_net = "local_network"
#  private_net = "private_cloud"


# SOTP API URL
SOTP_USR_LR_URL = "http://172.16.1.200:808/SOTP/index.php/interface/user/users_and_node/node_type/lr"
SOTP_LR_INFO_URL = "http://172.16.1.200:808/SOTP/index.php/interface/lr/get_all"
SOTP_LR_GRID_URL = "http://172.16.1.200:808/SOTP/index.php/interface/lr/getAllClusterGrid"
SOTP_LR_CLUSTER_URL = "http://172.16.1.200:808/SOTP/index.php/interface/lr/getAllCluster"

# configuration for log
LOG_PATH = "log/nc.log"
LOG_LEVEL = 20  # { 'DEBUG':10, 'INFO':20, 'WARNING':30, 'ERROR':40, 'CRITICAL':50 }
LOG_KEEP = 20

# default lr
DEFAULT_LR = [{
    "lrid": "",
    "ip": "",
    "port":"",
    "lr_type": "lr"
}]

# configuration for mysql DB
MYSQL_ARGUMENTS = {
    "host": "172.16.1.215",
    "port": 3306,
    "db": "nctest",
    "user": "root",
    "passwd": "db"
}

# configuration for redis
REDIS_ARGUMENTS = {
    "host": "127.0.0.1",
    "port": 6379,
    "db": 0,
    "password": None
}

'''
type: (dlr, std)
operator: (cernet, aliyun, ct)
cloud: (public, private, campus)
'''
