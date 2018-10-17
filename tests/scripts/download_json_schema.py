#!/usr/bin/env python3
import json
import os
import sys
from urllib import request

BASE_URL = "https://api.github.com/repos/elastic/apm-server/contents/{path}?ref={branch}"


def download_folder(name, branch, base_folder):
    response = request.urlopen(BASE_URL.format(path=name, branch=branch))
    data = json.loads(response.read().decode("utf-8"))
    for item in data:
        if item["type"] == "dir":
            download_folder(item["path"], branch, base_folder)
        elif item["type"] == "file":
            path = base_folder + item["path"][9:]
            os.makedirs(os.path.dirname(path), exist_ok=True)
            request.urlretrieve(item["download_url"], base_folder + item["path"][9:])
            print("downloaded {} to {}".format(item["path"][9:], os.path.dirname(path)))


if __name__ == "__main__":
    path = os.path.abspath(sys.argv[2])
    download_folder("docs/spec", sys.argv[1], path)
