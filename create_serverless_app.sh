# ------------------------------------------------------------------------
# This script creates Cloud Functions entities for audio alignment service
# ------------------------------------------------------------------------

# Cloud Object Storage instance name 
COS_INSTANCE_NAME=cloud-object-storage-cb

# Regional buckets in above Cloud Object Storage instance
RAW_BUCKET_NAME=choirless-videos-raw
CONVERTED_BUCKET_NAME=choirless-videos-converted
TRIMMED_BUCKET_NAME=choirless-videos-trimmed

# Namespace functions will be created int
NAMESPACE_NAME=choirless

##################
#### Clean up ####
##################

ic fn trigger delete bucket_raw_upload_trigger
ic fn trigger delete bucket_converted_upload_trigger
ic fn namespace delete choirless

###################################
#### Set up namespace and auth ####
###################################

# Create and set namespace
ibmcloud fn namespace create $NAMESPACE_NAME --description "Choirless video processing service"
ibmcloud fn property set --namespace $NAMESPACE_NAME

# List namespaces and entities in the current namespace
ibmcloud fn namespace list
ibmcloud fn list

# Prepare namespace for Cloud Object Storage triggers
ibmcloud iam authorization-policy-create functions cloud-object-storage "Notifications Manager" --source-service-instance-name $NAMESPACE_NAME --target-service-instance-name $COS_INSTANCE_NAME

# Create the package
ibmcloud fn package create audio_alignment
# Bind COS instance to the package
ibmcloud fn service bind cloud-object-storage audio_alignment --instance $COS_INSTANCE_NAME

#################
#### ACTIONS ####
#################

# Convert format
ibmcloud fn action update audio_alignment/convert_format convert_format.py --param src_bucket $RAW_BUCKET_NAME --param dst_bucket $CONVERTED_BUCKET_NAME \
	 --docker hammertoe/librosa_ml:latest --timeout 600000 --memory 512

# Calculate alignment
ibmcloud fn action update audio_alignment/calculate_alignment calculate_alignment.py --param bucket $CONVERTED_BUCKET_NAME \
	 --docker hammertoe/librosa_ml:latest --timeout 600000 --memory 512

# Trim clip
ibmcloud fn action update audio_alignment/trim_clip trim_clip.py --param src_bucket $CONVERTED_BUCKET_NAME --param dst_bucket $TRIMMED_BUCKET_NAME  \
	 --docker hammertoe/librosa_ml:latest --timeout 600000 --memory 512

###################
#### SEQUENCES ####
###################

# Calc alignment and Trim
ibmcloud fn action update audio_alignment/calc_and_trim --sequence audio_alignment/calculate_alignment,audio_alignment/trim_clip

##################
#### TRIGGERS ####
##################

# Upload to raw bucket
ibmcloud fn trigger create bucket_raw_upload_trigger --feed /whisk.system/cos/changes --param bucket $RAW_BUCKET_NAME --param event_types write

# Upload to converted bucket
ibmcloud fn trigger create bucket_converted_upload_trigger --feed /whisk.system/cos/changes --param bucket $CONVERTED_BUCKET_NAME --param event_types write


####################
####   RULES    ####
####################

# Upload to raw bucket
ibmcloud fn rule create bucket_raw_upload_rule bucket_raw_upload_trigger audio_alignment/convert_format

# Upload to converted bucket
ibmcloud fn rule create bucket_converted_upload_rule bucket_converted_upload_trigger audio_alignment/calc_and_trim


# Display entities in the current namespace
ibmcloud fn list

