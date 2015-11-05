#!/usr/bin/env python2
"""Aptly mirror/snapshot managment automation."""
import argparse
import datetime
import logging
import subprocess
import sys

import yaml


def init_hypothesis():
    try:  # pragma: no cover:w
        import os
        if 'HYPOTHESIS_PROFILE' in os.environ:
            from hypothesis import Settings
            Settings.register_profile("ci", Settings(
                max_examples=10000
            ))
            Settings.load_profile(os.getenv(u'HYPOTHESIS_PROFILE', 'default'))
    except (ImportError, AttributeError):  # pragma: no cover
        pass


def get_logger():
    """Get the logger.

    :rtype: logging.Logger"""
    return logging.getLogger("pyaptly")

lg = get_logger()
init_hypothesis()


def iso_first_week_start(iso_year, tzinfo=None):
    """The gregorian calendar date of the first day of the given ISO year

    :param iso_year: Year to find the date of the first week.
    :type  iso_year: int"""
    fourth_jan = datetime.datetime(iso_year, 1, 4, tzinfo=tzinfo)
    delta = datetime.timedelta(fourth_jan.isoweekday() - 1)
    return fourth_jan - delta


def iso_to_gregorian(iso_year, iso_week, iso_day, tzinfo=None):
    """Gregorian calendar date for the given ISO year, week and day

    :param iso_year: ISO year
    :type  iso_year: int
    :param iso_week: ISO week
    :type  iso_week: int
    :param  iso_day: ISO day
    :type   iso_day: int"""
    year_start = iso_first_week_start(iso_year, tzinfo)
    return year_start + datetime.timedelta(
        days=iso_day - 1,
        weeks=iso_week - 1
    )


def time_remove_tz(time):
    """Convert a :py:class`datetime.time` to :py:class`datetime.time` to
    without tzinfo.

    :param time: Time to convert
    :type  time: :py:class:`datetime.time`
    :rtype:      :py:class:`datetime.time`
    """
    return datetime.time(
        hour        = time.hour,
        minute      = time.minute,
        second      = time.second,
        microsecond = time.microsecond,
    )


def time_delta_helper(time):
    """Convert a :py:class`datetime.time` to :py:class`datetime.datetime` to
    calculate deltas

    :param time: Time to convert
    :type  time: :py:class:`datetime.time`
    :rtype:      :py:class:`datetime.datetime`
    """
    return datetime.datetime(
        year        = 2000,
        month       = 1,
        day         = 1,
        hour        = time.hour,
        minute      = time.minute,
        second      = time.second,
        microsecond = time.microsecond,
        tzinfo      = time.tzinfo,
    )


def date_round_weekly(date, day_of_week=1, time=None):
    """Round datetime back (floor) to a given the of the week.

    THIS FUNCTION IGNORES THE TZINFO OF TIME and assumes it is the same tz as
    the date.

    :param        date: Datetime object to round
    :type         date: :py:class:`datetime.datetime`
    :param day_of_week: ISO day of week: monday is 1 and sunday is 7
    :type  day_of_week: int
    :param        time: Roundpoint in the day (tzinfo ignored)
    :type         time: :py:class:`datetime.time`
    :rtype:             :py:class:`datetime.datetime`"""
    if time:
        time         = time_remove_tz(time)
    else:
        time         = datetime.time(hour=0, minute=0)

    delta            = datetime.timedelta(
        days         = day_of_week - 1,
        hours        = time.hour,
        minutes      = time.minute,
        seconds      = time.second,
        microseconds = time.microsecond,
    )
    raster_date  = date - delta
    iso = raster_date.isocalendar()
    rounded_date = iso_to_gregorian(iso[0], iso[1], 1, date.tzinfo)
    return rounded_date + delta


