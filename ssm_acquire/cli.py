# -*- coding: utf-8 -*-

"""Console script for ssm_acquire."""
import boto3
import sys
import click
import logging

from ssm_acquire import analyze as da
from ssm_acquire import jinja2_io

from ssm_acquire.acquire import acquire_plans
from ssm_acquire.command import ensure_command
from ssm_acquire.credential import get_credentials


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


def acquire_mem(instance_id, credentials, ssm_client):
    print('Acquire mode active.  Please give about a minute.')

    # Only supports amzn2 for now
    memdump_commands = acquire_plans['distros']['amzn2']['commands']

    # XXX TBD add a distro resolver and replace amzn2 with a dynamic distro.

    logger.info('Memory dump in progress for instance: {}.  Please '
        'wait.'.format(instance_id))
    
    ensure_command(ssm_client, memdump_commands, instance_id)

    logger.info('Memory dump complete.  Transfering to s3 bucket...')

    transfer_commands = jinja2_io.get_transfer_plans(
        credentials, 
        instance_id
    )['distros']['amzn2']['commands']

    ensure_command(ssm_client, transfer_commands, instance_id)

    logger.info('Transfer to s3 bucket complete.')

    print('Acquire complete.  Memory dumped and transfered to s3 bucket.')


def build_profile(instance_id, credentials, ssm_client):
    print('Build mode active.')

    logger.info('Attempting to build a rekall profile for instance: {}.'\
        .format(instance_id))

    build_commands = jinja2_io.get_build_plans(
        credentials, 
        instance_id
    )['distros']['amzn2']['commands']

    ensure_command(ssm_client, build_commands, instance_id)
        
    logger.info('Rekall profile build complete.')

    logger.info(
        'A .zip has been added to the asset store for instance: {}'.format(
            instance_id
        )
    )

    print('Build completed successfully.')


def interrogate_instance(instance_id, credentials, ssm_client):
    print('Interrogate mode active.')

    logger.info(
        'Attempting to interrogate the instance using the OSQuery binary for '
            'instance_id: {}'.format(instance_id)
    )

    interrogate_commands = jinja2_io.get_interrogate_plans(
        credentials, 
        instance_id
    )['distros']['amzn2']['commands']

    ensure_command(ssm_client, interrogate_commands, instance_id)

    logger.info('Interrogate instance complete.')

    logger.info(
        'A .log has been added to the asset store for instance: {}'.format(
            instance_id
        )
    )

    print('Interrogate completed successfully.')


@click.command()
@click.option('--instance_id', help='The EC2 instance you would like to '
    'operate on.')
@click.option('--region', default='us-west-2', help='The AWS region where '
    'the instance can be found.  Default region is us-west-2.')
@click.option('--build', is_flag=True, help='Specify if you would like to '
    'build a rekall profile with this capture.')
@click.option('--acquire', is_flag=True, help='Use linpmem to acquire a '
    'memory sample from the system in question.')
@click.option('--interrogate', is_flag=True, help='Use OSQuery binary to '
    'preserve top 10 type queries for rapid forensics.')
@click.option('--analyze', is_flag=True, help='Use docker and rekall to '
    'autoanalyze the memory capture.')
@click.option('--deploy', is_flag=True, help='Create a lambda function with '
    'a handler to take events from AWS GuardDuty.')
@click.option('--verbosity', default=0, help='Sets verbosity level. '
    'Default=0=WARNING; 1=INFO; 2=DEBUG. See '
    'https://docs.python.org/3/howto/logging.html for more details on the '
    'logging levels.')
def main(instance_id, region, build, acquire, interrogate, analyze, deploy,
    verbosity):
    """ssm_acquire: a rapid evidence preservation tool for Amazon EC2."""

    """
    print(os.path.dirname(__file__))
    print(os.path.abspath(os.path.dirname(__file__)))
    print(os.path.dirname(os.path.abspath(__file__)))
    print(os.path.realpath(__file__))
    print(os.path.relpath(__file__))
    print(os.path.abspath(__file__))
    exit()
    """

    # set logging level according to user input
    if verbosity == 1:
        logging.basicConfig(level=logging.INFO)
    elif verbosity >= 2:
        logging.basicConfig(level=logging.DEBUG)

    if instance_id is None:
        logger.warning('No EC2 instance specified.  Run \'ssm_acquire '
            '--help\' for usage details.')
        return 1

    if not (acquire or interrogate or build or analyze):
        logger.warning('No flags specified.  Run \'ssm_acquire --help\' '
            'for usage details.')
        return 1
    
    logger.info('Initializing ssm_acquire.')

    credentials = get_credentials(region, instance_id)

    ssm_client = boto3.client(
        'ssm',
        aws_access_key_id=credentials['Credentials']['AccessKeyId'],
        aws_secret_access_key=credentials['Credentials']['SecretAccessKey'],
        aws_session_token=credentials['Credentials']['SessionToken']
    )

    if analyze is True:
        analyze_capture(instance_id, credentials)

    if acquire is True:
        acquire_mem(instance_id, credentials, ssm_client)

    if build is True:
        build_profile(instance_id, credentials, ssm_client)

    if interrogate is True:
        interrogate_instance(instance_id, credentials, ssm_client)
    
    logger.info('ssm_acquire has completed successfully.')
    
    return 0


if __name__ == '__main__':
    sys.exit(main())  # pragma: no cover
