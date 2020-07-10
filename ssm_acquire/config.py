import everett.ext.inifile
import everett.manager
import os


def _get_config_manager():
    config_file = everett.ext.inifile.ConfigIniEnv([
        os.environ.get('THREATRESPONSE_INI'),
        '~/.threatresponse.ini',
        '/etc/threatresponse.ini'
    ])

    return everett.manager.ConfigManager([
        config_file, 
        everett.manager.ConfigOSEnv()
    ])


config_manager = _get_config_manager()

# will throw ConfigurationMissingError later in the chain if 
# .threatresponse.ini can't be found
asset_bucket = config_manager('asset_bucket', namespace='ssm_acquire')


def get_s3_arn(instance_id=None):
    """
    Returns the Amazon resource name of the S3 bucket.
    
    Appends the EC2 instance id to the S3 arn if it is provided.
    """
    s3_arn = 'arn:aws:s3:::{}'.format(asset_bucket)

    if instance_id:
        s3_arn += '/{}'.format(instance_id)

    return s3_arn


def get_s3_keys(s3_arn):
    """Returns the keys of the asset bucket."""
    return '{}/*'.format(s3_arn)


def get_ec2_arn(region, instance_id):
    r"""
    Gets the Amazon resource name for the EC2 instance in the specified 
    region.

    EC2 arn format is:
    arn:aws:ec2:\<REGION\>:\<ACCOUNT_ID\>:instance/\<instance-id\>

    ACCOUNT_ID is unnecessary in the context of this program.
    """
    return 'arn:aws:ec2:{}::instance/{}'.format(region, instance_id)