# -*- coding: utf-8 -*-

"""Console script for ssm_acquire."""
import boto3
import sys
import click
import itertools
import time
import logging

from botocore.exceptions import ClientError

from ssm_acquire import analyze as da
from ssm_acquire import common_cmd
from ssm_acquire import common_io
from ssm_acquire import credential


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


def acquire_mem(instance_id, credentials, ssm_client, spinner):
    print('Acquire mode active.')

    # Only supports amzn2 for now
    commands = common_io.acquire_plans['distros']['amzn2']['commands']

    # XXX TBD add a distro resolver and replace amzn2 with a dynamic distro.
    try:
        # will throw an error citing "invalid instance id" when ec2 
        # instance can't be seen by the program
        response = common_cmd.run_command(ssm_client, commands, instance_id)

        logger.info('Memory dump in progress for instance: {}.  Please '
            'wait.'.format(instance_id))

        result = common_cmd.wait_for_command(
            ssm_client, 
            response, 
            instance_id
        )

        logger.info(
            'Memory dump completed with result: {}'.format(result)
        )
                
        transfer_plan = common_io.load_transfer(
            credentials, 
            instance_id
        )['distros']['amzn2']['commands']

        response = common_cmd.run_command(
            ssm_client, 
            transfer_plan, 
            instance_id
        )

        logger.info(
            'Transfering memory dump to s3 bucket.'
        )
                
        result = common_cmd.wait_for_command(
            ssm_client, 
            response, 
            instance_id
        )
                
        logger.info(
            'Transfer sequence completed with result: {}'.format(result)
        )

        print('Acquire complete.  Memory dumped and transfered to s3 bucket.')
    except ClientError as e:
        logger.error(
            'The task could not be completed due to: {}'.format(e)
        )


def build_profile(instance_id, credentials, ssm_client, spinner):
    print('Build mode active.')

    build_plan = common_io.load_build(
        credentials, 
        instance_id
    )['distros']['amzn2']['commands']

    logger.info('Attempting to build a rekall profile for instance: {}.'\
        .format(instance_id))

    response = common_cmd.run_command(ssm_client, build_plan, instance_id)

    result = common_cmd.wait_for_command(
        ssm_client, 
        response, 
        instance_id
    )
        
    logger.info(
        'Rekall profile build completed with result: {}'.format(result)
    )

    logger.info(
        'A .zip has been added to the asset store for instance: {}'.format(
            instance_id
        )
    )

    print('Build completed successfully.')


def interrogate_instance(instance_id, credentials, ssm_client, spinner):
    print('Interrogate mode active.')

    interrogate_plan = common_io.load_interrogate(
        credentials, 
        instance_id
    )['distros']['amzn2']['commands']

    logger.info(
        'Attempting to interrogate the instance using the OSQuery binary '
            'for instance_id: {}'.format(instance_id)
    )

    response = common_cmd.run_command(
        ssm_client, 
        interrogate_plan, 
        instance_id
    )

    result = common_cmd.wait_for_command(
        ssm_client, 
        response, 
        instance_id
    )

    logger.info(
        'Interrogate instance completed with result: {}'.format(result)
    )

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
    
    credentials = common_cmd.get_credentials(region, instance_id)

    ssm_client = boto3.client(
        'ssm',
        aws_access_key_id=credentials['Credentials']['AccessKeyId'],
        aws_secret_access_key=credentials['Credentials']['SecretAccessKey'],
        aws_session_token=credentials['Credentials']['SessionToken']
    )

    spinner = itertools.cycle(['-', '/', '|', '\\'])

    if analyze is True:
        analyze_capture(instance_id, credentials)

    if acquire is True:
        acquire_mem(instance_id, credentials, ssm_client, spinner)

    if build is True:
        build_profile(instance_id, credentials, ssm_client, spinner)

    if interrogate is True:
        interrogate_instance(instance_id, credentials, ssm_client, spinner)
    
    logger.info('ssm_acquire has completed successfully.')
    return 0


if __name__ == '__main__':
    sys.exit(main())  # pragma: no cover