def date_round_daily(date, time=None):
    """Round datetime to day back (floor) to the roundpoint (time) in the day

    THIS FUNCTION IGNORES THE TZINFO OF TIME and assumes it is the same tz as
    the date.

    :param date: Datetime object to round
    :type  date: :py:class:`datetime.datetime`
    :param time: Roundpoint in the day (tzinfo ignored)
    :type  time: :py:class:`datetime.time`
    :rtype:      :py:class:`datetime.datetime`"""
    if time:
        time         = time_remove_tz(time)
    else:
        time         = datetime.time(hour=0, minute=0)
    delta            = datetime.timedelta(
        hours        = time.hour,
        minutes      = time.minute,
        seconds      = time.second,
        microseconds = time.microsecond,
    )
    raster_date  = date - delta
    rounded_date = datetime.datetime(
        year     = raster_date.year,
        month    = raster_date.month,
        day      = raster_date.day,
        tzinfo   = raster_date.tzinfo
    )
    return rounded_date + delta


def call_output(args, input_=None):
    p = subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    output, err = p.communicate(input_)
    if p.returncode != 0:
        raise subprocess.CalledProcessError(
            p.returncode,
            args,
        )
    return output


class Command(object):
    def __init__(self, cmd):
        self.cmd = cmd
        self._requires = set()
        self._provides = set()
        self._finished = None

    def append(self, argument):
        assert str(argument) == argument
        self.cmd.append(argument)

    def require(self, type_, identifier):
        assert type_ in ('snapshot', 'mirror', 'repo', 'any')
        self._requires.add((type_, identifier))

    def provide(self, type_, identifier):
        assert type_ in ('snapshot', 'mirror', 'repo', 'publish')
        self._provides.add((type_, identifier))

    def execute(self):
        if self._finished is not None:
            return self._finished

        lg.debug('Running command: %s', ' '.join(self.cmd))
        self._finished = subprocess.check_call(self.cmd)

        return self._finished

    def __str__(self):
        return " ".join(self.cmd)

    @staticmethod
    def order_commands(commands, has_dependency_cb=lambda: False):
        # Filter out any invalid entries.. TODO: Should be done
        # somewhere else...
        commands = [c for c in commands if c]

        lg.debug('Ordering commands: %s', [
            str(cmd) for cmd in commands
        ])

        have_requirements = set()
        scheduled  = []

        something_changed = True
        while something_changed:
            something_changed = False

            for cmd in commands:
                if cmd in scheduled:
                    continue

                can_schedule = True
                for req in cmd._requires:
                    if req not in have_requirements:
                        # No command providing our dependency.. Let's see if
                        # it's already otherwise fulfilled
                        if not has_dependency_cb(req):
                            can_schedule = False
                            # Break out of the requirements loop, as the
                            # command cannot be scheduled anyway.
                            break

                if can_schedule:
                    scheduled.append(cmd)
                    have_requirements = have_requirements.union(cmd._provides)
                    something_changed = True

        unresolved = [
            cmd
            for cmd in commands
            if cmd not in scheduled
        ]

        if len(unresolved) > 0:
            raise ValueError('Commands with unresolved deps: %s', [
                str(cmd) for cmd in unresolved
            ])

        # Just one last verification before we commence
        scheduled_set = set([cmd for cmd in scheduled])
        incoming_set  = set([cmd for cmd in commands])
        assert incoming_set == scheduled_set

        lg.info('Reordered commands: %s', [
            str(cmd) for cmd in scheduled
        ])

        return scheduled


class SystemStateReader(object):
    def __init__(self):
        self.gpg_keys  = set()
        self.mirrors   = set()
        self.snapshots = set()
        self.publishes = set()

    def read(self):
        self.read_gpg()
        self.read_mirror()
        self.read_snapshot()
        self.read_publishes()

    def read_gpg(self):
        self.gpg_keys = set()
        data = call_output([
            "gpg",
            "--no-default-keyring",
            "--keyring", "trustedkeys.gpg",
            "--list-keys",
            "--with-colons"
        ])
        lg.debug('GPG returned: %s', data)
        for line in data.split("\n"):
            field = line.split(":")
            if field[0] == "pub":
                key = field[4]
                key_short = key[8:]
                self.gpg_keys.add(key)
                self.gpg_keys.add(key_short)

    def read_publishes(self):
        self.mirrors = set()
        self.read_aptly_list("publish", self.publishes)

    def read_mirror(self):
        self.mirrors = set()
        self.read_aptly_list("mirror", self.mirrors)

    def read_snapshot(self):
        self.snapshots = set()
        self.read_aptly_list("snapshot", self.snapshots)

    def read_aptly_list(self, type_, list_):
        data = call_output([
            "aptly", type_, "list", "-raw"
        ])
        lg.debug('Aptly returned %s: %s', type_, data)
        for line in data.split("\n"):
            list_.add(line.strip())

    def has_dependency(self, dependency):
        type_, name = dependency

        if type_ == 'mirror':
            return name in self.mirrors
        elif type_ == 'snapshot':
            return name in self.snapshots
        elif type_ == 'gpg_key':
            return name in self.gpg_keys
        else:
            raise ValueError("Unknown dependency to resolve: %s" % dependency)


