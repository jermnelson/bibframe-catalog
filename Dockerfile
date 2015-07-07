# Dockerfile for BIBCAT
FROM ubuntu:14.04.2
MAINTAINER Jeremy Nelson <jermnelson@gmail.com>

# Set environmental variables

# Update Ubuntu and install Python 3 setuptools, git and other
# packages
RUN apt-get update && apt-get install -y && \
  apt-get install -y python3-setuptools &&\
  apt-get install -y git &&\
  apt-get install -y  nginx 


# Retrieve latest master branch of bibframe-catalog project on 
# github.coma

RUN git clone https://github.com/jermnelson/bibframe-catalog.git /opt/bibcat && \
    cd /opt/bibcat && \
    git checkout -b development && \
    git pull origin development
#&& \
#    pip3 install -r requirements.txt

WORKDIR /opt/bibcat
# Run application with uwsgi socket
CMD uwsgi -s /tmp/bibcat-uwsgi.sock -w runserver:app --chmod-socket=666 
