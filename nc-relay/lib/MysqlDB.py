#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import MySQLdb as mysql
import nc_config
reload(sys)
sys.setdefaultencoding("utf-8")

class DB(object):
    ''' 数据库连接类，包括连接、执行sql语句、批量执行等函数块 '''
    TIMEOUT = 5

    def __init__(self, dbargs):
        # self.logger = logging.getLogger("nc")
        if not set(("host", "user", "db", "passwd")) <= set(dbargs):
            raise TypeError("Required arguments miss.")
        self.host = dbargs['host']
        if dbargs.has_key("port"):
            self.port = dbargs['port']
        else: self.port = 3306
        self.user = dbargs['user']
        self.db = dbargs['db']
        self.passwd = dbargs['passwd']
        self.conn = None
        self.connect()

    def connect(self):
        try:
            self.conn = mysql.connect(host=self.host, port=self.port, user=self.user, passwd=self.passwd, db=self.db, \
                                      connect_timeout=self.TIMEOUT, charset='utf8')
        except Exception, e:
            print e
            raise
        # else:
        #     self.logger.info("Connect to %s successed."%self.host)

    def isMany(self, data):
        if data and isinstance(data, list):
            return True
        else: return False

    def __exec(self, cur, sqli, data=None):
        if self.isMany(data):
            return cur, cur.executemany(sqli, data)
        else:
            return cur, cur.execute(sqli, data)

    def execOnly(self, sqli, data=None):
        try:
            self.conn.ping()
        except:  # MySQLdb.OperationalError
            self.connect()
        cur = self.conn.cursor()
        rows = None
        try:
            cursor, rows = self.__exec(cur, sqli, data)
            self.conn.commit()
        finally:
            cur.close()
        return rows

    def execFetch(self, sqli, data=None):
        try:
            self.conn.ping()
        except:  # MySQLdb.OperationalError
            self.connect()
        cur = self.conn.cursor()
        try:
            cursor, _ = self.__exec(cur, sqli, data)
            res = cursor.fetchall()
            self.conn.commit()
            return res
        finally:
            cur.close()

    def __del__(self):
        if self.conn:
            self.conn.close()

# 创建数据库连接实例，以下代码全都会使用此对象
db = DB(nc_config.MYSQL_ARGUMENTS)
