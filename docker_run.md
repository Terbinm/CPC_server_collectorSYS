mongodb啟動命令
docker run -d --name my-mongo -p 27020:27017 -e MONGO_INITDB_ROOT_USERNAME=web_ui -e MONGO_INITDB_ROOT_PASSWORD=hod2iddfsgsrl -e MONGO_INITDB_DATABASE=web_db mongo

mongodb啟動命令(本機路徑版本)
docker run -d --name my-mongo-local `
  -p 27020:27017 `
  -e MONGO_INITDB_ROOT_USERNAME=web_ui `
  -e MONGO_INITDB_ROOT_PASSWORD=hod2iddfsgsrl `
  -e MONGO_INITDB_DATABASE=web_db `
  -v E:\mongodb2_vhtx:/data/db `
  mongo

redis啟動命令(Docker)

docker run -d `
  --name core_redis `
  --restart=always `
  -p 6379:6379 `
  redis:7-alpine `
  redis-server --appendonly yes --requirepass redis_password


rabbitmq啟動命令(Docker)

docker run -d `
  --hostname core_rabbitmq `
  --name core_rabbitmq `
  --restart=always `
  -p 5672:5672 `
  -p 15672:15672 `
  -e RABBITMQ_DEFAULT_USER=admin `
  -e RABBITMQ_DEFAULT_PASS=rabbitmq_admin_pass `
  -e RABBITMQ_DEFAULT_VHOST=/ `
  rabbitmq:3.12-management

