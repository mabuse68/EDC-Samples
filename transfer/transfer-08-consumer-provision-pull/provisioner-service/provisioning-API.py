# To run this server:
# uvicorn provisioning-API:app --reload --ssl-certfile certs/cert.pem --ssl-keyfile certs/key.pem --port httpport

from pydantic import BaseModel
import requests
import json
import logging
from datetime import datetime
from threading import Thread
from typing import Annotated
from fastapi import FastAPI, BackgroundTasks, Request
import logging, sys

app = FastAPI()
separator = '-' * 30

class EdcRequest(BaseModel):
    assetId: str
    transferProcessId: str
    callbackAddress: str
    resourceDefinitionId: str
    policy: dict


def task(edcRequest: EdcRequest):

# This server receives the following provision call content:
	'''{
	  "assetId": "assetId",
	  "transferProcessId": "099a99f1-f5bd-4eae-9a21-20f71a36b87c",
	  "policy": {
		"permissions": [],
		"prohibitions": [],
		"obligations": [],
		"extensibleProperties": {},
		"inheritsFrom": null,
		"assigner": null,
		"assignee": null,
		"target": "assetId",
		"@type": {
		  "@policytype": "set"
		}
	  },
	  "callbackAddress": "http://oatmeal:19193/management/callback",
	  "resourceDefinitionId": "2108d36c-c283-47cb-a51d-337f7c0f3a4f"
	}
	'''
    
    # Provision a route in Kong
    # The route has path = assetId and name = transferProcessId
    # The route will be used to forward requests through the API manager to the LDES service
	KongrouteAPI = 'http://englishbreakfast:8001/services/ldesservice/routes'
	#RouteData = {'paths[]':'/'+edcRequest.assetId,'name':edcRequest.transferProcessId,}
	RouteData = {'paths[]':'/'+edcRequest.assetId,'name':'ldesroute'}
	try:
		response=requests.post(KongrouteAPI, data= RouteData)
	except requests.exceptions.HTTPError as err:  # Any error: quit
		raise SystemExit(err)

	BaseURL= 'http://englishbreakfast:8000/'+edcRequest.assetId

	data = {
		"edctype": "dataspaceconnector:provisioner-callback-request",
		"resourceDefinitionId": edcRequest.resourceDefinitionId,
		"assetId": edcRequest.assetId,
		"resourceName": "ProvisionedResource",
		"contentDataAddress": {
			"properties": {
				"type": "HttpData",
				#"baseUrl": "http://oatmeal:8881/data/"
				"baseUrl": BaseURL
			}
		},
		"apiKeyJwt": "unused",
		"hasToken": False
	}
	completeUrl = edcRequest.callbackAddress +"/"+ edcRequest.transferProcessId + "/provision/"
	print(completeUrl)
	resp = requests.post(url=completeUrl, json=data,headers={"x-api-key": ""})
	print(separator)
	print("PROVISION SERVICE calls CONNECTOR back:")
	print(data)
	print("CONNECTOR response:")
	print(resp)

@app.post("/provision/")
async def provision(edcRequest: EdcRequest, request: Request):

    t = Thread(target=task,
               kwargs={
                   "edcRequest": edcRequest}
               )
    t.start()
    content = await request.body()
    headers = dict(request.headers)
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    print(separator)
    print(" + CONNECTOR called the PROVISION SERVICE at: "+ current_time)
    print("Request Content:")
    print(content.decode())
    print("Request Headers:")
    for key, value in headers.items():
        print(f"{key}: {value}")
    print(separator)
    return {}


@app.get("/data/")
        
async def getData(request: Request, edcRequest: EdcRequest):
    content = await request.body()
    headers = dict(request.headers)
    
    # Print the request content and headers on the console
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    print(separator)
    print(" + Hit on DATA API: "+ current_time)
    print("Request Content:")
    print(content.decode())
    
    print("Request Headers:")
    for key, value in headers.items():
        print(f"{key}: {value}")
    print(separator)
    
    #jsonmessage = json.dumps({"message":current_time})
    return {"response:":  edc.Request}
