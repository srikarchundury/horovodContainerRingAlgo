FROM horovod-spark-pytorch

USER root

# # add these below 2 lines for grouped-allreduce
# RUN sed -i '199s/dist_optimizer_args/dist_optimizer_args,num_groups=1/' /usr/local/lib/python3.9/dist-packages/horovod/spark/torch/remote.py
# ENV HOROVOD_CYCLE_TIME 0.1

COPY start-worker.sh /

ENV SPARK_WORKER_WEBUI_PORT 8081
ENV SPARK_WORKER_LOG /opt/spark/logs
ENV SPARK_MASTER "spark://spark-master:7077"

ENV export PYTHONNOUSERSITE 1

EXPOSE 8081

CMD ["/bin/bash", "/start-worker.sh"]