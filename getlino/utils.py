#!python
# Copyright 2019 Rumma & Ko Ltd
# License: BSD (see file COPYING for details)

import os
import stat
import shutil
import grp
import configparser
import subprocess
import click
import collections
from contextlib import contextmanager

from os.path import join

# currently getlino supports only nginx, maybe we might add other web servers
USE_NGINX = True

BATCH_HELP = "Whether to run in batch mode, i.e. without asking any questions.  "\
             "Don't use this on a machine that is already being used."
ASROOT_HELP = "Also install system packages (requires root permissions)"


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
add("presto", "lino-presto", "lino_presto.lib.presto.settings", "https://github.com/lino-framework/presto")
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
    def __init__(self, batch=False, asroot=False):
        self.batch = batch
        self.asroot = asroot
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

    def yes_or_no(self, msg, yes="yY", no="nN", default=True):
        """Ask for confirmation without accepting a mere RETURN."""
        if self.batch:
            return default
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
            with open(pth, 'w+') as fd:
                fd.write(content)
            with self.override_batch(True):
                self.check_permissions(pth, **kwargs)
            return True

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
        if not self.asroot:
            if len(self._system_packages):
                click.echo(
                    "Warning: the following system packages were not installed : {}".format(
                        ' '.join(list(self._system_packages))))
            return

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

