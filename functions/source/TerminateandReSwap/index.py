import boto3
import json
import traceback
import time
import sys
import logging
import threading

beanstalkclient = boto3.client('elasticbeanstalk')
codepipelineclient = boto3.client('codepipeline')

def handler(event, context):
    # make sure we send a failure to CodePipeline if the function is going to timeout
    timer = threading.Timer((context.get_remaining_time_in_millis() / 1000.00) - 0.5, timeout, args=[event, context])
    timer.start()
    try:
        # Extract the Job ID
        job_id = event['CodePipeline.job']['id']
        # Extract the Job Data
        job_data = event['CodePipeline.job']['data']
        user_parameters = job_data['actionConfiguration']['configuration']['UserParameters']
        #Calling DeleteConfigTemplate API
        DeleteConfigTemplate=DeleteConfigTemplateBlue(AppName=(json.loads(user_parameters)['BeanstalkAppName']),TempName=(json.loads(user_parameters)['CreateConfigTempName']))
        print (DeleteConfigTemplate)
        #re-swapping the urls
        reswap = SwapGreenandBlue(SourceEnv=(json.loads(user_parameters)['BlueEnvName']),DestEnv=(json.loads(user_parameters)['GreenEnvName']))
        if reswap == "Failure":
            raise Exception("Re-Swap did not happen")
        print ("Deleting the GreenEnvironment")
        DeleteGreenEnvironment(EnvName=(json.loads(user_parameters)['GreenEnvName']))
        #Delete the S3 CNAME Config file
        s3 = boto3.resource('s3')
        bucket = s3.Bucket(json.loads(user_parameters)['BlueCNAMEConfigBucket'])
        key = 'hello.json'
        objs = list(bucket.objects.filter(Prefix=key))
        if len(objs) > 0 and objs[0].key == key:
            obj = s3.Object(json.loads(user_parameters)['BlueCNAMEConfigBucket'],json.loads(user_parameters)['BlueCNAMEConfigFile'])
            obj.delete()
            print ("Successfully deleted the CNAME Config file")
        else:
            print("Seems like the CNAME Config file is already deleted!")
        #Send Success Message to CodePipeline
        Status="Success"
        Message="Successfully reswapped and terminated the Green Environment"

    except Exception as e:
        print('Function failed due to exception.')
        e = sys.exc_info()[0]
        print(e)
        traceback.print_exc()
        Status="Failure"
        Message=("Error occured while executing this. The error is %s" %e)

    finally:
        timer.cancel()
        if (Status =="Success"):
            put_job_success(job_id, Message)
        else:
            put_job_failure(job_id, Message)

def DeleteConfigTemplateBlue(AppName,TempName):
    #check if the config template exists
    ListTemplates = beanstalkclient.describe_applications(ApplicationNames=[AppName])['Applications'][0]['ConfigurationTemplates']
    if TempName not in ListTemplates:
        return ("Config Template does not exist")
    else:
        response = beanstalkclient.delete_configuration_template(ApplicationName=AppName,TemplateName=TempName)
        return ("Config Template Deleted")

def SwapGreenandBlue(SourceEnv, DestEnv):
    GetEnvData = (beanstalkclient.describe_environments(EnvironmentNames=[SourceEnv,DestEnv],IncludeDeleted=False))
    print (GetEnvData)
    if (((GetEnvData['Environments'][0]['Status']) == "Ready") and ((GetEnvData['Environments'][1]['Status']) == "Ready")):
        response = beanstalkclient.swap_environment_cnames(SourceEnvironmentName=SourceEnv,DestinationEnvironmentName=DestEnv)
        return ("Successful")
    else:
        return ("Failure")

def DeleteGreenEnvironment(EnvName):
    GetEnvData = (beanstalkclient.describe_environments(EnvironmentNames=[EnvName]))
    print(GetEnvData)
    #print (B['Environments'][0]['Status'])
    InvalidStatus = ["Terminating","Terminated"]
    if not(GetEnvData['Environments']==[]):
        #if not(B['Environments'][0]['Status']=="Terminated"): #or not(B['Environments'][0]['Status']=="Terminating")):
        if (GetEnvData['Environments'][0]['Status']) in InvalidStatus:
            return ("Already Terminated")
    while True:
        GreenEnvStatus = (beanstalkclient.describe_environments(EnvironmentNames=[EnvName]))['Environments'][0]['Status']
        print (GreenEnvStatus)
        time.sleep(10)
        if (GreenEnvStatus == 'Ready'):
            response = beanstalkclient.terminate_environment(EnvironmentName=EnvName)
            print (response)
            print ("Successfully Terminated Green Environment")
            return
def timeout(event, context):
    logging.error('Execution is about to time out, sending failure response to CodePipeline')
    put_job_failure(event['CodePipeline.job']['id'], "FunctionTimeOut")

def put_job_success(job, message):
    print('Putting job success')
    print(message)
    codepipelineclient.put_job_success_result(jobId=job)

def put_job_failure(job, message):
    print('Putting job failure')
    print(message)
    codepipelineclient.put_job_failure_result(jobId=job, failureDetails={'message': message, 'type': 'JobFailed'})
