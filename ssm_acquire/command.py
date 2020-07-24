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
    run_response = ssm_client.send_command(
        InstanceIds=[instance_id],
        DocumentName='AWS-RunShellScript',
        Comment='Incident response step execution for: {}'.format(instance_id),
        Parameters={
            "commands": commands
        }
    )

    return run_response


def _show_next_cycle_frame():
    """Shows the next frame of the itertools cycle."""
    sys.stdout.write(next(spinner))
    sys.stdout.flush()
    sys.stdout.write('\b')


def _get_invocation_response(ssm_client, run_response, instance_id):
    """
    Returns the response of calling the get_command_invocation function on 
    the SSM client.
    """
    return ssm_client.get_command_invocation(
        CommandId=run_response['Command']['CommandId'],
        InstanceId=instance_id
    )


def _is_invocation_registered(ssm_client, run_response, instance_id):
    """Polls the ssm_client to see if the SSM command has been received."""

    invocation_registered = False
    
    try:
        _get_invocation_response(ssm_client, run_response, instance_id)

        logger.debug('Invocation registered.  Please wait...')

        invocation_registered = True
    except ClientError as e:
        logger.debug('Invocation not yet registered with error code: {}.  '
            'Please wait...'.format(e.response['Error']['Code']))
    
    return invocation_registered


def _ensure_invocation_registered(ssm_client, run_response, instance_id):
    """Ensures that the ssm_client has received commands before the function 
    returns."""

    invocation_registered = _is_invocation_registered(
        ssm_client, 
        run_response, 
        instance_id
    )

    while not invocation_registered:
        _show_next_cycle_frame()

        time.sleep(0.5)

        invocation_registered = _is_invocation_registered(
            ssm_client, 
            run_response, 
            instance_id
        )


def _evaluate_invocation_response(inv_response):
    """
    Evaluates the return value of the command invocation.

    Returns whether the status indicates that the command has completed.
    """
    # TESTING
    print(inv_response)
    # TESTING

    status = inv_response['Status']

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


def _is_command_finished(ssm_client, run_response, instance_id):
    """
    Polls the ssm_client to see if the SSM command has completed.

    Returns the invocation response dict and the bool result as a tuple.
    """
    inv_response = _get_invocation_response(
        ssm_client, 
        run_response, 
        instance_id
    )

    finished = _evaluate_invocation_response(inv_response)

    return (inv_response, finished)


def _ensure_command_finished(ssm_client, run_response, instance_id):
    """
    Ensures that the registered commands are completed before the function 
    returns.

    Returns the invocation response that was received when the command 
    finished.
    """
    inv_response, finished = _is_command_finished(
        ssm_client, 
        run_response, 
        instance_id
    )

    while not finished:
        _show_next_cycle_frame()

        time.sleep(0.5)

        inv_response, finished = _is_command_finished(
            ssm_client, 
            run_response, 
            instance_id
        )
    
    return inv_response


def ensure_command(ssm_client, commands, instance_id):
    """
    Runs an SSM command and ensures that it completes before the function 
    returns.

    Returns a dict that is the final command invocation response.
    """
    run_response = _run_command(ssm_client, commands, instance_id)

    _ensure_invocation_registered(ssm_client, run_response, instance_id)

    inv_response = _ensure_command_finished(
        ssm_client, 
        run_response, 
        instance_id
    )

    return inv_response
