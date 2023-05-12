FROM horovod-spark-pytorch

USER root

# # add these below 2 lines for grouped-allreduce
# RUN sed -i '199s/dist_optimizer_args/dist_optimizer_args,num_groups=1/' /usr/local/lib/python3.9/dist-packages/horovod/spark/torch/remote.py
# ENV HOROVOD_CYCLE_TIME 0.1

ADD . /

WORKDIR /horovod_pytorch

ENTRYPOINT ["tail", "-f", "/dev/null"]