state = SystemStateReader()


def main(argv=None):
    """Called by command-line, defines parsers and executes commands"""
    if not argv:  # pragma: no cover
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description='Manage aptly')
    parser.add_argument(
        '--config',
        '-c',
        help='Yaml config file defining mirrors and snapshots',
        type=str
    )
    parser.add_argument(
        '--debug',
        '-d',
        help='Enable debug output',
        action='store_true',
    )
    subparsers = parser.add_subparsers()
    mirror_parser = subparsers.add_parser(
        'mirror',
        help='manage aptly mirrors'
    )
    mirror_parser.set_defaults(func=mirror)
    mirror_parser.add_argument(
        'task',
        type=str,
        choices=['create', 'drop', 'update']
    )
    mirror_parser.add_argument(
        'mirror_name',
        type=str,
        nargs='?',
        default='all'
    )
    snapshot_parser = subparsers.add_parser(
        'snapshot',
        help='manage aptly snapshots'
    )
    snapshot_parser.set_defaults(func=snapshot)
    snapshot_parser.add_argument('task', type=str, choices=['create', 'drop'])
    snapshot_parser.add_argument(
        'snapshot_name',
        type=str,
        nargs='?',
        default='all'
    )
    # TODO implement this
    # publish_parser = subparsers.add_parser(
    #     'publish',
    #     help='manage aptly publish endpoints'
    # )

    args = parser.parse_args(argv)
    root = logging.getLogger()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(logging.CRITICAL)
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    lg.debug("Args: %s", vars(args))

    with open(args.config, 'r') as cfgfile:
        cfg = yaml.load(cfgfile)
    state.read()

    # run function for selected subparser
    args.func(cfg, args)


def expand_timestamped_name(name, timestamp_config, date=None):
    """Expands the given name by adding a timestamp.

    The contents of the timestamp is configured by the given timestamp_config
    dict, which MUST contain a "time" key, and MAY contain a "repeat-weekly"
    key.

    If the key "repeat-weekly" is given, it is expected to contain a
    three-letter weekday name (mon, tue, thu, ...). The "time" key is expected
    to be a 24 hour HH:MM time specification.

    Timestamps are rounded down to the nearest time as specified (which may be
    on the previous day. If repeat-weekly is specified, it is rounded down
    (back in time) to the given weekday.)

    The name parameter may be a simple string. If it contains the marker "%T",
    then this placeholder will be replaced by the timestamp. If it does NOT
    contain that marker, then nothing happens (and the timestamp_config is not
    evaluated at all)

    If a datetime object is given as third parameter, then it is used to
    generate the timestamp. If it is omitted, the current date/time is used.

    Example:
    >>> expand_timestamped_name(
    ...     'foo-%T',
    ...     {'timestamp': {'time': '00:00'}},
    ...     datetime.datetime(2015,10,7, 15,30)  # A Wednesday
    ... )
    foo-20151007T0000Z

    >>> expand_timestamped_name(
    ...     'foo-%T',
    ...     {'timestamp': {'time': '00:00', 'repeat-weekly': 'mon'}},
    ...     datetime.datetime(2015,10,8, 15,30)  # A Thursday
    ... )
    foo-20151005T0000Z

    >>> expand_timestamped_name(
    ...     'foo',  # No %T placeholder, timestamp info is ignored
    ...     {'timestamp': {'time': '00:00', 'repeat-weekly': 'mon'}},
    ...     datetime.datetime(2015,10,8, 15,30)
    ... )
    foo
    """

    if '%T' not in name:
        return name

    timestamp_info = timestamp_config.get('timestamp', timestamp_config)
    config_time    = timestamp_info.get('time', 'FAIL')
    if config_time == 'FAIL':
        raise ValueError(
            "Timestamp config has no valid time entry: %s" %
            str(timestamp_config)
        )

    config_repeat_weekly = timestamp_info.get('repeat-weekly', None)

    hour, minute = [int(x) for x in config_time.split(':')][:2]

    if date is None:
        date = datetime.datetime.now()

    if config_repeat_weekly is not None:
        day_of_week = {
            'mon': 1,
            'tue': 2,
            'wed': 3,
            'thu': 4,
            'fri': 5,
            'sat': 6,
            'sun': 7,
        }.get(config_repeat_weekly.lower())

        timestamp = date_round_weekly(
            date,
            day_of_week,
            datetime.time(hour=hour, minute=minute)
        )
    else:
        timestamp = date_round_daily(
            date,
            datetime.time(hour=hour, minute=minute)
        )
    return name.replace('%T', timestamp.strftime('%Y%m%dT%H%MZ'))


