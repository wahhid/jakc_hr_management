from zklib import *
import sys

zk = zklib.ZKLib("172.16.120.121",4370)
ret = zk.connect()
print "Connection : ", ret