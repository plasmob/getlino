#!python
# Copyright 2019 Rumma & Ko Ltd
# License: BSD (see file COPYING for details)
#

import os, sys
import configparser
import virtualenv
import click
import subprocess
import collections
from cookiecutter.main import cookiecutter


CONF_FILES = ['/etc/getlino/getlino.conf', os.path.expanduser('~/.getlino.conf')]
CONFIG = configparser.ConfigParser()
FOUND_CONFIG_FILES = CONFIG.read(CONF_FILES)
DEFAULTSECTION = CONFIG.default_section


DbEngine = collections.namedtuple(
    'DbEngine', ('name', 'apt_packages', 'python_packages'))
KnownApp = collections.namedtuple(
    'KnownApp', ('name', 'settings_module', 'git_repo'))


# virtualenvs = '/opt/lino'

libreoffice_conf_path = '/etc/supervisor/conf.d/libreoffice.conf'
libreoffice_conf = """
[program:libreoffice]
command=libreoffice --accept="socket,host=127.0.0.1,port=8100;urp;" --nologo --headless --nofirststartwizard
user = root
"""


def create_virtualenv(envname):
    #virtualenvs_folder = os.path.expanduser(virtualenvs)
    venv_dir = os.path.join(virtualenvs, envname)
    virtualenv.create_environment(venv_dir)
    command = ". {}/{}/bin/activate".format(virtualenvs, envname)
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


# def install_postgresql(envdir):
#     command = """
#     sudo apt install postgresql postgresql-contrib
#     """
#     os.system(command)
#     install("psycopg2-binary", sys_executable=envdir)
#
#
# def install_mysql(envdir):
#     command = """
#     sudo apt install mysql-server libmysqlclient-dev python-dev libffi-dev libssl-dev
#     """
#     os.system(command)
#     install("mysqlclient", sys_executable=envdir)

DB_ENGINES = [
    DbEngine('pgsql', "postgresql postgresql-contrib", "psycopg2-binary"),
    DbEngine('mysql', "mysql-server libmysqlclient-dev python-dev libffi-dev libssl-dev", "mysqlclient"),
]


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

@click.command()
@click.option('--noinput', default=False, help="Don't ask any questions.")
@click.option('--projects_root', default='/usr/local/lino', help='Base directory for Lino sites.')
@click.option('--backups_root', default='/var/backups/lino', help='Base directory for backups.')
@click.option('--usergroup', default='www-data', help="User group for files to be shared with the web server.")
@click.option('--db_engine', default='mysql',
              type=click.Choice([e.name for e in DB_ENGINES]),
              help="Default database engine for new sites.")
@click.option('--repos_dir', default='repositories', help="Default repositories directory for new sites.")
@click.option('--env_dir', default='env', help="Default virtualenv directory for new sites.")
@click.option('--appy/--no-appy', default=True, help="Whether to use appypod and LibreOffice")
@click.option('--redis/--no-redis', default=True, help="Whether to use appypod and LibreOffice")
@click.option('--devtools/--no-devtools', default=False, help="Whether to use developer tools")
@click.pass_context
def config(ctx, noinput, projects_root, backups_root, usergroup, db_engine, repos_dir, env_dir, appy, redis, devtools):
    """Setup this machine to run as a Lino production server.
    """

    if len(FOUND_CONFIG_FILES):
        # reconfigure is not yet supported
        raise click.UsageError("Found existing config file(s) {}".format(
            FOUND_CONFIG_FILES))

    if not os.access('/root', os.W_OK):
        raise click.UsageError("This action requires root privileges.")

    if False:  # debug
        for p in ctx.command.get_params(ctx):
            print(p.name, CONFIG.get(DEFAULTSECTION, p.name,
                                     fallback="(not set)"), p.help)

    options = locals()

    def setdef(k):
        if not CONFIG.has_option(None, k):
            CONFIG.set(None, k, str(options[k]))

    setdef('projects_root')
    setdef('backups_root')
    setdef('usergroup')
    setdef('db_engine')
    setdef('repos_dir')
    setdef('env_dir')
    setdef('appy')
    setdef('redis')
    setdef('devtools')

    # write conf only if no system-wide config file exists
    conffile = CONF_FILES[0]
    if noinput or click.confirm("Create config file {} ...".format(
            conffile), default=True):
        pth = os.path.dirname(conffile)
        if not os.path.exists(pth):
            os.makedirs(pth, exist_ok=True)

        with open(conffile, 'w') as configfile:
            CONFIG.write(configfile)
        click.echo("Wrote config file " + conffile)
    else:
        raise click.Abort()


@click.command()
@click.option('--noinput', default=False, help="Don't ask any questions.")
@click.pass_context
def setup(ctx, noinput):
    """Setup this machine to run as a Lino production server.
    """

    def apt_install(packages):
        cmd = "apt-get install "
        if noinput:
            cmd += "-y "
        os.system(cmd + packages)

    pth = CONFIG.get(DEFAULTSECTION, 'projects_root')
    if not os.path.exists(pth):
        if noinput or click.confirm("Create projects root directory {} ...".format(pth), default=True):
            os.makedirs(pth, exist_ok=True)

    if noinput or click.confirm("Install system packages"):
        os.system("apt-get update")
        os.system("apt-get upgrade")
        apt_install("git subversion python3 python3-dev python3-setuptools python3-pip supervisor")
        apt_install("nginx")
        apt_install("monit")

        if CONFIG.get(DEFAULTSECTION, 'devtools'):
            apt_install("tidy swig graphviz sqlite3")

        if CONFIG.get(DEFAULTSECTION, 'redis'):
            apt_install("redis-server")

        for e in DB_ENGINES:
            if CONFIG.get(DEFAULTSECTION, 'db_engine') == e.name:
                apt_install(e.apt_packages)

        if CONFIG.get(DEFAULTSECTION, 'appy'):
            apt_install("libreoffice python3-uno")

            msg = "Create supervisor config for LibreOffice at {}".format(
                libreoffice_conf_path)
            if click.confirm(msg):
                with open(libreoffice_conf_path, 'w') as fd:
                    fd.write(libreoffice_conf)
                os.system("service supervisor restart")

    click.echo("Lino server setup completed.")


