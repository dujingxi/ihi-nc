
# basic config
tables = ["adjacency", "lr_node", "net_qos"]
operators = {
    'outer': ["aliyun", "aws"],
    'inner': ["ct", "cu", "cernet"]
}
area_net = "local_network"
private_net = "private_cloud"


# SOTP API URL
SOTP_USR_LR_URL = "http://172.16.1.200:8085/SOTP/index.php/interface/user/users_and_node/node_type/lr"
SOTP_LR_INFO_URL = "http://172.16.1.200:8085/SOTP/index.php/interface/lr/get_all"

# configuration for log
LOG_PATH = "./log"
LOG_LEVEL = 20  # { 'DEBUG':10, 'INFO':20, 'WARNING':30, 'ERROR':40, 'CRITICAL':50 }
LOG_KEEP = 20

# default lr
DEFAULT_LR = {"lrid": "", "ip": "", "port":""}

# configuration for mysql DB
MYSQL_ARGUMENTS = {
    "host": "172.16.1.215",
    "port": 3306,
    "db": "nc",
    "user": "root",
    "passwd": "db"
}


'''
type: (dlr, std)
operator: (cernet, aliyun, ct)
cloud: (public, private, campus)
'''
