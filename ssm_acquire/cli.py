# -*- coding: utf-8 -*-

"""Console script for ssm_acquire."""
import boto3
import sys
import click
import logging
import ssm_acquire

from ssm_acquire import analyze as da

from ssm_acquire.command import ensure_command
from ssm_acquire.credential import get_credentials

from ssm_acquire.acquire import dump_and_transfer
from ssm_acquire.build import build_profile
from ssm_acquire.interrogate import interrogate_instance


logger = logging.getLogger(__name__)


# TODO: throws error on valid instance; investigate analyze.py
def analyze_capture(instance_id, credentials):
    print('Analysis mode active.')
    
    analyzer = da.RekallManager(
        instance_id,
        credentials
    )
    
    analyzer.download_incident_data()
    analyzer.run_rekall_plugins()

    print('Analysis complete.  The rekall-json dumps have been added to '
        'the asset store.')


def _set_logging_level(verbosity):
    """Sets the logging level based on the verbosity value."""
    if verbosity == 1:
        logging.basicConfig(level=logging.INFO)
    elif verbosity >= 2:
        logging.basicConfig(level=logging.DEBUG)


def _valid_input(instance_id, region, analyze, acquire, build, interrogate):
    """
    Checks if the input is valid.
    
    Input is considered valid if the instance_id and region are provided, and 
    at least one of the flags is specified.
    """
    if instance_id is None:
        logger.warning('No EC2 instance specified.  Run \'ssm_acquire '
            '--help\' for usage details.')
        return False
    
    if region is None:
        logger.warning('No AWS region specified.  Run \'ssm_acquire --help\' '
            'for usage details.')
        return False

    if not (analyze or acquire or build or interrogate):
        logger.warning('No flags specified.  Run \'ssm_acquire --help\' '
            'for usage details.')
        return False
    
    return True


def _get_ssm_client(credentials, region):
    """Gets SSM client that can send commands to the EC2 instance."""
    return boto3.client(
        'ssm',
        aws_access_key_id=credentials['Credentials']['AccessKeyId'],
        aws_secret_access_key=credentials['Credentials']['SecretAccessKey'],
        aws_session_token=credentials['Credentials']['SessionToken'],
        region_name=region
    )


def _resolve_flags(
    analyze, 
    acquire, 
    build, 
    interrogate, 
    ssm_client, 
    instance_id, 
    credentials
):
    """Performs actions based on the flags set."""
    if analyze:
        analyze_capture(instance_id, credentials)

    if acquire:
        dump_and_transfer(ssm_client, instance_id, credentials)

    if build:
        build_profile(ssm_client, instance_id, credentials)

    if interrogate:
        interrogate_instance(ssm_client, instance_id, credentials)


def _main_helper(instance_id, region, build, acquire, interrogate, analyze):
    """
    Gets the tools needed to send commands to the EC2 instance and runs 
    commands based on the set flags.
    """
    logger.info('Initializing ssm_acquire.')

    credentials = get_credentials(region, instance_id)

    ssm_client = _get_ssm_client(credentials, region)

    _resolve_flags(
        analyze, 
        acquire, 
        build, 
        interrogate, 
        ssm_client, 
        instance_id, 
        credentials
    )
    
    logger.info('ssm_acquire has completed successfully.')


@click.command()
@click.option('--instance_id', help='The EC2 instance you would like to '
    'operate on.')
@click.option('--region', help='The AWS region where the instance can be '
    'found.  Example: us-east-1')
@click.option('--build', is_flag=True, help='Specify if you would like to '
    'build a rekall profile with this capture.')
@click.option('--acquire', is_flag=True, help='Use linpmem to acquire a '
    'memory sample from the system in question.')
@click.option('--interrogate', is_flag=True, help='Use OSQuery binary to '
    'preserve top 10 type queries for rapid forensics.')
@click.option('--analyze', is_flag=True, help='Use docker and rekall to '
    'autoanalyze the memory capture.')
@click.option('--deploy', is_flag=True, help='Create a lambda function with '
    'a handler to take events from AWS GuardDuty.\nNOTE: not implemented')
@click.option('--verbosity', default=0, help='Sets verbosity level. '
    'Default=0=WARNING; 1=INFO; 2=DEBUG. See '
    'https://docs.python.org/3/howto/logging.html for more details on the '
    'logging levels.')
def main(
    instance_id, 
    region, 
    build, 
    acquire, 
    interrogate, 
    analyze, 
    deploy, 
    verbosity
):
    """ssm_acquire: a rapid evidence preservation tool for Amazon EC2."""

    _set_logging_level(verbosity)

    if not _valid_input(
        instance_id, 
        region, 
        analyze, 
        acquire, 
        build, 
        interrogate
    ):
        return 1
    
    _main_helper(instance_id, region, build, acquire, interrogate, analyze)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())  # pragma: no cover
