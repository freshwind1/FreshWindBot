import re
import os
import httpx
import json
from typing import Optional, Union, Callable, Tuple
from nonebot.adapters.onebot.v11 import Message, MessageSegment
import asyncio
header = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36',
    'referer': 'https://www.bilibili.com',
    'Cookie': 'SESSDATA=09206495%2C1693398789%2Cd817e%2A32'
}


class AnalysisResponse:
    aid: str = None
    bvid: str = None
    cid: str = None
    title: str = None
    msg: Union[Message, str] = None
    vurl: str = None
    aurl: str = None


def InitPath(group_id: str, info: AnalysisResponse):
    if not group_id:
        group_id = "PrivateChat"
    path = f"{os.getcwd()}/BiliDownloads/{group_id}"
    temp_path = f"{path}/temp"
    video_path = f"{temp_path}/v{info.bvid}.m4s"
    audio_path = f"{temp_path}/a{info.bvid}.m4s"
    mp4_path = f"{path}/{info.title}.mp4"
    if not os.path.exists(path):
        os.makedirs(path)
    if not os.path.exists(temp_path):
        os.makedirs(temp_path)
    if os.path.exists(mp4_path):
        os.remove(mp4_path)
    return (video_path, audio_path, mp4_path)


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


def extract_url(msg: str):
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

        if "view?" in url:
            resp = await get_video_info(url, page=page)
    except Exception as e:
        msg = "bili_analysis error{}".format(e.__str__())

    return resp


async def get_video_info(url: str, **kwargs):
    resp = AnalysisResponse()
    try:
        async with httpx.AsyncClient(headers=header, follow_redirects=True) as client:
            data = (await client.get(url)).json().get("data")
            if not data:
                resp.msg = "解析到视频被删了/稿件不可见或审核中/权限不足"
                return resp

        vurl = f"https://www.bilibili.com/video/av{data['aid']}"
        resp.title = title = f"\n标题：{data['title']}\n"
        cover = MessageSegment.image(data["pic"])

        resp.aid = data["aid"]
        resp.cid = data["cid"]
        resp.bvid = data['bvid']

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

        resp.msg = Message([cover, vurl, title, tname, stat, desc])
    except Exception as e:
        resp.msg = e.__str__()
    return resp


async def get_playurl(info: AnalysisResponse):

    url = "https://api.bilibili.com/x/player/playurl"
    param = {
        "avid": info.aid,
        "cid": info.cid,
        "qn": 120,
        "fnver": 0,
        "fnval": 16,
        "fourk": 1
    }

    # https://api.bilibili.com/x/player/playurl?bvid=BV15z4y1Z734&cid=239973476&qn=120&fnval=16&fnver=0&fourk=1
    # https://api.bilibili.com/x/player/playurl?aid=584666059&cid=239973476&qn=120&fnver=0&fnval=16&fourk=1
    try:
        async with httpx.AsyncClient(headers=header, follow_redirects=True) as client:
            data = (await client.get(url, params=param)).json().get("data")
            if not data:
                return info
        info.vurl = data["dash"]["video"][0]["baseUrl"] or data["dash"]["video"][0]["backupUrl"][0]
        info.aurl = data["dash"]["audio"][0]["baseUrl"] or data["dash"]["audio"][0]["backupUrl"][0]
    except Exception as e:
        print('get_playurl error {}'.format(e.__str__()))

    return info


async def dwonload_file(url: str, filename: str, callback: Callable):
    async with httpx.AsyncClient(headers=header) as client:
        async with client.stream("GET", url) as resp:
            currentLen = 0
            totalLen = int(resp.headers["content-length"])
            with open(filename, "wb") as file:
                async for chunk in resp.aiter_bytes():
                    currentLen += len(chunk)
                    file.write(chunk)
                    callback(f"{(currentLen/totalLen)*100}%", end="")


async def download_video(group_id, info: AnalysisResponse):

    vpath, apath, mpath = InitPath(group_id, info)

    info = await get_playurl(info)
    # print(info.vurl, info.aurl)
    await asyncio.gather(
        dwonload_file(info.vurl, vpath, print),
        dwonload_file(info.aurl, apath, print)
    )
