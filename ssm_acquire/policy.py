import copy
import json
import os.path
import yaml

from ssm_acquire import config


def _get_policy_template():
    dirname = os.path.dirname(__file__)
    
    path = os.path.join(dirname, "policies/instance-scoped-policy.yml")

    return yaml.safe_load(open(path))['PolicyDocument']


policy_template = _get_policy_template()


def _update_STMT1(STMT1, instance_id):
    """
    Modifies the Resource dict of STMT1 *in place* with information about the 
    current EC2 instance and asset bucket.
    
    STMT1 requests permission to transfer the EC2 instance's memory dump to 
    the asset bucket.
    """
    s3_arn = config.get_s3_arn(instance_id=instance_id)

    STMT1['Resource'][0] = s3_arn
    STMT1['Resource'][1] = config.get_s3_keys(s3_arn)


# TODO: accessdeniedexception is now thrown when stmt3 doesn't have '*' for 
#       resources
def _update_STMT3(STMT3, region, instance_id):
    """
    Modifies the Resource dict of STMT3 *in place* with information about the 
    current EC2 instance and its region.
    
    STMT3 requests permission to send commands to the EC2 instance.
    """
    STMT3['Resource'][1] = config.get_ec2_arn(region, instance_id)


def _update_STMT4(STMT4):
    """
    Modifies the Resource dict of STMT4 *in place* with information about the 
    asset bucket.
    
    STMT4 requests permission to use the s3:ListBucket command.
    """
    s3_arn = config.get_s3_arn()

    STMT4['Resource'][0] = s3_arn
    STMT4['Resource'][1] = config.get_s3_keys(s3_arn)


def _update_statements(statements, region, instance_id):
    """Modifies the policy statements *in place* with region, instance_id, 
    and asset bucket information."""

    _update_STMT1(statements[0], instance_id)

    # STMT2 does not require any modifications

    # TODO: accessdeniedexception thrown when used vv
    _update_STMT3(statements[2], region, instance_id)

    _update_STMT4(statements[3])


def _get_updated_policy(region, instance_id):
    """
    Makes a copy of the policy template and sets the permission requests that 
    require information about the current region, asset bucket, and EC2 instance.

    Returns the modified copy.  The policy template is not modified.
    """

    updated_policy = copy.deepcopy(policy_template)

    _update_statements(updated_policy['Statement'], region, instance_id)

    return updated_policy


def get_json_policy(region, instance_id):
    """Returns a json object that contains permission requests to send 
    commands to the EC2 instance and asset bucket."""

    updated_policy = _get_updated_policy(region, instance_id)
        
    json_policy = json.dumps(updated_policy)
        
    return json_policy