# The first instruction is what image we want to base our container on
# We Use an official Python runtime as a parent image
FROM python:3.7

# The enviroment variable ensures that the python output is set straight
# to the terminal with out buffering it first
ENV PYTHONUNBUFFERED 1

# create root directory for our project in the container
RUN mkdir /getlino

# Set the working directory to /getlino
WORKDIR /getlino

ADD getlino.py /getlino/
# For testing
#COPY cookiecutter-startsite /usr/local/cookiecutter-startsite

RUN apt-get update && apt-get install -y --no-install-recommends apt-utils

# Install sudo package.
RUN apt-get install sudo

RUN adduser --disabled-password --gecos '' docker
RUN adduser docker sudo
RUN echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

USER docker

# this is where I was running into problems with the other approaches
RUN sudo apt-get update 

#RUN pip3 install getlino
RUN sudo pip3 install click argh virtualenv cookiecutter setuptools uwsgi
RUN sudo python getlino.py getlino.py configure -n
RUN sudo python getlino.py getlino.py setup -n
RUN sudo python getlino.py startsite -n