FROM horovod-spark-pytorch

USER root

# # add these below 2 lines for grouped-allreduce
# RUN sed -i '199s/dist_optimizer_args/dist_optimizer_args,num_groups=1/' /usr/local/lib/python3.9/dist-packages/horovod/spark/torch/remote.py
# ENV HOROVOD_CYCLE_TIME 0.1

COPY start-master.sh /

ENV SPARK_MASTER_PORT 7077
ENV SPARK_MASTER_WEBUI_PORT 8080
ENV SPARK_MASTER_LOG /opt/spark/logs

ENV export PYTHONNOUSERSITE 1

EXPOSE 8080 7077 6066

CMD ["/bin/bash", "/start-master.sh"]