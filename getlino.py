#!python
# Copyright 2019 Rumma & Ko Ltd
# License: BSD (see file COPYING for details)
#

import os, sys, stat, shutil, grp
import configparser
import virtualenv
import click
import subprocess
import collections
from cookiecutter.main import cookiecutter

DbEngine = collections.namedtuple(
    'DbEngine', ('name', 'apt_packages', 'python_packages'))
KnownApp = collections.namedtuple(
    'KnownApp', ('name', 'settings_module', 'git_repo'))

BATCH_HELP = "Whether to run in batch mode, i.e. without asking any questions.  "\
             "Don't use this on a machine that is already being used."

LIBREOFFICE_SUPERVISOR_CONF = """
[program:libreoffice]
command = libreoffice --accept="socket,host=127.0.0.1,port=8100;urp;" --nologo --headless --nofirststartwizard
user = root
"""


DB_ENGINES = [
    DbEngine('pgsql', "postgresql postgresql-contrib", "psycopg2-binary"),
    DbEngine('mysql', "mysql-server libmysqlclient-dev python-dev libffi-dev libssl-dev", "mysqlclient"),
]

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

CONF_FILES = ['/etc/getlino/getlino.conf', os.path.expanduser('~/.getlino.conf')]
CONFIG = configparser.ConfigParser()
FOUND_CONFIG_FILES = CONFIG.read(CONF_FILES)
DEFAULTSECTION = CONFIG[CONFIG.default_section]


CONFIGURE_OPTIONS = []

def add(spec, default, help, type=None):

    kwargs = dict()
    kwargs.update(help=help)
    if type is not None:
        kwargs.update(type=type)
    o = click.Option([spec], **kwargs)
    o.default = DEFAULTSECTION.get(o.name, default)
    CONFIGURE_OPTIONS.append(o)

# must be same order as in signature of configure command below
add('--projects-root', '/usr/local/lino', 'Base directory for Lino sites')
add('--backups-root', '/var/backups/lino', 'Base directory for backups')
add('--log-root', '/var/log/lino', 'Base directory for log files')
add('--usergroup', 'www-data', "User group for files to be shared with the web server")
add('--supervisor-dir', '/etc/supervisor/conf.d', "Directory for supervisor config files")
add('--db-engine', 'mysql', "Default database engine for new sites.", click.Choice([e.name for e in DB_ENGINES]))
add('--repos-dir', 'repositories', "Default repositories directory for new sites")
add('--env-dir', 'env', "Default virtualenv directory for new sites")
add('--appy/--no-appy', True, "Whether to use appypod and LibreOffice")
add('--redis/--no-redis', True, "Whether to use appypod and LibreOffice")
add('--devtools/--no-devtools', False, "Whether to use developer tools (build docs and run tests)")
add('--once/--no-once', False, "Setup a temporary server for a single test run")
add('--admin-name', 'Joe Dow', "The full name of the server maintainer")
add('--admin-email', 'joe@example.com', "The email address of the server maintainer")


def check_permissions(pth, batch=True, executable=False):
    si = os.stat(pth)

    # check whether group owner is what we want
    usergroup = DEFAULTSECTION.get('usergroup')
    if grp.getgrgid(si.st_gid).gr_name != usergroup:
        if batch or click.confirm("Set group owner for {}".format(pth), default=True):
            shutil.chown(pth, group=usergroup)

    # check access permissions
    mode = stat.S_IRGRP | stat.S_IWGRP
    mode |= stat.S_IRUSR | stat.S_IWUSR
    mode |= stat.S_IROTH
    if stat.S_ISDIR(si.st_mode):
        mode |= stat.S_ISGID | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    elif executable:
        mode |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    imode = stat.S_IMODE(si.st_mode)
    if imode ^ mode:
        msg = "Set mode for {} from {} to {}".format(
            pth, imode, mode)
            # pth, stat.filemode(imode), stat.filemode(mode))
        if batch or click.confirm(msg, default=True):
            os.chmod(pth, mode)


def write_supervisor_conf(filename, content):
    pth = os.path.join(DEFAULTSECTION.get('supervisor_dir'), filename)
    if os.path.exists(pth):
        return False
    with open(pth, 'w') as fd:
        fd.write(content)
    return True


def create_virtualenv(envname):
    #virtualenvs_folder = os.path.expanduser(virtualenvs)
    virtualenv.create_environment(envname)
    command = ". {}/bin/activate".format(envname)
    os.system(command)


def run_in_env(env, cmd):
    """env is the path of the venv"""
    cmd = ". {}/bin/activate && {}".format(env, cmd)
    os.system(cmd)

def install_python_requirements_old():
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


def yes_or_no(msg, yes="yY", no="nN"):
    """Ask for confirmation without accepting a mere RETURN."""
    click.echo(msg, nl=False)
    while True:
        c = click.getchar()
        if c in yes:
            click.echo(" Yes")
            return True
        elif c in no:
            click.echo(" No")
            return False

# This will be decorated below. We cannot use decorators because we define the
# list of options in CONFIGURE_OPTIONS

