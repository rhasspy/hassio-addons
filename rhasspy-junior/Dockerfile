FROM rhasspy/junior-hass

RUN apt-get update && \
    apt-get install --yes --no-install-recommends \
    libasound2-plugins

COPY run.sh /
RUN chmod a+x /run.sh

ENTRYPOINT ["bash", "/run.sh"]
