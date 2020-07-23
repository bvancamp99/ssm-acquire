import logging

from ssm_acquire.command import ensure_command


logger = logging.getLogger(__name__)


def _get_ami_acquisition_commands():
    return ['cat /etc/os-release']


_ami_acquisition_commands = _get_ami_acquisition_commands()


def _get_dictified_output_helper(std_output_list):
    std_output_dict = {}

    for line in std_output_list:
        key, value = line.split('=', 1)

        value = value.strip('\"')

        std_output_dict[key] = value
    
    return std_output_dict


def _get_dictified_output(std_output: str):
    std_output_list = std_output.splitlines()

    return _get_dictified_output_helper(std_output_list)


def _get_ami_dict(ssm_client, instance_id):
    inv_response = ensure_command(
        ssm_client, 
        _ami_acquisition_commands, 
        instance_id
    )

    std_output = inv_response['StandardOutputContent']

    return _get_dictified_output(std_output)



def get_ec2_ami(ssm_client, instance_id):
    ami_dict = _get_ami_dict(ssm_client, instance_id)

    return ami_dict['ID']