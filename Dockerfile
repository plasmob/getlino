# The first instruction is what image we want to base our container on
# We Use an official Python runtime as a parent image
FROM python:3.7

# The enviroment variable ensures that the python output is set straight
# to the terminal with out buffering it first
ENV PYTHONUNBUFFERED 1

# Thanks to https://github.com/phusion/baseimage-docker/issues/58
# ENV TERM=linux

# Set for all apt-get install, must be at the very beginning of the Dockerfile.
# Thanks to https://stackoverflow.com/questions/51023312/docker-having-issues-installing-apt-utils
ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update -y
RUN apt-get install -y --no-install-recommends apt-utils
RUN apt-get upgrade -y
RUN pip3 install -e git+https://github.com/plasmob/getlino.git#egg=getlino

# Install sudo package and create a user lino
RUN apt-get install -y sudo
RUN adduser --disabled-password --gecos '' lino
RUN adduser lino sudo
RUN echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

USER lino

RUN sudo getlino configure --batch
RUN sudo -H getlino startsite --batch noi mysite1