def snapshot(cfg, args):
    """Creates snapshots"""
    lg.debug("Snapshots to create: %s", (cfg['snapshot']))

    cmd_snapshot = snapshot_cmds[args.task]

    if args.snapshot_name == "all":
        commands = [
            cmd_snapshot(snapshot_name, snapshot_config)
            for snapshot_name, snapshot_config
            in cfg['snapshot'].items()
        ]

        for cmd in Command.order_commands(commands, state.has_dependency):
            cmd.execute()

    else:
        if args.snapshot_name in cfg['snapshot']:
            cmd = cmd_snapshot(
                args.snapshot_name,
                cfg['snapshot'][args.snapshot_name]
            )
            if cmd is not None:
                cmd.execute()
        else:
            raise ValueError(
                "Requested snapshot is not defined in config file: %s" % (
                    args.snapshot_name
                )
            )


def snapshot_spec_to_name(snapshot):
    """Converts a given snapshot short spec to a name.

    A short spec is a value that may either be a string or a dict.

    If it's a string, everything is fine and we just use that as
    a snapshot name.

    However if it's a dict, we assume it has the following keys:

     * name: template for the snapshot
     * timestamp: information on how to generate the timestamp.

     For further information regarding the timestamp's data structure,
     consult the documentation of expand_timestamped_name().
    """

    if hasattr(snapshot, 'items'):
        name      = snapshot['name']
        ts_config = snapshot['timestamp']

        return expand_timestamped_name(name, ts_config)
    else:
        return snapshot


def cmd_snapshot_create(snapshot_name, snapshot_config):
    """Call the aptly snapshot command"""

    # TODO: extract possible timestamp component
    # and generate *actual* snapshot name

    snapshot_name = expand_timestamped_name(
        snapshot_name, snapshot_config
    )

    if snapshot_name in state.snapshots:
        return
    default_aptly_cmd = ['aptly', 'snapshot', 'create']
    default_aptly_cmd.append(snapshot_name)
    default_aptly_cmd.append('from')

    if 'mirror' in snapshot_config:
        cmd = Command(
            default_aptly_cmd + ['mirror', snapshot_config['mirror']]
        )
        cmd.provide('snapshot', snapshot_name)
        cmd.require('mirror',  snapshot_config['mirror'])
        return cmd

    elif 'repo' in snapshot_config:
        cmd = Command(default_aptly_cmd + ['repo', snapshot_config['repo']])
        cmd.provide('snapshot', snapshot_name)
        cmd.require('repo',     snapshot_config['repo'])
        return cmd

    elif 'filter' in snapshot_config:
        cmd = Command([
            'aptly',
            'snapshot',
            'filter',
            snapshot_spec_to_name(snapshot_config['filter']['source']),
            snapshot_name,
            snapshot_config['filter']['query'],
        ])
        cmd.provide('snapshot', snapshot_name)
        cmd.require(
            'snapshot',
            snapshot_spec_to_name(snapshot_config['filter']['source'])
        )
        return cmd

    elif 'merge' in snapshot_config:
        cmd = Command([
            'aptly',
            'snapshot',
            'merge',
            snapshot_name,
        ])
        cmd.provide('snapshot', snapshot_name)

        for source in snapshot_config['merge']:
            source_name = snapshot_spec_to_name(source)
            cmd.append(source_name)
            cmd.require('snapshot', source_name)

        return cmd

    else:
        raise ValueError(
            "Don't know how to handle snapshot config" % (
                snapshot_config
            )
        )