def configure(ctx, batch,
              projects_root, backups_root, log_root, usergroup,
              supervisor_dir, db_engine, repos_dir, env_dir,
              appy, redis, devtools, admin_name, admin_email):
    """Write a system-wide config file.
    """

    if len(FOUND_CONFIG_FILES) > 1:
        # reconfigure is not yet supported
        raise click.UsageError("Found multiple config files: {}".format(
            FOUND_CONFIG_FILES))

    if not os.access('/root', os.X_OK):
        raise click.UsageError("This action requires root privileges.")

    # confvars = """projects_root backups_root usergroup
    # db_engine repos_dir supervisor_dir env_dir
    # appy redis devtools admin_name admin_email""".split()

    # conf_values = locals()

    for p in CONFIGURE_OPTIONS:
        k = p.name
        # if k == "batch":
        #     continue
        v = locals()[k]
        if batch:
            CONFIG.set(CONFIG.default_section, k, str(v))
        else:
            msg = "{} ({})".format(k, p.help)
            kwargs = dict(default=v)
            if p.type is not None:
                kwargs.update(type=p.type)
            answer = click.prompt(msg, **kwargs)
            # conf_values[k] = answer
            CONFIG.set(CONFIG.default_section, k, str(answer))

    # write system-wide config file
    conffile = CONF_FILES[0]
    if batch or yes_or_no("Write config file {} [y or n] ?".format(
            conffile)):
        print("Config file to use is {}".format(conffile))
        pth = os.path.dirname(conffile)
        if not os.path.exists(pth):
            os.makedirs(pth, exist_ok=True)

        with open(conffile, 'w') as fd:
            CONFIG.write(fd)
        click.echo("Wrote config file " + conffile)
    else:
        raise click.Abort()

params = [
    click.Option(['--batch/--no-batch'], default=False, help=BATCH_HELP)
] + CONFIGURE_OPTIONS
configure = click.pass_context(configure)
configure = click.Command('configure', callback=configure, params=params, help=configure.__doc__)



@click.command()
@click.option('--batch/--no-batch', default=False, help=BATCH_HELP)
@click.pass_context
def setup(ctx, batch):
    """Apply the configuration to set up this machine to become a Lino production server.
    """

    must_restart = set()

    def apt_install(packages):
        cmd = "apt-get install "
        if batch:
            cmd += "-y "
        os.system(cmd + packages)

    pth = DEFAULTSECTION.get('projects_root')
    if os.path.exists(pth):
        check_permissions(pth, batch)
    elif batch or click.confirm("Create projects root directory {}".format(pth), default=True):
        os.makedirs(pth, exist_ok=True)
        check_permissions(pth)

    if batch or click.confirm("Upgrade the system"):
        os.system("apt-get update")
        os.system("apt-get upgrade")

    if batch or click.confirm("Install required system packages"):
        apt_install("git subversion python3 python3-dev python3-setuptools python3-pip supervisor")
        apt_install("nginx")
        apt_install("monit")

        if DEFAULTSECTION.get('devtools'):
            apt_install("tidy swig graphviz sqlite3")

        if DEFAULTSECTION.get('redis'):
            apt_install("redis-server")

        for e in DB_ENGINES:
            if DEFAULTSECTION.get('db_engine') == e.name:
                apt_install(e.apt_packages)
        if DEFAULTSECTION.get('appy'):
            apt_install("libreoffice python3-uno")

            msg = "Create supervisor config for LibreOffice"
            if batch or click.confirm(msg):
                if write_supervisor_conf('libreoffice.conf',
                                         LIBREOFFICE_SUPERVISOR_CONF):
                    must_restart.add('supervisor')
    if len(must_restart):
        msg = "Restart services {}".format(must_restart)
        if batch or click.confirm(msg):
            for srv in must_restart:
                os.system("service {} restart".format(srv))

    click.echo("Lino server setup completed.")



@click.command()
@click.option('--env', default=None,
              help="Install into specified environment")
@click.pass_context
def install_python_requirements(ctx, env):
    """Install Python requirements for Lino.

    If you don't specify env, then getlino will look at the VIRTUAL_ENV
    environment variable. If this also is not set, it supposes that you are in
    a project directory.


    On Travis

    """
    raise Exception("Maybe nonsense!")
    if env is None:
        env = os.environ.get('VIRTUAL_ENV', DEFAULTSECTION.get('env_dir'))
    run_in_env(env, "pip install -U setuptools")
    run_in_env(env, "pip install appy")






@click.command()
@click.argument('appname', metavar="APPNAME", type=click.Choice(APPNAMES))
@click.argument('prjname')
@click.option('--server_url', default='https://myprjname.example.com',
              help="The URL where this site is published")
@click.option('--dev/--no-dev', default=False,
              help="Whether to use development version of the application")
