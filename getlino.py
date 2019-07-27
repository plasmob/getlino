#!python
# Copyright 2019 Rumma & Ko Ltd
# License: BSD (see file COPYING for details)

import os
import sys
import stat
import shutil
import grp
import configparser
import subprocess
import virtualenv
import click
import collections
from contextlib import contextmanager
from cookiecutter.main import cookiecutter

from os.path import join

# currently getlino supports only nginx, maybe we might add other web servers
USE_NGINX = True
SITES_AVAILABLE = '/etc/nginx/sites-available'
SITES_ENABLED = '/etc/nginx/sites-enabled'

COOKIECUTTER_URL = "https://github.com/lino-framework/cookiecutter-startsite"
BATCH_HELP = "Whether to run in batch mode, i.e. without asking any questions.  "\
             "Don't use this on a machine that is already being used."

CERTBOT_AUTO_RENEW = """
echo "0 0,12 * * * root python -c 'import random; import time; time.sleep(random.random() * 3600)' && /usr/local/bin/certbot-auto renew" | sudo tee -a /etc/crontab > /dev/null
"""
HEALTHCHECK_SH = """
#!/bin/bash
# generated by getlino
set -e  # exit on error
echo -n "Checking supervisor status: "
supervisorctl status | awk '{if ( $2 != "RUNNING" ) { print "ERROR: " $1 " is not running"; exit 1}}'
echo "... OK"
"""

# note that we double curly braces because we will run format() on this string:
LOGROTATE_CONF = """
{log_root}/{prjname}/lino.log {{
        weekly
        missingok
        rotate 156
        compress
        delaycompress
        notifempty
        create 660 root www-data
        su root www-data
        sharedscripts
}}

"""

MONIT_CONF = """
# generated by getlino
check program status with path /usr/local/bin/healthcheck.sh
    if status != 0 then alert
"""

LIBREOFFICE_SUPERVISOR_CONF = """
# generated by getlino
[program:libreoffice]
command = libreoffice --accept="socket,host=127.0.0.1,port=8100;urp;" --nologo --headless --nofirststartwizard
"""

UWSGI_SUPERVISOR_CONF = """
# generated by getlino
[program:{prjname}-uwsgi]
command = /usr/bin/uwsgi --ini {project_dir}/nginx/{prjname}_uwsgi.ini
user = {usergroup}
"""

LOCAL_SETTINGS = """
# generated by getlino
ADMINS = [ 
  ["{admin_name}", "{admin_email}"] 
]
EMAIL_HOST = 'localhost'
SERVER_EMAIL = 'noreply@{server_domain}'
DEFAULT_FROM_EMAIL = 'noreply@{server_domain}'
STATIC_ROOT = 'env/static'
TIME_ZONE = "{time_zone}"
"""

# Note that the DbEngine.name field must match the Django engine name
DbEngine = collections.namedtuple(
    'DbEngine', ('name', 'apt_packages', 'python_packages'))
DB_ENGINES = [
    DbEngine('postgresql', "postgresql postgresql-contrib", "psycopg2-binary"),
    DbEngine(
        'mysql', "mysql-server libmysqlclient-dev python-dev libffi-dev libssl-dev python-mysqldb", "mysqlclient"),
    DbEngine('sqlite3', "", "")
]

Repo = collections.namedtuple(
    'Repo', ('nickname', 'package_name', 'settings_module', 'git_repo'))
REPOS_DICT = {}
KNOWN_REPOS = []
def add(*args):
    t = Repo(*args)
    KNOWN_REPOS.append(t)
    REPOS_DICT[t.nickname] = t

