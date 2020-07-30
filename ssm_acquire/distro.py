import logging

from typing import List

from ssm_acquire.command import SSMClient


logger = logging.getLogger(__name__)


def _get_os_release_commands():
    return ['cat /etc/os-release']


_os_release_commands = _get_os_release_commands()


class Distrinfo:
    """
    Info about an EC2 instance's Linux distro.

    self.id is the Linux AMI of the EC2 instance as a string ID.
    Examples: amzn, ubuntu, rehl
    """
    def __init__(self, ssm_client: SSMClient):
        self.os_release = self._get_os_release(ssm_client)
        self.os_release_stdout = self._get_stdout_dict()
        self.id = self.os_release_stdout['ID']
    
    def _get_os_release(self, ssm_client: SSMClient):
        return ssm_client.ensure_commands(_os_release_commands)
    
    def _get_stdout_dict_helper(self, stdout: List[str]):
        """
        Returns a dict representation of the stdout list.
        """
        stdout_dict = {}

        for line in stdout:
            key, value = line.split('=', 1)

            value = value.strip('\"')

            stdout_dict[key] = value
        
        return stdout_dict

    def _get_stdout_dict(self):
        """
        Returns the 'StandardOutputContent' section of the os_release object 
        as a dictionary.
        """
        stdout = self.os_release['StandardOutputContent'].splitlines()

        return self._get_stdout_dict_helper(stdout)