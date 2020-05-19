import yaml
import pymongo
from py2neo import Graph, Node, Relationship, NodeMatcher


def loadConfig():
	with open('config.yml', encoding='utf-8') as f:
		_config = yaml.load(f,Loader=yaml.FullLoader)
	return _config


def neoClient(cf):
    graph = Graph(cf['neo4j']['uri'],
                  username=cf['neo4j']['username'],
                  password=cf['neo4j']['password'])
    return graph


def invoiceFindList(field, data):
    if field=='sale_contract_ids':
        sale_contract_ids = []
        htxx = data.get('htxx',[])
        if htxx:
            for line in htxx:
                id = line.get('contractno')
                if id and id.split('-')[0] not in sale_contract_ids:
                    sale_contract_ids.append(id.split('-')[0])
            return sale_contract_ids
        return []
    else:
        delivery_order_ids = []
        dnlist = data.get('dnlist', [])
        if dnlist:
            for line in dnlist:
                id = line.get('dnno')
                if id and id not in delivery_order_ids:
                    delivery_order_ids.append(id)
            if delivery_order_ids:
                return delivery_order_ids
            else:
                savedata = data.get('savedata', [])
                if savedata:
                    for line in savedata:
                        id = line.get('VBELN_DN')
                        if id and id not in delivery_order_ids:
                            delivery_order_ids.append(id)
                    return delivery_order_ids
                else:
                    return []
        else:
            savedata = data.get('savedata',[])
            if savedata:
                for line in savedata:
                    id = line.get('VBELN_DN')
                    if id and id not in delivery_order_ids:
                        delivery_order_ids.append(id)
                return delivery_order_ids
            else:
                return []


def getValueFromPath(name, fieldName, path, line, type):
    if fieldName in ['sale_contract_ids','delivery_order_ids'] and name=='invoice':
        return invoiceFindList(fieldName,line)
    data = line
    paths = path.split('.')
    leng = len(paths)-1
    for index,path in enumerate(paths):
        if isinstance(data, list):
            if index==leng:
                datalist = []
                for item in data:
                    res = item.get(path, {})
                    if res and (res not in datalist):
                        datalist.append(res)
                data = datalist
            else:
                pass
        else:
            data = data.get(path, {})
        if not data:
            return format_kongoutput(type, data)
    return format_output(type,data)


def format_output(output, value):
    try:
        if output == 'string':
            return '{}'.format(value)
        elif output == 'float':
            return float(value)
        else:
            return value
    except Exception as e:
        pass


def format_kongoutput(output, value):
    try:
        if output == 'dict':
            return {}
        elif output == 'int':
            return 0
        elif output == 'string':
            return ''
        elif output == 'float':
            return 0.0
        elif output == 'list':
            return []
        elif output == 'stringlist':
            return '[]'
        else:
            return value
    except Exception as e:
        pass

