# -*- coding: utf-8 -*-
import boto3.session
import logging

from prompt_toolkit import prompt

from ssm_acquire.config import config_manager
from ssm_acquire.policy import get_json_policy


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


def _get_boto_session(region):
    """
    Returns a boto session for the given region if specified.
    """
    if region:
        return boto3.session.Session(region_name=region)
    else:
        return boto3.session.Session()


def _get_sts_client(region):
    """
    Returns an sts client for the given region if specified.
    """
    boto_session = _get_boto_session(region)

    sts_client = boto_session.client('sts')

    return sts_client


def _assume_role_with_mfa(json_policy, sts_client):
    """
    Returns the credentials for assuming a role with mfa.
    """
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
    """
    Returns the credentials for assuming a role without mfa.
    """
    logger.info('Assuming role without MFA.')

    credentials = sts_client.assume_role(
        RoleArn=_role_arn,
        RoleSessionName='ssm-acquire',
        DurationSeconds=_session_duration,
        Policy=json_policy
    )

    return credentials


def _assume_role(region, instance_id, sts_client):
    """
    Returns the credentials for assuming a role with optional mfa.
    """
    json_policy = get_json_policy(region, instance_id)
    
    if _mfa_config:
        return _assume_role_with_mfa(json_policy, sts_client)
    else:
        return _assume_role_without_mfa(json_policy, sts_client)


def _get_session_token_with_mfa(sts_client):
    """
    Returns a session token from the sts client with mfa.
    """
    logger.info('Getting session token with MFA.')

    session_token = sts_client.get_session_token(
        DurationSeconds=_session_duration,
        SerialNumber=_mfa_config,
        TokenCode=_mfa_token
    )

    return session_token


def _get_session_token_without_mfa(sts_client):
    """
    Returns a session token from the sts client without mfa.
    """
    logger.info('Getting session token without MFA.')

    session_token = sts_client.get_session_token(
        DurationSeconds=_session_duration
    )

    return session_token


def _get_session_token(sts_client):
    """
    Returns a session token from the sts client with optional mfa.
    """
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
    """
    Obtains the credentials required to run commands on the EC2 instance.
    """
    sts_client = _get_sts_client(region)

    credentials = _get_credentials_helper(region, instance_id, sts_client)

    return credentials