add("noi", "lino-noi", "lino_noi.lib.noi.settings", "https://github.com/lino-framework/noi")
add("voga", "lino-voga", "lino_voga.lib.voga.settings", "https://github.com/lino-framework/voga")
add("cosi", "lino-cosi", "lino_cosi.lib.cosi.settings", "https://github.com/lino-framework/cosi")
add("avanti", "lino-avanti", "lino_avanti.lib.avanti.settings", "https://github.com/lino-framework/avanti")
add("amici", "lino-amici", "lino_amici.lib.amici.settings", "https://github.com/lino-framework/amici")
add("weleup", "lino-weleup", "lino_weleup.settings", "https://github.com/lino-framework/weleup")
add("welcht", "lino-welcht", "lino_welcht.settings", "https://github.com/lino-framework/welcht")
add("book", "lino-book", "", "https://github.com/lino-framework/book")
add("min2", "", "lino_book.projects.min2.settings", "")
add("lino", "lino", "", "https://github.com/lino-framework/lino")
add("xl", "lino-xl", "", "https://github.com/lino-framework/xl")
add("welfare", "lino-welfare", "", "https://github.com/lino-framework/welfare")

APPNAMES = [a.nickname for a in KNOWN_REPOS if a.settings_module]

CONF_FILES = ['/etc/getlino/getlino.conf',
              os.path.expanduser('~/.getlino.conf')]
CONFIG = configparser.ConfigParser()
FOUND_CONFIG_FILES = CONFIG.read(CONF_FILES)
DEFAULTSECTION = CONFIG[CONFIG.default_section]


class Installer(object):
    def __init__(self, batch=False):
        self.batch = batch
        self._services = set()
        self._system_packages = set()

    def check_overwrite(self, pth):
        """If pth (directory or file ) exists, remove it (after asking for confirmation).
        Return False if it exists and user doesn't confirm.
        """
        if not os.path.exists(pth):
            return True
        if os.path.isdir(pth):
            if self.yes_or_no("Overwrite existing directory {} ? [y or n]".format(pth)):
                shutil.rmtree(pth)
                return True
        else:
            if self.yes_or_no("Overwrite existing file {} ? [y or n]".format(pth)):
                os.remove(pth)
                return True
        return False

    def yes_or_no(self, msg, yes="yY", no="nN"):
        """Ask for confirmation without accepting a mere RETURN."""
        if self.batch:
            return True
        click.echo(msg, nl=False)
        while True:
            c = click.getchar()
            if c in yes:
                click.echo(" Yes")
                return True
            elif c in no:
                click.echo(" No")
                return False

    def must_restart(self, srvname):
        self._services.add(srvname)

    def runcmd(self, cmd, **kw):
        """Run the cmd similar as os.system(), but stop when Ctrl-C."""
        # kw.update(stdout=subprocess.PIPE)
        # kw.update(stderr=subprocess.STDOUT)
        kw.update(shell=True)
        kw.update(universal_newlines=True)
        # subprocess.check_output(cmd, **kw)
        if self.batch or click.confirm("run {}".format(cmd), default=True):
            click.echo(cmd)
            subprocess.run(cmd, **kw)

    def apt_install(self, packages):
        for pkg in packages.split():
            self._system_packages.add(pkg)

    def run_in_env(self, env, cmd):
        """env is the path of the virtualenv"""
        # click.echo(cmd)
        cmd = ". {}/bin/activate && {}".format(env, cmd)
        self.runcmd(cmd)

    def check_permissions(self, pth, executable=False):
        si = os.stat(pth)

        # check whether group owner is what we want
        usergroup = DEFAULTSECTION.get('usergroup')
        if grp.getgrgid(si.st_gid).gr_name != usergroup:
            if self.batch or click.confirm("Set group owner for {}".format(pth),
                                            default=True):
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
            if self.batch or click.confirm(msg, default=True):
                os.chmod(pth, mode)

    @contextmanager
    def override_batch(self, batch):
        old = self.batch
        try:
            self.batch = batch
            yield self
        finally:
            self.batch = old

    def write_file(self, pth, content, **kwargs):
        if self.check_overwrite(pth):
            with open(pth, 'w') as fd:
                fd.write(content)
            with self.override_batch(True):
                self.check_permissions(pth, **kwargs)

    def write_supervisor_conf(self, filename, content):
        self.write_file(
            join(DEFAULTSECTION.get('supervisor_dir'), filename), content)
        self.must_restart('supervisor')

    def setup_database(self, database, user, pwd, db_engine):
        if db_engine == 'sqlite3':
            click.echo("No setup needed for " + db_engine)
        elif db_engine == 'mysql':
            def run(cmd):
                self.runcmd('mysql -u root -p -e "{};"'.format(cmd))
            run("create user '{user}'@'localhost' identified by '{pwd}'".format(**locals()))
            run("create database {database} charset 'utf8'".format(**locals()))
            run("grant all PRIVILEGES on {database}.* to '{user}'@'localhost'".format(**locals()))
        elif db_engine == 'pgsql':
            def run(cmd):
                assert '"' not in cmd
                self.runcmd('sudo -u postgres bash -c "psql -c \"{}\";"'.format(cmd))
            run("CREATE USER {user} WITH PASSWORD '{pwd}';".format(**locals()))
            run("CREATE DATABASE {database};".format(**locals()))
            run("GRANT ALL PRIVILEGES ON DATABASE {database} TO {user};".format(**locals()))
        else:
            click.echo("Warning: Don't know how to setup " + db_engine)

    def run_apt_install(self):
        if len(self._system_packages) == 0:
            return
        # click.echo("Must install {} system packages: {}".format(
        #     len(self._system_packages), ' '.join(self._system_packages)))
        cmd = "apt-get install "
        if self.batch:
            cmd += "-y "
        self.runcmd(cmd + ' '.join(self._system_packages))

    def install_repo(self, repo):
        if not os.path.exists(repo.nickname):
            i.runcmd("git clone --depth 1 -b master {}".format(repo.git_repo))
            i.run_in_env(envdir, "pip install -e {}".format(repo.nickname))
        else:
            click.echo(
                "Don't install {} because the code repository exists.".format(
                    repo.package_name))

    def finish(self):
        self.run_apt_install()
        if len(self._services):
            msg = "Restart services {}".format(self._services)
            if self.batch or click.confirm(msg, default=True):
                with self.override_batch(True):
                    for srv in self._services:
                        self.runcmd("service {} restart".format(srv))


