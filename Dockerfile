# Dockerfile for BIBCAT
FROM ubuntu:14.04.2
MAINTAINER Jeremy Nelson <jermnelson@gmail.com>

# Set environmental variables

# Update Ubuntu and install Python 3 setuptools, git and other
# packages
RUN apt-get update && apt-get install -y \
  python3-setuptools \
  git \
  nginx 

ADD . /catalog
WORKDIR /opt/bibcat

# Retrieve latest master branch of bibframe-catalog project on 
# github.com
RUN git pull origin master

# Install all Python dependencies with pip
RUN pip install -r requirements.txt

# Run application with uwsgi socket
CMD uwsgi -s /tmp/bibcat-uwsgi.sock -w runserver:app --chmod-socket=666 
