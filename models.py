import time
import sys
from bson import json_util
from math import ceil
import copy
import pymongo
from tenacity import retry, stop_after_attempt
import requests
import json
import logging
from utils import *
from py2neo import Graph, Node, Relationship, NodeMatcher


logging.basicConfig(
    level = logging.ERROR,
    #level = logging.INFO,
    format = '%(asctime)s - %(name)s -'
    ' %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

class MongoBase(object):
    @retry(stop=stop_after_attempt(2))
    def connect(self):
        self.client = pymongo.MongoClient(self.cf['database']['ip&port'],
                                          username=self.cf['database']['username'],
                                          password=self.cf['database']['password'],
                                          authSource=self.cf['database']['authSource'],
                                          authMechanism=self.cf['database']['authMechanism'])
        self.mclient = self.client[self.cf['database']['dbname']][self._cf['collection']]


class Mongo(MongoBase):

    def count(self):
        return self.mclient.find(self._cf['pattern']).count()

    @retry(stop=stop_after_attempt(2))
    def pagingFind(self, limit, skip):
        #skip = 22800
        self.log(self.name, skip, limit)
        if self._cf['show']:
            return list(self.mclient.find(self._cf['pattern'],
                                     self._cf['show'],
                                    ).skip(skip).limit(limit))
        else:
            return list(self.mclient.find(self._cf['pattern'],
                                          ).skip(skip).limit(limit))

    @retry(stop=stop_after_attempt(2))
    def Aggregate(self):
        result = self.mclient.aggregate(self._cf['pattern'])
        if result:
            result = list(result)
            self.log(self.name, 'count', len(result))
            return result
        return []

    @retry(stop=stop_after_attempt(2))
    def findOne(self, unique):
        return self.mclient.find_one({self._cf['findKey']: unique})

class Sap(object):
    def isValid(self, data):
        if data:
            return True
        return False

    @retry(stop=stop_after_attempt(2))
    def getData(self, url, data):
        result = requests.post(url, json=data)
        if not self.isValid(result):
            raise ValueError()
        return result.json()

    @retry(stop=stop_after_attempt(2))
    def count(self):
        url = self._cf['url'].format(self.cf['general']['domain'], self.cf['general']['mandt'])
        data = eval(str(self._cf['getPage'])%self.cf['general']['mandt'])
        return int(self.getData(url, data)['RESULT'][0]['TOTAL'])

    @retry(stop=stop_after_attempt(2))
    def pagingFind(self, limit, skip):
        self.log(self.name, skip, limit)
        url = self._cf['url'].format(self.cf['general']['domain'], self.cf['general']['mandt'])
        data = eval(str(self._cf['getMsg']) % (self.cf['general']['mandt'], skip, limit))
        return self.getData(url, data)['RESULT']

class SSap(Sap):
    @retry(stop=stop_after_attempt(2))
    def count(self):
        url = self._cf['url'].format(self.cf['general']['domain'],self.cf['general']['mandt'])
        data = self._cf['getMsg']
        return int(self.getData(url, data)['TOTALPAGE'])

    @retry(stop=stop_after_attempt(2))
    def pagingFind(self,limit, skip):
        pageNo = int(skip/self.pageSize)+1
        self.log(self.name, pageNo, limit*pageNo)
        url = self._cf['url'].format(self.cf['general']['domain'],self.cf['general']['mandt'])
        data = self._cf['getMsg']
        data['PAGENO'] = pageNo
        data['PAGESIZE'] = limit
        return self.getData(url, data)['ITEM_DATA']


class BaseFlow():
    def log(self, name, key, value, level=2):
        if level == 1:
            pass
        elif level == 2:
            print('[{}######{}######{}]\n'.format(name, key, value))
        elif level == 3:
            print('[{}######{}######{}]\n'.format(name, key, value))

    def record(self, mData, gDate):
        if mData['id']:
            logger.error('-' * 130)
            logger.error('[mData={}]'.format(mData))
            logger.error('[gDate={}]'.format(gDate))
            logger.error('-' * 130)

    def delay(self, timeout=0):
        if timeout:
            time.sleep(timeout)
        else:
            time.sleep(self._cf['sleep'])


class GeneralFlow(BaseFlow):
    def __init__(self, cf, name):
        self.name = name
        self.cf = cf
        self._cf = self.cf[name]
        self.graph = neoClient(cf)
        self.nodeMatcher = NodeMatcher(self.graph)

    @property
    def pageSize(self):
        return self._cf.get('pagesize') if self._cf.get('pagesize',None) else 200

    def paging(self):
        total = self.count()
        self.log(self.name,'count',total)
        return range(ceil(total/self.pageSize))

    def getId(self, data, ids, sign):
        if ',' == sign:
            idlist=[]
            for id in ids:
                idlist.append(data.get(id,''))
            return ('_'.join(idlist)).strip('_')
        elif '||' ==sign:
            for id in ids:
                value = data.get(id,'')
                if value:
                    self.log(self.name,id,value)
                    return value
        elif '--' == sign:
            for id in ids[1:]:
                idlist = []
                idlist.append(data.get(id,0.0))
            return data.get(ids[0],0.0)-sum(idlist)

    def getValues(self, data):
        dataDict = {}
        for field in  self._cf['fields']:
            if field[0]=='id':
                dataDict[field[0]] = self.getId(data, field[1].split(self._cf.get('sign','$$')), self._cf.get('sign','$$')) if self._cf.get('sign','$$') in field[1] else getValueFromPath(self.name, field[0],field[1], data, field[2])
            else:
                dataDict[field[0]] = getValueFromPath(self.name, field[0],field[1], data, field[2])
        for field  in self._cf['orderfields']:
            if len(dataDict[field])>1:
                dataDict[field] = sorted(dataDict[field],reverse=True)

        logger.warning('[source dataDict={}]'.format(dataDict))
        return dataDict

    def fetch(self):
        if isinstance(self,MongoGeneralFlow):
            self.connect()
        messages = []
        for i in self.paging():
            self.delay()
            messages = self.pagingFind(self.pageSize, i*self.pageSize)
            for message in messages:
                yield self.getValues(message)


    @retry(stop=stop_after_attempt(2))
    def nodeMatch(self, mData):
        data = self.nodeMatcher.match(self._cf['nodeName'],id=mData['id']).first()
        data = dict(data) if data else {}
        try:
            data.pop('__v')
        except:
            pass
        return data

    def matcher(self, mData):
        gDate = self.nodeMatch(mData)
        gDate = self.order(gDate)
        logger.warning('[source gDate={}]'.format(gDate))
        if not gDate or (json.dumps(mData, ensure_ascii=False) != json.dumps(gDate, ensure_ascii=False)):
            self.record(mData,gDate)
        #else:
        #    logger.error('[success ={}]'.format(gDate['id']))

    def check(self):
        pass

    def order(self,gDate):
        dataDict = {}
        for field in self._cf['fields']:
            dataDict[field[0]] = gDate.get(field[0]) if gDate.get(field[0],None) is not None else format_kongoutput(field[2],gDate.get(field[0]))
        for field  in self._cf['orderfields']:
            if len(dataDict[field])>1:
                dataDict[field] = sorted(dataDict[field],reverse=True)
        return dataDict

    def work(self):
        for message in self.fetch():
            self.log(self.name, 'message', message, level=self._cf['level'])
            self.matcher(message)
        self.log(self.name, 'end','ok')


class MSSpecialFlow(GeneralFlow):
    def isValid(self, data):
        if data:
            return True
        return False

    def fetch(self):
        if isinstance(self,MongoSapSpecialFlow):
            self.connect()
        messages = []
        for i in self.paging():
            self.delay()
            messages = self.pagingFind(self.pageSize, i*self.pageSize)
            for message in messages:
                self.delay()
                data = self.getData(message)
                if data:
                    message.update(data[0])
                    yield self.packaging(message)

    @retry(stop=stop_after_attempt(2))
    def getData(self, message):
        url = self._cf['url'].format(self.cf['general']['domain'],self.cf['general']['mandt'])
        sap_code = message.get('sap_code')
        data = ''
        if sap_code:
            data = eval(str(self._cf['getMsg']) % (self.cf['general']['mandt'], sap_code))
        else:
            return None
        result = requests.post(url, json=data)
        time.sleep(self._cf['sleep'])
        if not self.isValid(result):
            raise ValueError()
        return result.json()['RESULT']


class DuoGeneralFlow(Sap, GeneralFlow):

    @retry(stop=stop_after_attempt(2))
    def getRelation(self, searchPattern, unique):
        if not unique:
            return []
        url = self._cf['url'].format(self.cf['general']['domain'],self.cf['general']['mandt'])
        data = eval(str(searchPattern) % (self.cf['general']['mandt'], unique))
        return self.getData(url, data)['RESULT']

    def fetch(self):
        messages = []
        for i in self.paging():
            self.delay()
            messages = self.pagingFind(self.pageSize, i*self.pageSize)
            for message in messages:
                self.delay()
                data = self.getRelation(self._cf[self.name],message.get(self._cf['unique']))
                if data:
                    for line in data:
                        yield self.getValues(line)


class SapFlow(Sap,GeneralFlow):
    pass


class PatchGeneralFlow(MongoBase, SapFlow):

    @retry(stop=stop_after_attempt(2))
    def mFind(self, pattern):
        mpattern = copy.deepcopy(self._cf['pattern'])
        mpattern.update(pattern)
        return list(self.mclient.find(mpattern,
                                    self._cf['show']).sort([('_id',1)]))

    @retry(stop=stop_after_attempt(2))
    def getPatch(self, unique):
        if not unique:
            return []
        pattern = {self._cf['unique'][1]:unique}
        return self.mFind(pattern)


    def fetch(self):
        if isinstance(self,PatchGeneralFlow):
            self.connect()
        messages = []
        for i in self.paging():
            self.delay()
            messages = self.pagingFind(self.pageSize, i*self.pageSize)
            for message in messages:
                patch = {}
                self.delay()
                data = self.getPatch(message.get(self._cf['unique'][0]))
                if data:
                    if len(data)!=1:
                        logger.warning('[{} more contractids]:{}'.format(self.name,data))
                    patch = data[-1]
                message.update(patch)
                yield self.getValues(message)


class AGeneral(GeneralFlow):
    def fetch(self):
        if isinstance(self, Mongo):
            self.connect()
        lines = []
        lines = self.Aggregate()
        for line in lines:
            message = self.findOne(line[self._cf['unique']])
            if message:
                yield self.getValues(message)

    def work(self):
        for message in self.fetch():
            self.log(self.name, 'message', message, level=self._cf['level'])
            self.matcher(message)
        self.log(self.name, 'end','ok')


class MongoSapSpecialFlow(Mongo,MSSpecialFlow):
    pass



class MongoGeneralFlow(Mongo,GeneralFlow):
    pass

class SSapFlow(SSap,GeneralFlow):
    pass

class AGeneralFlow(Mongo,AGeneral):
    pass

class BGeneralFlow(MongoGeneralFlow):

    def fetch(self):
        if isinstance(self,MongoGeneralFlow):
            self.connect()
        messages = []
        for i in self.paging():
            self.delay()
            messages = self.pagingFind(self.pageSize, i*self.pageSize)
            for message in messages:
                yield self.getValues(self.stringData(message))

    def stringData(self, data):
        if data.get('comments',[]):
            info = json_util.dumps(data['comments'],ensure_ascii=False,separators=(',', ':'))
            info = info.replace('$', '')
            data['comments'] = info
        else:
            data['comments'] = '[]'
        return data




def invoice(cf, funcName='invoice'):
    MongoGeneralFlow(cf,funcName).work()


def payment(cf, funcName='payment'):
    SapFlow(cf, funcName).work()

def PayWithPurchase(cf, funcName='PayWithPurchase'):
    DuoGeneralFlow(cf, funcName).work()

def PayWithRebate(cf, funcName='PayWithRebate'):
    DuoGeneralFlow(cf, funcName).work()


def purchaseorder(cf, funcName='purchaseorder'):
    PatchGeneralFlow(cf, funcName).work()

def iepurchaseorder(cf, funcName='iepurchaseorder'):
    SapFlow(cf, funcName).work()

def customer(cf, funcName='customer'):
    SapFlow(cf, funcName).work()

def account(cf, funcName='account'):
    SapFlow(cf, funcName).work()

def receivable(cf, funcName='receivable'):
    SSapFlow(cf, funcName).work()

def productouts(cf, funcName='productouts'):
    MongoGeneralFlow(cf,funcName).work()

def contract(cf, funcName='contract'):
    AGeneralFlow(cf,funcName).work()

def cuscredit(cf, funcName='cuscredit'):
    MongoGeneralFlow(cf,funcName).work()

def cuscomment(cf, funcName='cuscomment'):
    BGeneralFlow(cf,funcName).work()