def check_usergroup(usergroup):
    for gid in os.getgroups():
        if grp.getgrgid(gid).gr_name == usergroup:
            return True
    return False


def install(packages, sys_executable=None):
    if sys_executable:
        command = ". {}/bin/activate".format(sys_executable)
        runcmd(command)
        for package in packages.split(' '):
            subprocess.call(
                ["{}/bin/python".format(sys_executable), "-m", "pip", "install", package])
    else:
        subprocess.call([sys.executable, "-m", "pip", "install", packages])


# The configure command will be decorated below. We cannot use decorators
# because we define the list of options in CONFIGURE_OPTIONS because we need
# that list also for asking questions using the help text.

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
add('--prod/--no-prod', True, "Whether this is a production server")
add('--projects-root', '/usr/local/lino', 'Base directory for Lino sites')
add('--local-prefix', 'lino_local', "Prefix for for local server-wide importable packages")
add('--shared-env', '/usr/local/lino/shared/env', "Directory with shared virtualenv")
add('--repositories-root', '', "Base directory for shared code repositories")
add('--webdav/--no-webdav', True, "Whether to enable webdav on new sites.")
add('--backups-root', '/var/backups/lino', 'Base directory for backups')
add('--log-root', '/var/log/lino', 'Base directory for log files')
add('--usergroup', 'www-data', "User group for files to be shared with the web server")
add('--supervisor-dir', '/etc/supervisor/conf.d',
    "Directory for supervisor config files")
add('--db-engine', 'sqlite3', "Default database engine for new sites.",
    click.Choice([e.name for e in DB_ENGINES]))
add('--db-port', 3306, "Default database port for new sites.")
add('--db-host', 'localhost', "Default database host name for new sites.")
add('--env-link', 'env', "link to virtualenv (relative to project dir)")
add('--repos-link', 'repositories', "link to code repositories (relative to virtualenv)")
add('--appy/--no-appy', True, "Whether this server provides appypod and LibreOffice")
add('--redis/--no-redis', True, "Whether this server provides redis")
add('--devtools/--no-devtools', False,
    "Whether this server provides developer tools (build docs and run tests)")
