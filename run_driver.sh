docker build -t spark-driver-image docker/driver/.
docker compose -f driver-compose.yml -p driver up