def mirror(cfg, args):
    """Creates mirrors"""
    lg.debug("Mirrors to create: %s", cfg['mirror'])

    cmd_mirror = mirror_cmds[args.task]

    if args.mirror_name == "all":
        for mirror_name, mirror_config in cfg['mirror'].items():
            cmd_mirror(mirror_name, mirror_config)
    else:
        if args.mirror_name in cfg['mirror']:
            cmd_mirror(
                args.mirror_name,
                cfg['mirror'][args.mirror_name]
            )
        else:
            raise ValueError(
                "Requested mirror is not defined in config file: %s" % (
                    args.mirror_name
                )
            )


def add_gpg_keys(mirror_config):
    if 'gpg-keys' in mirror_config:
        keys = mirror_config['gpg-keys']
        keys_urls = {}
        if 'gpg-urls' in mirror_config:
            urls = mirror_config['gpg-urls']
            urls_len = len(urls)
            for x in range(len(keys)):
                if x < urls_len:
                    url = urls[x]
                else:
                    url = None
                keys_urls[keys[x]] = url
        else:
            for key in keys:
                keys_urls[key] = None

    for key in keys_urls.keys():
        if key in state.gpg_keys:
            continue
        try:
            key_command = [
                "gpg",
                "--no-default-keyring",
                "--keyring",
                "trustedkeys.gpg",
                "--keyserver",
                "pool.sks-keyservers.net",
                "--recv-keys",
                key
            ]
            subprocess.check_call(key_command)
        except subprocess.CalledProcessError:
            url = keys_urls[key]
            if url:
                key_command = (
                    "wget -q -O - %s | "
                    "gpg --no-default-keyring "
                    "--keyring trustedkeys.gpg --import"
                ) % url
                subprocess.check_call(['bash', '-c', key_command])
            else:
                raise


def cmd_mirror_create(mirror_name, mirror_config):
    """Call the aptly mirror command"""
    if mirror_name in state.mirrors:
        return
    add_gpg_keys(mirror_config)
    aptly_cmd = ['aptly', 'mirror', 'create']
    if 'sources' in mirror_config and mirror_config['sources']:
        aptly_cmd.append('-with-sources')
    if 'udeb' in mirror_config and mirror_config['udeb']:
        aptly_cmd.append('-with-udebs')
    if 'architectures' in mirror_config:
        aptly_cmd.append('-architectures={0}'.format(
            ','.join(mirror_config['architectures'])
        ))
    aptly_cmd.append(mirror_name)
    aptly_cmd.append(mirror_config['archive'])
    aptly_cmd.append(mirror_config['distribution'])
    for component in mirror_config['components']:
        aptly_cmd.append(component)
    lg.debug('Running command: %s', ' '.join(aptly_cmd))
    subprocess.check_call(aptly_cmd)


def cmd_mirror_update(mirror_name, mirror_config):
    """Call the aptly mirror command"""
    if mirror_name not in state.mirrors:
        raise Exception("Mirror not created yet")
    add_gpg_keys(mirror_config)
    aptly_cmd = ['aptly', 'mirror', 'update']
    aptly_cmd.append(mirror_name)
    lg.debug('Running command: %s', ' '.join(aptly_cmd))
    subprocess.check_call(aptly_cmd)

mirror_cmds = {
    'create': cmd_mirror_create,
    'update': cmd_mirror_update,
}

snapshot_cmds = {
    'create': cmd_snapshot_create,
}

if __name__ == '__main__':  # pragma: no cover
    main()
