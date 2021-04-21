ARG BUILD_FROM
FROM $BUILD_FROM

LABEL maintainer="Michael Hansen <mike@rhasspy.org>"

ENV LANG C.UTF-8

ENV CONFIG_PATH /data/options.json

COPY run.sh /

ENTRYPOINT ["/run.sh"]
