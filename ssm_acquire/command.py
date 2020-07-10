import itertools
import logging
import sys
import time

from botocore.exceptions import ClientError


logger = logging.getLogger(__name__)

spinner = itertools.cycle(['-', '/', '|', '\\'])


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