./run_program_in_driver.sh mnist.py > comp/1pass-reduce-18-out &

processId1=$!  ## And here we got the procees Id
echo "started $processId1"

./record_docker_stats.sh > comp/1pass-18-reduce.csv &

processId2=$!  ## And here we got the procees Id
echo "started $processId2"

while [ ! -z "$( ps -ef | grep $processId1 | grep -v grep )" ]
do
    echo "running $processId1"
done

echo "killing $processId2"

kill -9 $processId2;