# Configure a connector with provisioning extensions

We configure the Provider connector with the extension that enables HTTP Provisioning.

HTTP Provisioning works this way:
* A connector is built with HTTP Provisioning extension
* The connector's  ```provisioner ``` property is associated to a ```dataAddress``` type. Every ```transferRequest``` for that dataAddress type will trigger provisioning.
* A consumer sends a ```TransferRequest``` with the triggering ```dataAddress``` type, the provider sends a provision request to an external service that implements provision logic (called very immaginatively: Provisioner Service)
* The Provisioner Service does his provisioning stuff, it is expected that it will return an HTTP endpoint where the dataTransfer request will find the data to a callback on the Provider connector.
* The Trasnfer goes on, the ```dataAddress``` of the request points now to the porvisioned data source.

 The connector configuration file can be found here: [provider-configuration.properties](http-pull-prov-provider/provider-configuration.properties)

 ## Properties
 > [!NOTE] The host where both the connector and the provisioner service run must have a resolvable hostname. The callback system doesn't work with ```localhost```.
 
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
Each transfer that involves a source of ```HTTPData``` type will be a provisioned one (i.e., the address of the data source is provided by the Provisioner Service)