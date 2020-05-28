import io
import json
import os
import librosa
import numpy as np
import tempfile
from pathlib import Path

import ibm_boto3
from ibm_botocore.client import Config, ClientError


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



# function to process the signals and get something that 
# we can compare against each other.
def process_signal(o):
    # normalise the values (zscore)
    o = (o - np.mean(o)) / np.std(o)
    # take any values > 2 standard deviations
    o = np.where(o > 2, 1.0, 0.0)
    
    # add an 'decay' to the values such that we can do a more 'fuzzy' match
    # forward pass
    for i in range(1, len(o)):
        o[i] = max(o[i], o[i-1] * 0.9)
        
    # backwards pass
    for i in range(len(o)-2, 0, -1):
        o[i] = max(o[i], o[i+1] * 0.9)
    
    return o

# Find the offest with the lowest error       
def find_offset(x0, x1):
    offsets = tuple(range(-100, 100))
    errors = [ (measure_error(x0, x1, offset), offset) for offset in offsets ]
    
    error, offset = sorted(errors)[0]
                     
    return offset, error


# function to measure two waveforms with one offset by a certian amount
def measure_error(x0, x1, offset):
    max_len = min(len(x0), len(x1))
    
    # calculate the mean squared error of the two signals
    diff = x0[:max_len] - np.roll(x1[:max_len], offset)
    err = np.sum(diff**2) / len(diff)
    return err

def main(params):

    resultsGetParams = getParamsCOS(params)
    
    cos = resultsGetParams.get('cos')
    cos_params = resultsGetParams.get('params')
    bucket = cos_params.get('bucket')

    try:
        if not bucket or not cos:
            raise ValueError(f"bucket name, key, and apikey are required for this operation. bucket: {bucket} cos: {cos}")
    except ValueError as e:
        print(e)
        raise

    reference_id = params['reference']
    part_id = params['part']

    def load_from_cos(key):
        # Create a temp dir for our files to use
        with tempfile.TemporaryDirectory() as tmpdir:
    
            cos_object = cos.get_object(
                Bucket=bucket,
                Key=key)
            
            # write out files to temp dir
            file_path = Path(tmpdir, key)
            with open(file_path, "wb") as fp:
                fp.write(cos_object['Body'].read())

            # load the audio from out temp file
            return librosa.load(file_path,
                                sr=SAMPLE_RATE, mono=True, offset=5, duration=20)

    # load in the leader
    x0, fs0 = load_from_cos(reference_id)

    # load in sarah
    x1, fs1 = load_from_cos(part_id)

    # Normalise the two signals so that they are the same average amplitude (volume)
    x0 = (x0 - np.mean(x0)) / np.std(x0)
    x1 = (x1 - np.mean(x1)) / np.std(x1)

    # Calculate the 'onset strength' of the files, ie where parts start
    o0 = librosa.onset.onset_strength(x0, sr=fs0)
    o1 = librosa.onset.onset_strength(x1, sr=fs1)

    # process the signal of the leader and sarah
    s0 = process_signal(o0)
    s1 = process_signal(o1)

    # Actually calculate the offset
    offset, error = find_offset(s0, s1)

    return {"reference": params["reference"],
            "part": params["part"],
            "offset": ((offset * 512) / SAMPLE_RATE) * 1000,
            "err": error}
