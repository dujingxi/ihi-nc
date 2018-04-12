#!/usr/bin/env python2.7
#-*- coding:utf-8

# Filename: route_map.py
# Description: Check the network condition between two LRs

# Author: fanyongjun <fanyongjun@streamocean.com>
# License: StreamOcean
# Last-Updated: 2018/02/02

import config
import gevent
import json
import logger
import math
import os
import ping
import psutil
import socket
import sys
import threading
import time
import urllib2

try:
    import psutil
except ImportError as e:
    print "You should 'pip install psutil' firstly"
    sys.exit()

qos_result = {}
sys_load_result = {}
logger.init_log("route_map")


def get_local_lr_id(lrid_file):
    """
      Get local LR id from local file
    """
    try:
        with open(lrid_file) as fd:
            local_lr_id = fd.read()
    except IOError:
        logger.logger.error("No such file %s" % lrid_file)
        local_lr_id = ''
    return local_lr_id.strip()


def get_lr_info(nc_node_list, local_lr_id):
    """
      Get other LR id and ip list from NC
    """
    res = {}
    full_url = os.path.join(nc_node_list,local_lr_id)
    try:
        result = urllib2.urlopen(full_url,timeout=2)
        res = json.loads(result.read())
    except urllib2.URLError as e:
        logger.logger.error("Wrong NC_Server:%s;Reason:%s" % (nc_node_list,e.reason))
    except urllib2.HTTPError as e:
        logger.logger.error("Wrong NC_Server:%s;Reason:%s" % (nc_node_list, e.reason))
    return res


def get_sys_load(local_lr_id):
    """
      Calc system current load
      use cpu_idle, mem_free, nic_send/recv usage rate
    """
    global sys_load_result
    sys_load_result['id'] = local_lr_id 
    cpu_idle = psutil.cpu_times_percent().idle
    nic_speed =  float(math.pow(psutil.net_if_stats()['eth0'].speed,3))
    nic_send_1 = psutil.net_io_counters(pernic=True)['eth0'].bytes_sent
    nic_recv_1 = psutil.net_io_counters(pernic=True)['eth0'].bytes_recv
    while True:
        reload(config)
        sys_load_interval = config.sys_load_interval
        nc_upload_sysload = config.nc_upload_sysload
        gevent.sleep(sys_load_interval)

        cpu_idle = round(psutil.cpu_times_percent().idle / 100,3)
        mem_free = round((100 - psutil.virtual_memory().percent) / 100,3)
        nic_send_2 = psutil.net_io_counters(pernic=True)['eth0'].bytes_sent
        nic_recv_2 = psutil.net_io_counters(pernic=True)['eth0'].bytes_recv
        nic_send_use = round(math.log10((nic_send_2 - nic_send_1) * 8 / 10 / nic_speed),3) * (-1)
        nic_recv_use = round(math.log10((nic_recv_2 - nic_recv_1) * 8 / 10 / nic_speed),3) * (-1)
        result = round(cpu_idle + mem_free + nic_send_use + nic_recv_use,3)
        nic_send_1 = nic_send_2
        nic_recv_1 = nic_recv_2
        sys_load_result['sysload'] = result
        logger.logger.error("qos_result:%s" % qos_result)
        post_result_nc(nc_upload_sysload,sys_load_result)
        # print sys_load_result


def check_lr_service(ip,port):
    """
      Check whether the service of LR is running
      The connection will end after 2seconds
    """
    s = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect((ip,int(port)))
        s.shutdown(2)
        return True
    except:
        return False


