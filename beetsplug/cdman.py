from pathlib import Path
import psutil
from typing import Optional, override
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand
from beets.library import Library
from optparse import Values

from beetsplug.cd.cd import CD
from beetsplug.cd_parser import CDParser
from beetsplug.config import Config
from beetsplug.dimensional_thread_pool_executor import DimensionalThreadPoolExecutor


class CDManPlugin(BeetsPlugin):
    def __init__(self, name: Optional[str] = None):
        super().__init__(name)

        hw_thread_count = psutil.cpu_count() or 4
        self.config.add({
            "cds_path": "~/Music/CDs",
            "bitrate": 128,
            "threads": hw_thread_count,
        })

    @override
    def commands(self):
        return [self._get_subcommand()]

    def _get_subcommand(self):
        cmd = Subcommand("cdman", help="manage CDs")
        cmd.parser.add_option(
            "--threads", "-t",
            help="The maximum number of threads to use. " +
                "This overrides the config value of the same name.",
            type=int,
        )
        cmd.parser.add_option(
            "--bitrate", "-b",
            help="The bitrate (in kbps) to use when converting files to MP3. " +
                "This overrides the config value of the same name.",
            type=int,
        )
        cmd.parser.add_option(
            "--populate-mode", "-p",
            help="Determines how Audio CDs are populated. "+
                "Must be one of COPY, HARD_LINK, or SOFT_LINK. "+
                "This overrides the config value of the same name.",
            type=str,
        )
        cmd.parser.add_option(
            "--dry", "-d",
            help="When run with this flag present, 'cdman' goes through "
                "all the motions of a normal command, but doesn't "
                "actually perform any conversions. "
                "Note that directories may be created in your cds_path directory.",
            action="store_true",
        )
        cmd.parser.add_option(
            "--verbose", "-v",
            help="Prints detailed output of what 'cdman' is currently doing.",
            action="store_true",
        )

        def cdman_cmd(lib: Library, opts: Values, args: list[str]):
            self._cmd(lib, opts, args)
        cmd.func = cdman_cmd
        return cmd

    def _cmd(self, lib: Library, opts: Values, args: list[str]):
        max_threads: int = self.config["threads"].get(int) if opts.threads is None else opts.threads  # type: ignore
        self._executor = DimensionalThreadPoolExecutor(max_threads)

        Config.verbose = opts.verbose
        Config.dry = opts.dry

        cd_parser = CDParser(lib, opts, self.config, self._executor)
        if len(args) == 0:
            # Load CDs from config
            cds = cd_parser.from_config()
        else:
            # Load CDs from args
            cds: list[CD] = []
            for arg in args:
                arg_path = Path(arg)
                if not arg_path.exists():
                    print(f"No such file or directory: {arg_path}")
                    continue
                arg_cds = cd_parser.from_path(arg_path)
                cds.extend(arg_cds)

        with self._executor:
            for cd in cds:
                cd.numberize()
                cd.cleanup()
                cd.populate()
        return None
