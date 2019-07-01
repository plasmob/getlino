#!python
# Copyright 2019 Rumma & Ko Ltd
# License: BSD (see file COPYING for details)
#
# Create a new Lino production site on this server
# This is meant as template for a script to be adapted to your system.
# This is not meant to be used as is.

from __future__ import print_function
from __future__ import absolute_import
import os, sys, argh
import configparser
import virtualenv
import subprocess

CONFIG_FILE = os.path.expanduser('~/.getlino.conf')
virtualenvs = '~./virtualenv'
config = configparser.ConfigParser()


def create_virtualenv(envname):
    virtualenvs_folder = os.path.expanduser(virtualenvs)
    venv_dir = os.path.join(virtualenvs_folder, envname)
    virtualenv.create_environment(venv_dir)
    command = ". {}/{}/bin/activate".format(virtualenvs_folder, envname)
    os.system(command)


def install_os_requirements():
    command = """
    sudo apt-get update && \
    sudo apt-get upgrade -y && \ 	
    sudo apt-get install -y \
	git \
	python3 \
	python3-dev \
	python3-setuptools \
	python3-pip \
	nginx \
	supervisor \
	libreoffice \
	python3-uno \
	tidy \
	swig \
	graphviz \
	sqlite3 && \
	sudo apt-get install redis-server ; redis-server &
	libreoffice '--accept=socket,host=127.0.0.1,port=8100;urp;headless;' & 
    """
    os.system(command)


def install_python_requirements():
    command = """
    pip3 install -U pip setuptools
    pip3 install -e svn+https://svn.forge.pallavi.be/appy-dev/dev1#egg=appy
    pip3 install uwsgi
    """
    os.system(command)


def install(packages, sys_executable=None):
    if sys_executable:
        command = ". {}/bin/activate".format(sys_executable)
        os.system(command)
        for package in packages.split(' '):
            subprocess.call(["{}/bin/python".format(sys_executable), "-m", "pip", "install", package])
    else:
        subprocess.call([sys.executable, "-m", "pip", "install", packages])


# @dispatch_command
# @arg('-mode',help="Prod or Dev mode")
# @arg('-projects_root',  default='/usr/local/lino',help="The path of the main project folder")
# @arg('-prjname',help="The project name")
# @arg('-appname',help="The application name")
# @arg('-projects_prefix',help="The project prefix")
# @arg('-arch_dir',help="The path of the backups folder")
# @arg('-envdir',  help="The name of the python virtualenv")
# @arg('-reposdir', help="The name of the repositories")
# @arg('-usergroup', help="The name of the usergroup")
def setup(envdir='env',
          projects_root='/usr/local/lino',
          arch_dir='/var/backups/lino',
          ):
    """Setup Lino framework and its dependency on a fresh linux machine.
    """

    if not os.path.exists(CONFIG_FILE):
        print("Creating lino config file at {} ...".format(CONFIG_FILE))
        config_folder_path = os.path.dirname(CONFIG_FILE)
        os.system("sudo mkdir {}".format(config_folder_path))

    if not os.path.exists(arch_dir):
        print("Creating lino backup folder {} ...".format(arch_dir))
        os.system("sudo mkdir {}".format(arch_dir))

    if not os.path.exists(projects_root):
        print("Creating lino projects root {} ...".format(projects_root))
        os.system("sudo mkdir {}".format(projects_root))

    config.read(CONFIG_FILE)
    config['LINO'] = {}
    config['LINO']['projects_root'] = projects_root
    config['LINO']['envdir'] = envdir
    config['LINO']['arch_dir'] = arch_dir

    prjdir = os.path.join(projects_root, envdir)
    install('virtualenv')
    create_virtualenv(envdir)
    install_os_requirements()
    # sys_executable = os.path.join(os.path.expanduser(virtualenvs), envdir)
    # install('cookiecutter setuptools uwsgi', sys_executable=sys_executable)

    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)
    return "Lino installating completed."


def startsite(mode='dev',
              projects_root='/usr/local/lino',
              projects_prefix='prod_sites',
              arch_dir='/var/backups/lino',
              envdir='env', reposdir='repositories',
              usergroup='www-data',
              prjname='prjname',
              appname='appname'):
    """
    Create a new Lino site.
    :param mode:
    :param projects_root:
    :param projects_prefix:
    :param arch_dir:
    :param envdir:
    :param reposdir:
    :param usergroup:
    :param prjname:
    :param appname:
    :return:
    """
    out = subprocess.Popen(['groups | grep ' + usergroup], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
    stdout, stderr = out.communicate()
    if str(stdout):
        print("OK you belong to the {0} user group.".format(usergroup))
    else:
        print("ERROR: you don't belong to the {0} user group.".format(usergroup))
        print("Maybe you want to run:")
        # echo sudo usermod -a -G $USERGROUP `whoami`
        print("echo sudo adduser `whoami` {0}".format(usergroup))
        return

    if not os.path.exists(projects_root):
        print("Oops, {0} does not exist.".format(projects_root))
        return ''

    prjdir = os.path.join(projects_root, prjname)
    if os.path.exists(prjdir):
        print("Oops, a directory {0} exists already. Delete it yourself if you dare!".format(prjdir))
        return
    print('Create a new production site into {0} using Lino {1} ...'.format(prjdir, appname))
    print('Are you sure? [y/N] ')
    answer = input()
    if answer not in ['Yes', 'y', 'Y']:
        return

    os.system('mkdir {0}'.format(prjdir))
    os.system('cd {0}'.format(prjdir))
    install('virtualenv')
    create_virtualenv(prjdir, envdir)
    sys_executable = os.path.join(os.path.expanduser(prjdir), envdir)
    install('cookiecutter', sys_executable=sys_executable)
    print(sys_executable)
    command = ". {}/bin/activate".format(sys_executable)
    os.system(command)
    os.system('cd {0}'.format(prjdir))
    os.system("cookiecutter https://github.com/lino-framework/cookiecutter-startsite")


parser = argh.ArghParser()
parser.add_commands([startsite, setup])

if __name__ == '__main__':
    parser.dispatch()
