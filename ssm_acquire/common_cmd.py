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





def _get_ec2_arn(region, instance_id):
    r"""
    Gets the Amazon resource name for the EC2 instance in the specified 
    region.

    EC2 arn format is:
    arn:aws:ec2:\<REGION\>:\<ACCOUNT_ID\>:instance/\<instance-id\>

    ACCOUNT_ID is unnecessary in the context of this program.
    """

    return 'arn:aws:ec2:{}:*:instance/{}'.format(region, instance_id)


# TODO: compartmentalize into separate functions
def _get_permissions_needed(region, instance_id):
    """Using the policy document as a template, returns a json-formatted 
    string containing the permissions needed for program execution."""

    policy_statements = common_io.policy['PolicyDocument']['Statement']

    # STMT1 modification

    s3_arn = 'arn:aws:s3:{}:*:{}/{}'.format(
        region, 
        common_io.s3_bucket, 
        instance_id
    )

    s3_keys = '{}/*'.format(s3_arn)

    policy_statements[0]['Resource'][0] = s3_arn
    policy_statements[0]['Resource'][1] = s3_keys

    # STMT2 does not require any modifications

    # STMT3

    policy_statements[2]['Resource'][1] = _get_ec2_arn(
        region, 
        instance_id
    )

    # STMT4

    s3_arn = 'arn:aws:s3:{}:*:{}'.format(region, common_io.s3_bucket)

    s3_keys = '{}/*'.format(s3_arn)

    policy_statements[3]['Resource'][0] = s3_arn
    policy_statements[3]['Resource'][1] = s3_keys
    
    json_statements = json.dumps(common_io.policy['PolicyDocument'])

    logger.info('Limited scope role generated for assumeRole: {}'.format(json_statements))
    
    return json_statements


"""
def _get_limited_policy(region, instance_id):
    s3_bucket = common_io.s3_bucket

    policy_template = common_io.policy

    instance_arn = _generate_arn_for_instance(region, instance_id)
    
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
"""


def get_credentials(region, instance_id):
    """Obtains the credentials required to run commands on the EC2 
    instance."""

    permissions_needed = _get_permissions_needed(region, instance_id)

    logger.debug('Generating limited scoped policy for instance-id to be '
        'used in all operations: {}'.format(permissions_needed))
    
    sts_manager = credential.StsManager(
        region_name=region, 
        limited_scope_policy=permissions_needed
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