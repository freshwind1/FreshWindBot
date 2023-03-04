from nonebot import get_driver, on_regex
from nonebot.adapters import Event, Bot
from nonebot.adapters.onebot.v11 import GroupMessageEvent

from .config import Config
from .bili_utils import *
import re

# global_config = get_driver().config
# config = Config.parse_obj(global_config)

bili23_analysis = on_regex(
    r"(b23.tv)|(bili(22|23|33|2233).cn)|(.bilibili.com)|(^(av|cv)(\d+))|(^BV([a-zA-Z0-9]{10})+)|"
    r"(\[\[QQ小程序\]哔哩哔哩\])|(QQ小程序&amp;#93;哔哩哔哩)|(QQ小程序&#93;哔哩哔哩)",
    flags=re.I,
)


@bili23_analysis.handle()
async def main_analysis(bot: Bot, event: GroupMessageEvent):
    msg = str(event.get_message()).strip()
    msg = await handle_short_url(msg)

    gid = event.group_id
    # root = await bot.get_group_root_files(group_id=gid)

    resp = await bili_analysis(gid, msg)
    if resp.msg:
        await bot.send(event, resp.msg)

    msg = await download_video(bot, gid, resp)

    # await bot.send(event, msg)
