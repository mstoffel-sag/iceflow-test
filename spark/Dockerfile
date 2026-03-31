FROM apache/spark:3.5.8-scala2.12-java17-python3-ubuntu

USER root

# Download Iceberg and S3 JARs at build time
RUN MAVEN="https://repo1.maven.org/maven2" && \
    curl -fsSL "$MAVEN/org/apache/iceberg/iceberg-spark-runtime-3.5_2.12/1.10.1/iceberg-spark-runtime-3.5_2.12-1.10.1.jar" \
         -o /opt/spark/jars/iceberg-spark-runtime-3.5_2.12-1.10.1.jar && \
    curl -fsSL "$MAVEN/org/apache/hadoop/hadoop-aws/3.4.3/hadoop-aws-3.4.3.jar" \
         -o /opt/spark/jars/hadoop-aws-3.4.3.jar && \
    curl -fsSL "$MAVEN/com/amazonaws/aws-java-sdk-bundle/1.12.797/aws-java-sdk-bundle-1.12.797.jar" \
         -o /opt/spark/jars/aws-java-sdk-bundle-1.12.797.jar && \
    curl -fsSL "$MAVEN/software/amazon/awssdk/bundle/2.42.24/bundle-2.42.24.jar" \
         -o /opt/spark/jars/aws-sdk-bundle-2.42.24.jar

# Entrypoint: substitute env vars into spark-defaults.conf, then run Thrift Server as PID 1
COPY entrypoint.sh /opt/spark/entrypoint.sh
COPY create_views.sql /opt/spark/create_views.sql
RUN chmod +x /opt/spark/entrypoint.sh

USER spark
ENTRYPOINT ["/opt/spark/entrypoint.sh"]
