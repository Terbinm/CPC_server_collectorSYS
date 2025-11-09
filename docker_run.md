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
