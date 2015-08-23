#Dockerfile for BIBCAT
FROM python:3.4.3
MAINTAINER Jeremy Nelson <jermnelson@gmail.com>

# Set environmental variables
ENV BIBCAT_HOME /opt/bibcat
ENV NGINX_HOME /etc/nginx

# Update Ubuntu and install Python 3 setuptools, git and other
# packages
RUN apt-get update && apt-get install -y && \
  apt-get install -y python3-setuptools &&\
  apt-get install -y git &&\
  apt-get install -y  nginx &&\
  apt-get install -y python3-pip


# Retrieve latest master branch of bibframe-catalog project on 
# github.coma
RUN git clone https://github.com/jermnelson/bibframe-catalog.git $BIBCAT_HOME \
    && cd $BIBCAT_HOME \
    && git checkout -b development \
    && git pull origin development \
    && pip3 install -r requirements.txt \
    && python3 make-config.py create \
    && rm $NGINX_HOME/sites-enabled/default \
    && cp bibcat.conf $NGINX_HOME/sites-available/bibcat.conf \
    && ln -s $NGINX_HOME/sites-available/bibcat.conf $NGINX_HOME/sites-enabled/bibcat.conf
    
EXPOSE 80
WORKDIR $BIBCAT_HOME
# Run application with uwsgi socket with nginx
COPY docker-entrypoint.sh $BIBCAT_HOME/
ENTRYPOINT ["./docker-entrypoint.sh"]
