import argparse
import os
import subprocess
import sys
from distutils.version import LooseVersion

import numpy as np

import pyspark
import pyspark.sql.types as T
from pyspark import SparkConf
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
if LooseVersion(pyspark.__version__) < LooseVersion('3.0.0'):
    from pyspark.ml.feature import OneHotEncoderEstimator as OneHotEncoder
else:
    from pyspark.ml.feature import OneHotEncoder
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf

import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

import horovod.spark.torch as hvd
from horovod.spark.common.backend import SparkBackend
from horovod.spark.common.store import Store

num_workers = 5
num_epochs = 18
# when equal to num_workers, becomes all-reduce
num_back_passes = 1

parser = argparse.ArgumentParser(description='PyTorch Spark MNIST Example',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--master', default='spark://spark-master:7077',
                    help='spark master to connect to')
parser.add_argument('--num-proc', type=int, default=num_workers,
                    help='number of worker processes for training, default: `spark.default.parallelism`')
parser.add_argument('--limit', type=int, default=20000,
                    help='limit value to data frame to train on smaller datasets')
parser.add_argument('--batch-size', type=int, default=128,
                    help='input batch size for training')
parser.add_argument('--epochs', type=int, default=num_epochs,
                    help='number of epochs to train')
parser.add_argument('--work-dir', default='/opt/spark-data',
                    help='temporary working directory to write intermediate files (prefix with hdfs:// to use HDFS)')
parser.add_argument('--data-dir', default='/opt/spark-data',
                    help='location of the training dataset in the local filesystem (will be downloaded if needed)')


def round_to_batch_size(df, bs):
    c = df.count()
    x = c // bs
    x = c * bs
    return df.limit(x)

if __name__ == '__main__':
    args = parser.parse_args()

    # Initialize SparkSession
    # conf = SparkConf().setAppName('pytorch_spark_mnist').set('spark.sql.shuffle.partitions', '7').set('spark.sql.sources.parallelPartitionDiscovery.threshold', '8').set('spark.sql.sources.parallelPartitionDiscovery.parallelism', '8').set('spark.sql.files.minPartitionNum', '8').set('spark.sql.files.maxPartitionBytes', '128')
    # conf = SparkConf().setAppName('pytorch_spark_mnist').set('spark.sql.sources.parallelPartitionDiscovery.threshold', 1)
    conf = SparkConf().setAppName('pytorch_spark_mnist').set('spark.sql.shuffle.partitions', str(args.num_proc))
    if args.master:
        conf.setMaster(args.master)
    elif args.num_proc:
        conf.setMaster('local[{}]'.format(args.num_proc))
    spark = SparkSession.builder.config(conf=conf).getOrCreate()

    # Setup our store for intermediate data
    store = Store.create(args.work_dir)

    # Download MNIST dataset
    data_url = 'https://www.csie.ntu.edu.tw/~cjlin/libsvmtools/datasets/multiclass/mnist.bz2'
    libsvm_path = os.path.join(args.data_dir, 'mnist.bz2')
    if not os.path.exists(libsvm_path):
        subprocess.check_output(['wget', data_url, '-O', libsvm_path])

    # Load dataset into a Spark DataFrame
    df = spark.read.format('libsvm') \
        .option('numFeatures', '784') \
        .load(libsvm_path)

    df = df.limit(args.limit)
 
    print("overall count - ", df.count())

    # One-hot encode labels into SparseVectors
    encoder = OneHotEncoder(inputCols=['label'],
                            outputCols=['label_vec'],
                            dropLast=False)
    model = encoder.fit(df)
    train_df = model.transform(df)

    # Train/test split
    train_df, test_df = train_df.randomSplit([0.9, 0.1])
    train_df = train_df.repartition(args.num_proc)
    test_df = test_df.repartition(args.num_proc)
    # train_df = round_to_batch_size(train_df, args.batch_size)
    # test_df = round_to_batch_size(test_df, args.batch_size)
    # print(train_df.count(), test_df.count())

    # Define the PyTorch model without any Horovod-specific parameters
    class Net(nn.Module):
        def __init__(self):
            super(Net, self).__init__()
            self.conv1 = nn.Conv2d(1, 10, kernel_size=5)
            self.conv2 = nn.Conv2d(10, 20, kernel_size=5)
            self.conv2_drop = nn.Dropout2d()
            self.fc1 = nn.Linear(320, 50)
            self.fc2 = nn.Linear(50, 10)

        def forward(self, features):
            x = features.float()
            x = F.relu(F.max_pool2d(self.conv1(x), 2))
            x = F.relu(F.max_pool2d(self.conv2_drop(self.conv2(x)), 2))
            x = x.view(-1, 320)
            x = F.relu(self.fc1(x))
            x = F.dropout(x, training=self.training)
            x = self.fc2(x)
            return F.log_softmax(x)

    model = Net()
    optimizer = optim.SGD(model.parameters(), lr=0.01, momentum=0.5)

    loss = nn.NLLLoss()

    # Train a Horovod Spark Estimator on the DataFrame
    backend = SparkBackend(num_proc=args.num_proc,
                           stdout=sys.stdout, stderr=sys.stderr,
                           prefix_output_with_timestamp=True)
    torch_estimator = hvd.TorchEstimator(backend=backend,
                                         store=store,
                                         model=model,
                                         optimizer=optimizer,
                                         backward_passes_per_step = num_back_passes,
                                         loss=lambda input, target: loss(input, target.long()),
                                         input_shapes=[[-1, 1, 28, 28]],
                                         feature_cols=['features'],
                                         label_cols=['label'],
                                         batch_size=args.batch_size,
                                         epochs=args.epochs,
                                         validation=0.1,
                                         verbose=1)

    torch_model = torch_estimator.fit(train_df).setOutputCols(['label_prob'])

    # Evaluate the model on the held-out test DataFrame
    pred_df = torch_model.transform(test_df)

    argmax = udf(lambda v: float(np.argmax(v)), returnType=T.DoubleType())
    pred_df = pred_df.withColumn('label_pred', argmax(pred_df.label_prob))
    evaluator = MulticlassClassificationEvaluator(predictionCol='label_pred', labelCol='label', metricName='accuracy')
    print('Test accuracy:', evaluator.evaluate(pred_df))

    spark.stop()