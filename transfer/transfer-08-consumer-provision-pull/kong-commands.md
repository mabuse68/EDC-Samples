# Useful Kong commands

For convenience, we list some useful Kong management commands:
```bash
### Change a service:
curl -X PATCH http://oatmeal:8001/services/ldesservice \
--data url='http://ldes.vsds.odt.imec-apt.be/water-quality-observations/by-time?created=2023-07-13T14:00:27.956Z' -s | jq

### Create a route (this will be created by the provisioner):
curl -X POST http://oatmeal:8001/services/ldesservice/routes \
 --data 'paths[]=/ldesroute' \
 --data 'name=ldesroute' | jq

### List Services, list routes:
curl -X GET http://oatmeal:8001/services -s | jq
curl -X GET http://oatmeal:8001/routes -s | jq

### Delete Services, delete routes:
curl -i -X DELETE http://oatmeal:8001/services/ldesservice
curl -i -X DELETE http://oatmeal:8001/routes/ldesStream
curl -i -X DELETE http://oatmeal:8001/services/ldesservice/routes/ldesStream
```

You now have all instruments you need to play with KONG's API Services and Routes.