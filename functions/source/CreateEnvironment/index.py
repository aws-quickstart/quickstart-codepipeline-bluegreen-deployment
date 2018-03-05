import boto3
import json
import traceback
import sys
import logging
import threading
import time

beanstalkclient = boto3.client('elasticbeanstalk')
codepipelineclient = boto3.client('codepipeline')

def handler(event, context):
    timer = threading.Timer((context.get_remaining_time_in_millis() / 1000.00) - 0.5, timeout, args=[event, context])
    timer.start()
    try:
        # Extract the Job ID
        job_id = event['CodePipeline.job']['id']
        # Extract the Job Data
        job_data = event['CodePipeline.job']['data']
        user_parameters = job_data['actionConfiguration']['configuration']['UserParameters']
        print(job_data)
        print(event)
        BlueEnvInfo=GetBlueEnvInfo(EnvName=(json.loads(user_parameters)['BlueEnvName']))
        BlueEnvId=(BlueEnvInfo['Environments'][0]['EnvironmentId'])
        BlueVersionLabel=(BlueEnvInfo['Environments'][0]['VersionLabel'])
        
        #Calling CreateConfigTemplate API
        ConfigTemplate=CreateConfigTemplateBlue(AppName=(json.loads(user_parameters)['BeanstalkAppName']),BlueEnvId=BlueEnvId,TempName=json.loads(user_parameters)['CreateConfigTempName'])
        ReturnedTempName=ConfigTemplate
        print (ReturnedTempName)
        if not ReturnedTempName:
          #raise Exception if the Config file does not exist
          raise Exception("There were some issue while creating a Configuration Template from the Blue Environment")
        else:
          GreenEnvId=CreateGreenEnvironment(EnvName=(json.loads(user_parameters)['GreenEnvName']),ConfigTemplate=ReturnedTempName,AppVersion=BlueVersionLabel,AppName=(json.loads(user_parameters)['BeanstalkAppName']))
          print (GreenEnvId)
          #print (GreenEnvIddetails)
          if GreenEnvId:
              Status="Success"
              Message="Successfully created the Green Environment/Environment with the provided name already exists"
              #Create a CNAME Config file
              BlueEnvCname=(BlueEnvInfo['Environments'][0]['CNAME'])
              s3 = boto3.resource('s3')
              bucket = s3.Bucket(json.loads(user_parameters)['BlueCNAMEConfigBucket'])
              key = json.loads(user_parameters)['BlueCNAMEConfigFile']
              objs = list(bucket.objects.filter(Prefix=key))
              if len(objs) > 0 and objs[0].key == key:
                  print("BlueCNAMEConfigFile Already Exists!")
              else:
                  obj = s3.Object(json.loads(user_parameters)['BlueCNAMEConfigBucket'], json.loads(user_parameters)['BlueCNAMEConfigFile'])
                  BlueEnvCnameFile = {'BlueEnvUrl': BlueEnvCname}
                  obj.put(Body=json.dumps(BlueEnvCnameFile))
                  print ("Created a new CNAME file")
          else:
              Status="Failure"
              Message="Something went wrong on GreenEnv Creation"
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

def CreateConfigTemplateBlue(AppName,BlueEnvId,TempName):
    ListTemplates = beanstalkclient.describe_applications(ApplicationNames=[AppName])['Applications'][0]['ConfigurationTemplates']
    count = 0
    while count < len(ListTemplates):
        print (ListTemplates[count])
        if ListTemplates[count] == TempName:
            print ("ConfigTempAlreadyExists")
            return TempName
            break
        count += 1
    response = beanstalkclient.create_configuration_template(
    ApplicationName=AppName,
    TemplateName=TempName,
    EnvironmentId=BlueEnvId)
    return response['TemplateName']

def GetBlueEnvInfo(EnvName):
    response = beanstalkclient.describe_environments(
    EnvironmentNames=[
        EnvName
    ])
    print("Described the environment")
    return response

def CreateGreenEnvironment(EnvName,ConfigTemplate,AppVersion,AppName):
    GetEnvData = (beanstalkclient.describe_environments(EnvironmentNames=[EnvName]))
    print(GetEnvData)
    #print (B['Environments'][0]['Status'])
    InvalidStatus = ["Terminating","Terminated"]
    if not(GetEnvData['Environments']==[]):
        print("Environment Exists")
        if not(GetEnvData['Environments'][0]['Status']) in InvalidStatus:
            print("Existing Environment with the name %s not in Invalid Status" % EnvName)
            return (GetEnvData['Environments'][0]['EnvironmentId'])
    print ("Creating a new Environment")
    response = beanstalkclient.create_environment(
    ApplicationName=AppName,
    EnvironmentName=EnvName,
    TemplateName=ConfigTemplate,
    VersionLabel=AppVersion)
    return response['EnvironmentId']

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
