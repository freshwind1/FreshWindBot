import sys
import os
import nonebot
from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11Adapter
from nonebot.adapters.onebot.v11 import Bot


path = os.path.dirname(os.path.realpath(sys.argv[0]))


nonebot.init(apscheduler_autostart=True)


driver = nonebot.get_driver()
driver.register_adapter(ONEBOT_V11Adapter)
nonebot.load_from_toml("pyproject.toml")

if __name__ == "__main__":

    nonebot.run()
