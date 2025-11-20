#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/11/9 下午7:21
# @Author  : Heshouyi
# @File    : file_path.py
# @Software: PyCharm
# @description:

import os

'''项目目录'''
# 项目根目录，指向graph_knowledge/backend
project_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

'''一级目录'''
app_path = os.path.abspath(os.path.join(project_path, 'app'))     # app根目录

'''二级目录'''
core_path = os.path.abspath(os.path.join(app_path, 'core'))     # core目录
log_path = os.path.abspath(os.path.join(project_path, 'logs'))      # 日志目录
static_path = os.path.abspath(os.path.join(project_path, 'static'))     # 静态资源目录


if __name__ == '__main__':
    print(project_path)
