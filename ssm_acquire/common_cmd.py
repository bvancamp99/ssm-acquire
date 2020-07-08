import itertools
import json
import logging
import sys
import time

from botocore.exceptions import ClientError

from ssm_acquire import common_io
from ssm_acquire import credential


logger = logging.getLogger(__name__)

spinner = itertools.cycle(['-', '/', '|', '\\'])


def generate_arn_for_instance(region, instance_id):
    return 'arn:aws:ec2:*:*:instance/{}'.format(instance_id)


def get_limited_policy(region, instance_id):
    s3_bucket = common_io.s3_bucket

    policy_template = common_io.policy

    instance_arn = generate_arn_for_instance(region, instance_id)
    
    # TODO: figure out what's going on here
    for permission in policy_template['PolicyDocument']['Statement']:
        if permission['Action'][0] == 's3:PutObject':
            s3_arn = 'arn:aws:s3:::{}/{}'.format(s3_bucket, instance_id)
            s3_keys = 'arn:aws:s3:::{}/{}/*'.format(s3_bucket, instance_id)
            record_index = policy_template['PolicyDocument']['Statement'].index(permission)
            policy_template['PolicyDocument']['Statement'][record_index]['Resource'][0] = s3_arn
            policy_template['PolicyDocument']['Statement'][record_index]['Resource'][1] = s3_keys
        elif permission['Action'][0].startswith('ssm:Send'):
            record_index = policy_template['PolicyDocument']['Statement'].index(permission)
            policy_template['PolicyDocument']['Statement'][record_index]['Resource'][1] = instance_arn
        elif permission['Sid'] == 'STMT4':
            s3_arn = 'arn:aws:s3:::{}'.format(s3_bucket)
            s3_keys = 'arn:aws:s3:::{}/*'.format(s3_bucket)
            record_index = policy_template['PolicyDocument']['Statement'].index(permission)
            policy_template['PolicyDocument']['Statement'][record_index]['Resource'][0] = s3_arn
            policy_template['PolicyDocument']['Statement'][record_index]['Resource'][1] = s3_keys
    
    statements = json.dumps(policy_template['PolicyDocument'])

    logger.info('Limited scope role generated for assumeRole: {}'.format(statements))
    
    return statements


def get_credentials(region, instance_id):
    """Obtains the credentials required to run commands on the EC2 
    instance."""

    logger.info('Initializing ssm_acquire.')

    limited_scope_policy = get_limited_policy(region, instance_id)

    logger.debug('Generating limited scoped policy for instance-id to be '
        'used in all operations: {}'.format(limited_scope_policy))
    
    sts_manager = credential.StsManager(
        region_name=region, 
        limited_scope_policy=limited_scope_policy
    )

    credentials = sts_manager.auth()

    return credentials


def _run_command(ssm_client, commands, instance_id):
    """Runs an SSM command and returns the boto3 response."""
    # XXX TBD add a test to see if another invocation is pending and raise if waiting.
    response = ssm_client.send_command(
        InstanceIds=[instance_id],
        DocumentName='AWS-RunShellScript',
        Comment='Incident response step execution for: {}'.format(instance_id),
        Parameters={
            "commands": commands
        }
    )

    return response


def _show_next_cycle_frame():
    """Shows the next frame of the itertools cycle."""
    sys.stdout.write(next(spinner))
    sys.stdout.flush()
    sys.stdout.write('\b')


def _is_invocation_registered(ssm_client, response, instance_id):
    """Polls the ssm_client to see if the SSM command has been received."""
    
    invocation_registered = False
    
    try:
        ssm_client.get_command_invocation(
            CommandId=response['Command']['CommandId'],
            InstanceId=instance_id
        )

        logger.debug('Invocation registered.  Please wait...')

        invocation_registered = True
    except ClientError as e:
        logger.debug('Invocation not yet registered with error code: {}.  '
            'Please wait...'.format(e.response['Error']['Code']))
    
    return invocation_registered


def _ensure_invocation_registered(ssm_client, response, instance_id):
    """Ensures that the ssm_client has received commands before the function 
    returns."""

    invocation_registered = _is_invocation_registered(
        ssm_client, 
        response, 
        instance_id
    )

    while not invocation_registered:
        _show_next_cycle_frame()

        time.sleep(0.5)

        invocation_registered = _is_invocation_registered(
            ssm_client, 
            response, 
            instance_id
        )


def _evaluate_status(status):
    """Evaluates completion status str and returns its bool equivalent."""

    """From docs: 'Status': 'Pending'|'InProgress'|'Delayed'|'Success'|
    'Cancelled'|'TimedOut'|'Failed'|'Cancelling'"""

    finished = False

    if status == 'Success':
        finished = True
    elif status == 'Cancelled':
        finished = True
        print('SSM command was cancelled.')
    elif status == 'TimedOut':
        finished = True
        print('SSM command timed out.')
    elif status == 'Failed':
        finished = True
        print('SSM command failed.')
    
    return finished


def _is_command_finished(ssm_client, response, instance_id):
    """Polls the ssm_client to see if the SSM command has completed."""

    status = ssm_client.get_command_invocation(
        CommandId=response['Command']['CommandId'],
        InstanceId=instance_id
    )['Status']

    finished = _evaluate_status(status)

    return finished


def _ensure_command_finished(ssm_client, response, instance_id):
    """Ensures that the registered commands are completed before the function 
    returns."""

    finished = _is_command_finished(ssm_client, response, instance_id)

    while not finished:
        _show_next_cycle_frame()

        time.sleep(0.5)

        finished = _is_command_finished(ssm_client, response, instance_id)


def ensure_command(ssm_client, commands, instance_id):
    """Runs an SSM command and ensures that it completes before the function 
    returns."""

    # will throw an error citing "invalid instance id" when ec2 
    # instance can't be seen by the program
    response = _run_command(ssm_client, commands, instance_id)

    _ensure_invocation_registered(ssm_client, response, instance_id)

    _ensure_command_finished(ssm_client, response, instance_id)