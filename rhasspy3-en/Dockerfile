FROM rhasspy/rhasspy3-addon-base:en-0.0.1 as build

COPY rhasspy3_configuration.yaml /app/config/configuration.yaml
COPY run.sh /app/
RUN chmod a+x /app/run.sh

# HTTP
EXPOSE 13331

ENTRYPOINT ["bash", "/app/run.sh"]