KNOWN_APPS = [
  KnownApp("noi", "lino_noi.lib.noi.settings", "https://github.com/lino-framework/noi"),
  KnownApp("voga", "lino_voga.lib.voga.settings", "https://github.com/lino-framework/voga"),
  KnownApp("cosi", "lino_cosi.lib.cosi.settings", "https://github.com/lino-framework/cosi"),
  KnownApp("avanti", "lino_avanti.lib.avanti.settings", "https://github.com/lino-framework/avanti"),
  KnownApp("weleup", "lino_weleup.lib.weleup.settings", "https://github.com/lino-framework/weleup"),
  KnownApp("welcht", "lino_voga.lib.voga.settings", "https://github.com/lino-framework/welcht"),
  KnownApp("min2", "lino_book.projects.min2.settings", "https://github.com/lino-framework/book"),
]


APPNAMES = [a.name for a in KNOWN_APPS]

@click.command()
@click.option('--mode', default='dev', type=click.Choice("prod dev".split()), help='Operation mode')
@click.argument('appname', metavar="APPNAME", type=click.Choice(APPNAMES))
@click.argument('prjname')
@click.pass_context
def startsite(ctx, prjname, appname,
              mode,
              reposdir,
              envdir,
              app_git_repo='https://github.com/lino-framework/noi',
              app_package='lino_noi',
              app_settings='lino_noi.lib.noi.settings',
              server_url="https://myprjname.lino-framework.org",
              admin_full_name='Joe Dow',
              admin_email='joe@example.com',
              db_engine='sqlite',
              db_user='lino',
              db_password='1234',
              conffile='/etc/getlino.conf',
              no_input=False):
    """
    Create a new Lino site.

    Arguments:

    APPNAME : The application to run on the new site. 

    PRJNAME : The project name for the new site.

    """ # .format(appnames=' '.join(APPNAMES))
    if len(FOUND_CONFIG_FILES) == 0:
        raise click.UsageError("This server is not yet confgured. Did you run `getlino install`?")

    prjpath = os.path.join(CONFIG.get(DEFAULTSECTION, 'projects_root'), prjname)
    if os.path.exists(prjpath):
        raise click.UsageError("Project directory {} already exists.")

    raise Exception("Sorry, this command is not yet fully implemented")

    projects_root = CONFIG.get(DEFAULTSECTION, 'projects_root')
    # envdir = config['LINO']['envdir']

    if not no_input:
        if not click.confirm("virtualenv directory : {}".format(full_envdir), default=True):
            print("virtualenv directory")
            answer = input()
            if len(answer):
                full_envdir = answer

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

    install('virtualenv')
    full_envdir = os.path.join(projects_root,prjname, envdir)
    create_virtualenv(full_envdir)
    install("uwsgi", sys_executable=full_envdir)
    # install("cookiecutter", sys_executable=full_envdir)
    install("svn+https://svn.forge.pallavi.be/appy-dev/dev1#egg=appy", sys_executable=full_envdir)

    extra_context = {
        "prjname": prjname,
        "projects_root":projects_root,
        "reposdir":reposdir,
        "appname": appname,
        "app_git_repo": app_git_repo,
        "app_package": app_package,
        "app_settings": app_settings,
        "use_app_dev": "y",
        "use_lino_dev": "n",
        "server_url": server_url,
        "admin_full_name": admin_full_name,
        "admin_email": admin_email,
        "db_engine": db_engine,
        "db_user": db_user,
        "db_password": db_password,
        "db_name": prjname,
        "usergroup": CONFIG.get(DEFAULTSECTION, 'usergroup')
    }

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

    print('Create a new production site into {0} using Lino {1} ...'.format(projects_root, appname))
    if not no_input:
        print('Are you sure? [y/N] ')
        answer = input()
        if answer not in ['Yes', 'y', 'Y']:
            return

    os.system('mkdir {0}'.format(projects_root))
    os.system('cd {0}'.format(projects_root))
    #sys_executable = os.path.join(os.path.expanduser(projects_root), envdir)
    install('cookiecutter', sys_executable=full_envdir)
    print(full_envdir)
    command = ". {}/bin/activate".format(full_envdir)
    os.system(command)
    os.system('cd {0}'.format(projects_root))
    # os.system("cookiecutter https://github.com/lino-framework/cookiecutter-startsite")
    
    #cookiecutter(
    #    "https://github.com/lino-framework/cookiecutter-startsite",
    #    no_input=True, extra_context=extra_context)
    #Testing 
    cookiecutter(
        "/media/khchine5/011113a1-84fe-48ef-826d-4c81de9456731/home/khchine5/PycharmProjects/lino/cookiecutter-startsite",
        no_input=True, extra_context=extra_context)

@click.group()
def main():
    pass

main.add_command(config)
main.add_command(setup)
main.add_command(startsite)

if __name__ == '__main__':
    main(auto_envvar_prefix='GETLINO')


# parser = argh.ArghParser()
# parser.add_commands([setup, startsite])
#
# if __name__ == '__main__':
#     parser.dispatch()
