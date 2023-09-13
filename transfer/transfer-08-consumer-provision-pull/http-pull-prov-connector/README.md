# Build the connector with the provisioning extension

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

To build the connector execute the following command:

```bash
./gradlew transfer:transfer-08-consumer-pull-prov:http-pull-prov-connector:build
```

After the build ends, you can verify that the connector jar is created in the directory
[http-pull-connector.jar](http-pull-connector/build/libs/http-pull-connector.jar)