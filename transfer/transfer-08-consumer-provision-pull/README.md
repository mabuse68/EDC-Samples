# Implement a "Consumer Pull" Http transfer flow with Provider provisioning of an API route

This example builds on Transfer-06-consumer-pull usecase, but it adds the capability to provision a custom endpoint on an API manager running on the backend to access a data service.

The purpose of this example is to implement the flow for dynamic source provisioning, and share the data between 2 connectors on a proxied connection.


The usecase needs the following components:
* A data source, we choose an [LDES](https://semiceu.github.io/LinkedDataEventStreams/) data stream of water quality sensors (read further in this document).
* The Provider Connector.
* An HTTP Provisioner service. The connector calls this service passing the parameters to provision an HTTP data source. The service sends back, asynchronously, the data source details, like its URL, or authentication token.
* An API manager, used to create an API endpoint for each data transfer agreement.
* A callback service to dispatch authorization credentials that the client will use to query the data.
* A Consumer connector, in our case also the endpoint that the client will use to query data.


# Prerequisites
For the sake of simplicity, all the components run on the same machine.
* Docker is used to run Kong Gateway and supporting database locally.
* curl is used to send requests to Kong Gateway. curl is pre-installed on most systems.
* jq is used to process JSON responses on the command line. While useful, this tool is not necessary to complete the tasks of this tutorial. If you wish to proceed without jq, modify the commands to remove jq processing.
* JVM v17 or later version.
* Gradle and Maven to build the connectors.
* Python 3.x, [Uvicorn](https://www.uvicorn.org/) to run the Provisioning API server.
* The machine where the Provider Connector runs must have a hostname different from localhost, and be able to resolve the name to 127.0.0.1. Without a hostname set, the provisioning doesn't work.

# What this demo delivers
At the end of this example the reader will have an understanding of the necessary steps to implement a data transfer where the data source is dynamically provisioned.


The steps are the following:

* Install an API manager (Kong) and ceate a service to expose a data sorce
* Configure and run the Provider connector with provision extension
* Run the Provisioner Server
* Run the Consumer connector
* Run a Http server that will receive the Endpoint Data Reference (EDR) on the consumer side, that
  contains the url to be used to get the data.
* Register data plane instances for both Provider and Consumer connectors
* Create an Asset on the provider (The asset will have a placeholder URL that will be provisioned later)
* Create an access policy on the provider (The policy will define the access right to the data)
* Create a contract definition on the provider

The consumer is now able to fetch the catalog from the provider and to see the
contract offerings generated from the resources that have been created.

Once the catalog is available, to access the data, the consumer should follow the following steps:

* Perform a contract negotiation with the provider
* Perform a transfer
    * The Consumer initiates a file transfer request
    * The Provider calls the Provisioner, the transfer remains on hold until the Provisioner returns the Source's address.
    * The Provider is then able to send an EndpointDataReference to the consumer
* The consumer could reach the endpoint and access the data

Also, in order to keep things organized, the code in this example has been separated into several
Java modules:

* `connector`: contains the configuration and build files for both the
  consumer and the provider connector
* `backend-service`: represent the backend service where the consumer connector will send the
  EndpointDataReference to access the data

> [!NOTE]
> For the sake of simplicity, we will use an in-memory catalog and fill it with just one single asset. The in-memory catalog isn't persistent, and it's lost after every connector's shutdown.


# Prepare the environment

## Resolve a specific hostname
This step is mandatory, the provisioning extension works only if the hostname where the connector runs is resolvable.


If you run this on a Linux or OSX machine, set a hostname and configure the local resolver.
On you shell of choice (bash in the example here):
```bash
pico /etc/hosts
```
Add the following line to the hosts file:
```bash
127.0.0.1               oatmeal
```
Where oatmeal is the hostname we will use in this example, you can use another hostname if you prefer.

> [!NOTE]
> From now on, all shell commands are executed from the root directory of this repository, adjust relative paths consequently if you work from another directory.


## Install and configure the API manager

Install a local API manager if you don't already have one running. 
For this example, we will use [Kong](https://docs.konghq.com/gateway/latest/get-started/).

Kong provides a configurable shell script that downloads and runs the docker images needed to run the server and its database:
```bash
curl -Ls https://get.konghq.com/quickstart | bash
```
To stop Kong's containers, run this command:
```bash
curl https://get.konghq.com/quickstart | bash -s -- -d -a kong-quickstart
```
Verify Kong is running by issuing this command:
```bash
curl -s oatmeal:8001 | jq '.configuration'
```

### Port bindings
Kong exposes by default the port-ranges 8000...8004, 8443...8447. If these ports are already in use in you machine, you will have to download the quickstart script and edit the port bindings before executing it:
```bash
curl -Ls https://get.konghq.com/quickstart.sh
pico quickstart.sh
```
Edit the following:
```bash
DEFAULT_PROXY_PORT=8000
DEFAULT_ADMIN_PORT=8001
DEFAULT_MANAGER_PORT=8002
DEFAULT_DEVPORTAL_PORT=8003
DEFAULT_FILES_PORT=8004
```
And then execute the script to start Kong back again.

### Pre-provision a service on the API manager
In this sample scenario, the data owner defines a service on the API manager that points to the LDES stream that measures water quality in the FLemish region:
https://ldes.vsds.odt.imec-apt.be/water-quality-observations

Supposing Kong management interface is accessible on port 8001:
```bash
curl -X POST http://oatmeal:8001/services \
--data name='ldesservice' \
--data url='http://ldes.vsds.odt.imec-apt.be/water-quality-observations' -s | jq
```

> [!NOTE]
> In Kong, a service defines the backend data source, while a route defines the API endpoint where to access it. In this sample the producer connector provisions a route for a known service. 

The source LDES server demands that every request contains the Accept header, preferably with value text:turtle. However the connector proxy doesn't seem to support such header in the native request. We solve this issue with a hack: we add the header on all upstream requests via Kong:

```bash
curl -X POST http://localhost:8001/services/ldesservice/plugins \
    --data "name=request-transformer"  \
    --data "config.add.headers=accept:text/turtle" | jq 
```


The diagram below resumes the whole setup:


![Diagram of an EDC connector provisioning an API endpoint on a Kong API manager](pictures/API-Services-and-routes.png)


Both services and routes can be configured to implement access control, parameter substitution, header injection, or any other exotic HTTP configuration that one might concoct.

See [here](transfer/transfer-08-consumer-provision-pull/kong-commands.md) for a list of Kong commands that might be useful during testing and experimenting.


## Install Uvicorn
Provided you have Python on your machine, install the Uvicorn package that we will use to implement the Provisioning API service.
```bash
pip install uvicorn
```


## Run the Provisioner Service
Once a consumer connector requests a data transfer, the producer connector sends a POST request to the Provisioning Service before the actual data transfer takes place.
We configure the provisioner connector to look for a ```/provision``` endpoint for its POST call. 
The call's payload contains a context of the data sharing request and a callback endpoint that the Provisioner Service uses to return the result of its provisioning, and an URL that will become the ```dataAddress``` of the transfer request.

The [Provisioning-API](./Provisioner-service/provisioning-API.py) service is our Provisioner.
Start the Provisioning-API service from this root folder by executing this command:

```bash
uvicorn transfer.transfer-08-consumer-provision-pull.provisioner-service.provisioning-API:app --reload --port 8881
```
**N.B.:** notice the dotted notation of the path where Uvicorn can find the App.

## Build the connector
The build file of the connector is located here:
```bash
transfer/transfer-08-consumer-provision-pull/http-pull-prov-connector/build.kts
```
The build configuration file includes the extensions needed to enable provisioning (it's not a standard extension). Never mind the naming conventions of packages, as they aren't consistent in the EDC project at the time of writing. 

The provisioning extension is in the EDC Maven directory:

```config
val edcGroupId = "org.eclipse.edc"
val edcVersion = "0.2.1"
.
.
    implementation("${edcGroupId}:provision-http:${edcVersion}")
    implementation(libs.edc.data.plane.client)
```
> [!NOTE]
> **N.B.:** change the edcVersion value to the current one.

Build the connector by executing the following command:

```bash
./gradlew transfer:transfer-08-consumer-pull-prov:http-pull-prov-connector:build
```

After the build ends, you can verify that the connector jar is created in the directory
[http-pull-prov-connector.jar](http-pull-prov-connector/build/libs/http-pull-prov-connector.jar)


### Configure the two connectors

We will run a Provider and a Consumer connector, the former is the connector that provisions an API endpoint and exposes the data, the latter is the connector that initiates the data transfer and consumes the data.

Their configuration files can be found here:

 [provider](http-pull-prov-provider/provider-configuration.properties)
 [consumer](http-pull-prov-consumer/consumer-configuration.properties)
 
### HTTP Pull properties
 ```java
edc.receiver.http.endpoint=http://oatmeal:4000/receiver/urn:connector:provider/callback 
```
This property is used to resolve the host where the connector sends the access token for the data transfer (See Sample 06).
And
 ```java
edc.dataplane.token.validation.endpoint=http://oatmeal:29192/control/token
```
This property is used to define the endpoint exposed by the control plane to validate the access token.
 
### HTTP Endpoint Provision  properties

```java
edc.hostname=oatmeal
```
The connector must resolve a hostname where it runs to implement provisioner's callback properly

```java
provisioner.http.entries.default.provisioner.type=provider
```
The connector uses the "provider" identifier to trigger the provisioning extension

```java
provisioner.http.entries.default.endpoint=http://oatmeal:8881/provision
```
Our Provisioning server will run on the same host on port 8881

```java
provisioner.http.entries.default.data.address.type=HttpData
```
The HTTPData type address can be provisioned. This config enables the http pull usecase on a dynamically provisioned asset

```java
edc.transfer.proxy.token.validity.seconds=3600
```
Custom token validity raised to 1hr to help with debugging.

Enough with building and configuring. Let's start sharing data dynamically!


## Run the connectors

To run the provider, just run the following command

```bash
java -Dedc.keystore=transfer/transfer-08-consumer-provision-pull/certs/cert.pfx -Dedc.keystore.password=123456 -Dedc.vault=transfer/transfer-08-consumer-provision-pull/http-pull-provider/provider-vault.properties -Dedc.fs.config=transfer/transfer-08-consumer-provision-pull/http-pull-provider/provider-configuration.properties -jar transfer/transfer-08-consumer-provision-pull/http-pull-prov-connector/build/libs/pull-connector.jar
```

To run a consumer, just run the following command

```bash
java -Dedc.keystore=transfer/transfer-08-consumer-provision-pull/certs/cert.pfx -Dedc.keystore.password=123456 -Dedc.vault=transfer/transfer-08-consumer-provision-pull/http-pull-consumer/consumer-vault.properties -Dedc.fs.config=transfer/transfer-08-consumer-provision-pull/http-pull-consumer/consumer-configuration.properties -jar transfer/transfer-08-consumer-provision-pull/http-pull-prov-connector/build/libs/pull-connector.jar
```

Assuming you didn't change the ports in config files, the consumer will listen on the
ports `29191`, `29192` (management API) and `29292` (IDS API) and the provider will listen on the
ports `12181`, `19182` (management API) and `19282` (IDS API).


# Run the sample

Running this sample consists of multiple steps, that are executed one by one and following the same
order.


> [!NOTE]
> If you have some issues with the jq option, know that it's not mandatory because it is just used to format the output.


### 1. Register data plane instance for provider

We register a data plane instance that handles the http provision and implement an http proxy pipeline to serve the data. 
We use the connector management API and insert in the request body the data plane paramters. 

Notice that the data plane will accept two kind of sources:

``` HTTPData ```
This describes an HTTP data source, like a REST API. The ```HTTPData``` source type has been configured prcedently to trigger an HTTP-based provisioning as soon as it is involved in a data transfer.

``` HTTPProxy```
This data sink type uses the connector as Proxy.

```bash
curl -H 'Content-Type: application/json' \
     -d '{
           "@context": {
             "edc": "https://w3id.org/edc/v0.0.1/ns/"
           },
           "@id": "http-pull-provider-dataplane",
           "url": "http://oatmeal:19192/control/transfer",
           "allowedSourceTypes": [ "HttpData", "HttpProxy" ],
           "allowedDestTypes": [ "HttpProxy", "HttpData" ],
           "properties": {
             "https://w3id.org/edc/v0.0.1/ns/publicApiUrl": "http://oatmeal:19291/public/"
           }
         }' \
     -X POST "http://oatmeal:19193/management/v2/dataplanes"
```

### 2. Register data plane instance for consumer

We register the consumer dataplane, this time we don't need to provision anything on the consumer, but nothing would prevent to have a consumer that provisions the destination endpoint autmatically, it is just not the case in the HTTP Pull pattern, where the destination endpoint is the connector itself.

```bash
curl -H 'Content-Type: application/json' \
     -d '{
           "@context": {
             "edc": "https://w3id.org/edc/v0.0.1/ns/"
           },
           "@id": "http-pull-consumer-dataplane",
           "url": "http://oatmeal:29192/control/transfer",
           "allowedSourceTypes": [ "HttpData" ],
           "allowedDestTypes": [ "HttpProxy", "HttpData" ],
           "properties": {
             "https://w3id.org/edc/v0.0.1/ns/publicApiUrl/publicApiUrl": "http://oatmeal:29291/public/"
            }
         }' \
             -X POST "http://oatmeal:29193/management/v2/dataplanes"
```

### 3. Create an Asset on the provider side

We need to register the asset in the Provider's internal list of resources. This step defines where the asset can be found, how to connect to it, and which options to activate, like ‘‘‘Proxypath‘‘‘, that allows headers and parameters forwarding when querying the asset.

The type of asset is.

```bash
curl -d '{
           "@context": {
             "edc": "https://w3id.org/edc/v0.0.1/ns/"
           },
           "asset": {
             "@id": "ldesStream",
             "properties": {
               "name": "product description",
               "contenttype": "application/json"
             }
           },
           "dataAddress": {
             "type": "HttpData",
             "baseUrl": "http://example.com",
             "name": "ldesServer",
             "proxyPath": "true",
             "proxyQueryParams": "true",
             "proxyBody": "true",
             "proxyMethod": "true"
           }
         }' -H 'content-type: application/json' http://oatmeal:19193/management/v2/assets \
         -s | jq
```

> [!NOTE]
> The `baseUrl` property of the `dataAddress` is a placeholder. It is replaced by the effective data source when provisioning happens. 
> The BaseUrl can be omitted, nevertheless it should be kept in the configuration if the asset must be consumed by a non-provisioned data sharing.

Additional properties on `HttpData` can be used to allow consumers to enrich the data request:

- `proxyPath`: allows specifying additional path segments.
- `proxyQueryParams`: allows specifying query params.
- `proxyBody`: allows attaching a body.
- `proxyMethod`: allows specifying the Http Method (default `GET`)

### 4. Create a Policy on the provider

In order to manage the accessibility rules of an asset, it is essential to create a policy. However,
to keep things simple, we will choose a policy that gives direct access to all the assets that are
associated within the contract definitions.
This means that the consumer connector can request any asset from the provider connector.

```bash
curl -d '{
           "@context": {
             "edc": "https://w3id.org/edc/v0.0.1/ns/",
             "odrl": "http://www.w3.org/ns/odrl/2/"
           },
           "@id": "aPolicy",
           "policy": {
             "@type": "set",
             "odrl:permission": [],
             "odrl:prohibition": [],
             "odrl:obligation": []
           }
         }' -H 'content-type: application/json' http://oatmeal:19193/management/v2/policydefinitions \
         -s | jq
```

### 5. Create a contract definition on Provider

To ensure an exchange between providers and consumers, the supplier must create a contract offer for
the good, on the basis of which a contract agreement can be negotiated. The contract definition
associates policies to a selection of assets to generate the contract offers that will be put in the
catalog. In this case, the selection is empty, so every asset is attached to these policies

```bash
curl -d '{
           "@context": {
             "edc": "https://w3id.org/edc/v0.0.1/ns/"
           },
           "@id": "1",
           "accessPolicyId": "aPolicy",
           "contractPolicyId": "aPolicy",
           "assetsSelector": []
         }' -H 'content-type: application/json' http://oatmeal:19193/management/v2/contractdefinitions \
         -s | jq
```

Sample output:

```json
{
  ...
  "@id": "1",
  "edc:createdAt": 1674578184023,
  ...
}
```

### 6. How to fetch the provider asset's catalog on consumer side

In order to consume any data, the consumer must fetch the catalog from the provider. The catalog contains
all the contract offers available for negotiation. In this sample, it will just contain a single contract
offer, the so-called "catalog". To get the catalog from the consumer side, you can use the following
endpoint:

```bash
curl -X POST "http://oatmeal:29193/management/v2/catalog/request" \
    -H 'Content-Type: application/json' \
    -d '{
      "@context": {
        "edc": "https://w3id.org/edc/v0.0.1/ns/"
      },
      "providerUrl": "http://oatmeal:19194/protocol",
      "protocol": "dataspace-protocol-http"
    }' -s | jq
```

The Catalog will contain the description of our offering (dataset + policies). Each offering is mapped to the DCAT properties ```dcat:distribution```.
Here's is a sample output:

```json
{
  "@id": "a827c478-6742-4709-a24a-bdaddec736a3",
  "@type": "dcat:Catalog",
  "dcat:dataset": {
    "@id": "ldesStream",
    "@type": "dcat:Dataset",
    "odrl:hasPolicy": {
      "@id": "MQ==:bGRlc1N0cmVhbQ==:MjE2ZmIzYjgtM2I2ZS00YmM1LWI4YWItNWMxMThlYmQyZWM3",
      "@type": "odrl:Set",
      "odrl:permission": [],
      "odrl:prohibition": [],
      "odrl:obligation": [],
      "odrl:target": "ldesStream"
    },
    "dcat:distribution": [
      {
        "@type": "dcat:Distribution",
        "dct:format": {
          "@id": "HttpProxy"
        },
        "dcat:accessService": "34bcedfb-1e74-42a6-928d-4cd2402a6c4b"
      },
      {
        "@type": "dcat:Distribution",
        "dct:format": {
          "@id": "HttpData"
        },
        "dcat:accessService": "34bcedfb-1e74-42a6-928d-4cd2402a6c4b"
      }
    ],
    "edc:name": "product description",
    "edc:id": "ldesStream",
    "edc:contenttype": "application/json"
  },
  "dcat:service": {
    "@id": "34bcedfb-1e74-42a6-928d-4cd2402a6c4b",
    "@type": "dcat:DataService",
    "dct:terms": "connector",
    "dct:endpointUrl": "http://oatmeal:19194/protocol"
  },
  "edc:participantId": "provider",
  "@context": {
    "dct": "https://purl.org/dc/terms/",
    "edc": "https://w3id.org/edc/v0.0.1/ns/",
    "dcat": "https://www.w3.org/ns/dcat/",
    "odrl": "http://www.w3.org/ns/odrl/2/",
    "dspace": "https://w3id.org/dspace/v0.8/"
  }
}
```

### 7. Negotiate a contract

The next step is to negotiate a contract, the result of a negotiation is a data sharing agreement.
In a business environment, the negotiation can be an asynchronous process, perhaps involving human intervention, between providers and consumers. In this sample we keep it as simple as it can be.

The sequence looks as follows:

1. Consumer sends a contract offer to the provider (__currently, this has to be equal to the
   provider's offer!__)
2. Provider validates the received offer against its own offer
3. Provider either sends an agreement or a rejection, depending on the validation result
4. In case of successful validation, provider and consumer store the received agreement for later
   reference

Of course, this is the simplest possible negotiation sequence. Later on, both connectors can also
send counter offers in addition to just confirming or declining an offer.

> [!NOTE]
> The contract negotiation needs the ```offerId``` of the asset that we want to share. Be sure to copy its value from the output of the command we executed in the previous step (the catalog request).

```bash
curl -d '{
  "@context": {
    "edc": "https://w3id.org/edc/v0.0.1/ns/",
    "odrl": "http://www.w3.org/ns/odrl/2/"
  },
  "@type": "NegotiationInitiateRequestDto",
  "connectorId": "provider",
  "connectorAddress": "http://oatmeal:19194/protocol",
  "consumerId": "consumer",
  "providerId": "provider",
  "protocol": "dataspace-protocol-http",
  "offer": {
   "offerId": "MQ==:bGRlc1N0cmVhbQ==:MjE2ZmIzYjgtM2I2ZS00YmM1LWI4YWItNWMxMThlYmQyZWM3",
   "assetId": "ldesStream",
   "policy": {
     "@id": "MQ==:bGRlc1N0cmVhbQ==:MjE2ZmIzYjgtM2I2ZS00YmM1LWI4YWItNWMxMThlYmQyZWM3",
     "@type": "Set",
     "odrl:permission": [],
     "odrl:prohibition": [],
     "odrl:obligation": [],
     "odrl:target": "assetId"
   }
  }
}' -X POST -H 'content-type: application/json' http://oatmeal:29193/management/v2/contractnegotiations \
-s | jq
```

Sample output:

```json
{
  "@type": "edc:IdResponse",
  "@id": "5c05b9e3-dc36-48b5-b27a-c33cd88a9cf5",
  "edc:createdAt": 1693263918896,
  "@context": {
    "dct": "https://purl.org/dc/terms/",
    "edc": "https://w3id.org/edc/v0.0.1/ns/",
    "dcat": "https://www.w3.org/ns/dcat/",
    "odrl": "http://www.w3.org/ns/odrl/2/",
    "dspace": "https://w3id.org/dspace/v0.8/"
  }
}
```

### 8. Getting the contract agreement id

After calling the endpoint for initiating a contract negotiation, we get a UUID as the response.
This UUID is the ID of the ongoing contract negotiation between consumer and provider. The
negotiation sequence between provider and consumer is executed asynchronously in the background by a
state machine. Once both provider and consumer either reach the `confirmed` or the  `declined`
state, the negotiation is finished. 

> [!NOTE]
> Be sure to replace the UUID on the command below with the one from the output of the previous command.

```bash
curl -X GET "http://oatmeal:29193/management/v2/contractnegotiations/5c05b9e3-dc36-48b5-b27a-c33cd88a9cf5" \
     --header 'Content-Type: application/json' \
     -s | jq
```

The sample output is:

```json
{
  "@type": "edc:ContractNegotiation",
  "@id": "5c05b9e3-dc36-48b5-b27a-c33cd88a9cf5",
  "edc:type": "CONSUMER",
  "edc:protocol": "dataspace-protocol-http",
  "edc:state": "FINALIZED",
  "edc:counterPartyId": "provider",
  "edc:counterPartyAddress": "http://oatmeal:19194/protocol",
  "edc:callbackAddresses": [],
  "edc:createdAt": 1693263918896,
  "edc:contractAgreementId": "MQ==:bGRlc1N0cmVhbQ==:NmE0Y2I1Y2UtMGExMC00M2RmLTgzMmUtOWJlMDE4YzQyYzAw",
  "@context": {
    "dct": "https://purl.org/dc/terms/",
    "edc": "https://w3id.org/edc/v0.0.1/ns/",
    "dcat": "https://www.w3.org/ns/dcat/",
    "odrl": "http://www.w3.org/ns/odrl/2/",
    "dspace": "https://w3id.org/dspace/v0.8/"
  }
}
```

### 9. Start the transfer

As a pre-requisite, you need to have a backend service that runs on port 4000.
The service receives from the provider a POST method with the authorization token to read the data. It dumps it on its standard output (console).

```bash
./gradlew util:http-request-logger:build HTTP_SERVER_PORT=4000

java -jar util/http-request-logger/build/libs/http-request-logger.jar
```

Now that we have a contract agreement, **we can finally request the file.**
In the request body, we need to specify which asset we want transferred, the ID of the contract agreement, the address of the provider connector and where we want the file transferred. You will find the request body below.
Before executing the request, insert the contract agreement ID from the previous step. 

> [!NOTE]
> Be sure to copy the value of ```edc:contractAgreementId``` from the result of the previous call as the value of the ```contractId``` in the following command:

```bash
curl -X POST "http://oatmeal:29193/management/v2/transferprocesses" \
    -H "Content-Type: application/json" \
    -d '{
        "@context": {
          "edc": "https://w3id.org/edc/v0.0.1/ns/"
        },
        "@type": "TransferRequestDto",
        "connectorId": "provider",
        "connectorAddress": "http://oatmeal:19194/protocol",
        "contractId": "MQ==:bGRlc1N0cmVhbQ==:NmE0Y2I1Y2UtMGExMC00M2RmLTgzMmUtOWJlMDE4YzQyYzAw",
        "assetId": "ldesStream",
        "managedResources": false,
        "protocol": "dataspace-protocol-http",
        "dataDestination": { 
          "type": "HttpProxy" 
        }
    }' \
    -s | jq
```

Then, we will get a UUID in the response. This time, this is the ID of the `TransferProcess` (
process id) created on the consumer
side, because like the contract negotiation, the data transfer is handled in a state machine and
performed asynchronously.
The "HttpProxy" method is used for the consumer pull method, and it means that it will be up to the consumer to request the data to the provider and that the request will be a proxy for the datasource.

Sample output:

```json
{
  "@type": "edc:IdResponse",
  "@id": "a0eb3271-373a-4965-b2e4-642c1afbfcdd",
  "edc:createdAt": 1693263963311,
  "@context": {
    "dct": "https://purl.org/dc/terms/",
    "edc": "https://w3id.org/edc/v0.0.1/ns/",
    "dcat": "https://www.w3.org/ns/dcat/",
    "odrl": "http://www.w3.org/ns/odrl/2/",
    "dspace": "https://w3id.org/dspace/v0.8/"
  }
}
```

### 10. Check if the provisioning took place

The Provisioner Service is activated by the transfer request we sent in the previous step. 
On the server console you should be able to observe the result of the provisioning operation:

```bash
----------------------------
 + CONNECTOR called the PROVISION SERVICE at: 10:04:12
Request Content:
{"assetId":"ldesStream","transferProcessId":"546f6f5f-424b-4d44-bbd8-92d659eed91c","policy":{"permissions":[],"prohibitions":[],"obligations":[],"extensibleProperties":{},"inheritsFrom":null,"assigner":null,"assignee":null,"target":"ldesStream","@type":{"@policytype":"set"}},"callbackAddress":"http://oatmeal:19193/management/callback","resourceDefinitionId":"98eec735-bd8c-4ab5-b388-3afbaa7c88bb"}
Request Headers:
content-type: application/json; charset=utf-8
content-length: 399
host: oatmeal:8881
connection: Keep-Alive
accept-encoding: gzip
user-agent: okhttp/4.11.0
------------------------------
INFO:     127.0.0.1:52856 - "POST /provision/ HTTP/1.1" 200 OK
http://oatmeal:19193/management/callback/546f6f5f-424b-4d44-bbd8-92d659eed91c/provision/
------------------------------
PROVISION SERVICE calls CONNECTOR back:
{'edctype': 'dataspaceconnector:provisioner-callback-request', 'resourceDefinitionId': '98eec735-bd8c-4ab5-b388-3afbaa7c88bb', 'assetId': 'ldesStream', 'resourceName': 'ProvisionedResource', 'contentDataAddress': {'properties': {'type': 'HttpData', 'baseUrl': 'http://englishbreakfast:8000/ldesStream'}}, 'apiKeyJwt': 'unused', 'hasToken': False}
CONNECTOR response:
<Response [204]>
INFO:     127.0.0.1:52945 - "POST /provision HTTP/1.1" 307 Temporary Redirect
------------------------------
```

You can also check the status of the transfer by issuing the following command:

```bash
curl http://oatmeal:29193/management/v2/transferprocesses/<transfer process id>
```


You should see the Transfer Process in `COMPLETED` state: 
```json
{
  ...
  "@id": "0f648d82-23b4-464d-8f7b-c89860efe7c9",
  "edc:state": "COMPLETED",
  ...
}

```

### 11. Pull the data

At this step, if you look at the backend service logs, you will have a json representing
the data useful for reading the data. This is presented in the following section.

Sample log for the Backend Service:

```json
Request Body: {"id":"6810a50c-778e-4318-9c2e-a06ccd83f63b",
  "endpoint":"http://oatmeal:19291/public/",
  "authKey":"Authorization",
  "authCode":"eyJhbGciOiJSUzI1NiJ9.eyJleHAiOjE2OTMzMTM5NzAsImRhZCI6IntcInByb3BlcnRpZXNcIjp7XCJiYXNlVXJsXCI6XCJodHRwOi8vZW5nbGlzaGJyZWFrZmFzdDo4MDAwL2xkZXNTdHJlYW1cIixcImh0dHBzOi8vdzNpZC5vcmcvZWRjL3YwLjAuMS9ucy90eXBlXCI6XCJIdHRwRGF0YVwiLFwiaHR0cHM6Ly93M2lkLm9yZy9lZGMvdjAuMC4xL25zL2tleU5hbWVcIjpcIlByb3Zpc2lvbmVkUmVzb3VyY2VcIn19IiwiY2lkIjoiTVE9PTpiR1JsYzFOMGNtVmhiUT09Ok5EbGhaVGxqWW1RdE1qY3pZeTAwTXpSaUxXRXhZemt0TlRaallXRmhORGM1T1dVNSJ9.b1EtjQ8ZtbqSqyrzNWzmX4LNddI0FKMmONShin0wZwEibNHMK9OUnDOdDJhituIuhfGu9lNOf_cGFkSeblYxKh0FhLJi3DrgOD694W1v8REO8u1gH2TBftu4dw_T4_mQT4nKO-m7FmpfBEUU_N3UqWyY--GM0IQ2NtN79pZIy9kE-Li_o_e8JhSzjBGc3tMmIxLVAEpnB2CFhiYL8IKiK3Jbzl2bsNFlizgTcj2Hj4f5n4E4KOTofEmQVFskfsgspF4uMZPIBTY4sQQVwspT09nbUqOKHKbiXIP-X5Dl3-EL469jpygapMHIbc4P38SiCeJyYFC87Xw2NLNiftHzHA",
  "properties":{}
}
```

Once this json is read, use a tool like postman or curl to execute the following query, to read the
data

```bash
curl --location --request GET 'http://oatmeal:29291/public/' \
--header 'Authorization: <auth code>'
```

If all has gone well, the call should return the root of our LDES stream:
```json
water-quality-observations:by-time
        rdf:type              tree:Node ;
        tree:viewDescription  by-time:description .

<https://ldes.vsds.odt.imec-apt.be/water-quality-observations>
        rdf:type            ldes:EventStream ;
        <http://example.org/memberType>
                sosa:ObservationCollection ;
        ldes:timestampPath  prov:generatedAtTime ;
        ldes:versionOfPath  terms:isVersionOf ;
        tree:shape          water-quality-observations:shape ;
        tree:view           water-quality-observations:by-time , water-quality-observations:by-page .

by-page:description  rdf:type       tree:ViewDescription ;
        tree:fragmentationStrategy  ( [ rdf:type                     tree:PaginationFragmentation ;
                                        tree:bidirectionalRelations  "false" ;
                                        tree:memberLimit             "100"
                                      ]
                                    ) .

by-time:description  rdf:type       tree:ViewDescription ;
        tree:fragmentationStrategy  ( [ rdf:type                tree:TimebasedFragmentation ;
                                        tree:fragmentationPath  "http://purl.org/dc/terms/created" ;
                                        tree:memberLimit        "100"
                                      ]
                                    ) .

water-quality-observations:by-page
        rdf:type              tree:Node ;
        tree:viewDescription  by-page:description .

water-quality-observations:shape
        rdf:type           shacl:NodeShape ;
        shacl:deactivated  true ;
        shacl:nodeShape    [ shacl:closed         true ;
                             shacl:propertyShape  []
                           ] .
```

# Caveat Emptor: still to be implemented / extended

- Headers are not passed through this configuration, see [This discussion thread](https://github.com/eclipse-edc/Connector/discussions/2107#discussioncomment-6923928).

- Params are not passed on the HTTPData data type.
  -  Either refactor this sample with HTTPProxy data type
  - Or define params statically on the Provider (forcing us to publish an asset per fragment). See [This discussion thread](https://github.com/eclipse-edc/Connector/discussions/2107#discussioncomment-6914331) on the subject. 
