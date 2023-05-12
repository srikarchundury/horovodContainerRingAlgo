docker build -t spark-master-image docker/master/.
docker build -t spark-worker-image docker/worker/.
docker compose -f cluster-compose.yml -p cluster up