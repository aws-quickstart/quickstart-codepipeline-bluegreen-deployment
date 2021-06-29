#!/bin/sh -x

echo $BlueEnvName
cname=$(aws elasticbeanstalk describe-environments --environment-names ${BlueEnvName} --region $AWS_REGION --query Environments[0].CNAME --output text)
echo $cname
if [ $cname ]
  then
      status=$( curl -LI http://$cname -o /dev/null -w '%{http_code}\n' -s )
  echo $status
  echo $BlueEnvName
  if [ ${status} = "200" ] || [ ${status} = "301" ]
      then exit 0
  else
    exit 1
  fi
else
    exit 1
fi
