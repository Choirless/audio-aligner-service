import io
import json
import os
import librosa
import numpy as np
import tempfile
from pathlib import Path

import ibm_boto3
from ibm_botocore.client import Config, ClientError

import ffmpeg

SAMPLE_RATE = 44100


def getParamsCOS(args):
    endpoint = args.get('endpoint','https://s3.us.cloud-object-storage.appdomain.cloud')
    if not (endpoint.startswith("https://") or endpoint.startswith("http://")) : endpoint = "https://" + endpoint
    api_key_id = args.get('apikey', args.get('apiKeyId', args.get('__bx_creds', {}).get('cloud-object-storage', {}).get('apikey', os.environ.get('__OW_IAM_NAMESPACE_API_KEY') or ''))) 
    service_instance_id = args.get('resource_instance_id', args.get('serviceInstanceId', args.get('__bx_creds', {}).get('cloud-object-storage', {}).get('resource_instance_id', '')))
    ibm_auth_endpoint = args.get('ibmAuthEndpoint', 'https://iam.cloud.ibm.com/identity/token')
    params = {}
    params['bucket'] = args.get('bucket')
    params['endpoint'] = endpoint
    if not api_key_id:
        return {'cos': None, 'params':params}
    cos = ibm_boto3.client('s3',
                           ibm_api_key_id=api_key_id,
                           ibm_service_instance_id=service_instance_id,
                           ibm_auth_endpoint=ibm_auth_endpoint,
                           config=Config(signature_version='oauth'),
                           endpoint_url=endpoint)
    return {'cos':cos, 'params':params}


def main(params):

    resultsGetParams = getParamsCOS(params)
    
    cos = resultsGetParams.get('cos')
    cos_params = resultsGetParams.get('params')
    src_bucket = params.get('src_bucket')
    dst_bucket = params.get('dst_bucket')

    if not cos:
        raise ValueError(f"could not create COS instance")

    part_id = params['part']

    # Create a temp dir for our files to use
    with tempfile.TemporaryDirectory() as tmpdir:
    
        # download file to temp dir
        file_path = Path(tmpdir, part_id)
        new_path = file_path.with_name("converted-" + file_path.name).with_suffix(".mp4")

        cos.download_file(src_bucket, part_id, str(file_path))
        
        stream = ffmpeg.input(str(file_path))
        audio = stream.audio.filter('aresample', 44100)
        video = stream.video.filter('fps', fps=25, round='up')
        out = ffmpeg.output(audio, video, str(new_path))
        stdout, stderr = out.run()

        cos.upload_file(str(new_path), dst_bucket, str(new_path.name))

        return {"src_bucket": src_bucket,
                "dst_bucket": dst_bucket,
                "src_key": part_id,
                "dst_key": str(new_path.name)}
                
            