@click.pass_context
def startsite(ctx, appname, prjname,
              dev,server_url,
              admin_full_name='Joe Dow',
              admin_email='joe@example.com',
              db_engine='sqlite',
              db_user='lino',
              db_password='1234',
              conffile=CONF_FILES[0],
              no_input=False):
    """
    Create a new Lino site.

    Arguments:

    APPNAME : The application to run on the new site. 

    PRJNAME : The project name for the new site.

    """ # .format(appnames=' '.join(APPNAMES))
    if len(FOUND_CONFIG_FILES) == 0:
        raise click.UsageError("This server is not yet configured. Did you run `sudo getlino.py configure`?")

    prjpath = os.path.join(DEFAULTSECTION.get('projects_root'), prjname)
    if os.path.exists(prjpath):
        raise click.UsageError("Project directory {} already exists.")

    #raise Exception("Sorry, this command is not yet fully implemented")

    projects_root = DEFAULTSECTION.get('projects_root')
    env_dir = DEFAULTSECTION.get('env_dir')
    db_engine = DEFAULTSECTION.get('db_engine')
    full_envdir = os.path.join(projects_root,prjname,env_dir)
    project_dir = os.path.join(projects_root,prjname)
    repos_dir = DEFAULTSECTION.get('repos_dir')
    full_repos_dir = os.path.join(full_envdir,repos_dir)
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

        if not click.confirm("Lino application name : {} ".format(prjname), default=True):
            print("Lino application name :")
            answer = input()
            if len(answer):
                prjname = answer

            

        #if not click.confirm("Application git repo  : {} ".format(app_git_repo), default=True):
        #    print("Application git repo :")
        #    answer = input()
        #    if len(answer):
        #        app_git_repo = answer

        #if not click.confirm("Application setting  : {} ".format(app_settings), default=True):
        #    print("Application setting :")
        #    answer = input()
        #    if len(answer):
        #        app_settings = answer

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

    app_git_repo = KNOWN_APPS[APPNAMES.index(appname)].git_repo
    app_settings = KNOWN_APPS[APPNAMES.index(appname)].settings_module
    app_package = app_settings.split('.')[0]
    app_package_name = app_git_repo.split('/')[-1]

    install('virtualenv')
    install('cookiecutter')

    extra_context = {
        "prjname": prjname,
        "projects_root":projects_root,
        "reposdir":repos_dir,
        "appname": appname,
        "app_git_repo": app_git_repo,
        "app_package": app_package,
        "app_settings": app_settings,
        "use_app_dev": "y" if dev else 'n',
        "use_lino_dev": "y" if dev else 'n',
        "server_url": server_url,
        "admin_full_name": admin_full_name,
        "admin_email": admin_email,
        "db_engine": db_engine,
        "db_user": db_user,
        "db_password": db_password,
        "db_name": prjname,
        "usergroup": DEFAULTSECTION.get('usergroup')
    }
    usergroup = DEFAULTSECTION.get('usergroup')

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

    print('Creating a new production site into {0} using Lino {1} ...'.format(projects_root, appname))

    #os.system('mkdir {0}'.format(projects_root))
    #os.system('cd {0}'.format(projects_root))
    #sys_executable = os.path.join(os.path.expanduser(projects_root), envdir)
    #print(full_envdir)
    #command = ". {}/bin/activate".format(full_envdir)
    #os.system(command)
    #os.system('cd {0}'.format(projects_root))
    # os.system("cookiecutter https://github.com/lino-framework/cookiecutter-startsite")
    
    cookiecutter(
        "https://github.com/lino-framework/cookiecutter-startsite",
        no_input=True, extra_context=extra_context,output_dir=projects_root)

    create_virtualenv(full_envdir)
    for e in DB_ENGINES:
        if DEFAULTSECTION.get('db_engine') == e.name:
            run_in_env(full_envdir,e.python_packages)
    if not os.path.exists(full_repos_dir):
            os.makedirs(full_repos_dir, exist_ok=True)
    os.chdir(full_repos_dir)

    if dev or True:
        os.system("sudo git clone https://github.com/lino-framework/lino")
        run_in_env(full_envdir,"pip install -e lino")
        os.system("sudo git clone https://github.com/lino-framework/xl")
        run_in_env(full_envdir,"pip install -e xl")

    if app_git_repo:
        os.system("sudo git clone {}".format(app_git_repo))
        run_in_env(full_envdir,"pip install -e {}".format(app_package_name))
    else:
        run_in_env(full_envdir,"pip install {}".format(app_package_name))


    run_in_env(full_envdir, "pip install -U uwsgi")
    run_in_env(full_envdir, "pip install -U svn+https://svn.forge.pallavi.be/appy-dev/dev1#egg=appy")
    os.chdir(project_dir)
    prep_command = "python manage.py prep --noinput"
    print(prep_command)
    run_in_env(full_envdir,prep_command)
    #Testing 
    #cookiecutter(
    #    "/media/khchine5/011113a1-84fe-48ef-826d-4c81de9456731/home/khchine5/PycharmProjects/lino/cookiecutter-startsite",
    #    no_input=True, extra_context=extra_context)

@click.group()
def main():
    pass

main.add_command(configure)
main.add_command(install_python_requirements)
main.add_command(setup)
main.add_command(startsite)

if __name__ == '__main__':
    main()
    # main(auto_envvar_prefix='GETLINO')


