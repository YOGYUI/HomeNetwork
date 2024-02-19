# syntax=docker/dockerfile:1
FROM alpine:latest
LABEL maintainer="YOGYUI lee2002w@gmail.com"

# install required packages
RUN apk add --update --no-cache \
    bash curl nano vim wget git openrc \
    gcc openssl-dev libffi-dev python3-dev musl-dev linux-headers \
    python3 py3-pip  

# create directory and copy source code
RUN mkdir -p /repos/yogyui/homenetwork/hillstate-gwanggyosan
COPY . /repos/yogyui/homenetwork/hillstate-gwanggyosan
WORKDIR /repos/yogyui/homenetwork/hillstate-gwanggyosan

# expose default web server port (todo: dynamic expose?)
EXPOSE 7929

# create & activate python virtual environment, install python requirements
RUN /bin/bash -c "source ./bootstrap.sh; pip3 install -r ./requirements.txt"

# activate python venv and launch application
CMD /bin/bash -c "source ./activate.sh; python3 app.py; /bin/bash"
