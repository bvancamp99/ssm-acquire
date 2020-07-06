# -*- coding: utf-8 -*-

"""Console script for ssm_acquire."""
import boto3
import sys
import click
import itertools
import time
import logging
"""
import os # temporary
from pathlib import Path
"""

from botocore.exceptions import ClientError

from ssm_acquire import analyze as da
from ssm_acquire import common
from ssm_acquire import credential


config = common.get_config()

logger = logging.getLogger(__name__)


def get_credentials(region, instance_id):
    logger.info('Initializing ssm_acquire.')

    limited_scope_policy = common.get_limited_policy(region, instance_id)

    logger.debug('Generating limited scoped policy for instance-id to be '
        'used in all operations: {}'.format(limited_scope_policy))
    
    sts_manager = credential.StsManager(
        region_name=region, 
        limited_scope_policy=limited_scope_policy
    )

    credentials = sts_manager.auth()

    return credentials


def wait_for_status(ssm_client, response, instance_id, spinner):
    status = common.check_status(ssm_client, response, instance_id)

    while not status:
        status = common.check_status(ssm_client, response, instance_id)

        sys.stdout.write(next(spinner))
        sys.stdout.flush()
        sys.stdout.write('\b')

        time.sleep(0.5)
    
    return status


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
    commands = common.load_acquire()['distros']['amzn2']['commands']

    # XXX TBD add a distro resolver and replace amzn2 with a dynamic distro.
    try:
        # will throw an error citing "invalid instance id" when ec2 
        # instance can't be seen by the program
        response = common.run_command(ssm_client, commands, instance_id)

        time.sleep(2)  # Wait for the command to register.

        logger.info('Memory dump in progress for instance: {}.  Please '
            'wait.'.format(instance_id))

        status = wait_for_status(ssm_client, response, instance_id, spinner)

        if status == 'Success':
            logger.info(
                'The task completed with status: {}'.format(status)
            )
            logger.info(
                'Proceeding to copy off the data to the asset store.'
            )
                
            transfer_plan = common.load_transfer(
                credentials, 
                instance_id
            )['distros']['amzn2']['commands']

            response = common.run_command(
                ssm_client, 
                transfer_plan, 
                instance_id
            )

            time.sleep(2)

            logger.info(
                'Copying the asset to s3 bucket for preservation.'
            )
                
            status = wait_for_status(
                ssm_client, 
                response, 
                instance_id, 
                spinner
            )
                
            logger.info('Transfer sequence complete.')

            print('Acquire complete.  Memory dumped and transfered to s3 '
                'bucket.')
        else:
            logger.error(
                'The task did not complete status: {}'.format(status)
            )
    except ClientError as e:
        logger.error(
            'The task could not be completed due to: {}'.format(e)
        )


def build_profile(instance_id, credentials, ssm_client, spinner):
    print('Build mode active.')

    build_plan = common.load_build(
        credentials, 
        instance_id
    )['distros']['amzn2']['commands']

    logger.info('Attempting to build a rekall profile for instance: {}.'\
        .format(instance_id))

    response = common.run_command(ssm_client, build_plan, instance_id)

    logger.info('An attempt to build a rekall profile has begun.  Please '
        'wait.')

    time.sleep(2)

    status = wait_for_status(ssm_client, response, instance_id, spinner)
        
    if status == 'Success':
        logger.info(
            'Rekall profile build complete. A .zip has been added to the '
                'asset store for instance: {}'.format(instance_id)
        )

        print('Build completed successfully.')
    else:
        logger.error('Rekall profile build failure.')


def interrogate_instance(instance_id, credentials, ssm_client, spinner):
    print('Interrogate mode active.')

    interrogate_plan = common.load_interrogate(
        credentials, 
        instance_id
    )['distros']['amzn2']['commands']

    logger.info(
        'Attempting to interrogate the instance using the OSQuery binary '
            'for instance_id: {}'.format(instance_id)
    )

    response = common.run_command(
        ssm_client, 
        interrogate_plan, 
        instance_id
    )

    time.sleep(2)

    status = wait_for_status(ssm_client, response, instance_id, spinner)
        
    if status == 'Success':
        logger.info(
            'Interrogation of system complete.  The result of this has '
                'been added to asset store for: {}'.format(instance_id)
        )

        print('Interrogate completed successfully.')
    else:
        logger.error('Instance interrogation failure.')


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
    
    credentials = get_credentials(region, instance_id)

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


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
