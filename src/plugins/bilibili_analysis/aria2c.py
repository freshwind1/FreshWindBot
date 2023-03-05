import httpx
import psutil
import os
import sys


class Aria2c:

    def __init__(self):
        pass

    def init_client(self):
        pids = psutil.pids()
        pro = []
        for pid in pids:
            p = psutil.Process(pid)
            name = p.name()
            if name == 'aria2.exe' or name == 'aria2c.exe':
                pro.extend([name, pid])
        # print( f"{os.path.dirname(os.path.realpath(sys.argv[0]))}/Aria2/AriaNg启动器.exe")
        if len(pro) < 4:
            os.system(
                f"{os.path.dirname(os.path.realpath(sys.argv[0]))}/Aria2/AriaNg启动器.exe")


aria2 = Aria2c()
aria2.init_client()