add('--server-domain', 'localhost', "Domain name of this server")
add('--https/--no-https', False, "Whether this server uses secure http")
add('--monit/--no-monit', True, "Whether this server uses monit")
add('--admin-name', 'Joe Dow', "The full name of the server administrator")
add('--admin-email', 'joe@example.com',
    "The email address of the server administrator")
add('--time-zone', 'Europe/Brussels', "The TIME_ZONE to set on new sites")


def configure(ctx, batch,
              prod, projects_root, local_prefix, shared_env, repositories_root,
              webdav, backups_root, log_root, usergroup,
              supervisor_dir, db_engine, db_port, db_host, env_link, repos_link,
              appy, redis, devtools, server_domain, https, monit,
              admin_name, admin_email, time_zone):
    """
    Edit and/or create a configuration file and
    set up this machine to become a Lino production server
    according to the configuration file.
    """

    if len(FOUND_CONFIG_FILES) > 1:
        # reconfigure is not yet supported
        raise click.UsageError("Found multiple config files: {}".format(
            FOUND_CONFIG_FILES))

    i = Installer(batch)

    # write config file. if there is no system-wide file but a user file, write
    # the user file. Otherwise write the system-wide file.
    if len(FOUND_CONFIG_FILES) == 1:
        conffile = FOUND_CONFIG_FILES[0]
        msg = "This will update configuration file {}"
    else:
        conffile = CONF_FILES[0]
        msg = "This will create configuration file {}"

    # before asking questions check whether we will be able to store them
    click.echo(msg.format(conffile))
    if True:  # batch or click.confirm(msg.format(conffile), default=True):
        pth = os.path.dirname(conffile)
        if not os.path.exists(pth):
            os.makedirs(pth, exist_ok=True)

        if not os.access(os.path.dirname(conffile), os.W_OK):
            raise click.ClickException(
                "No write permission for file {}".format(conffile))

        if not os.access(conffile, os.W_OK):
            raise click.ClickException(
                "No write permission for file {}".format(conffile))
    else:
        raise click.Abort()

    for p in CONFIGURE_OPTIONS:
        k = p.name
        v = locals()[k]
        if batch:
            CONFIG.set(CONFIG.default_section, k, str(v))
        else:
            msg = "- {} ({})".format(k, p.help)
            kwargs = dict(default=v)
            if p.type is not None:
                kwargs.update(type=p.type)
            answer = click.prompt(msg, **kwargs)
            # conf_values[k] = answer
            CONFIG.set(CONFIG.default_section, k, str(answer))

    if not i.yes_or_no("Okay to configure your system using above options? [y or n]"):
        raise click.Abort()

    with open(conffile, 'w') as fd:
        CONFIG.write(fd)
    click.echo("Wrote config file " + conffile)

    if DEFAULTSECTION.getboolean('monit'):
        i.write_file('/usr/local/bin/healthcheck.sh', HEALTHCHECK_SH, executable=True)
        i.write_file('/etc/monit/conf.d/lino.conf', MONIT_CONF)

    pth = DEFAULTSECTION.get('projects_root')
    if os.path.exists(pth):
        i.check_permissions(pth)
    elif batch or click.confirm("Create projects root directory {}".format(pth), default=True):
        os.makedirs(pth, exist_ok=True)
        i.check_permissions(pth)

    local_prefix = DEFAULTSECTION.get('local_prefix')
    pth = join(DEFAULTSECTION.get('projects_root'), local_prefix)
    if os.path.exists(pth):
        i.check_permissions(pth)
    elif batch or click.confirm("Create shared settings package {}".format(pth), default=True):
        os.makedirs(pth, exist_ok=True)
    with i.override_batch(True):
        i.check_permissions(pth)
        i.write_file(join(pth, '__init__.py'), '')
    i.write_file(join(pth, 'settings.py'),
                 LOCAL_SETTINGS.format(**DEFAULTSECTION))

    prod = DEFAULTSECTION.getboolean('prod')

    if prod:
        if batch or click.confirm("Upgrade the system", default=True):
            with i.override_batch(True):
                i.runcmd("apt-get update")
                i.runcmd("apt-get upgrade")

    i.apt_install(
        "git subversion python3 python3-dev python3-setuptools python3-pip supervisor")

    if prod:
        i.apt_install("nginx uwsgi-plugin-python3")
        i.apt_install("logrotate")

    if DEFAULTSECTION.getboolean('devtools'):
        i.apt_install("tidy swig graphviz sqlite3")

    if DEFAULTSECTION.getboolean('monit'):
        i.apt_install("monit")

    if DEFAULTSECTION.getboolean('redis'):
        i.apt_install("redis-server")

    for e in DB_ENGINES:
        if DEFAULTSECTION.get('db_engine') == e.name:
            i.apt_install(e.apt_packages)

    if DEFAULTSECTION.getboolean('appy'):
        i.apt_install("libreoffice python3-uno")

    i.finish()

    if DEFAULTSECTION.get('db_engine') == 'mysql':
        i.runcmd("sudo mysql_secure_installation")

    if DEFAULTSECTION.getboolean('appy'):
        i.write_supervisor_conf(
            'libreoffice.conf',
            LIBREOFFICE_SUPERVISOR_CONF.format(**DEFAULTSECTION))

    if DEFAULTSECTION.getboolean('https'):
        if shutil.which("certbot-auto"):
            click.echo("certbot-auto already installed")
        elif batch or click.confirm("Install certbot-auto ?", default=True):
            with i.override_batch(True):
                i.runcmd("wget https://dl.eff.org/certbot-auto")
                i.runcmd("mv certbot-auto /usr/local/bin/certbot-auto")
                i.runcmd("chown root /usr/local/bin/certbot-auto")
                i.runcmd("chmod 0755 /usr/local/bin/certbot-auto")
                i.runcmd("certbot-auto -n")
                i.runcmd("certbot-auto register --agree-tos -m {} -n".format(DEFAULTSECTION.get('admin_email')))
        if batch or click.confirm("Set up automatic certificate renewal ", default=True):
            i.runcmd(CERTBOT_AUTO_RENEW)

    click.echo("Lino server setup completed.")

