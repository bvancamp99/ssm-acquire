import logging
import os.path
import yaml

from ssm_acquire.jinja2_io import get_jinja2_plan

from ssm_acquire.command import SSMClient
from ssm_acquire.distro import Distrinfo


logger = logging.getLogger(__name__)


def _get_acquire_plans():
    dirname = os.path.dirname(__file__)

    path = os.path.join(dirname, "acquire-plans/linpmem.yml")

    return yaml.safe_load(open(path))


acquire_plans = _get_acquire_plans()


def _get_linux_memdump_commands(distro_id: str):
    """
    Gets acquire commands to send to SSM based on the linux distro of the EC2 
    instance.
    """
    linux_plans = acquire_plans['linux']

    setup = linux_plans['setup'][distro_id]

    commands = linux_plans['commands']

    return setup + commands


# TODO: unused until windows is supported for transfer
def _get_windows_memdump_commands():
    windows_plans = acquire_plans['windows']

    setup = windows_plans['setup']

    commands = windows_plans['commands']

    return setup + commands


def _get_memdump_commands(distrinfo: Distrinfo):
    """
    Gets commands to dump the volatile memory of the EC2 instance.
    """
    return _get_linux_memdump_commands(distrinfo.id)


def _dump_EC2_mem(ssm_client: SSMClient, distrinfo: Distrinfo):
    """
    Dumps the volatile memory of an EC2 instance to its home directory. 
    
    Uses linpmem.
    """
    memdump_commands = _get_memdump_commands(distrinfo)

    logger.info(
        'Memory dump in progress for instance: {}.  Please wait.'.format(
            ssm_client.instance_id
        )
    )
    
    ssm_client.ensure_commands(memdump_commands)

    logger.info('Memory dump complete.')


def _get_transfer_plans(ssm_client: SSMClient):
    """
    Loads the j2-formatted plans to transfer the memory dump to the asset 
    bucket.
    """
    j2_file = "transfer-plans/linpmem.yml.j2"

    transfer_plan = get_jinja2_plan(ssm_client, j2_file)

    return yaml.safe_load(transfer_plan)


def _get_linux_transfer_commands(transfer_plans, distro_id: str):
    linux_plans = transfer_plans['linux']

    setup = linux_plans['setup'][distro_id]

    commands = linux_plans['commands']

    return setup + commands


def _get_transfer_commands(ssm_client: SSMClient, distrinfo: Distrinfo):
    """
    Gets commands to transfer the dumped memory of the EC2 instance to the 
    asset bucket.
    """
    transfer_plans = _get_transfer_plans(ssm_client)

    return _get_linux_transfer_commands(transfer_plans, distrinfo.id)


def _transfer_mem_to_asset_bucket(
    ssm_client: SSMClient, 
    distrinfo: Distrinfo
):
    """
    Transfers the dumped memory of an EC2 instance from its home directory to 
    the asset bucket.
    """
    transfer_commands = _get_transfer_commands(ssm_client, distrinfo)

    logger.info('Transfering memory dump to s3 bucket...')

    ssm_client.ensure_commands(transfer_commands)

    logger.info('Transfer to s3 bucket complete.')


def dump_and_transfer(ssm_client: SSMClient, distrinfo: Distrinfo):
    """
    Dump and transfer the volatile memory of an EC2 instance to the asset 
    bucket.  Uses linpmem.
    """
    print('Acquire mode active.  Please give about a minute.')

    _dump_EC2_mem(ssm_client, distrinfo)

    _transfer_mem_to_asset_bucket(ssm_client, distrinfo)

    print('Acquire complete.  Memory dumped and transfered to s3 bucket.')