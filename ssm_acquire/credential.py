# -*- coding: utf-8 -*-
import boto3.session
import logging

from prompt_toolkit import prompt

from ssm_acquire.config import config_manager
from ssm_acquire import policy


logger = logging.getLogger(__name__)

_role_arn = config_manager('ssm_acquire_role_arn', namespace='ssm_acquire')

_mfa_config = config_manager(
    'mfa_serial_number', 
    namespace='ssm_acquire', 
    default=''
)

_session_duration = int(
    config_manager(
        'assume_role_session_duration', 
        namespace='ssm_acquire',
        default='3600'
    )
)


def _get_mfa_token():
    mfa_token = None

    if _mfa_config:
        mfa_token = prompt('Please enter your MFA Token: ')
    
    return mfa_token


_mfa_token = _get_mfa_token()


def _get_sts_client(region):
    """Returns an sts client for the given region."""

    boto_session = boto3.session.Session(region_name=region)

    sts_client = boto_session.client('sts')

    return sts_client


def _assume_role_with_mfa(json_policy, sts_client):
    """Returns the credentials for assuming a role with mfa."""

    logger.info('Assuming role with MFA.')

    credentials = sts_client.assume_role(
        RoleArn=_role_arn,
        RoleSessionName='ssm-acquire',
        DurationSeconds=_session_duration,
        SerialNumber=_mfa_config,
        TokenCode=_mfa_token,
        Policy=json_policy
    )

    return credentials


def _assume_role_without_mfa(json_policy, sts_client):
    """Returns the credentials for assuming a role without mfa."""

    logger.info('Assuming role without MFA.')

    credentials = sts_client.assume_role(
        RoleArn=_role_arn,
        RoleSessionName='ssm-acquire',
        DurationSeconds=_session_duration,
        Policy=json_policy
    )

    return credentials


def _assume_role(region, instance_id, sts_client):
    """Returns the credentials for assuming a role with optional mfa."""

    json_policy = policy.get_json_policy(region, instance_id)
    
    if _mfa_config:
        return _assume_role_with_mfa(json_policy, sts_client)
    else:
        return _assume_role_without_mfa(json_policy, sts_client)


def _get_session_token_with_mfa(sts_client):
    """Returns a session token from the sts client with mfa."""

    logger.info('Getting session token with MFA.')

    session_token = sts_client.get_session_token(
        DurationSeconds=_session_duration,
        SerialNumber=_mfa_config,
        TokenCode=_mfa_token
    )

    return session_token


def _get_session_token_without_mfa(sts_client):
    """Returns a session token from the sts client without mfa."""

    logger.info('Getting session token without MFA.')

    session_token = sts_client.get_session_token(
        DurationSeconds=_session_duration
    )

    return session_token


def _get_session_token(sts_client):
    """Returns a session token from the sts client with optional mfa."""

    if _mfa_config:
        return _get_session_token_with_mfa(sts_client)
    else:
        return _get_session_token_without_mfa(sts_client)


def _get_credentials_helper(region, instance_id, sts_client):
    """
    Returns the credentials for assuming a role if a role arn is provided.
    
    Otherwise, returns a session token from the sts client.
    """

    if _role_arn:
        return _assume_role(region, instance_id, sts_client)
    else:
        return _get_session_token(sts_client)


def get_credentials(region, instance_id):
    """Obtains the credentials required to run commands on the EC2 
    instance."""

    sts_client = _get_sts_client(region)

    credentials = _get_credentials_helper(region, instance_id, sts_client)

    return credentials


"""
class StsManager(object):
    def __init__(self, region_name, limited_scope_policy):
        self.boto_session = boto3.session.Session(region_name=region_name)
        self.sts_client = self.boto_session.client('sts')
        self.limited_scope_policy = limited_scope_policy

    def auth(self):
        if self._should_mfa() and self._should_assume_role():
            logger.info(
                'Assuming the response role using mfa. role: {}, mfa: {}'.format(
                    config('ssm_acquire_role_arn', namespace='ssm_acquire'),
                    config('mfa_serial_number', namespace='ssm_acquire', default='None')
                )
            )            
            return self.assume_role_with_mfa(self.sts_client, config('ssm_acquire_role_arn', namespace='ssm_acquire'))
        elif self._should_mfa() and not self._should_assume_role():
            logger.info(
                'Assume role not specified in the threatresponse.ini generating session token with mfa. mfa: {}.'.format(
                    config('mfa_serial_number', namespace='ssm_acquire', default='None')
                )
            )
            return self.get_session_token_with_mfa(self.sts_client)
        elif self._should_assume_role() and not self._should_mfa():
            logger.info(
                'Assuming the response role. role: {}'.format(
                    config('ssm_acquire_role_arn', namespace='ssm_acquire'),
                    config('mfa_serial_number', namespace='ssm_acquire', default='None')
                )
            )
            return self.assume_role(self.sts_client, config('ssm_acquire_role_arn', namespace='ssm_acquire'))
        else:
            logger.info(
                'Assume role not specificed in the threatresponse.ini genetating sesssion token using current credials.'.format(
                    config('mfa_serial_number', namespace='ssm_acquire', default='None')
                )
            )
            return self.get_session_token()

    def _should_mfa(self):
        if config('mfa_serial_number', namespace='ssm_acquire', default='None') != 'None':
            return True
        else:
            return False

    def _should_assume_role(self):
        if config('ssm_acquire_role_arn', namespace='ssm_acquire', default='None') != 'None':
            return True
        else:
            return False

    def get_session_token_with_mfa(self, client):
        token_code = prompt('Please enter your MFA Token: ')
        response = client.get_session_token(
            DurationSeconds=config('assume_role_session_duration', default='3600', namespace='ssm_acquire'),
            SerialNumber=config('mfa_serial_number', namespace='ssm_acquire', default='None'),
            TokenCode=token_code
        )
        return response

    def get_session_token(self, client):
        response = client.get_session_token(
            DurationSeconds=config('assume_role_session_duration', default='3600', namespace='ssm_acquire')
        )
        return response

    def assume_role(self, client, role_arn):
        response = client.assume_role(
            RoleArn=role_arn,
            RoleSessionName='ssm-acquire',
            DurationSeconds=3600,
            Policy=self.limited_scope_policy
        )
        return response

    def assume_role_with_mfa(self, client, role_arn):
        token_code = prompt('Please enter your MFA Token: ')
        response = client.assume_role(
            RoleArn=role_arn,
            RoleSessionName='ssm-acquire',
            DurationSeconds=3600,
            SerialNumber=config('mfa_serial_number', namespace='ssm_acquire', default='None'),
            TokenCode=token_code,
            Policy=self.limited_scope_policy
        )
        return response
"""