params = [
    click.Option(['--batch/--no-batch'], default=False, help=BATCH_HELP)
] + CONFIGURE_OPTIONS
configure = click.pass_context(configure)
configure = click.Command('configure', callback=configure,
                          params=params, help=configure.__doc__)



@click.command()
@click.argument('appname', metavar="APPNAME", type=click.Choice(APPNAMES))
@click.argument('prjname')
@click.option('--batch/--no-batch', default=False, help=BATCH_HELP)
@click.option('--dev-repos', default='',
              help="List of packages for which to install development version")
@click.pass_context
def startsite(ctx, appname, prjname, batch, dev_repos):
    """
    Create a new Lino site.

    Arguments:

    APPNAME : The application to run on the new site. 

    SITENAME : The name for the new site.

    """ # .format(appnames=' '.join(APPNAMES))

    if len(FOUND_CONFIG_FILES) == 0:
        raise click.UsageError(
            "This server is not yet configured. Did you run `sudo getlino.py configure`?")

    i = Installer(batch)

    # if os.path.exists(prjpath):
    #     raise click.UsageError("Project directory {} already exists.".format(prjpath))

    prod = DEFAULTSECTION.getboolean('prod')
    projects_root = DEFAULTSECTION.get('projects_root')
    local_prefix = DEFAULTSECTION.get('local_prefix')
    python_path_root = join(projects_root, local_prefix)
    project_dir = join(python_path_root, prjname)
    shared_env = DEFAULTSECTION.get('shared_env')
    admin_name = DEFAULTSECTION.get('admin_name')
    admin_email = DEFAULTSECTION.get('admin_email')
    server_domain = prjname + "." + DEFAULTSECTION.get('server_domain')
    server_url = ("https://" if DEFAULTSECTION.getboolean('https') else "http://") \
                 + server_domain
    db_user = prjname
    db_password = "1234"  # todo: generate random password
    db_engine = DEFAULTSECTION.get('db_engine')
    db_port = DEFAULTSECTION.get('db_port')

    if not i.check_overwrite(project_dir):
        raise click.Abort()

    if not prod and not shared_env:
        raise click.ClickException(
            "Cannot startsite in a development environment without a shared-env!")

    usergroup = DEFAULTSECTION.get('usergroup')

    if check_usergroup(usergroup) or True:
        click.echo("OK you belong to the {0} user group.".format(usergroup))
    else:
        msg = """\
ERROR: you don't belong to the {0} user group.  Maybe you want to run:
sudo adduser `whoami` {0}"""
        raise click.ClickException(msg.format(usergroup))

    app = REPOS_DICT.get(appname, None)
    if app is None:
        raise click.ClickException("Invalid application nickname {}".format(appname))

    if not app.settings_module:
        raise click.ClickException("{} is a library, not an application".format(appname))

    app_package = app.package_name
    # app_package = app.settings_module.split('.')[0]
    repo_nickname = app.git_repo.split('/')[-1]

    context = {}
    context.update(DEFAULTSECTION)
    pip_packages = []
    if app.nickname not in dev_repos:
        pip_packages.append(app.package_name)
    for nickname in ("lino", "xl"):
        if nickname not in dev_repos:
            pip_packages.append(REPOS_DICT[nickname].package_name)
    context.update({
        "prjname": prjname,
        "appname": appname,
        "server_type": "production" if prod else "development",
        "project_dir": project_dir,
        "repo_nickname": repo_nickname,
        "app_package": app_package,
        "app_settings_module": app.settings_module,
        "django_settings_module": "{}.{}.settings".format(local_prefix, prjname),
        "server_domain":server_domain,
        "dev_packages": ' '.join([a.nickname for a in KNOWN_REPOS if a.nickname in dev_repos]),
        "pip_packages": ' '.join(pip_packages),
        # "use_app_dev": app.nickname in dev_repos,
        # "use_lino_dev": linodev,
        "server_url": server_url,
        "db_name": prjname,
        "python_path": projects_root,
        "usergroup": usergroup
    })

    click.echo(
        'Create a new Lino {appname} {server_type} site into {project_dir}'.format(
            **context))

    if not batch:
        shared_env = click.prompt("Shared virtualenv", default=shared_env)
        # if prod:
        #     server_url = click.prompt("Server URL ", default=server_url)
        #     admin_name = click.prompt("Administrator's full name", default=admin_name)
        #     admin_email = click.prompt("Administrator's full name", default=admin_email)
        if db_engine != "sqlite3":

            click.echo(
                "Database settings (for {db_engine} on {db_host}:{db_port}):".format(
                    **context))
            db_user = click.prompt("- user name", default=db_user)
            db_password = click.prompt("- user password", default=db_password)
            # db_port = click.prompt("- port", default=db_port)
            # db_host = click.prompt("- host name", default=db_host)

    if not i.yes_or_no("OK to create {} with above options ? [y or n]".format(project_dir)):
        raise click.Abort()

    context.update({
        "db_user": db_user,
        "db_password": db_password,
    })

    os.umask(0o002)

    # click.echo("cookiecutter context is {}...".format(extra_context))
    click.echo("Running cookiecutter {}...".format(COOKIECUTTER_URL))
    cookiecutter(
        COOKIECUTTER_URL,
        no_input=True, extra_context=context, output_dir=python_path_root)

    if prod:
        logdir = join(DEFAULTSECTION.get("log_root"), prjname)
        if i.check_overwrite(logdir):
            os.makedirs(logdir, exist_ok=True)
        with i.override_batch(True):
            i.check_permissions(logdir)
            os.symlink(logdir, join(project_dir, 'log'))

            # add cron logrotate entry
            i.write_file(
                '/etc/logrotate.d/lino-{}.conf'.format(prjname),
                LOGROTATE_CONF.format(**context))

    os.makedirs(join(project_dir, 'media'), exist_ok=True)

    is_new_env = True
    if shared_env:
        envdir = shared_env
        if os.path.exists(envdir):
            is_new_env = False
            venv_msg = "Update shared virtualenv in {}"
        else:
            venv_msg = "Create shared virtualenv in {}"
    else:
        envdir = join(project_dir, DEFAULTSECTION.get('env_link'))
        venv_msg = "Create local virtualenv in {}"

    if is_new_env:
        if batch or click.confirm(venv_msg.format(envdir), default=True):
            virtualenv.create_environment(envdir)

    if prod:
        if shared_env:
            os.symlink(envdir, join(project_dir, DEFAULTSECTION.get('env_link')))
            static_dir = join(shared_env, 'static')
            if not os.path.exists(static_dir):
                os.makedirs(static_dir, exist_ok=True)

        i.batch = True  # Don't exaggerate with questions. Remove for debugging.

        full_repos_dir = DEFAULTSECTION.get('repositories_root')
        if not full_repos_dir:
            full_repos_dir = join(envdir, DEFAULTSECTION.get('repos_link'))
            if not os.path.exists(full_repos_dir):
                os.makedirs(full_repos_dir, exist_ok=True)
                i.check_permissions(full_repos_dir)

        click.echo("Installing repositories ...".format(full_repos_dir))
        if dev_repos:
            os.chdir(full_repos_dir)
            for nickname in dev_repos.split():
                lib = REPOS_DICT.get(nickname, None)
                if lib is None:
                    raise click.ClickException("Invalid repo nickname {}".format(nckname))
                i.install_repo(lib)
        # else:
        #     i.run_in_env(envdir, "pip install lino")
        #
        # if dev and app.git_repo:
        #     os.chdir(full_repos_dir)
        #     if not os.path.exists(repo_nickname):
        #         i.runcmd("git clone --depth 1 -b master {}".format(app.git_repo))
        #         i.run_in_env(envdir, "pip install -e {}".format(repo_nickname))
        # else:
        #     i.run_in_env(envdir, "pip install {}".format(app_package))

        for e in DB_ENGINES:
            if DEFAULTSECTION.get('db_engine') == e.name:
                i.run_in_env(envdir, "pip install {}".format(e.python_packages))

        i.batch = batch

        if USE_NGINX:

            if batch or click.confirm("Configure nginx", default=True):
                filename = "{}.conf".format(prjname)
                avpth = join(SITES_AVAILABLE, filename)
                enpth = join(SITES_ENABLED, filename)
                with i.override_batch(True):
                    if i.check_overwrite(avpth):
                        shutil.copyfile(join(project_dir, 'nginx', filename), avpth)
                    if i.check_overwrite(enpth):
                        os.symlink(avpth, enpth)
                    i.must_restart("nginx")
                    i.write_supervisor_conf('{}-uwsgi.conf'.format(prjname),
                         UWSGI_SUPERVISOR_CONF.format(**context))
                if DEFAULTSECTION.getboolean('https'):
                    i.runcmd("sudo certbot-auto --nginx -d {} -d www.{}".format(server_domain,server_domain))
                    i.must_restart("nginx")

    os.chdir(project_dir)
    i.run_in_env(envdir, "python manage.py configure")
    i.setup_database(prjname, db_user, db_password, db_engine)
    i.run_in_env(envdir, "python manage.py prep --noinput")

    if prod:
        i.run_in_env(envdir, "python manage.py collectstatic --noinput")

    i.finish()


@click.group()
def main():
    pass

main.add_command(configure)
main.add_command(startsite)

if __name__ == '__main__':
    main()
    # main(auto_envvar_prefix='GETLINO')