def check_ping(ip, port, dst_id, timeout, count, psize):
    """
      Check the network situation between LRs
      1. Check the service of LR is normal(ip and port), if not, do not do ping test
      2. Check connection between two LR,if packet drop rate is 100%, do not do ping check
      3. Do ping check: max/avg response time and packet drop rate
    """
    if not check_lr_service(ip,port):
        logger.logger.error("The service of %s:%s is not running" % (ip,port))
        tmp_dict = {}
        tmp_dict['dst_id'] = dst_id
        tmp_dict['percent_lost'] = 100
        tmp_dict['mrtt'] = 0.0
        tmp_dict['artt'] = 0.0
        qos_result['data'].append(tmp_dict)
    else:
        try:
            test_result = ping.quiet_ping(ip, timeout=1, count=4, psize=64)
        except Error as e:
            logger.logger.error("test quiet_ping error,ip:%s;Reason:%s" % (ip,e.reason))
        else:
            if test_result[0] == 100:
                tmp_dict = {}
                tmp_dict['dst_id'] = dst_id
                tmp_dict['percent_lost'] = test_result[0]
                tmp_dict['mrtt'] = 0.0
                tmp_dict['artt'] = 0.0
                qos_result['data'].append(tmp_dict)
            else:
                try:
                    result = ping.quiet_ping(ip, timeout=timeout, count=count,  psize=psize)
                except Error as e:
                    logger.logger.error("normal quiet_ping error,ip:%s;Reason:%s" % (ip,e.reason))
                else:
                    tmp_dict = {}
                    tmp_dict['dst_id'] = dst_id
                    tmp_dict['percent_lost'] = result[0]
                    tmp_dict['mrtt'] = round(result[1],2)
                    tmp_dict['artt'] = round(result[2],2)
                    qos_result['data'].append(tmp_dict)


def do_check_ping(local_lr_id):
    global qos_result
    while True:
        reload(config)
        nc_upload_qos = config.nc_upload_qos
        nc_get_lr_info = config.nc_get_lr_info
        ping_check_interval = config.ping_check_interval
        timeout = config.ping_args['timeout']
        count = config.ping_args['count']
        psize = config.ping_args['psize']
        tds = []
        lr_id_list = []
        qos_result['data'] = []

        lrc_lr_info = get_lr_info(nc_get_lr_info, local_lr_id)
        # print lr_info
        if not lrc_lr_info or not lrc_lr_info['node_list']:
            logger.logger.error("%s can't get LR_Cluster info from nc_server %s!" % (local_lr_id, nc_upload_qos))
        else:
            logger.logger.info("lr_info:%s" % lrc_lr_info)
            for node in lrc_lr_info['node_list']:
                lr_id_list.append(node['id']) 
            if local_lr_id in lr_id_list:
                # print "doing ping check"
                for node in lrc_lr_info['node_list']:
                    ip = node['ip']
                    port = int(node['port'])
                    dst_id = node['id']
                    t = threading.Thread(target=check_ping, args=(ip,port,dst_id,timeout,count,psize))
                    tds.append(t)
                for t in tds:
                    t.start()
                    t.join()
                logger.logger.error("qos_result:%s" % qos_result)
                post_result_nc(nc_upload_qos,qos_result)
        # print qos_result
        gevent.sleep(ping_check_interval)


def post_result_nc(nc_api,post_data):
    """
      1. Post sys_load to NC server and get lr_list for ping test
      2. Post ping check result to NC server
    """
    # print qos_result
    headers = {"Content-type":"application/json"}
    req = urllib2.Request(nc_api,headers=headers,data=json.dumps(post_data))
    try:
        res = urllib2.urlopen(req)
    except urllib2.URLError as e:
        logger.logger.error("Post result to NC_Server %s Failed!Reason:%s" % (nc_api,e.reason))
    except urllib2.HTTPError as e:
        logger.logger.error("Post result to NC_Server %s Failed!Reason:%s" % (nc_api,e.reason))


def startup():
    global qos_result
    lr_id_dir = config.lr_id_dir
    local_lr_id = get_local_lr_id(lr_id_dir)
    if not local_lr_id:
        sys.exit()
    qos_result['id'] = local_lr_id
 
    gevent_list = []

    g1 = gevent.spawn(do_check_ping,local_lr_id)
    g2 = gevent.spawn(get_sys_load,local_lr_id) 
    gevent_list.append(g1)
    gevent_list.append(g2)
    
    for g in gevent_list:
        g.join()
 

if __name__ == '__main__':
    # ip_list = [
    #            '61.133.11.40',
    #            'bj-vp.ml.streamocean.net',
    #            'bj-vb.ml.streamocean.net',
    #            'bj-m.ml.streamocean.net',
    #            'www.baidu.com',
    #            'gz-e.ml.streamocean.net',
    #            'dg-w.ml.streamocean.com',
    #            '106.14.5.150',
    #            '39.106.102.189',
    #            '101.200.201.175',
    #            '47.94.200.24',
    #           ]
    startup()
