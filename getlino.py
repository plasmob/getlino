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
import click
import subprocess, cookiecutter

CONFIG_FILE = os.path.expanduser('~/.getlino.conf')
virtualenvs = '~/.virtualenv'
config = configparser.ConfigParser()

libreoffice_conf = """
[program:libreoffice]
command=libreoffice --accept="socket,host=127.0.0.1,port=8100;urp;" --nologo --headless --nofirststartwizard
user = root
"""

libreoffice_conf_path = '/etc/supervisor/conf.d/libreoffice.conf'


def create_virtualenv(envname):
    virtualenvs_folder = os.path.expanduser(virtualenvs)
    venv_dir = os.path.join(virtualenvs_folder, envname)
    virtualenv.create_environment(venv_dir)
    command = ". {}/{}/bin/activate".format(virtualenvs_folder, envname)
    os.system(command)


def create_libreoffice_conf():
    with open(libreoffice_conf_path, 'w') as configfile:
        configfile.write(libreoffice_conf)

    os.system("sudo service supervisor restart")
    print("Creating a supervisor conf for Libreoffice at {}".format(libreoffice_conf_path))


def install_os_requirements():
    command = """
    sudo apt-get update && \
    sudo apt-get upgrade -y && \ 	
    sudo apt-get install -y \
	git \
	subversion \
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


def install_postgresql(envdir):
    command = """
    sudo apt install postgresql postgresql-contrib 
    """
    os.system(command)
    install("psycopg2-binary", sys_executable=envdir)


def install_mysql(envdir):
    command = """
    sudo apt install mysql-server libmysqlclient-dev python-dev libffi-dev libssl-dev
    """
    os.system(command)
    install("mysqlclient", sys_executable=envdir)


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
          projects_root='/opt/lino',
          projects_prefix='prod_sites',
          arch_dir='/var/backups/lino',
          db_engine='sqlite',
          no_input=False
          ):
    """Setup Lino framework and its dependency on a fresh linux machine.
    """

    if not os.path.exists(CONFIG_FILE):
        print("Creating lino config file at {} ...".format(CONFIG_FILE))
        config_folder_path = os.path.dirname(CONFIG_FILE)
        os.system("sudo mkdir {}".format(config_folder_path))

    full_envdir = os.path.join(os.path.expanduser(virtualenvs), envdir)

    if not no_input:
        if not click.confirm("Backup folder : {} ".format(arch_dir), default=True):
            print("Backup folder :")
            answer = input()
            if len(answer):
                arch_dir = answer
        if not os.path.exists(arch_dir):
            print("Creating lino backup folder {} ...".format(arch_dir))
            os.system("sudo mkdir {}".format(arch_dir))

        if not click.confirm("projects root : {} ".format(projects_root), default=True):
            print("projects root")
            answer = input()
            if len(answer):
                projects_root = answer
        if not click.confirm("projects prefix : {} ".format(projects_prefix), default=True):
            print("projects prefix")
            answer = input()
            if len(answer):
                projects_prefix = answer
        if not os.path.exists(os.path.join(projects_root, projects_prefix)):
            print("Creating lino projects root {} ...".format(os.path.join(projects_root, projects_prefix)))
            os.system("sudo mkdir {}".format(projects_root))
            os.system("sudo mkdir {}".format(os.path.join(projects_root, projects_prefix)))

        if not click.confirm("virtualenv directory : {}".format(full_envdir), default=True):
            print("virtualenv directory")
            answer = input()
            if len(answer):
                full_envdir = answer

    install('virtualenv')
    create_virtualenv(full_envdir)

    if not no_input:
        print('What database engine would use ?')
        print('1) postgresql')
        print('2) mysql')
        print('3) sqlite')
        answer = input()
        if answer in ['1', 1]:
            install_postgresql(full_envdir)
            db_engine = 'postgresql'
        elif answer in ['2', 2]:
            install_mysql(full_envdir)
            db_engine = 'mysql'

    config.read(CONFIG_FILE)
    config['LINO'] = {}
    config['LINO']['projects_root'] = projects_root
    config['LINO']['envdir'] = envdir
    config['LINO']['arch_dir'] = arch_dir
    config['LINO']['projects_prefix'] = projects_prefix
    config['LINO']['db_engine'] = db_engine

    install_os_requirements()
    create_libreoffice_conf()
    install("uwsgi", sys_executable=full_envdir)
    install("cookiecutter", sys_executable=full_envdir)
    install("svn+https://svn.forge.pallavi.be/appy-dev/dev1#egg=appy", sys_executable=full_envdir)

    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)
    return "Lino installation completed."


def startsite(mode='dev',
              reposdir='repositories',
              usergroup='www-data',
              prjname='prjname',
              appname='appname',
              app_git_repo='https://github.com/lino-framework/noi',
              app_package='lino_noi',
              app_settings='lino_noi.lib.noi.settings',
              server_url="https://myprjname.lino-framework.org",
              admin_full_name='Joe Dow',
              admin_email='joe@example.com',
              db_user='lino',
              db_password='1234',
              no_input=False):
    """
    Create a new Lino site.
    """
    config.read(CONFIG_FILE)
    prjdir = config['LINO']['projects_root']
    envdir = config['LINO']['envdir']

    if not no_input:
        if not click.confirm("Project name : {} ".format(prjname), default=True):
            print("Project name :")
            answer = input()
            if len(answer):
                prjname = answer

        if not click.confirm("Application name : {} ".format(appname), default=True):
            print("Application name :")
            answer = input()
            if len(answer):
                appname = answer

        if not click.confirm("Lino application name : {} ".format(app_package), default=True):
            print("Lino application name :")
            answer = input()
            if len(answer):
                app_package = answer

        if not click.confirm("Application git repo  : {} ".format(app_git_repo), default=True):
            print("Application git repo :")
            answer = input()
            if len(answer):
                app_git_repo = answer

        if not click.confirm("Application setting  : {} ".format(app_settings), default=True):
            print("Application setting :")
            answer = input()
            if len(answer):
                app_settings = answer

        if not click.confirm("Server URL  : {} ".format(server_url), default=True):
            print("Server URL :")
            answer = input()
            if len(answer):
                server_url = answer

        if not click.confirm("Admin full name  : {} ".format(admin_full_name), default=True):
            print("Admin full name :")
            answer = input()
            if len(answer):
                admin_full_name = answer

        if not click.confirm("Admin email  : {} ".format(admin_email), default=True):
            print("Admin email :")
            answer = input()
            if len(answer):
                admin_email = answer

        if not click.confirm("db user  : {} ".format(db_user), default=True):
            print("db user :")
            answer = input()
            if len(answer):
                db_user = answer

        if not click.confirm("db password  : {} ".format(db_password), default=True):
            print("db password :")
            answer = input()
            if len(answer):
                db_password = answer

    extra_context = {
        "prjname": prjname,
        "appname": appname,
        "app_git_repo": app_git_repo,
        "app_package": app_package,
        "app_settings": app_settings,
        "use_app_dev": "y",
        "use_lino_dev": "n",
        "server_url": server_url,
        "admin_full_name": admin_full_name,
        "admin_email": admin_email,
        "db_engine": config['LINO']['db_engine'],
        "db_user": db_user,
        "db_password": db_password,
        "db_name": prjname,
        "usergroup": usergroup
    }

    # Database
    print("Database user :")
    answer = input()
    if len(answer):
        arch_dir = answer
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

    print('Create a new production site into {0} using Lino {1} ...'.format(prjdir, appname))
    print('Are you sure? [y/N] ')
    answer = input()
    if answer not in ['Yes', 'y', 'Y']:
        return

    os.system('mkdir {0}'.format(prjdir))
    os.system('cd {0}'.format(prjdir))
    install('virtualenv')
    create_virtualenv(envdir)
    sys_executable = os.path.join(os.path.expanduser(prjdir), envdir)
    install('cookiecutter', sys_executable=sys_executable)
    print(sys_executable)
    command = ". {}/bin/activate".format(sys_executable)
    os.system(command)
    os.system('cd {0}'.format(prjdir))
    os.system("cookiecutter https://github.com/lino-framework/cookiecutter-startsite")
    cookiecutter.main(
        "git@github.com:lino-framework/cookiecutter-startsite.git",
        no_input=True, extra_context=extra_context)


parser = argh.ArghParser()
parser.add_commands([setup, startsite])

if __name__ == '__main__':
    parser.dispatch()
