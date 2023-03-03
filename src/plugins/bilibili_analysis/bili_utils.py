import re
import httpx
import json
from typing import Optional
from nonebot.adapters.onebot.v11 import Message, MessageSegment

header = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36',
    'referer': 'https://www.bilibili.com',
    'Cookie': 'SESSDATA=09206495%2C1693398789%2Cd817e%2A32'
}


class AnalysisResponse:
    pass


def handle_num(num: int) -> str:
    if num > 10000:
        num = f"{num / 10000:.2f}万"
    return num


async def handle_short_url(msg: str) -> str:
    """处理短链接"""
    b23 = re.compile(r"b23.tv/(\w+)|(bili(22|23|33|2233).cn)/(\w+)",
                     re.I).search(msg.replace("\\", ""))
    if b23:
        try:
            async with httpx.AsyncClient(headers=header, timeout=10, follow_redirects=True) as client:
                resp = await client.get(f"https://{b23[0]}")
                return str(resp.url)
        except:
            pass
    return msg


def extract_url(msg: str) -> str:
    """提取api地址"""
    url = ""
    # 视频分p
    page = re.compile(r"([?&]|&amp;)p=\d+").search(msg)
    aid = re.compile(r"av\d+", re.I).search(msg)
    bvid = re.compile(r"BV([A-Za-z0-9]{10})+", re.I).search(msg)
    epid = re.compile(r"ep\d+", re.I).search(msg)
    ssid = re.compile(r"ss\d+", re.I).search(msg)
    if aid:
        url = f"https://api.bilibili.com/x/web-interface/view?aid={aid[0][2:]}"
    elif bvid:
        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid[0]}"

    return url, page


async def bili_analysis(group_id: Optional[int], msg: str):
    try:
        url, page = extract_url(msg)

        msg, vurl = "", ""
        if "view?" in url:
            msg, vurl = await get_video_info(url, page=page)
    except Exception as e:
        msg = "bili_analysis error{}".format(e.__str__())

    return msg


async def get_video_info(url: str, **kwargs):
    try:
        async with httpx.AsyncClient(headers=header, follow_redirects=True) as client:
            data = (await client.get(url)).json().get("data")
            if not data:
                return "解析到视频被删了/稿件不可见或审核中/权限不足", url

        vurl = f"https://www.bilibili.com/video/av{data['aid']}"
        title = f"\n标题：{data['title']}\n"
        cover = MessageSegment.image(data["pic"])

        if page := kwargs.get("page"):
            page = page[0].replace("&amp;", "&")
            p = int(page[3:])
            if p <= len(data["pages"]):
                vurl += f"?p={p}"
                part = data["pages"][p - 1]["part"]
                if part != data["title"]:
                    title += f"小标题：{part}\n"

        tname = f"类型：{data['tname']} | UP：{data['owner']['name']}\n"
        stat = f"播放：{handle_num(data['stat']['view'])} | 弹幕：{handle_num(data['stat']['danmaku'])} | 收藏：{handle_num(data['stat']['favorite'])}\n"
        stat += f"点赞：{handle_num(data['stat']['like'])} | 硬币：{handle_num(data['stat']['coin'])} | 评论：{handle_num(data['stat']['reply'])}\n"
        desc = f"简介：{data['desc']}"
        msg = Message([cover, vurl, title, tname, stat, desc])
    except Exception as e:
        msg = e.__str__()
    return msg, vurl
