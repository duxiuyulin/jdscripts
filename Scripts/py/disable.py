# -*- coding:utf-8 -*-
"""
cron: 20 10 */7 * *
new Env('禁用重复任务');
"""

import json
import logging
import os
import sys
import time
import traceback

import requests

logger = logging.getLogger(name=None)  # 创建一个日志对象
logging.Formatter("%(message)s")  # 日志内容格式化
logger.setLevel(logging.INFO)  # 设置日志等级
logger.addHandler(logging.StreamHandler())  # 添加控制台日志
# logger.addHandler(logging.FileHandler(filename="text.log", mode="w"))  # 添加文件日志


ip = "localhost"
sub_str = os.getenv("RES_SUB", "Aaron-lv_sync")
sub_list = sub_str.split("&")
res_only = os.getenv("RES_ONLY", True)
headers = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36",
}


def load_send() -> None:
    logger.info("加载推送功能中...")
    global send
    send = None
    cur_path = os.path.abspath(os.path.dirname(__file__))
    sys.path.append(cur_path)
    if os.path.exists(cur_path + "/notify.py"):
        try:
            from notify import send
        except Exception:
            send = None
            logger.info(f"❌加载通知服务失败!!!\n{traceback.format_exc()}")


def get_tasklist() -> list:
    tasklist = []
    t = round(time.time() * 1000)
    url = f"http://{ip}:5700/api/crons?searchValue=&t={t}"
    response = requests.get(url=url, headers=headers)
    datas = json.loads(response.content.decode("utf-8"))
    if datas.get("code") == 200:
        tasklist = datas.get("data")
    return tasklist


def filter_res_sub(tasklist: list) -> tuple:
    filter_list = []
    res_list = []
    for task in tasklist:
        for sub in sub_list:
            if task.get("command").find(sub) == -1:
                flag = False
            else:
                flag = True
                break
        if flag:
            res_list.append(task)
        else:
            filter_list.append(task)
    return filter_list, res_list


def get_duplicate_list(tasklist: list) -> tuple:
    names = {}
    ids = []
    tem_tasks = []
    cmds = []
    tem_cmds = []
    for task in tasklist:
        if task.get("name") in names.keys():
            ids.append(task["_id"])
            cmds.append(task.get("command"))
        else:
            tem_tasks.append(task)
            names[task["name"]] = 1
    return ids, cmds, tem_cmds, tem_tasks


def reserve_task_only(ids: list, cmds: list, tem_tasks: list, res_list: list) -> tuple:
    if len(ids) == 0:
        return ids
    res_cmds = []
    for task1 in tem_tasks:
        for task2 in res_list:
            if task1["name"] == task2["name"]:
                ids.append(task1["_id"])
                cmds.append(task1.get("command"))
            elif task1.get("command") not in res_cmds:
                res_cmds.append(task1.get("command"))
    return ids, cmds, res_cmds


def disable_duplicate_tasks(ids: list) -> None:
    t = round(time.time() * 1000)
    url = f"http://{ip}:5700/api/crons/disable?t={t}"
    data = json.dumps(ids)
    headers["Content-Type"] = "application/json;charset=UTF-8"
    response = requests.put(url=url, headers=headers, data=data)
    datas = json.loads(response.content.decode("utf-8"))
    if datas.get("code") != 200:
        logger.info(f"❌出错!!!错误信息为：{datas}")
    else:
        logger.info("🎉成功禁用重复任务~")


def get_token() -> str or None:
    try:
        with open("/ql/config/auth.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        logger.info(f"❌无法获取 token!!!\n{traceback.format_exc()}")
        send("💔禁用重复任务失败", "无法获取 token!!!")
        exit(1)
    return data.get("token")


if __name__ == "__main__":
    logger.info("===> 禁用重复任务开始 <===")
    load_send()
    token = get_token()
    headers["Authorization"] = f"Bearer {token}"

    # 获取过滤后的任务列表
    sub_str = "\n".join(sub_list)
    logger.info(f"\n=== 你选择过滤的任务前缀为 ===\n{sub_str}")
    tasklist = get_tasklist()
    if len(tasklist) == 0:
        logger.info("❌无法获取 tasklist!!!")
        exit(1)
    filter_list, res_list = filter_res_sub(tasklist)

    ids, cmds, tem_cmds, tem_tasks = get_duplicate_list(filter_list)
    # 是否在重复任务中只保留设置的前缀
    if res_only:
        ids, cmds, res_cmds = reserve_task_only(ids, cmds, tem_tasks, res_list)
    else:
        res_cmds = tem_cmds
        logger.info("你选择保留除了设置的前缀以外的其他任务")

    sum = f"所有任务数量为：{len(tasklist)}"
    filter = f"过滤的任务数量为：{len(res_list)}"
    disable = f"禁用的任务数量为：{len(ids)}"
    logging.info("\n=== 禁用数量统计 ===\n" + sum + "\n" + filter + "\n" + disable)

    dis_str = "\n".join(cmds)
    res_str = "\n".join(res_cmds)
    dis_result = f"\n=== 本次禁用了以下任务 ===\n{dis_str}"
    res_result = f"\n=== 本次保留了以下任务 ===\n{res_str}"
    logger.info(dis_result)
    logger.info(res_result)

    if len(ids) == 0:
        logger.info("😁没有重复任务~")
    else:
        disable_duplicate_tasks(ids)
    if send:
        send("💖禁用重复任务成功", f"\n{sum}\n{filter}\n{disable}")
