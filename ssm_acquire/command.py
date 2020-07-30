import boto3
import itertools
import logging
import sys
import time

from typing import List

from botocore.exceptions import ClientError

from ssm_acquire import cred


logger = logging.getLogger(__name__)


class SSMClient:
    """
    Represents a client that manages the sending of commands to SSM for a 
    given EC2 instance and the evaluation of responses from SSM.
    """
    def __init__(self, region, instance_id):
        self.credentials = cred.get_credentials(region, instance_id)
        self.boto3_client = self._get_boto3_client(self.credentials, region)
        self.instance_id = instance_id
        self.spinner = itertools.cycle(['-', '/', '|', '\\'])
    
    def _get_boto3_client_without_region(self, credentials):
        return boto3.client(
            'ssm',
            aws_access_key_id=credentials['Credentials']['AccessKeyId'],
            aws_secret_access_key=credentials['Credentials']\
                ['SecretAccessKey'],
            aws_session_token=credentials['Credentials']['SessionToken'],
        )

    def _get_boto3_client_with_region(self, credentials, region):
        return boto3.client(
            'ssm',
            aws_access_key_id=credentials['Credentials']['AccessKeyId'],
            aws_secret_access_key=credentials['Credentials']\
                ['SecretAccessKey'],
            aws_session_token=credentials['Credentials']['SessionToken'],
            region_name=region
        )

    def _get_boto3_client(self, credentials, region):
        """
        Gets boto3 client that can send commands to the EC2 instance via SSM.
        """
        if region:
            return self._get_boto3_client_with_region(credentials, region)
        else:
            return self._get_boto3_client_without_region(credentials)
    
    def _send_commands(self, commands: List[str]):
        """
        Sends a list of commands to SSM and returns its response.
        """
        send_response = self.boto3_client.send_command(
            InstanceIds=[self.instance_id],
            DocumentName='AWS-RunShellScript',
            Comment='Incident response step execution for: {}'.format(
                self.instance_id
            ),
            Parameters={
                "commands": commands
            }
        )
        
        return send_response
    
    def _show_next_cycle_frame(self):
        """
        Shows the next frame of the itertools cycle.
        """
        sys.stdout.write(next(self.spinner))
        sys.stdout.flush()
        sys.stdout.write('\b')
    
    def _get_invocation_response(self, send_response):
        """
        Returns the response of calling the get_command_invocation function 
        on the client.
        """
        return self.boto3_client.get_command_invocation(
            CommandId=send_response['Command']['CommandId'],
            InstanceId=self.instance_id
        )
    
    def _is_invocation_registered(self, send_response):
        """
        Polls the ssm_client to see if the SSM command has been received.
        """
        invocation_registered = False
        
        try:
            self._get_invocation_response(send_response)

            logger.debug('Invocation registered.  Please wait...')

            invocation_registered = True
        except ClientError as e:
            logger.debug(
                'Invocation not yet registered with error code: {}.  Please '
                'wait...'.format(
                    e.response['Error']['Code']
                )
            )
        
        return invocation_registered
    
    def _ensure_invocation_registered(self, send_response):
        """
        Ensures that the client has received commands before the function 
        returns.
        """

        invocation_registered = self._is_invocation_registered(send_response)

        while not invocation_registered:
            self._show_next_cycle_frame()

            time.sleep(0.5)

            invocation_registered = self._is_invocation_registered(
                send_response
            )
    
    def _evaluate_invocation_response(self, inv_response):
        """
        Evaluates the return value of the command invocation.

        Returns whether the status indicates that the command has completed.
        """
        status = inv_response['Status']

        """
        From docs: 'Status': 'Pending'|'InProgress'|'Delayed'|'Success'|
        'Cancelled'|'TimedOut'|'Failed'|'Cancelling'
        """

        finished = False

        if status == 'Success' or status == 'Cancelled' or status == \
            'TimedOut' or status == 'Failed':
            finished = True

            logger.info(
                'SSM command completed with status: {}'.format(
                    status
                )
            )
        
        return finished
    
    def _is_command_finished(self, send_response):
        """
        Polls the ssm_client to see if the SSM command has completed.

        Returns the invocation response dict and the bool result as a tuple.
        """
        inv_response = self._get_invocation_response(send_response)

        finished = self._evaluate_invocation_response(inv_response)

        return (inv_response, finished)
    
    def _ensure_command_finished(self, send_response):
        """
        Ensures that the registered commands are completed before the 
        function returns.

        Returns the invocation response that was received when the command 
        finished.
        """
        inv_response, finished = self._is_command_finished(send_response)

        while not finished:
            self._show_next_cycle_frame()

            time.sleep(0.5)

            inv_response, finished = self._is_command_finished(send_response)
        
        return inv_response
    
    def ensure_commands(self, commands: List[str]):
        """
        Runs a list of commands on the EC2 instance via SSM.
        
        Ensures that the commands have completed before the function returns.

        Returns a dict that is the final command invocation response.
        """
        send_response = self._send_commands(commands)

        self._ensure_invocation_registered(send_response)

        inv_response = self._ensure_command_finished(send_response)

        return inv_response