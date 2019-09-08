'''
   Base driver class
'''

import pandas as pd
import requests
import json
from copy import deepcopy
import pyperclip
import math
import re
import inspect
import yaml
import itertools
from datetime import datetime
import warnings
#from datapungi-fed import generalSettings        #NOTE: projectName 
import generalSettings        #NOTE: projectName 
#from datapungi-fed import utils                  #NOTE: projectName  
import utils                  #NOTE: projectName  

class driverCore():
    def __init__(self,baseRequest={},connectionParameters={},userSettings={}):
        self._connectionInfo = generalSettings.getGeneralSettings(connectionParameters = connectionParameters, userSettings = userSettings )
        self._baseRequest    = self._getBaseRequest(baseRequest,connectionParameters,userSettings)  
        self._lastLoad       = {}  #data stored here to assist functions such as clipcode        
    
    def _queryApiCleanOutput(self,urlPrefix,api,localVars,method,params,nonQueryArgs,warningsList):
        query = self._getBaseQuery('series/',api,localVars,self.series,params,nonQueryArgs)
        
        #get data and clean it
        retrivedData = requests.get(**query)
        df_output = self._cleanOutput(api,query,retrivedData)
        
        #print warning if there is more data the limit to download
        for entry in warningsList:
            self._warnings(entry,retrivedData,warningsOn) 
        
        #short or detailed output, update _lastLoad attribute:
        output = self._formatOutputupdateLoadedAttrib(query,df_output,retrivedData,verbose)
    
    def _cleanOutput(self,api,query,retrivedData):
        '''
         This is a placeholder - specific implementations should have their own cleaning method
        '''
        return(retrivedData)
    
    def _getBaseQuery(self,urlPrefix,api,localVars,method,params,removeMethodArgs):
        '''
          Return a dictionary of request arguments.

          Args:
              urlPrefix (str) - string appended to the end of the core url (eg, series -> http:...\series? )
              api (str) - (Specific to datapungi_fed) the name of the database (eg, categories)
              locals    - local data of othe method - to get the passed method arguments
              method (func) - the actual method being called (not just a name, will use this to gets its arguments. eg, driver's main method)
              params (dict) - a dictionary with request paramters used to override all other given parameters 
              removeMethodArgs (list) - the arguments of the method that are not request parameters (eg, self, params, verbose)
          Returns:
              query (dict) - a dictionary with 'url' and 'params' (a string) to be passed to a request
        '''
        query = deepcopy(self._baseRequest)
        
        #update query url
        query['url'] = query['url']+urlPrefix+api
          
        #update basequery with passed parameters 
        allArgs = inspect.getfullargspec(method).args
        inputParams = { key:localVars[key] for key in allArgs if key not in removeMethodArgs } #args that are query params
        inputParams = dict(filter( lambda entry: entry[1] != '', inputParams.items() )) #filter params.
        
        #override if passing arg "params" is non-empty:
        # - ensure symbols such as + and ; don't get sent to url symbols FED won't read
        query['params'].update(inputParams)       
        query['params'].update(params)
        query['params'] = '&'.join([str(entry[0]) + "=" + str(entry[1]) for entry in query['params'].items()])

        return(query)
    
    def _getBaseRequest(self,baseRequest={},connectionParameters={},userSettings={}):
        '''
          Write a base request.  This is the information that gets used in most requests such as getting the userKey
        '''
        if baseRequest =={}:
           connectInfo = generalSettings.getGeneralSettings(connectionParameters = connectionParameters, userSettings = userSettings )
           return(connectInfo.baseRequest)
        else:
           return(baseRequest)
    def _formatOutputupdateLoadedAttrib(self,query,df_output,retrivedData,verbose):
        if verbose == False:
            self._lastLoad = df_output
            return(df_output)
        else:
            code = _getCode(query,self._connectionInfo.userSettings,self._cleanCode)
            output = dict(dataFrame = df_output, request = retrivedData, code = code)  
            self._lastLoad = output
            return(output)
    
    def _warnings(self,warningName,inputs,warningsOn = True):
        if not warningsOn:
            return
        
        if warningName == 'countPassLimit':
            '''
              warns if number of lines in database exceeds the number that can be downloaded.
              inputs = a request result of a FED API 
            '''
            _count = inputs.json().get('count',1)
            _limit = inputs.json().get('limit',1000)
            if _count > _limit:
              warningText = 'NOTICE: dataset exceeds download limit! Check - count ({}) and limit ({})'.format(_count,_limit)
              warnings.warn(warningText) 
        
    def _getBaseCode(self,codeEntries): 
        '''
          The base format of a code that can be used to replicate a driver using Requests directly.
        '''
        userSettings = utils.getUserSettings()
        pkgConfig    = utils.getPkgConfig()
        storagePref  = userSettings['ApiKeysPath'].split('.')[-1]
        
        passToCode = {'ApiKeyLabel':userSettings["ApiKeyLabel"], "url":pkgConfig['url'], 'ApiKeysPath':userSettings['ApiKeysPath']}
        if storagePref == 'json':
            code = '''
import requests
import json    
import pandas as pd

# json file should contain: {"BEA":{"key":"YOUR KEY","url": "{url}" }

apiKeysFile = '{ApiKeysPath}'
with open(apiKeysFile) as jsonFile:
   apiInfo = json.load(jsonFile)
   url,key = apiInfo['{ApiKeyLabel}']['url'], apiInfo['{ApiKeyLabel}']['key']    
            '''.format(**passToCode)
    
        if storagePref == 'env':
            code = '''
import requests
import os 
import pandas as pd

url = "{url}"
key = os.getenv("{ApiKeyLabel}") 
            '''.format(**passToCode)
    
        if storagePref == 'yaml':
            code = '''
import requests
import yaml 
import pandas as pd

apiKeysFile = '{ApiKeysPath}'
with open(apiKeysFile, 'r') as stream:
    apiInfo= yaml.safe_load(stream)
    url,key = apiInfo['{ApiKeyLabel}']['url'], apiInfo['{ApiKeyLabel}']['key']
     '''
    
        return(code)

    def _getCode(self,query,userSettings={},pandasCode=""):
        #general code to all drivers:
        try:
            url        = query['url']
            if not userSettings:  #if userSettings is empty dict 
                    apiKeyPath = generalSettings.getGeneralSettings( ).userSettings['ApiKeysPath']
            else:
                apiKeyPath = userSettings['ApiKeysPath']
        except:
            url         = " incomplete connection information "
            apiKeyPath = " incomplete connection information "
        
        baseCode = _getBaseCode([url,apiKeyPath])
        
        #specific code to this driver:
        queryClean = deepcopy(query)
        queryClean['url'] = 'url'
        queryClean['params']['UserID'] = 'key'
        
        
        queryCode = '''
    query = {}
    retrivedData = requests.get(**query)
    
    {} #replace json by xml if this is the request format
        '''.format(json.dumps(queryClean),pandasCode)
        
        queryCode = queryCode.replace('"url": "url"', '"url": url')
        queryCode = queryCode.replace('"UserID": "key"', '"UserID": key')
        
        return(baseCode + queryCode)
    
    def _clipcode(self):
        '''
           Copy the string to the user's clipboard (windows only)
        '''
        try:
            pyperclip.copy(self._lastLoad['code'])
        except:
            print("Loaded session does not have a code entry.  Re-run with verbose option set to True. eg: v.drivername(...,verbose=True)")