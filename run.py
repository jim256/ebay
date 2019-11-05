"""Executor for scrapy spiders."""
import argparse
import json
import logging.handlers
import os
import pathlib
import sys
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

__author__ = '@james-carpenter'
__version__ = '0.1.0'


def parse_args() -> argparse.Namespace:
    """Read command line args, preprocess some, and pass-through the rest."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description='Executor for scrapy spiders.',
    )
    parser.add_argument('spider', help='Name of scrapy spider to execute. (required)')
    parser.add_argument('--output',
                        help=('Location to export scraped results. \n'
                              'Overrides the scrapy FEED_URI setting.'))
    parser.add_argument('--output-format',
                        help=('Output format for scraped items. \n'
                              'Overrides the scrapy FEED_FORMAT setting.'))
    parser.add_argument('--loglevel',
                        help='Overrides scrapy LOG_LEVEL setting.')
    parser.add_argument('--logfile',
                        type=lambda x: pathlib.Path(x).absolute(),
                        default=pathlib.Path(__file__).absolute().parent / 'logs' / '{}.log',
                        help=('Path to log file. \n'
                              'This will rotate on each execution, keeping the last '
                              '--log-backup-count files. \n'
                              'The <spider> parameter value will be available as a positional '
                              'format argument. \n'
                              'Overrides the scrapy LOG_FILE setting. (default: logs/{spider}.log)'))
    parser.add_argument('--log-backup-count',
                        type=int,
                        default=50,
                        help='Number of prior log files to keep. (default: 50)')
    parser.add_argument('--log-to-console',
                        action='store_true',
                        help='Output log events to the console in addition to --logfile (default: False)')
    parser.add_argument('--configfile',
                        type=lambda x: pathlib.Path(x).absolute(),
                        help='Path to config file with overrides for settings')
    args = parser.parse_args()
    return args


def init_settings(args) -> dict:
    # Get default values
    project_settings = get_project_settings()
    settings = {k: v.value for k, v in project_settings.attributes.items()}

    # Override with config file
    try:
        with open(args.configfile) as f:
            config = json.load(f)
    except Exception as e:
        print(f'Failed to load config from {args.configfile}: {e}', file=sys.stderr)
        sys.exit(1)
    settings.update(config)

    # Optionally override with command line
    if args.output:
        settings['FEED_URI'] = None if args.output == '-' else args.output
    if args.output_format:
        settings['FEED_FORMAT'] = args.output_format
    if args.loglevel:
        settings['LOG_LEVEL'] = args.loglevel
    settings['LOG_FILE'] = None if args.logfile == '-' else str(args.logfile).format(args.spider)
    settings['LOG_TO_CONSOLE'] = args.log_to_console

    return settings


def setup_logging(settings: dict):
    # setup log rotation
    if settings['LOG_FILE'] and settings['LOG_FILE'] != '-':
        # Check if log exists and should therefore be rolled
        if os.path.isfile(settings['LOG_FILE']):
            handler = logging.handlers.RotatingFileHandler(settings['LOG_FILE'], backupCount=args.log_backup_count)
            # Roll over on application start
            handler.doRollover()
        else:
            os.makedirs(os.path.dirname(settings['LOG_FILE']), exist_ok=True)
    if settings['LOG_TO_CONSOLE']:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(fmt=settings['LOG_FORMAT'], datefmt=settings['LOG_DATEFORMAT']))
        log = logging.getLogger()
        log.addHandler(handler)
        log.setLevel(getattr(logging, settings['LOG_LEVEL']))


if __name__ == '__main__':
    args = parse_args()
    settings = init_settings(args)
    setup_logging(settings)

    process = CrawlerProcess(settings)
    process.crawl(args.spider)
    process.start()  # the script will block here until the crawling is finished
