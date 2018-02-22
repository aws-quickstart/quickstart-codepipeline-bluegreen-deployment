#!/bin/sh -e

#a=$(aws elasticbeanstalk describe-environments --environment-names Test-env8 --region eu-west-1 | jq -r .Environments[0].Status)
#call S3 to get the CNAME file content
aws s3api get-object --bucket $BlueCNAMEConfigBucket --key $BlueCNAMEConfigFile $BlueCNAMEConfigFile --region us-east-2
file="./$BlueCNAMEConfigFile"
if [ ! -f "$file" ];
then
   echo "Nothing to do"
else
  Blueurl=$(cat $BlueCNAMEConfigFile |jq -r .BlueEnvUrl)
  echo $Blueurl
  GreenCNAME=$(aws elasticbeanstalk describe-environments --environment-names $GreenEnvName --region $AWS_REGION --query Environments[0].CNAME --output text)
  echo $GreenCNAME
  if [ $Blueurl = $GreenCNAME ];
  then
     echo "nothing to Swap"
  else
    while true
    do
    greenenvstatus=$(aws elasticbeanstalk describe-environments --environment-names $GreenEnvName --region $AWS_REGION --query Environments[0].Status --output text)
    echo $greenenvstatus
    sleep 10s
    if [ $greenenvstatus = "Ready" ]
    then
      echo $(aws elasticbeanstalk swap-environment-cnames --source-environment-name $BlueEnvName --destination-environment-name $GreenEnvName --region $AWS_REGION)
      echo "Urls are swapped now"
      break
    fi
  done
 fi
fi
