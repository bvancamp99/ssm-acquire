import itertools
import json
import logging
import sys
import time

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


def run_command(ssm_client, commands, instance_id):
    """Run an ssm command.  Return the boto3 response."""
    
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


def _check_status(ssm_client, response, instance_id):
    logger.debug('Attempting to retrieve status for command_id: {}'.format(response['Command']['CommandId']))

    response = ssm_client.get_command_invocation(
        CommandId=response['Command']['CommandId'],
        InstanceId=instance_id
    )

    # print('response[\'Status\']={}'.format(response['Status']))

    if response['Status'] == 'Pending':
        return None
    if response['Status'] == 'InProgress':
        return None
    if response['Status'] == 'Delayed':
        return None
    if response['Status'] == 'Cancelling':
        return None
    return response['Status']


def wait_for_command(ssm_client, response, instance_id):
    # Wait for the command to register.
    time.sleep(2)

    result = _check_status(ssm_client, response, instance_id)

    while not result:
        result = _check_status(ssm_client, response, instance_id)

        sys.stdout.write(next(spinner))
        sys.stdout.flush()
        sys.stdout.write('\b')

        time.sleep(0.5)
    
    return result
