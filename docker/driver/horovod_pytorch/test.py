from pyspark.sql import SparkSession
from pyspark import SparkConf
conf = SparkConf().setAppName('example')
conf.setMaster("spark://spark-master:7077")
spark = SparkSession.builder.config(conf=conf).getOrCreate()
sc=spark.sparkContext
text_file = sc.textFile("/tmp/spark-data/test.py")
counts = text_file.flatMap(lambda line: line.split(" ")).map(lambda word: (word, 1)).reduceByKey(lambda x, y: x + y)
output = counts.collect()
print(output)