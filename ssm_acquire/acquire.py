import logging
import os.path
import yaml

from ssm_acquire.command import ensure_command
from ssm_acquire.jinja2_io import get_jinja2_plan


logger = logging.getLogger(__name__)


def _get_acquire_plans():
    dirname = os.path.dirname(__file__)

    path = os.path.join(dirname, "acquire-plans/linpmem.yml")

    return yaml.safe_load(open(path))


acquire_plans = _get_acquire_plans()


def _get_linux_commands(distro: str):
    linux_plans = acquire_plans['linux']

    setup = linux_plans['setup'][distro]

    commands = linux_plans['commands']

    return setup + commands


def _get_windows_commands():
    windows_plans = acquire_plans['windows']

    setup = windows_plans['setup']

    commands = windows_plans['commands']

    return setup + commands


def _get_memdump_commands():
    """
    TODO: Only supports amzn2 for now.  Add support for other distros.
    
    Gets commands to dump the volatile memory of the EC2 instance.
    """
    return acquire_plans['distros']['amzn2']['commands']


def _dump_EC2_mem(ssm_client, instance_id):
    """
    Dumps the volatile memory of an EC2 instance to its home directory. 
    Uses linpmem.
    """
    memdump_commands = _get_memdump_commands()

    logger.info('Memory dump in progress for instance: {}.  Please wait.'.\
        format(instance_id))
    
    ensure_command(ssm_client, memdump_commands, instance_id)

    logger.info('Memory dump complete.')


def _get_transfer_plans(credentials, instance_id):
    """
    Loads the j2-formatted plans to transfer the memory dump to the asset 
    bucket.
    """
    j2_file = "transfer-plans/linpmem.yml.j2"

    transfer_plan = get_jinja2_plan(credentials, instance_id, j2_file)

    return yaml.safe_load(transfer_plan)


def _get_transfer_commands(instance_id, credentials):
    """
    TODO: Only supports amzn2 for now.  Add support for other distros.
    
    Gets commands to transfer the dumped memory of the EC2 instance to the 
    asset bucket.
    """
    return _get_transfer_plans(
        credentials, 
        instance_id
    )['distros']['amzn2']['commands']


def _transfer_mem_to_asset_bucket(ssm_client, instance_id, credentials):
    """
    Transfers the dumped memory of an EC2 instance from its home directory to 
    the asset bucket.
    """
    transfer_commands = _get_transfer_commands(instance_id, credentials)

    logger.info('Transfering memory dump to s3 bucket...')

    ensure_command(ssm_client, transfer_commands, instance_id)

    logger.info('Transfer to s3 bucket complete.')


def dump_and_transfer(ssm_client, instance_id, credentials):
    """
    Dump and transfer the volatile memory of an EC2 instance to the asset 
    bucket.  Uses linpmem.
    """
    print('Acquire mode active.  Please give about a minute.')

    _dump_EC2_mem(ssm_client, instance_id)

    _transfer_mem_to_asset_bucket(ssm_client, instance_id, credentials)

    print('Acquire complete.  Memory dumped and transfered to s3 bucket.')