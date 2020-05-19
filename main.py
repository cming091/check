import sys
import os
import importlib
from utils import loadConfig
import models


def start(name):
    config = loadConfig()
    func = models.__dict__[name]
    func(config)

def main():
    if len(sys.argv) != 2:
        print('usage python main.py argv')
        os._exit(0)
    start(sys.argv[1])


if __name__=="__main__":
    main()