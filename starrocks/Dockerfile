FROM starrocks/allin1-ubuntu:latest

USER root

# curl for OAuth2 token fetch; default-mysql-client for running setup SQL against FE
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl default-mysql-client && \
    rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /starrocks-setup/entrypoint.sh
COPY setup.sql.template /starrocks-setup/setup.sql.template
RUN chmod +x /starrocks-setup/entrypoint.sh

ENTRYPOINT ["/starrocks-setup/entrypoint.sh"]
