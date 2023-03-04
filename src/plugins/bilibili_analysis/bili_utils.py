import re
import os
import httpx
import json
from typing import Optional, Union, Callable, Tuple
from nonebot.adapters.onebot.v11 import Message, MessageSegment, Bot
from ffmpy3 import FFmpeg
from tqdm import tqdm
import asyncio
header = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36',
    'referer': 'https://www.bilibili.com',
    'Cookie': 'SESSDATA=09206495%2C1693398789%2Cd817e%2A32'

}

# 'Cookie': 'SESSDATA=09206495%2C1693398789%2Cd817e%2A32'


class AnalysisResponse:
    aid: str = None
    bvid: str = None
    cid: str = None
    title: str = None
    msg: Union[Message, str] = None
    vurl: str = None
    aurl: str = None


def InitPath(group_id: str, info: AnalysisResponse):
    path = f"{os.getcwd()}/BiliDownloads/{group_id}"
    temp_path = f"{path}/temp"
    video_path = f"{temp_path}/v{info.bvid}.m4s"
    audio_path = f"{temp_path}/a{info.bvid}.m4s"
    mp4_path = f"{path}/{info.aid}_{info.cid}.mp4"
    if not os.path.exists(path):
        os.makedirs(path)
    if not os.path.exists(temp_path):
        os.makedirs(temp_path)
    if os.path.exists(mp4_path):
        os.remove(mp4_path)
    return (video_path, audio_path, mp4_path)


async def create_group_folder(bot: Bot, foldername: str, gid: int):
    root = await bot.get_group_root_files(group_id=gid)
    folders = root.get("folders")
    if folders:
        for fd in folders:
            if foldername == fd["folder_name"]:
                return fd["folder_id"]

    await bot.create_group_file_folder(group_id=gid, name=foldername, parent_i="/")
    id = await get_group_folder_id(bot, foldername, gid)

    return id


async def get_group_folder_id(bot: Bot, fdname: str, gid: int) -> str:
    root = await bot.get_group_root_files(group_id=gid)
    folders = root.get("folders")
    for fd in folders:
        if fd["folder_name"] == fdname:
            return fd["folder_id"]
    return id


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
        async with httpx.AsyncClient(headers=header, follow_redirects=True, verify=False) as client:
            data = (await client.get(url)).json().get("data")
            if not data:
                resp.msg = "解析到视频被删了/稿件不可见或审核中/权限不足"
                return resp

        vurl = f"https://www.bilibili.com/video/av{data['aid']}"
        title = f"\n标题：{data['title']}\n"
        resp.title = data['title']
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
        async with httpx.AsyncClient(headers=header, follow_redirects=True, verify=False) as client:
            data = (await client.get(url, params=param)).json().get("data")
            if not data:
                return info
        info.vurl = data["dash"]["video"][0]["baseUrl"] or data["dash"]["video"][0]["backupUrl"][0]
        info.aurl = data["dash"]["audio"][0]["baseUrl"] or data["dash"]["audio"][0]["backupUrl"][0]
    except Exception as e:
        print('get_playurl error {}'.format(e.__str__()))

    return info


async def dwonload_file(url: str, filename: str, callback: Callable):
    async with httpx.AsyncClient(headers=header, verify=False) as client:
        async with client.stream("GET", url) as resp:
            totalLen = int(resp.headers["content-length"])
            with open(filename, "wb") as file, tqdm(desc=filename, total=totalLen, unit="iB",
                                                    unit_scale=True, unit_divisor=1024) as pbar:
                async for chunk in resp.aiter_bytes(chunk_size=1024):
                    size = file.write(chunk)
                    pbar.update(size)
            pbar.close()


async def download_video(bot: Bot, gid: int, info: AnalysisResponse):

    vpath, apath, mpath = InitPath(str(gid), info)

    info = await get_playurl(info)
    if not info.vurl or not info.aurl:
        return "获取下载地址失败~"
    # print(info.vurl, info.aurl)
    await asyncio.gather(
        dwonload_file(info.vurl, vpath, print),
        dwonload_file(info.aurl, apath, print)
    )

    await fileToMp4(vpath, apath, mpath)

    id = await create_group_folder(bot, "BiliDonwloads", gid)

    await bot.upload_group_file(group_id=gid, file=str(mpath), name=f"{info.title}.mp4", folder=id)

    #return Message("")


async def fileToMp4(path1: str, path2: str, outpath: str):
    ff = FFmpeg(inputs={
        path1: None,
        path2: None
    }, outputs={outpath: "-c copy"})
    await ff.run_async()
    await asyncio.sleep(0.5)
